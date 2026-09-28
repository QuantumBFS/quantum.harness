#!/usr/bin/env python3
"""Solve the finite-window giant-string closure with the full linear GHD modes.

For each finite regulator field ``h`` this program finds ``tau_h`` from the
target-free thermal-fluctuation condition

    Var[F_h(q,tau_h)] = 1,

so that ``ell=1/h^2`` is the RMS propagation length and
``t_h=tau_h/h^3``.  The complete non-diagonal ``A,D,Q`` generator determines
both the field-to-time map and the non-Gaussian wall shape.  The resulting
irregular time knots are interpolated only after the microscopic propagation
and passed through the frozen weak projection.  Neither KPZ profile data nor
target Burgers coefficients enter.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.interpolate import CubicSpline, PchipInterpolator
from scipy.optimize import brentq
from scipy.signal import savgol_filter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_self_consistent_full_mode_wall import (  # noqa: E402
    _variance_from_curvature,
    _wall_shape,
)
from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    full_diffusion_operator_field_adaptive_rapidity,
)
from src.infinite_mode_fluctuating_ghd import (  # noqa: E402
    joint_scaled_spin_structure_grid,
)
from src.tension_resolution import fit_profiled_weak  # noqa: E402


def derive(args: argparse.Namespace) -> dict[str, object]:
    fields = np.asarray(sorted(args.fields, reverse=True), dtype=float)
    q_curvature = np.arange(0.0, 1.0 + 0.5 * args.curvature_q_step, args.curvature_q_step)
    q = np.arange(0.0, args.q_maximum + 0.5 * args.q_step, args.q_step)
    x = (np.arange(args.length) - 0.5 * (args.length - 1)) * args.dx
    y_grid = np.linspace(-args.y_maximum, args.y_maximum, args.y_points)
    knot_times = []
    knot_profiles = []
    rows = []
    for h in fields:
        raw = full_diffusion_operator_field_adaptive_rapidity(
            float(h),
            string_xi_cutoff=args.string_xi_cutoff,
            string_xi_buffer=args.string_xi_buffer,
            scaled_rapidity_extent=args.scaled_rapidity_extent,
            scaled_rapidity_map_alpha=args.scaled_rapidity_map_alpha,
            nodes_per_string=args.nodes_per_string,
            kernel_theta_step=args.kernel_theta_step,
            string_boundary="robin",
            operator_only=True,
        )

        def variance_minus_one(tau: float) -> float:
            propagated = joint_scaled_spin_structure_grid(
                raw["velocity"],
                raw["diffusion_operator"],
                raw["static_covariance"],
                raw["noise_covariance"],
                raw["spin_projection"],
                float(h),
                q_curvature,
                float(tau),
            )
            structure = np.real(
                propagated["structure_factor_over_susceptibility"]
            )
            return _variance_from_curvature(q_curvature, structure) - 1.0

        lower_value = variance_minus_one(args.tau_bracket[0])
        upper_value = variance_minus_one(args.tau_bracket[1])
        if not lower_value < 0.0 < upper_value:
            raise RuntimeError(
                f"field {h}: variance root not bracketed: {lower_value}, {upper_value}"
            )
        tau = float(
            brentq(
                variance_minus_one,
                args.tau_bracket[0],
                args.tau_bracket[1],
                xtol=1.0e-8,
                rtol=1.0e-8,
            )
        )
        propagated = joint_scaled_spin_structure_grid(
            raw["velocity"],
            raw["diffusion_operator"],
            raw["static_covariance"],
            raw["noise_covariance"],
            raw["spin_projection"],
            float(h),
            q,
            tau,
        )
        structure = np.real(propagated["structure_factor_over_susceptibility"])
        variance = _variance_from_curvature(q, structure)
        wall_y = _wall_shape(q, structure, variance, y_grid)
        wall_spline = CubicSpline(y_grid, wall_y)
        ell = 1.0 / h**2
        physical_time = tau / h**3
        scaled_x = x / ell
        profile = wall_spline(np.clip(scaled_x, y_grid[0], y_grid[-1]))
        profile = np.where(scaled_x < y_grid[0], -0.5, profile)
        profile = np.where(scaled_x > y_grid[-1], 0.5, profile)
        knot_times.append(physical_time)
        knot_profiles.append(profile)
        covariance_diagonal = np.diag(raw["static_covariance"])
        susceptibility = float(
            np.dot(
                raw["spin_projection"] * covariance_diagonal,
                raw["spin_projection"],
            )
        )
        exact_chi = 1.0 / (4.0 * np.cosh(h) ** 2)
        rows.append(
            {
                "field": float(h),
                "mode_count": int(raw["mode_count"]),
                "tau_root": tau,
                "physical_time": physical_time,
                "rms_length": ell,
                "root_variance_residual": variance - 1.0,
                "susceptibility_captured_fraction": susceptibility / exact_chi,
                "fdt_residual": float(propagated["fdt_residual"]),
                "structure_at_qmax": float(structure[-1]),
                "wall_at_ymax": float(wall_y[-1]),
            }
        )

    knot_times = np.asarray(knot_times)
    knot_profiles = np.asarray(knot_profiles)
    order = np.argsort(knot_times)
    knot_times = knot_times[order]
    knot_profiles = knot_profiles[order]
    rows = [rows[index] for index in order]
    if knot_times[0] > args.profile_start or knot_times[-1] < args.profile_stop:
        raise RuntimeError(
            "self-consistent field knots do not cover the requested profile window"
        )
    times = np.arange(args.profile_start, args.profile_stop + 0.5 * args.dt, args.dt)
    profiles = PchipInterpolator(knot_times, knot_profiles, axis=0)(times)
    profiles = savgol_filter(profiles, 31, 7, axis=1, mode="interp")
    fit = fit_profiled_weak(
        x,
        times,
        profiles,
        t_window=(args.fit_start, args.fit_stop),
        x_crop=(args.x_crop[0], args.x_crop[1]),
        gamma=0.0,
    )
    return {
        "schema": 1,
        "method": "finite_window_self_consistent_full_non_diagonal_linear_fghd",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "self_consistency": {
            "equations": [
                "ell=1/h^2 at chi=1/4",
                "Var_q[F_h(q,tau_h)]=1",
                "t_h=tau_h/h^3",
            ],
            "kpz_scaling_function_used": False,
            "exact_D0_inserted_into_wall_scale": False,
        },
        "regulators": {
            "fields": fields.tolist(),
            "q_maximum": args.q_maximum,
            "q_step": args.q_step,
            "curvature_q_step": args.curvature_q_step,
            "nodes_per_string": args.nodes_per_string,
            "string_xi_cutoff": args.string_xi_cutoff,
            "string_xi_buffer": args.string_xi_buffer,
        },
        "self_consistent_knots": rows,
        "frozen_weak_projection": {
            "a": float(fit.a),
            "D": float(fit.D0),
            "mse": float(fit.mse),
            "n_obs": int(fit.n_obs),
        },
        "scope": {
            "complete_linear_A_D_Q_propagated": True,
            "finite_window_field_dependence_retained": True,
            "nonlinear_state_derivative_vertices_included": False,
            "physical_F1_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fields", nargs="+", type=float,
        default=[0.26, 0.24, 0.22, 0.20, 0.18, 0.16, 0.145, 0.135],
    )
    parser.add_argument("--string-xi-cutoff", type=float, default=6.0)
    parser.add_argument("--string-xi-buffer", type=float, default=3.0)
    parser.add_argument("--scaled-rapidity-extent", type=float, default=20.0)
    parser.add_argument("--scaled-rapidity-map-alpha", type=float, default=4.0)
    parser.add_argument("--nodes-per-string", type=int, default=32)
    parser.add_argument("--kernel-theta-step", type=float, default=1.0)
    parser.add_argument("--q-maximum", type=float, default=12.0)
    parser.add_argument("--q-step", type=float, default=0.25)
    parser.add_argument("--curvature-q-step", type=float, default=0.25)
    parser.add_argument("--tau-bracket", nargs=2, type=float, default=[0.1, 1.2])
    parser.add_argument("--y-maximum", type=float, default=10.0)
    parser.add_argument("--y-points", type=int, default=2001)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--dx", type=float, default=1.0)
    parser.add_argument("--dt", type=float, default=0.2)
    parser.add_argument("--profile-start", type=float, default=50.0)
    parser.add_argument("--profile-stop", type=float, default=200.0)
    parser.add_argument("--fit-start", type=float, default=52.0)
    parser.add_argument("--fit-stop", type=float, default=198.0)
    parser.add_argument("--x-crop", nargs=2, type=float, default=[-120.0, 120.0])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(args)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
