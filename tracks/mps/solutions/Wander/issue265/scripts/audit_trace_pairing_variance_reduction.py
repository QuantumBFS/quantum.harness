#!/usr/bin/env python3
"""Audit cyclic within-frame Wick pairings at fixed theory regulator.

The comparison is paired by stochastic seed.  It uses only theory artifacts
and never reads a wall trajectory or target Burgers coefficients.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _seed(path: Path, payload: dict[str, object]) -> int:
    value = payload["regulator"].get("seed")
    if value is not None:
        return int(value)
    match = re.search(r"seed(\d+)", path.name)
    if not match:
        raise ValueError(f"missing seed in {path}")
    return int(match.group(1))


def _endpoint(payload: dict[str, object]) -> complex:
    pair = payload["structure_factors_over_chi_by_wave_then_time"][1][-1]
    return complex(*pair)


def audit(
    paths: list[Path],
    *,
    required_replicates: int = 4,
    target_complex_sem: float = 5e-4,
) -> dict[str, object]:
    if target_complex_sem <= 0.0:
        raise ValueError("target_complex_sem must be positive")
    groups: dict[int, dict[int, tuple[Path, dict[str, object]]]] = {}
    common_signature = None
    for path in paths:
        payload = json.loads(path.read_text())
        if payload.get("uses_target_a_or_D") or payload.get("uses_target_trajectory"):
            raise ValueError(f"forbidden target dependency in {path}")
        if not payload["iteration"]["converged"]:
            raise ValueError(f"unconverged fixed point in {path}")
        regulator = payload["regulator"]
        count = int(regulator.get("trace_pairings_per_frame", 1))
        scope = payload.get("scope", {})
        if not scope.get("full_non_diagonal_diffusion"):
            raise ValueError(f"full non-diagonal diffusion not certified in {path}")
        if not scope.get("full_background_fdt_noise_covariance"):
            raise ValueError(f"full FDT noise covariance not certified in {path}")
        if not payload.get("fdt", {}).get("positive_semidefinite"):
            raise ValueError(f"non-positive FDT covariance in {path}")
        if count > 1:
            diagnostics = payload.get("matrix_diagnostics")
            if diagnostics is None:
                raise ValueError(f"missing paired-run matrix diagnostics in {path}")
            if diagnostics["diffusion_off_diagonal_frobenius_fraction"] <= 0.0:
                raise ValueError(f"diagonal diffusion used in {path}")
            if diagnostics["fdt_noise_off_diagonal_frobenius_fraction"] <= 0.0:
                raise ValueError(f"diagonal FDT noise used in {path}")
            if diagnostics["diffusion_static_metric_commutator_relative_norm"] > 1e-10:
                raise ValueError(f"thermodynamic metric mismatch in {path}")
        seed = _seed(path, payload)
        if seed in groups.setdefault(count, {}):
            raise ValueError(f"duplicate seed {seed} for pairing count {count}")
        groups[count][seed] = (path, payload)
        signature_keys = (
            "field",
            "nodes_per_string",
            "string_xi_cutoff",
            "string_xi_buffer",
            "scaled_rapidity_extent",
            "scaled_rapidity_map_alpha",
            "kernel_theta_step",
            "fourier_points",
            "samples_per_internal_wave",
            "trace_distribution",
            "trace_source_layout",
            "lattice_wave_number",
        )
        signature = tuple((key, regulator[key]) for key in signature_keys)
        signature += (
            ("scaled_times", tuple(payload["scaled_times_tau_equals_t_h3"])),
            ("scaled_waves", tuple(payload["scaled_waves_q_equals_k_over_h2"])),
        )
        if common_signature is None:
            common_signature = signature
        elif signature != common_signature:
            raise ValueError(f"regulator mismatch in {path}")

    counts = sorted(groups)
    if counts[0] != 1 or len(counts) < 2:
        raise ValueError("pairing count 1 and at least one larger count are required")
    seeds = sorted(set.intersection(*(set(groups[count]) for count in counts)))
    if len(seeds) < required_replicates:
        raise ValueError("insufficient common stochastic seeds")

    values = {
        count: np.asarray([_endpoint(groups[count][seed][1]) for seed in seeds])
        for count in counts
    }
    baseline = values[1]
    baseline_variance = float(np.var(baseline.real, ddof=1))
    rows = []
    accepted = True
    for count in counts:
        sample = values[count]
        real_variance = float(np.var(sample.real, ddof=1))
        imaginary_variance = float(np.var(sample.imag, ddof=1))
        complex_variance = real_variance + imaginary_variance
        endpoint_complex_sem = float(np.sqrt(complex_variance / len(sample)))
        estimated_replicates_for_target_sem = max(
            required_replicates,
            int(math.ceil(complex_variance / target_complex_sem**2)),
        )
        difference = sample - baseline
        paired_sem = float(
            np.sqrt(np.sum(np.abs(difference - np.mean(difference)) ** 2)
                    / (len(difference) - 1) / len(difference))
        )
        shift = float(abs(np.mean(difference)))
        ratio = real_variance / max(baseline_variance, np.finfo(float).tiny)
        matrix_diagnostics = [
            groups[count][seed][1].get("matrix_diagnostics") for seed in seeds
        ]
        operator_evidence = None
        if all(row is not None for row in matrix_diagnostics):
            operator_evidence = {
                "diffusion_off_diagonal_frobenius_fraction_range": [
                    float(min(row["diffusion_off_diagonal_frobenius_fraction"] for row in matrix_diagnostics)),
                    float(max(row["diffusion_off_diagonal_frobenius_fraction"] for row in matrix_diagnostics)),
                ],
                "fdt_noise_off_diagonal_frobenius_fraction_range": [
                    float(min(row["fdt_noise_off_diagonal_frobenius_fraction"] for row in matrix_diagnostics)),
                    float(max(row["fdt_noise_off_diagonal_frobenius_fraction"] for row in matrix_diagnostics)),
                ],
                "maximum_diffusion_static_metric_commutator_relative_norm": float(
                    max(row["diffusion_static_metric_commutator_relative_norm"] for row in matrix_diagnostics)
                ),
            }
        row_accepted = bool(
            count == 1
            or (shift <= 2.0 * max(paired_sem, np.finfo(float).tiny)
                and ratio <= 1.0)
        )
        accepted &= row_accepted
        rows.append(
            {
                "trace_pairings_per_frame": count,
                "endpoint_mean": [float(np.mean(sample).real), float(np.mean(sample).imag)],
                "endpoint_real_variance": real_variance,
                "endpoint_imaginary_variance": imaginary_variance,
                "endpoint_complex_sem": endpoint_complex_sem,
                "target_complex_sem": target_complex_sem,
                "plugin_minimum_independent_replicates_for_target_sem": (
                    estimated_replicates_for_target_sem
                ),
                "full_matrix_operator_evidence": operator_evidence,
                "real_variance_ratio_to_single_pairing": ratio,
                "paired_complex_mean_shift": shift,
                "paired_complex_shift_sem": paired_sem,
                "accepted": row_accepted,
            }
        )

    return {
        "schema": 1,
        "method": "paired_cyclic_wick_trace_variance_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "common_seeds": seeds,
        "common_regulator_signature": dict(common_signature or ()),
        "target_complex_sem": target_complex_sem,
        "replicate_count_estimate_is_plugin_not_acceptance_evidence": True,
        "paired_runs_require_numeric_full_matrix_operator_evidence": True,
        "rows": rows,
        "input_sha256_by_file": {str(path): _sha256(path) for path in paths},
        "trace_pairing_variance_reduction_accepted": bool(accepted),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--required-replicates", type=int, default=4)
    parser.add_argument("--target-complex-sem", type=float, default=5e-4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        args.inputs,
        required_replicates=args.required_replicates,
        target_complex_sem=args.target_complex_sem,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
