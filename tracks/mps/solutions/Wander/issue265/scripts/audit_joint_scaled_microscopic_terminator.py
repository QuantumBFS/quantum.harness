#!/usr/bin/env python3
"""Peel exact XXX Mori moments from a joint-scaled full-mode GHD kernel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    mori_kernel_from_lanczos_terminator,
    mori_lanczos_stieltjes_bounds,
    mori_lanczos_terminator_from_kernel,
    xxx_mori_long_wave_lanczos,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT
        / "docs/regulated_infinite_mode_fghd_adaptive_joint_scaled_spectrum.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--hydrodynamic-p-maximum", type=float, default=7.59375)
    parser.add_argument("--relative-tolerance", type=float, default=0.02)
    parser.add_argument(
        "--recurrent-count",
        type=int,
        help="peel only this many exact recurrents (default: all available)",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if payload.get("uses_target_a_or_D") or payload.get("uses_target_trajectory"):
        raise RuntimeError("input certificate is target contaminated")
    per_field = []
    all_positive = True
    all_inside_bounds = True
    maximum_reconstruction_residual = 0.0
    for row in sorted(payload["rows"], key=lambda item: item["field"], reverse=True):
        field = float(row["field"])
        by_wave = row["exact_full_complement_mori_resolvent"]
        if len(by_wave) != 1:
            raise ValueError("audit currently requires exactly one scaled wave number")
        wave_text, by_frequency = next(iter(by_wave.items()))
        wave = float(wave_text)
        # The joint scaling sends k=q h^2 to zero.  Use the thirteen strict
        # long-wave recurrents (through the independently calculated mu26)
        # rather than discarding mu18 through mu26 merely because finite-k closed
        # forms are presently available only through mu16.  The remaining
        # finite-k error is explicitly O(k^2)=O(h^4).
        all_recurrents = np.asarray(
            xxx_mori_long_wave_lanczos()["squared_recurrents"]
        )
        recurrent_count = args.recurrent_count or int(all_recurrents.size)
        if recurrent_count < 1 or recurrent_count > all_recurrents.size:
            raise ValueError("recurrent-count exceeds the exact microscopic prefix")
        recurrents = all_recurrents[:recurrent_count]
        entries = []
        for frequency_text, datum in sorted(
            by_frequency.items(), key=lambda item: float(item[0])
        ):
            frequency = float(frequency_text)
            kernel = float(datum["continuity_memory"]["real"])
            bounds = mori_lanczos_stieltjes_bounds(
                np.asarray(frequency), 0.5, recurrents
            )
            lower = float(bounds["lower"])
            upper = float(bounds["upper"])
            inside = lower <= kernel <= upper
            terminator = float(
                mori_lanczos_terminator_from_kernel(
                    frequency, kernel, 0.5, recurrents
                )
            )
            reconstructed = float(
                mori_kernel_from_lanczos_terminator(
                    frequency, terminator, 0.5, recurrents
                )
            )
            residual = abs(reconstructed - kernel) / abs(kernel)
            maximum_reconstruction_residual = max(
                maximum_reconstruction_residual, residual
            )
            all_positive = all_positive and terminator > 0.0
            all_inside_bounds = all_inside_bounds and inside
            entries.append(
                {
                    "scaled_frequency_p_equals_z_over_h3": frequency / field**3,
                    "laplace_frequency": frequency,
                    "total_continuity_kernel": kernel,
                    "moment_lower_bound": lower,
                    "moment_upper_bound": upper,
                    "inside_exact_moment_interval": inside,
                    "thirteenth_level_terminator": terminator,
                    "scaled_h_times_terminator": field * terminator,
                    "reconstruction_relative_residual": residual,
                }
            )
        per_field.append(
            {
                "field": field,
                "wave_number": wave,
                "scaled_wave_q_equals_k_over_h2": wave / field**2,
                "exact_squared_recurrents": recurrents.tolist(),
                "entries": entries,
            }
        )
    scaled = np.asarray(
        [[entry["scaled_h_times_terminator"] for entry in row["entries"]] for row in per_field]
    )
    relative_steps = np.abs(np.diff(scaled, axis=0)) / np.maximum(
        np.abs(scaled[1:]), 1.0e-15
    )
    scaled_frequencies = np.asarray(
        [
            entry["scaled_frequency_p_equals_z_over_h3"]
            for entry in per_field[0]["entries"]
        ]
    )
    low_frequency_mask = scaled_frequencies <= args.hydrodynamic_p_maximum
    if not np.any(low_frequency_mask):
        raise ValueError("declared hydrodynamic p window contains no points")
    low_frequency_change = float(np.max(relative_steps[-1, low_frequency_mask]))
    result = {
        "schema": 1,
        "method": "exact_finite_recurrent_long_wave_peeling_of_joint_scaled_full_mode_kernel",
        "exact_recurrent_count": int(recurrent_count),
        "exact_even_moment_order": int(2 * recurrent_count),
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "per_field": per_field,
        "audit": {
            "all_terminators_positive": bool(all_positive),
            "all_kernels_inside_exact_moment_intervals": bool(all_inside_bounds),
            "maximum_reconstruction_relative_residual": float(
                maximum_reconstruction_residual
            ),
            "maximum_last_field_step_relative_scaled_terminator_change": float(
                np.max(relative_steps[-1])
            ),
            "last_field_step_relative_scaled_terminator_change_by_p": (
                relative_steps[-1].tolist()
            ),
            "declared_hydrodynamic_p_maximum": args.hydrodynamic_p_maximum,
            "declared_relative_tolerance": args.relative_tolerance,
            "maximum_low_p_last_field_step_relative_change": low_frequency_change,
            "finite_pole_terminator_assumed": False,
            "finite_k_recurrent_error_order": "O(k^2)=O(h^4) at fixed q=k/h^2",
            "linear_full_mode_joint_scaling_supported_on_declared_low_p_window": bool(
                all_positive
                and all_inside_bounds
                and low_frequency_change < args.relative_tolerance
            ),
            "linear_full_mode_joint_scaling_supported_on_entire_sampled_p_grid": bool(
                all_positive
                and all_inside_bounds
                and np.max(relative_steps[-1]) < args.relative_tolerance
            ),
            "physical_full_nonlinear_terminator_claimed": False,
            "remaining_requirement": (
                "add the UV-matched nonlinear fluctuating-GHD vertices before "
                "promoting the linear full-mode terminator to the physical F1"
            ),
        },
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
