#!/usr/bin/env python3
"""Derive the no-trajectory XXX-to-finite-window closure hierarchy.

The calculation accepts only the declared time window.  All other numerical
inputs are microscopic TBA constants or universal stationary-KPZ integrals
stored with their definitions in ``src.heisenberg_burgers_bridge``.  It never
opens a Heisenberg trajectory or accepts target Burgers coefficients.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    EXACT_D0_INFINITY_T,
    finite_field_scale_correction,
    kpz_lambda_from_tba,
    theory_only_current_projection,
    theory_only_current_projection_diagnostics,
    theory_only_running_current_projection,
    theory_only_strong_projection,
    theory_only_strong_scale_corrected_projection,
    theory_only_scale_corrected_projection,
    theory_only_width_rate_projection,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output; the same JSON is always printed to stdout",
    )
    return parser.parse_args()


def _pair(values: tuple[float, float]) -> dict[str, float]:
    return {"a": float(values[0]), "D": float(values[1])}


def derive(t_start: float, t_stop: float) -> dict[str, object]:
    if not 0.0 < t_start < t_stop:
        raise ValueError("Require 0 < t-start < t-stop")

    leading_strong = theory_only_strong_projection(t_start, t_stop)
    leading_current = theory_only_current_projection(t_start, t_stop)
    scale_correction = finite_field_scale_correction()
    corrected_strong = theory_only_strong_scale_corrected_projection(
        scale_correction, t_start, t_stop
    )
    corrected_current = theory_only_scale_corrected_projection(
        scale_correction, t_start, t_stop
    )
    pairs = np.asarray(
        [leading_strong, leading_current, corrected_strong, corrected_current],
        dtype=float,
    )
    lower = np.min(pairs, axis=0)
    upper = np.max(pairs, axis=0)
    center = 0.5 * (lower + upper)
    half_width = 0.5 * (upper - lower)

    endpoints = np.asarray([t_start, t_stop], dtype=float)
    running = theory_only_running_current_projection(endpoints)
    current_diagnostics = theory_only_current_projection_diagnostics(
        t_start, t_stop
    )
    width = theory_only_width_rate_projection(t_start, t_stop)

    return {
        "schema_version": 1,
        "inputs": {
            "t_start": float(t_start),
            "t_stop": float(t_stop),
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "microscopic_model": "spin-1/2 isotropic Heisenberg chain, J=1",
            "initial_state": "infinite-temperature infinitesimal sharp domain wall",
        },
        "microscopic_and_universal_inputs": {
            "D0": float(EXACT_D0_INFINITY_T),
            "lambda_kpz_self_consistent": float(kpz_lambda_from_tba()),
            "spectral_scale_correction": float(scale_correction),
        },
        "constant_window_projections": {
            "leading_strong": _pair(leading_strong),
            "leading_current": _pair(leading_current),
            "spectral_scale_strong": _pair(corrected_strong),
            "spectral_scale_current": _pair(corrected_current),
        },
        "scheme_variation_estimate": {
            "a": float(center[0]),
            "a_half_width": float(half_width[0]),
            "D": float(center[1]),
            "D_half_width": float(half_width[1]),
            "interpretation": (
                "restricted strong/current operator-level truncation band; "
                "not a confidence interval and not an envelope over every "
                "possible observable projector"
            ),
        },
        "running_local_current_projection": {
            "times": endpoints.tolist(),
            "a": np.asarray(running["coefficient"]).tolist(),
            "D": np.asarray(running["diffusion"]).tolist(),
            "alpha": float(running["alpha"]),
            "delta": float(running["delta"]),
            "relative_current_residual": float(
                running["relative_current_residual"]
            ),
        },
        "constant_current_diagnostics": {
            "relative_current_residual": float(
                current_diagnostics["relative_current_residual"]
            ),
            "normalized_condition_number": float(
                current_diagnostics["normalized_condition_number"]
            ),
        },
        "width_rate_projection": {
            "a": float(width["coefficient"]),
            "D": float(width["diffusion"]),
            "relative_rate_residual": float(width["relative_rate_residual"]),
        },
    }


def main() -> int:
    args = _arguments()
    result = derive(args.t_start, args.t_stop)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
