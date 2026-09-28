#!/usr/bin/env python3
"""Audit mu20-preserving UV subtraction of the complete full-mode one-loop tail."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mori_moment_matching import (  # noqa: E402
    match_kernels_to_exact_lanczos,
    moment_preserving_jet_subtraction,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, complex):
        if abs(value.imag) <= 1.0e-12 * max(abs(value.real), 1.0):
            return float(value.real)
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def derive(
    linear_path: Path,
    loop_path: Path,
    *,
    matching_rates: tuple[float, ...],
    maximum_laplace_frequency: float,
    spectral_nodes: int,
    spectral_maximum: float,
    spectral_relative_tolerance: float,
    cutoff_relative_tolerance: float,
) -> dict[str, object]:
    linear = json.loads(linear_path.read_text())
    loop = json.loads(loop_path.read_text())
    for payload in [linear, loop]:
        inputs = payload["inputs"]
        if inputs.get("trajectory_data_used") or inputs.get("target_coefficients_used"):
            raise RuntimeError("target-contaminated source certificate")
    for key in [
        "field",
        "string_xi_cutoff",
        "string_xi_buffer",
        "rapidity_u_extent",
        "rapidity_points",
        "wave_number",
    ]:
        if linear["inputs"][key] != loop["inputs"][key]:
            raise ValueError(f"source mismatch in {key}")
    projected = linear["projected_mori"]
    all_z = np.asarray(projected["laplace_values"], dtype=float)
    select = all_z <= maximum_laplace_frequency
    z = all_z[select]
    if z.size < 3:
        raise ValueError("low-frequency overlap band must contain at least three points")
    base = np.asarray(projected["mori_kernel"]["real"], dtype=float)[select]
    times = np.asarray(loop["times"], dtype=float)
    omega = np.concatenate(
        ([0.0], np.geomspace(float(np.min(z)) / 20.0, spectral_maximum, spectral_nodes - 1))
    )

    rate_rows = []
    finest_candidates = []
    for rate in matching_rates:
        candidates = []
        cutoff_rows = []
        for row in loop["uv_rows"]:
            memory = np.asarray(
                row["colored_memory"]["total_colored_continuity_memory"]["values"],
                dtype=float,
            )
            raw = np.asarray(
                [np.trapezoid(np.exp(-frequency * times) * memory, times) for frequency in z]
            )
            derivative_record = row.get("colored_memory_zero_time_derivatives")
            if not derivative_record or int(derivative_record["maximum_order"]) < 20:
                raise ValueError("source does not contain analytic derivatives through order 20")
            derivatives = np.asarray(derivative_record["real"], dtype=float)[:21]
            subtraction = moment_preserving_jet_subtraction(
                z,
                raw,
                derivatives,
                white_contact=float(row["multiplicative_noise_delta_memory"]),
                matching_rate=rate,
            )
            renormalized = np.real(
                np.asarray(subtraction["renormalized_colored_laplace"])
            )
            candidates.append(base + renormalized)
            cutoff_rows.append(
                {
                    "fourier_points": int(row["fourier_points"]),
                    "maximum_resolved_wave_number": float(row["maximum_resolved_wave_number"]),
                    "raw_colored_laplace": raw,
                    "localized_jet_laplace": np.real(
                        subtraction["localized_jet_laplace"]
                    ),
                    "renormalized_colored_laplace": renormalized,
                    "cancelled_white_contact": float(
                        row["multiplicative_noise_delta_memory"]
                    ),
                    "analytic_derivative_count": 21,
                }
            )
        candidates_array = np.asarray(candidates)
        matching = match_kernels_to_exact_lanczos(
            z,
            candidates_array,
            spectral_frequencies=omega,
            spectral_relative_tolerance=spectral_relative_tolerance,
            cutoff_relative_tolerance=cutoff_relative_tolerance,
            required_tail_count=2,
        )
        finest_candidates.append(candidates_array[-1])
        rate_rows.append(
            {
                "matching_rate": float(rate),
                "cutoffs": cutoff_rows,
                "candidate_kernels": candidates_array,
                "matching": matching,
            }
        )

    finest_candidates = np.asarray(finest_candidates)
    scheme_center = np.mean(finest_candidates, axis=0)
    scheme_spread = np.max(finest_candidates, axis=0) - np.min(finest_candidates, axis=0)
    scheme_relative_spread = float(
        np.max(
            np.abs(scheme_spread)
            / np.maximum(np.abs(scheme_center), np.finfo(float).tiny)
        )
    )
    every_rate_matches = bool(
        all(row["matching"]["matching_complete"] for row in rate_rows)
    )
    return {
        "schema": 1,
        "method": "mu20_preserving_exponential_jet_subtraction",
        "sources": {str(linear_path): _sha256(linear_path), str(loop_path): _sha256(loop_path)},
        "inputs": {
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "matching_rates": list(matching_rates),
            "maximum_laplace_frequency": maximum_laplace_frequency,
            "finite_time_laplace_maximum": float(times[-1]),
            "known_colored_derivative_orders": list(range(21)),
            "white_contact_cancelled_by_exact_large_z_asymptotic": True,
        },
        "laplace_frequency": z,
        "linear_full_mode_kernel": base,
        "matching_rate_rows": rate_rows,
        "finest_cutoff_matching_scheme_relative_spread": scheme_relative_spread,
        "gates": {
            "every_matching_rate_positive_and_cutoff_stable": every_rate_matches,
            "matching_scheme_relative_spread_below_10_percent": bool(
                scheme_relative_spread <= 0.1
            ),
            "finite_time_laplace_tail_controlled": False,
            "joint_zero_field_infinite_mode_limit_complete": False,
            "physical_F1_perp_certified": False,
        },
        "interpretation": (
            "The subtraction preserves the exact known large-z moment prefix. "
            "Dependence on the localization rate is a matching-scheme error, "
            "not a statistical uncertainty.  No Burgers projection is allowed "
            "until scheme, cutoff, finite-time, and zero-field gates all pass."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("linear_certificate", type=Path)
    parser.add_argument("one_loop_certificate", type=Path)
    parser.add_argument("--matching-rates", nargs="+", type=float, default=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0])
    parser.add_argument("--maximum-laplace-frequency", type=float, default=0.1)
    parser.add_argument("--spectral-nodes", type=int, default=256)
    parser.add_argument("--spectral-maximum", type=float, default=20.0)
    parser.add_argument("--spectral-relative-tolerance", type=float, default=0.02)
    parser.add_argument("--cutoff-relative-tolerance", type=float, default=0.1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(
        args.linear_certificate,
        args.one_loop_certificate,
        matching_rates=tuple(args.matching_rates),
        maximum_laplace_frequency=args.maximum_laplace_frequency,
        spectral_nodes=args.spectral_nodes,
        spectral_maximum=args.spectral_maximum,
        spectral_relative_tolerance=args.spectral_relative_tolerance,
        cutoff_relative_tolerance=args.cutoff_relative_tolerance,
    )
    encoded = json.dumps(_jsonable(result), indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
