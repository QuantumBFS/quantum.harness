#!/usr/bin/env python3
"""Apply the frozen public-profile weak estimator to the theory-only KPZ wall.

The sampled profile contains no Heisenberg trajectory.  It is constructed from
the stationary Prähofer--Spohn scaling table and the giant-string/TBA KPZ scale,
then passed through exactly the spatial grid, time grid, upstream Savitzky--
Golay operation, crop, test functions, and weak least-squares estimator that
define the quoted public-profile pair.

No target Burgers coefficient is accepted as an input.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.signal import savgol_filter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_theory_finite_size_lattice import (  # noqa: E402
    _load_spline,
    _wall_and_time_derivative,
)
from src.heisenberg_burgers_bridge import (  # noqa: E402
    finite_field_scale_correction,
    kpz_lambda_from_tba,
)
from src.tension_resolution import fit_profiled_weak  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--dx", type=float, default=1.0)
    parser.add_argument("--dt", type=float, default=0.2)
    parser.add_argument("--profile-start", type=float, default=50.0)
    parser.add_argument("--profile-stop", type=float, default=200.0)
    parser.add_argument("--fit-start", type=float, default=52.0)
    parser.add_argument("--fit-stop", type=float, default=198.0)
    parser.add_argument("--x-crop", nargs=2, type=float, default=(-120.0, 120.0))
    parser.add_argument("--kpz-table", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--full-tba-d1-estimate", type=float, default=-0.82)
    return parser.parse_args()


def derive(
    *,
    length: int,
    dx: float,
    dt: float,
    profile_start: float,
    profile_stop: float,
    fit_start: float,
    fit_stop: float,
    x_crop: tuple[float, float],
    spline,
    full_tba_d1_estimate: float | None = -0.82,
) -> dict[str, object]:
    if length < 32 or length % 2:
        raise ValueError("length must be an even integer >=32")
    if dx <= 0.0 or dt <= 0.0:
        raise ValueError("dx and dt must be positive")
    if not 0.0 < profile_start <= fit_start < fit_stop <= profile_stop:
        raise ValueError("fit window must lie inside the positive profile window")
    if not x_crop[0] < x_crop[1]:
        raise ValueError("x crop must be increasing")

    lam = kpz_lambda_from_tba()
    x = (np.arange(length, dtype=float) - 0.5 * (length - 1)) * dx
    times = np.arange(profile_start, profile_stop + 0.5 * dt, dt)
    def evaluate(scale_correction: float) -> dict[str, float | int]:
        wall_rows = []
        table_edge = float(spline.x[-1])
        for time in times:
            if scale_correction == 0.0:
                row = _wall_and_time_derivative(
                    x, float(time), spline, lam
                )[0]
            else:
                front_length = lam ** (2.0 / 3.0) * (
                    time ** (2.0 / 3.0)
                    + scale_correction * time ** (1.0 / 3.0)
                )
                if front_length <= 0.0:
                    raise ValueError("scale correction makes the front length non-positive")
                scaled = x / front_length
                absolute = np.minimum(np.abs(scaled), table_edge)
                row = np.sign(scaled) * spline(absolute, 1) / 4.0
                row = np.where(scaled < -table_edge, -0.5, row)
                row = np.where(scaled > table_edge, 0.5, row)
            wall_rows.append(row)

        # This is the outer preprocessing frozen by the public-data conversion.
        # fit_profiled_weak then applies its own (9,3) spatial and (5,2) temporal
        # smoothing and the eleven compact-on-grid test functions.
        wall = savgol_filter(
            np.stack(wall_rows),
            window_length=31,
            polyorder=7,
            axis=1,
            mode="interp",
        )
        fit = fit_profiled_weak(
            x,
            times,
            wall,
            t_window=(fit_start, fit_stop),
            x_crop=x_crop,
            gamma=0.0,
        )
        return {
            "a": float(fit.a),
            "D": float(fit.D0),
            "mse": float(fit.mse),
            "n_obs": int(fit.n_obs),
        }

    spectral_correction = finite_field_scale_correction()
    full_tba_diagnostic = None
    if full_tba_d1_estimate is not None:
        full_tba_scale = finite_field_scale_correction(
            float(full_tba_d1_estimate)
        )
        full_tba_diagnostic = {
            "D1": float(full_tba_d1_estimate),
            "scale_correction": float(full_tba_scale),
            "physical_subleading_coefficient_claimed": False,
            **evaluate(full_tba_scale),
        }
    return {
        "schema_version": 1,
        "inputs": {
            "length": int(length),
            "dx": float(dx),
            "dt": float(dt),
            "profile_window": [float(profile_start), float(profile_stop)],
            "fit_window": [float(fit_start), float(fit_stop)],
            "x_crop": [float(x_crop[0]), float(x_crop[1])],
            "outer_savgol": [31, 7],
            "inner_spatial_savgol": [9, 3],
            "inner_temporal_savgol": [5, 2],
            "test_function_count": 11,
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "theory": {
            "kpz_scale": float(lam),
            "profile": "stationary_Praehofer_Spohn_KPZ_wall",
        },
        "frozen_weak_estimator": {
            "leading_kpz": evaluate(0.0),
            "spectral_scale_diagnostic": {
                "scale_correction": float(spectral_correction),
                "physical_subleading_coefficient_claimed": False,
                **evaluate(spectral_correction),
            },
            "provisional_full_tba_scale_diagnostic": full_tba_diagnostic,
        },
    }


def main() -> int:
    args = _arguments()
    result = derive(
        length=args.length,
        dx=args.dx,
        dt=args.dt,
        profile_start=args.profile_start,
        profile_stop=args.profile_stop,
        fit_start=args.fit_start,
        fit_stop=args.fit_stop,
        x_crop=(float(args.x_crop[0]), float(args.x_crop[1])),
        spline=_load_spline(args.kpz_table),
        full_tba_d1_estimate=args.full_tba_d1_estimate,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
