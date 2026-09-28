#!/usr/bin/env python3
"""Audit direct full-noise propagation across finite-field GHD regulators."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fdt-tolerance", type=float, default=1.0e-10)
    parser.add_argument("--static-capture-minimum", type=float, default=0.95)
    parser.add_argument("--static-capture-maximum", type=float, default=1.01)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    args = _arguments()
    rows = []
    hashes = {}
    for supplied in args.inputs:
        path = supplied if supplied.is_absolute() else ROOT / supplied
        payload = json.loads(path.read_text())
        hashes[str(path.relative_to(ROOT))] = _sha256(path)
        for row in payload["rows"]:
            if len(row["direct_full_noise_propagation"]) != 1:
                raise ValueError("audit expects exactly one propagated wave number")
            wave, noise = next(iter(row["direct_full_noise_propagation"].items()))
            full = np.asarray(
                noise["equal_time_covariance_from_direct_full_noise"], dtype=float
            )
            diagonal = np.asarray(
                noise["equal_time_covariance_from_diagonal_noise_only"], dtype=float
            )
            offdiagonal = np.asarray(
                noise["equal_time_covariance_from_offdiagonal_noise"], dtype=float
            )
            total = np.asarray(noise["total_equal_time_covariance_direct"], dtype=float)
            rows.append(
                {
                    "field": float(row["field"]),
                    "active_strings": int(row["active_strings"]),
                    "mode_count": int(row["mode_count"]),
                    "wave_number": float(wave),
                    "susceptibility_captured_fraction": float(
                        row["susceptibility_captured_fraction"]
                    ),
                    "fdt_operator_residual": float(row["fdt_residual"]),
                    "direct_noise_fdt_maximum_absolute_residual": float(
                        noise["maximum_direct_vs_fdt_absolute_residual"]
                    ),
                    "direct_total_covariance_maximum_absolute_residual": float(
                        np.max(np.abs(total - 1.0))
                    ),
                    "spin_diffusion": float(row["spin_diffusion"]),
                    "field_times_spin_diffusion": float(
                        row["h_times_spin_diffusion"]
                    ),
                    "spin_to_complement_diffusion_norm": float(
                        row["diffusion_complement"]["spin_to_complement_norm"]
                    ),
                    "spin_to_complement_noise_norm": float(
                        row["noise_complement"]["spin_to_complement_norm"]
                    ),
                    "final_full_noise_covariance": float(full[-1]),
                    "final_diagonal_noise_only_covariance": float(diagonal[-1]),
                    "final_offdiagonal_noise_covariance": float(offdiagonal[-1]),
                    "final_offdiagonal_fraction_of_full_noise": float(
                        offdiagonal[-1] / full[-1]
                    ),
                    "diagonal_plus_offdiagonal_residual": float(
                        np.max(np.abs(diagonal + offdiagonal - full))
                    ),
                }
            )
    rows.sort(key=lambda row: row["field"], reverse=True)
    scaled = np.asarray([row["field_times_spin_diffusion"] for row in rows])
    relative_steps = np.abs(np.diff(scaled)) / np.maximum(
        np.abs(scaled[1:]), np.finfo(float).tiny
    )
    fdt_pass = all(
        row["fdt_operator_residual"] <= args.fdt_tolerance
        and row["direct_noise_fdt_maximum_absolute_residual"] <= args.fdt_tolerance
        and row["direct_total_covariance_maximum_absolute_residual"]
        <= args.fdt_tolerance
        for row in rows
    )
    static_pass = all(
        args.static_capture_minimum
        <= row["susceptibility_captured_fraction"]
        <= args.static_capture_maximum
        for row in rows
    )
    offdiagonal_present = all(
        row["spin_to_complement_noise_norm"] > 0.0
        and abs(row["final_offdiagonal_noise_covariance"]) > args.fdt_tolerance
        for row in rows
    )
    payload = {
        "schema": 1,
        "method": "direct_full_nondiagonal_noise_fghd_regulator_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "uses_auxiliary_field_or_finite_pole_closure": False,
        "rows": rows,
        "field_times_spin_diffusion_relative_steps": relative_steps.tolist(),
        "gates": {
            "full_fdt_propagation_pass": fdt_pass,
            "static_susceptibility_capture_pass": static_pass,
            "offdiagonal_noise_material_and_retained": offdiagonal_present,
            "finite_regulator_calculation_valid": bool(
                fdt_pass and static_pass and offdiagonal_present
            ),
            "infinite_mode_zero_field_limit_accepted": False,
            "finite_window_a_and_D_uniquely_determined": False,
        },
        "nonacceptance_reason": (
            "This sequence varies h and the number of strings together but does not "
            "supply independent tails in string cutoff, rapidity extent, node count, "
            "spatial wave number, and nonlinear magnetic vertices.  It therefore "
            "certifies the finite-regulator full A,D,Q propagation only."
        ),
        "source_sha256": hashes,
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n")


if __name__ == "__main__":
    main()
