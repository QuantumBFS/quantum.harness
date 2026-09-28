#!/usr/bin/env python3
"""Evaluate the normal-ordered two-cubic-velocity Mori memory at finite cutoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    effective_velocity_second_frechet_derivative,
    full_diffusion_operator_field,
)
from src.full_mode_analytic_certificates import (  # noqa: E402
    normal_ordered_cubic_velocity_force_memory,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field", type=float, default=0.25)
    parser.add_argument("--xi-cutoff", type=float, default=0.25)
    parser.add_argument("--xi-buffer", type=float, default=0.5)
    parser.add_argument("--u-extent", type=float, default=1.5)
    parser.add_argument("--rapidity-points", type=int, default=16)
    parser.add_argument("--wave-number", type=float, default=0.04)
    parser.add_argument("--fourier-cutoffs", type=int, nargs="+", default=[4, 6, 8])
    parser.add_argument("--times", type=float, nargs="+", default=[0, 1, 5, 10, 25, 50])
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    modes = full_diffusion_operator_field(
        args.field,
        string_xi_cutoff=args.xi_cutoff,
        string_xi_buffer=args.xi_buffer,
        rapidity_u_extent=args.u_extent,
        rapidity_points=args.rapidity_points,
        string_boundary="robin",
    )
    second = effective_velocity_second_frechet_derivative(modes)
    times = np.asarray(args.times, dtype=float)
    rows = []
    for points in args.fourier_cutoffs:
        waves = args.wave_number * (np.fft.fftfreq(points) * points)
        # The retained grid has fixed Fourier spacing Delta k=wave_number.
        # Hence its real-space period is 2*pi/Delta k, independent of the UV
        # cutoff.  An extra division by ``points`` would spuriously multiply
        # each Fourier covariance by points and the W^2 memory by points^2.
        cell_length = 2.0 * np.pi / args.wave_number
        result = normal_ordered_cubic_velocity_force_memory(
            waves,
            1,
            modes["velocity"],
            modes["diffusion_operator"],
            modes["static_covariance"],
            second["velocity_hessian"],
            modes["spin_projection"],
            times,
            spatial_cell_length=cell_length,
            lattice_wave_number=lambda k: 2.0 * np.sin(k / 2.0),
        )
        memory = np.real(np.asarray(result["continuity_normalized_cubic_memory"]))
        rows.append(
            {
                "fourier_points": points,
                "maximum_resolved_wave_number": float(np.max(np.abs(waves))),
                "spatial_cell_length": float(cell_length),
                "dealiased_ordered_momentum_triplets": int(
                    result["dealiased_ordered_momentum_triplets"]
                ),
                "continuity_normalized_W2_memory": memory.tolist(),
                "integral_to_maximum_time": float(np.trapezoid(memory, times)),
                "zero_time_nonnegative": bool(result["zero_time_nonnegative"]),
            }
        )
    payload = {
        "schema": 1,
        "method": "deterministic_six_point_Wick_contraction_of_normal_ordered_cubic_velocity",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "inputs": {
            "field": args.field,
            "xi_cutoff": args.xi_cutoff,
            "xi_buffer": args.xi_buffer,
            "u_extent": args.u_extent,
            "rapidity_points": args.rapidity_points,
            "wave_number": args.wave_number,
            "times": times.tolist(),
            "fourier_cutoffs": args.fourier_cutoffs,
        },
        "operator": {
            "dimension": int(np.asarray(modes["velocity"]).size),
            "active_strings": int(modes["active_strings"]),
            "velocity_hessian_schwarz_relative_residual": float(
                second["raw_schwarz_relative_residual"]
            ),
        },
        "rows": rows,
        "scope": {
            "fixed_fourier_spacing_has_fixed_spatial_cell_length": True,
            "first_order_cubic_tadpole_removed_by_explicit_counterterm": True,
            "first_nonzero_cubic_velocity_memory_W2_evaluated": True,
            "wrapped_cubic_aliases_removed": True,
            "full_string_zero_field_limit_complete": False,
            "microscopic_mori_uv_matching_complete": False,
            "physical_F1_perp_claimed": False,
        },
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")


if __name__ == "__main__":
    main()
