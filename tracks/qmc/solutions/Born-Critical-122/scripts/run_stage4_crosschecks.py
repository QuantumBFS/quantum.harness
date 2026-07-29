#!/usr/bin/env python3
"""Run independent local-Metropolis and isotropic-construction checks."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import socket

import numpy as np

from borncritical.conventions import SELFDUAL_THETA, selfdual_couplings
from borncritical.gaussian_born import GaussianBornCircuit
from borncritical.metropolis_tn import (
    DenseRecordContraction,
    integrated_autocorrelation_time,
    local_metropolis,
)


def atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def sequential_records(
    size: int, layers: int, samples: int, seed: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    evaluator = DenseRecordContraction(size, layers)
    rng = np.random.default_rng(seed)
    records = np.empty((samples, evaluator.variable_count), dtype=np.int8)
    log_probability = np.empty(samples, dtype=float)
    log_norm = np.empty(samples, dtype=float)
    maximum_oracle_error = 0.0
    for sample in range(samples):
        circuit = GaussianBornCircuit(size=size)
        bits: list[int] = []
        for _ in range(layers):
            layer = circuit.sample_layer(rng)
            bits.extend(int(value == -1) for value in layer.s)
            bits.extend(int(value == -1) for value in layer.t)
        records[sample] = bits
        dense_log_probability = evaluator.log_probability(records[sample])
        dense_log_norm = evaluator.log_norm(records[sample])
        maximum_oracle_error = max(
            maximum_oracle_error,
            abs(dense_log_probability - circuit.total_log_probability),
            abs(dense_log_norm - circuit.total_log_norm),
        )
        log_probability[sample] = dense_log_probability
        log_norm[sample] = dense_log_norm
    return records, log_probability, log_norm, maximum_oracle_error


def iid_summary(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "standard_error": float(
            np.std(values, ddof=1) / math.sqrt(values.size)
        ),
    }


def chain_summary(values: np.ndarray) -> dict[str, float]:
    tau = integrated_autocorrelation_time(values)
    return {
        "mean": float(np.mean(values)),
        "integrated_autocorrelation_time": tau,
        "effective_samples": float(values.size / (2.0 * tau)),
        "standard_error": float(
            math.sqrt(np.var(values, ddof=1) * 2.0 * tau / values.size)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=4000)
    parser.add_argument("--burnin-sweeps", type=int, default=500)
    parser.add_argument("--layers", type=int, default=1)
    parser.add_argument("--stage2-metrics", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    records: dict[str, object] = {}
    all_comparisons_pass = True
    maximum_oracle_error = 0.0

    for size in (6, 8):
        normalization = 2.0 * size * args.layers
        sequential_bits, sequential_lp, sequential_ln, oracle_error = (
            sequential_records(
                size, args.layers, args.samples, 422607280200 + size
            )
        )
        maximum_oracle_error = max(maximum_oracle_error, oracle_error)
        evaluator = DenseRecordContraction(size, args.layers)
        metropolis = local_metropolis(
            evaluator,
            seed=422607280300 + size,
            burnin_sweeps=args.burnin_sweeps,
            samples=args.samples,
        )
        sequential_observables = {
            "shannon_rate": -sequential_lp / normalization,
            "log_norm_rate": sequential_ln / normalization,
            "negative_outcome_density": np.mean(sequential_bits, axis=1),
        }
        metropolis_observables = {
            "shannon_rate": -metropolis.log_probabilities / normalization,
            "log_norm_rate": metropolis.log_norms / normalization,
            "negative_outcome_density": np.mean(
                metropolis.records, axis=1
            ),
        }
        comparisons: dict[str, object] = {}
        for name in sequential_observables:
            sequential_summary = iid_summary(sequential_observables[name])
            metropolis_summary = chain_summary(metropolis_observables[name])
            difference = abs(
                sequential_summary["mean"] - metropolis_summary["mean"]
            )
            combined = math.hypot(
                sequential_summary["standard_error"],
                metropolis_summary["standard_error"],
            )
            distance = difference / combined
            comparisons[name] = {
                "sequential": sequential_summary,
                "metropolis": metropolis_summary,
                "absolute_difference": difference,
                "distance_combined_standard_errors": distance,
                "passes_4se": distance <= 4.0,
            }
            all_comparisons_pass &= distance <= 4.0
        quarter = max(1, args.burnin_sweeps // 4)
        burn = -metropolis.burnin_log_probability / normalization
        records[str(size)] = {
            "layers": args.layers,
            "record_variables": evaluator.variable_count,
            "burnin_sweeps": args.burnin_sweeps,
            "stored_samples": args.samples,
            "metropolis_acceptance_rate": metropolis.acceptance_rate,
            "burnin_first_quarter_mean_shannon_rate": float(
                np.mean(burn[:quarter])
            ),
            "burnin_last_quarter_mean_shannon_rate": float(
                np.mean(burn[-quarter:])
            ),
            "burnin_quarter_absolute_shift": float(
                abs(np.mean(burn[:quarter]) - np.mean(burn[-quarter:]))
            ),
            "comparisons": comparisons,
        }

    beta, beta_prime = selfdual_couplings(SELFDUAL_THETA)
    stage2_metrics = json.loads(
        args.stage2_metrics.read_text(encoding="utf-8")
    )
    stage2_main = float(stage2_metrics["main_central_charge"])
    local_weight_ratio = math.tanh(beta) / math.tanh(beta_prime)
    isotropy = {
        "theta": SELFDUAL_THETA,
        "beta": beta,
        "beta_prime": beta_prime,
        "absolute_coupling_difference": abs(beta - beta_prime),
        "spatial_to_temporal_local_weight_ratio": local_weight_ratio,
        "ratio_distance_from_one": abs(local_weight_ratio - 1.0),
        "square_lattice_sublayers_per_cycle": 2,
        "clean_isotropic_stage2_job": "17178",
        "clean_isotropic_stage2_c": stage2_main,
        "clean_isotropic_stage2_relative_error": abs(stage2_main - 0.5) / 0.5,
        "coupling_ratio_within_one_percent": (
            abs(local_weight_ratio - 1.0) <= 0.01
        ),
        "clean_transfer_normalization_within_half_percent": (
            abs(stage2_main - 0.5) / 0.5 <= 0.005
        ),
        "supports_alpha_one": (
            abs(local_weight_ratio - 1.0) <= 0.01
            and abs(stage2_main - 0.5) / 0.5 <= 0.005
        ),
        "interpretation": (
            "At theta=pi/4 the dual MZ and MX local weights are exactly equal; "
            "one cycle is normalized as two equal square-lattice sublayers. "
            "The independently implemented clean square-lattice transfer "
            "benchmark validates this alpha=1 normalization."
        ),
    }
    gates = {
        "dense_contraction_matches_gaussian_chain": maximum_oracle_error <= 1e-11,
        "metropolis_observables_match_sequential_born": all_comparisons_pass,
        "isotropic_construction_supports_alpha_one": isotropy["supports_alpha_one"],
    }
    payload = {
        "schema_version": 1,
        "stage": "stage4d-crosschecks",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "maximum_dense_gaussian_log_weight_error": maximum_oracle_error,
        "sizes": records,
        "isotropy": isotropy,
        "gates": gates,
        "passes": all(gates.values()),
    }
    atomic_json(output / "metrics.json", payload)
    atomic_json(
        output / "manifest.json",
        {
            "schema_version": 1,
            "status": "success" if payload["passes"] else "failed",
            "stage": payload["stage"],
            "hostname": payload["hostname"],
            "slurm_job_id": payload["slurm_job_id"],
            "artifacts": ["metrics.json"],
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
