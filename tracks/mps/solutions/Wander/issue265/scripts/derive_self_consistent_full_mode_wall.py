#!/usr/bin/env python3
"""Build a target-free wall from the full joint-scaled linear GHD spectrum.

The complete non-diagonal finite-field operators are propagated at fixed
``q=k/h^2`` and ``tau=t*h^3``.  The ``h->0`` shape is extrapolated before an
inverse Fourier transform.  Its variance is normalized internally, removing
the harmless factor-of-two convention between GHD diffusion matrices and a
scalar diffusion equation.  The physical RMS width is fixed only by the exact
giant-string amplitude ``D0=5*pi/27``.  No target wall or Burgers coefficient
is read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import savgol_filter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    full_diffusion_operator_field_adaptive_rapidity,
)
from src.heisenberg_burgers_bridge import EXACT_D0_INFINITY_T  # noqa: E402
from src.infinite_mode_fluctuating_ghd import (  # noqa: E402
    joint_scaled_spin_structure_grid,
)
from src.tension_resolution import fit_profiled_weak  # noqa: E402


def _zero_field_schemes(fields: np.ndarray, values: np.ndarray):
    schemes = {"smallest_field": values[-1]}
    for degree in (1, 2):
        coefficients = np.polynomial.polynomial.polyfit(fields, values, degree)
        schemes[f"field_polynomial_degree_{degree}"] = coefficients[0]
    return schemes


def _variance_from_curvature(q: np.ndarray, structure: np.ndarray) -> float:
    mask = (q > 0.0) & (q <= 1.0)
    if np.count_nonzero(mask) < 3:
        raise ValueError("q grid needs at least three points in (0,1]")
    x = q[mask] ** 2
    design = np.column_stack((x, x**2))
    coefficient, *_ = np.linalg.lstsq(design, 1.0 - structure[mask], rcond=None)
    variance = 2.0 * coefficient[0]
    if not np.isfinite(variance) or variance <= 0.0:
        raise ValueError("extrapolated structure has non-positive variance")
    return float(variance)


def _wall_shape(
    q: np.ndarray, structure: np.ndarray, variance: float, y: np.ndarray
) -> np.ndarray:
    # kappa=sqrt(variance)*q makes the reconstructed density have unit
    # variance.  U(y)=pi^-1 int_0^inf sin(kappa*y) F(kappa)/kappa dkappa.
    phase = np.sqrt(variance) * np.outer(y, q)
    integrand = np.empty_like(phase)
    integrand[:, 0] = np.sqrt(variance) * y
    integrand[:, 1:] = (
        np.sin(phase[:, 1:]) / q[None, 1:] * structure[None, 1:]
    )
    wall = np.trapezoid(integrand, q, axis=1) / np.pi
    wall[np.argmin(np.abs(y))] = 0.0
    return wall


def derive(args: argparse.Namespace) -> dict[str, object]:
    fields = np.asarray(sorted(args.fields, reverse=True), dtype=float)
    q = np.arange(0.0, args.q_maximum + 0.5 * args.q_step, args.q_step)
    chi = 0.25
    rms_scale = (4.0 * EXACT_D0_INFINITY_T * np.sqrt(chi)) ** (2.0 / 3.0)
    # h=1/sqrt(4 chi ell), ell=rms_scale*t^(2/3), hence tau=t*h^3.
    tau = 1.0 / (4.0 * EXACT_D0_INFINITY_T * np.sqrt(chi))
    rows = []
    structures = []
    for field in fields:
        raw = full_diffusion_operator_field_adaptive_rapidity(
            float(field),
            string_xi_cutoff=args.string_xi_cutoff,
            string_xi_buffer=args.string_xi_buffer,
            scaled_rapidity_extent=args.scaled_rapidity_extent,
            scaled_rapidity_map_alpha=args.scaled_rapidity_map_alpha,
            nodes_per_string=args.nodes_per_string,
            kernel_theta_step=args.kernel_theta_step,
            string_boundary="robin",
            operator_only=True,
        )
        propagated = joint_scaled_spin_structure_grid(
            raw["velocity"],
            raw["diffusion_operator"],
            raw["static_covariance"],
            raw["noise_covariance"],
            raw["spin_projection"],
            float(field),
            q,
            tau,
        )
        structure = np.real(propagated["structure_factor_over_susceptibility"])
        structures.append(structure)
        susceptibility = float(
            np.dot(
                raw["spin_projection"] * np.diag(raw["static_covariance"]),
                raw["spin_projection"],
            )
        )
        exact_chi = 1.0 / (4.0 * np.cosh(field) ** 2)
        rows.append(
            {
                "field": float(field),
                "mode_count": int(raw["mode_count"]),
                "susceptibility_captured_fraction": susceptibility / exact_chi,
                "fdt_residual": float(propagated["fdt_residual"]),
                "structure_factor": structure.tolist(),
            }
        )
    structures_array = np.asarray(structures)
    schemes = _zero_field_schemes(fields, structures_array)
    x = (np.arange(args.length) - 0.5 * (args.length - 1)) * args.dx
    times = np.arange(args.profile_start, args.profile_stop + 0.5 * args.dt, args.dt)
    y_grid = np.linspace(-args.y_maximum, args.y_maximum, args.y_points)
    scheme_rows = {}
    for name, structure in schemes.items():
        structure = np.asarray(structure, dtype=float)
        structure[0] = 1.0
        variance = _variance_from_curvature(q, structure)
        wall_y = _wall_shape(q, structure, variance, y_grid)
        spline = CubicSpline(y_grid, wall_y)
        profiles = []
        for time in times:
            ell = rms_scale * time ** (2.0 / 3.0)
            y = x / ell
            profile = spline(np.clip(y, y_grid[0], y_grid[-1]))
            profile = np.where(y < y_grid[0], -0.5, profile)
            profile = np.where(y > y_grid[-1], 0.5, profile)
            profiles.append(profile)
        profiles = savgol_filter(
            np.asarray(profiles), 31, 7, axis=1, mode="interp"
        )
        fit = fit_profiled_weak(
            x,
            times,
            profiles,
            t_window=(args.fit_start, args.fit_stop),
            x_crop=(args.x_crop[0], args.x_crop[1]),
            gamma=0.0,
        )
        scheme_rows[name] = {
            "variance_before_internal_normalization": variance,
            "wall_at_positive_y_boundary": float(wall_y[-1]),
            "fourier_tail_structure_at_qmax": float(structure[-1]),
            "a": float(fit.a),
            "D": float(fit.D0),
            "mse": float(fit.mse),
            "n_obs": int(fit.n_obs),
        }
    pairs = np.asarray([[row["a"], row["D"]] for row in scheme_rows.values()])
    return {
        "schema": 1,
        "method": "self_consistent_full_non_diagonal_linear_fghd_wall",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "microscopic_inputs": {
            "D0": float(EXACT_D0_INFINITY_T),
            "chi": chi,
            "rms_width_scale": float(rms_scale),
            "joint_scaled_time_tau": float(tau),
        },
        "regulators": {
            "fields": fields.tolist(),
            "q": q.tolist(),
            "q_maximum": args.q_maximum,
            "q_step": args.q_step,
            "nodes_per_string": args.nodes_per_string,
            "string_xi_cutoff": args.string_xi_cutoff,
            "string_xi_buffer": args.string_xi_buffer,
        },
        "field_rows": rows,
        "zero_field_wall_schemes": scheme_rows,
        "scheme_envelope": {
            "a_min": float(np.min(pairs[:, 0])),
            "a_max": float(np.max(pairs[:, 0])),
            "D_min": float(np.min(pairs[:, 1])),
            "D_max": float(np.max(pairs[:, 1])),
        },
        "scope": {
            "complete_linear_A_D_Q_propagated": True,
            "variance_scale_fixed_by_exact_D0_not_target_fit": True,
            "nonlinear_vertices_included": False,
            "physical_F1_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fields", nargs="+", type=float, default=[0.125, 0.1, 1 / 12])
    parser.add_argument("--string-xi-cutoff", type=float, default=6.0)
    parser.add_argument("--string-xi-buffer", type=float, default=3.0)
    parser.add_argument("--scaled-rapidity-extent", type=float, default=20.0)
    parser.add_argument("--scaled-rapidity-map-alpha", type=float, default=4.0)
    parser.add_argument("--nodes-per-string", type=int, default=32)
    parser.add_argument("--kernel-theta-step", type=float, default=1.0)
    parser.add_argument("--q-maximum", type=float, default=12.0)
    parser.add_argument("--q-step", type=float, default=0.25)
    parser.add_argument("--y-maximum", type=float, default=18.0)
    parser.add_argument("--y-points", type=int, default=3601)
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
