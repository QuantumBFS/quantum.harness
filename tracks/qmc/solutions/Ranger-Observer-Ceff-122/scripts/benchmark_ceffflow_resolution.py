#!/usr/bin/env python3
"""Measure local cost and particle-count drift of degraded-record filtering."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import time

import numpy as np

from ceffflow.channels import ConfusionChannel
from ceffflow.resolution import estimate_degraded_record_rates


def _finite_json(value):
    """Replace non-finite NumPy/Python floats by JSON null."""

    if isinstance(value, dict):
        return {key: _finite_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_finite_json(item) for item in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--particles", default="4,8,16,32")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--burn-in", type=int, default=5)
    parser.add_argument("--block-size", type=int, default=5)
    parser.add_argument("--lengths", default="4,6,8")
    parser.add_argument("--seeds", default="122")
    parser.add_argument(
        "--backend", choices=("scalar", "batched"), default="batched"
    )
    args = parser.parse_args()
    lengths = [int(value) for value in args.lengths.split(",")]
    counts = [int(value) for value in args.particles.split(",")]
    seeds = [int(value) for value in args.seeds.split(",")]
    rows = []
    for count in counts:
        for seed in seeds:
            start_usage = resource.getrusage(resource.RUSAGE_SELF)
            start = time.perf_counter()
            estimate = estimate_degraded_record_rates(
                lengths,
                ConfusionChannel(0.1),
                particles=count,
                steps=args.steps,
                burn_in=args.burn_in,
                block_size=args.block_size,
                seed=seed,
                batched=args.backend == "batched",
            )
            elapsed = time.perf_counter() - start
            end_usage = resource.getrusage(resource.RUSAGE_SELF)
            rows.append(
                {
                    "particles": count,
                    "seed": seed,
                    "wall_seconds": elapsed,
                    "user_cpu_seconds": (
                        end_usage.ru_utime - start_usage.ru_utime
                    ),
                    "system_cpu_seconds": (
                        end_usage.ru_stime - start_usage.ru_stime
                    ),
                    "max_rss_process_units": end_usage.ru_maxrss,
                    "mean_record_rates": estimate.means.tolist(),
                }
            )
    aggregates = []
    for count in counts:
        samples = np.asarray(
            [
                row["mean_record_rates"]
                for row in rows
                if row["particles"] == count
            ],
            dtype=float,
        )
        standard_errors = (
            np.std(samples, axis=0, ddof=1) / np.sqrt(samples.shape[0])
            if samples.shape[0] > 1
            else np.full(samples.shape[1], np.nan)
        )
        aggregates.append(
            {
                "particles": count,
                "mean_record_rates": np.mean(samples, axis=0).tolist(),
                "between_seed_standard_errors": standard_errors.tolist(),
                "mean_wall_seconds": float(
                    np.mean(
                        [
                            row["wall_seconds"]
                            for row in rows
                            if row["particles"] == count
                        ]
                    )
                ),
            }
        )
    reference = aggregates[-1]
    reference_means = np.asarray(reference["mean_record_rates"])
    reference_errors = np.asarray(reference["between_seed_standard_errors"])
    for aggregate in aggregates:
        means = np.asarray(aggregate["mean_record_rates"])
        errors = np.asarray(aggregate["between_seed_standard_errors"])
        drift = np.abs(means - reference_means)
        combined_error = np.sqrt(errors**2 + reference_errors**2)
        resolved = np.isfinite(combined_error) & (drift <= combined_error)
        aggregate["absolute_drift_from_largest_particles"] = drift.tolist()
        aggregate["combined_standard_error"] = combined_error.tolist()
        aggregate["within_combined_standard_error"] = resolved.tolist()
        aggregate["particle_convergence_passed"] = bool(np.all(resolved))
    payload = {
        "status": "cost benchmark; not a central-charge production run",
        "channel": {"kind": "confusion", "parameter": 0.1},
        "lengths": lengths,
        "steps": args.steps,
        "burn_in": args.burn_in,
        "block_size": args.block_size,
        "seeds": seeds,
        "backend": args.backend,
        "measurements": rows,
        "aggregates": aggregates,
        "convergence_rule": (
            "absolute particle-count drift from the largest ensemble must "
            "not exceed the quadrature-combined between-seed standard error "
            "at every width"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_finite_json(payload), indent=2, allow_nan=False) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
