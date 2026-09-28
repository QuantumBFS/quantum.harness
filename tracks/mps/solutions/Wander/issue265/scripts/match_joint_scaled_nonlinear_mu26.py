#!/usr/bin/env python3
"""Top-level mu26 matching of joint-scaled nonlinear fluctuating GHD.

For every field regulator this program reconstructs the complete non-diagonal
linear Mori kernel at fixed ``q=k/h^2`` and ``p=z/h^3``.  It adds the Laplace
transform of the colored velocity/diffusion/cross force from the matrix-free
nonlinear certificate.  The hydrodynamic white delta contact is cancelled in
full because an analytic microscopic Mori kernel has no constant large-z
term.  Only then is the exact XXX mu26 prefix peeled from the *top-level*
kernel.  The residual terminator is tested for positivity; it is never
replaced by a prescribed number of poles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    full_diffusion_operator_field_adaptive_rapidity,
)
from src.heisenberg_burgers_bridge import (  # noqa: E402
    mori_kernel_from_lanczos_terminator,
    mori_lanczos_stieltjes_bounds,
    mori_lanczos_terminator_from_kernel,
    xxx_mori_long_wave_lanczos,
)
from src.infinite_mode_fluctuating_ghd import (  # noqa: E402
    krylov_spin_mori_resolvent,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _laplace(times: np.ndarray, values: np.ndarray, z: np.ndarray) -> np.ndarray:
    return np.asarray(
        [np.trapezoid(np.exp(-frequency * times) * values, times) for frequency in z]
    )


def derive(args: argparse.Namespace) -> dict[str, object]:
    if len(args.certificates) < 2:
        raise ValueError("at least two field regulators are required")
    lanczos = xxx_mori_long_wave_lanczos()
    mu0 = float(lanczos["mu0"])
    recurrents = np.asarray(lanczos["squared_recurrents"], dtype=float)
    p = np.asarray(args.scaled_laplace_frequencies, dtype=float)
    if p.ndim != 1 or p.size < 3 or np.any(p <= 0.0):
        raise ValueError("need at least three positive scaled frequencies p")

    sources = []
    for path in args.certificates:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("uses_target_trajectory") or payload.get("uses_target_a_or_D"):
            raise RuntimeError(f"target-contaminated certificate: {path}")
        coordinates = payload["hydrodynamic_coordinates"]
        if not coordinates.get("joint_scaled_input"):
            raise ValueError(f"certificate is not joint-scaled: {path}")
        sources.append((float(payload["regulator"]["field"]), path, payload))
    sources.sort(key=lambda item: item[0], reverse=True)

    reference_q = None
    reference_tau = None
    rows = []
    scaled_total_rows = []
    all_inside = True
    all_positive = True
    maximum_reconstruction_residual = 0.0
    for h, path, payload in sources:
        coordinates = payload["hydrodynamic_coordinates"]
        q = float(coordinates["scaled_wave_step_q_equals_k_over_h2"])
        tau = np.asarray(coordinates["scaled_times_tau_equals_t_h3"], dtype=float)
        if reference_q is None:
            reference_q = q
            reference_tau = tau
        elif not np.isclose(q, reference_q) or not np.allclose(tau, reference_tau):
            raise ValueError("all certificates must use the same q and tau grids")
        times = tau / h**3
        z = p * h**3
        memory = np.asarray(
            [row["continuity_memory_estimates"]["total"][0] for row in payload["rows"]],
            dtype=float,
        )
        memory_error = np.asarray(
            [row["standard_error_complex_norms"]["total"] for row in payload["rows"]],
            dtype=float,
        )
        colored = _laplace(times, memory, z)
        # Common random vectors correlate the time points.  Integrating the
        # pointwise standard errors is a conservative triangle bound.
        colored_error_bound = _laplace(times, memory_error, z)

        modes = full_diffusion_operator_field_adaptive_rapidity(
            h,
            string_xi_cutoff=args.string_xi_cutoff,
            string_xi_buffer=args.string_xi_buffer,
            scaled_rapidity_extent=args.scaled_rapidity_extent,
            scaled_rapidity_map_alpha=args.scaled_rapidity_map_alpha,
            nodes_per_string=args.nodes_per_string,
            kernel_theta_step=args.kernel_theta_step,
            string_boundary="robin",
            operator_only=True,
        )
        wave = q * h**2
        linear = []
        linear_residuals = []
        for frequency in z:
            solved = krylov_spin_mori_resolvent(
                modes["velocity"],
                modes["diffusion_operator"],
                modes["static_covariance"],
                modes["noise_covariance"],
                modes["spin_projection"],
                wave,
                float(frequency),
            )
            if int(solved["gmres_info"]) != 0:
                raise RuntimeError(f"GMRES failed for h={h}, z={frequency}")
            linear.append(float(complex(solved["continuity_memory"]).real))
            linear_residuals.append(float(solved["linear_solve_relative_residual"]))
        linear = np.asarray(linear)
        total = linear + colored
        scaled_total_rows.append(h * total)

        frequency_rows = []
        terminators = []
        for pp, frequency, base, correction, error, candidate in zip(
            p, z, linear, colored, colored_error_bound, total
        ):
            bounds = mori_lanczos_stieltjes_bounds(frequency, mu0, recurrents)
            lower = float(bounds["lower"])
            upper = float(bounds["upper"])
            inside = bool(lower <= candidate <= upper)
            terminator = float(
                mori_lanczos_terminator_from_kernel(
                    frequency, candidate, mu0, recurrents
                )
            )
            if terminator > 0.0:
                reconstructed = float(
                    mori_kernel_from_lanczos_terminator(
                        frequency, terminator, mu0, recurrents
                    )
                )
                residual = abs(reconstructed - candidate) / max(
                    abs(candidate), 1.0e-300
                )
            else:
                reconstructed = None
                residual = None
            all_inside = all_inside and inside
            all_positive = all_positive and terminator > 0.0
            if residual is not None:
                maximum_reconstruction_residual = max(
                    maximum_reconstruction_residual, residual
                )
            terminators.append(terminator)
            frequency_rows.append(
                {
                    "scaled_frequency_p": float(pp),
                    "physical_frequency_z": float(frequency),
                    "scaled_linear_hK": float(h * base),
                    "scaled_colored_hDeltaK": float(h * correction),
                    "scaled_colored_error_upper_bound": float(h * error),
                    "scaled_total_hK": float(h * candidate),
                    "mu26_stieltjes_lower": lower,
                    "mu26_stieltjes_upper": upper,
                    "inside_mu26_interval": inside,
                    "mu26_terminator": terminator,
                    "terminator_positive": bool(terminator > 0.0),
                    "reconstruction_relative_residual": residual,
                }
            )
        susceptibility = float(
            modes["spin_projection"]
            @ modes["static_covariance"]
            @ modes["spin_projection"]
        )
        exact_chi = 1.0 / (4.0 * np.cosh(h) ** 2)
        rows.append(
            {
                "field": h,
                "source": str(path),
                "source_sha256": _sha256(path),
                "mode_count": int(modes["mode_count"]),
                "susceptibility_captured_fraction": susceptibility / exact_chi,
                "white_contact_bare": float(
                    payload["multiplicative_noise_delta_memory"]["estimate"]
                ),
                "white_contact_counterterm": float(
                    -payload["multiplicative_noise_delta_memory"]["estimate"]
                ),
                "renormalized_white_contact": 0.0,
                "maximum_linear_gmres_residual": max(linear_residuals),
                "frequency_rows": frequency_rows,
                "terminators": terminators,
            }
        )

    scaled_total = np.asarray(scaled_total_rows)
    absolute = np.abs(scaled_total[-1] - scaled_total[-2])
    scale = np.maximum.reduce(
        (
            np.abs(scaled_total[-1]),
            np.abs(scaled_total[-2]),
            np.full_like(absolute, 1.0e-300),
        )
    )
    relative = absolute / scale
    return {
        "schema": 1,
        "method": "joint_scaled_top_level_nonlinear_fghd_mu26_matching",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "scaled_variables": {
            "q_equals_k_over_h2": reference_q,
            "p_equals_z_over_h3": p.tolist(),
            "tau_equals_t_h3": reference_tau.tolist(),
        },
        "operator_regulators": {
            "string_xi_cutoff": args.string_xi_cutoff,
            "string_xi_buffer": args.string_xi_buffer,
            "scaled_rapidity_extent": args.scaled_rapidity_extent,
            "scaled_rapidity_map_alpha": args.scaled_rapidity_map_alpha,
            "nodes_per_string": args.nodes_per_string,
            "kernel_theta_step": args.kernel_theta_step,
        },
        "exact_prefix": {
            "recurrent_count": int(recurrents.size),
            "highest_even_moment": int(2 * recurrents.size),
            "finite_k_error_order": "O(k^2)=O(q^2 h^4)",
        },
        "rows": rows,
        "last_field_step": {
            "scaled_total_hK_relative_change_by_p": relative.tolist(),
            "maximum_scaled_total_hK_relative_change": float(np.max(relative)),
        },
        "gates": {
            "complete_non_diagonal_linear_operator": True,
            "complete_colored_velocity_diffusion_cross_added": True,
            "white_contact_uniquely_cancelled_by_large_z_regularity": True,
            "all_candidates_inside_mu26_intervals": all_inside,
            "all_mu26_terminators_positive": all_positive,
            "maximum_reconstruction_relative_residual": maximum_reconstruction_residual,
            "finite_time_tail_converged": False,
            "joint_field_limit_converged": False,
            "physical_F1_certified": False,
        },
        "interpretation": (
            "The nonlinear continuum is matched at the physical top-level Mori "
            "kernel before peeling mu26.  A failed interval or regulator gate "
            "rejects this finite-regulator approximation; it does not imply a "
            "finite-pole or second-mode closure."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificates", nargs="+", type=Path)
    parser.add_argument(
        "--scaled-laplace-frequencies", nargs="+", type=float, default=[1.0, 2.0, 4.0]
    )
    parser.add_argument("--string-xi-cutoff", type=float, default=6.0)
    parser.add_argument("--string-xi-buffer", type=float, default=3.0)
    parser.add_argument("--scaled-rapidity-extent", type=float, default=12.0)
    parser.add_argument("--scaled-rapidity-map-alpha", type=float, default=4.0)
    parser.add_argument("--nodes-per-string", type=int, default=12)
    parser.add_argument("--kernel-theta-step", type=float, default=1.0)
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
