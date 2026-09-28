#!/usr/bin/env python3
"""Self-consistent joint-scaled mode-coupling resummation of full-mode F-GHD.

The bare matrix-free velocity/diffusion/cross loop uses linear propagators and
has a non-uniform zero-field limit.  This diagnostic dresses both internal
lines by ``exp[-Gamma |khat|^(3/2) t]`` and determines ``Gamma`` from the
external Dyson equation

    Gamma = sqrt(qhat) h [K_linear + Delta K_Gamma]

at ``z=Gamma |khat|^(3/2)``.  The full non-diagonal finite-field linear Mori
kernel and every retained internal-wave contribution are used.  This is the
minimal scalar self-consistent mode-coupling closure, not an assumption that
the complete infinite-mode theory contains one or two physical fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import brentq


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    full_diffusion_operator_field_adaptive_rapidity,
)
from src.infinite_mode_fluctuating_ghd import (  # noqa: E402
    krylov_spin_mori_resolvent,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _internal_damped_memory(
    payload: dict[str, object], gamma: float
) -> np.ndarray:
    h = float(payload["regulator"]["field"])
    points = int(payload["regulator"]["fourier_points"])
    wave_step = float(payload["hydrodynamic_coordinates"]["physical_wave_step"])
    cell_length = 2.0 * np.pi / (points * wave_step)
    exact_chi = 1.0 / (4.0 * np.cosh(h) ** 2)
    captured_chi = (
        float(payload["static_susceptibility_captured_fraction"]) * exact_chi
    )
    fourier_chi = captured_chi / cell_length
    external_symbol = 2.0 * np.sin(0.5 * wave_step)
    normalization = fourier_chi * external_symbol**2
    values = []
    for row in payload["rows"]:
        time = float(row["time"])
        total = 0.0j
        for internal in row["internal_wave_rows"]:
            p_symbol = 2.0 * np.sin(0.5 * float(internal["p_wave"]))
            q_symbol = 2.0 * np.sin(0.5 * float(internal["q_wave"]))
            damping = np.exp(
                -gamma
                * (abs(p_symbol) ** 1.5 + abs(q_symbol) ** 1.5)
                * time
            )
            pair = internal["estimates"]["total"]
            total += complex(float(pair[0]), float(pair[1])) * damping
        values.append((total / normalization).real)
    return np.asarray(values)


def derive(args: argparse.Namespace) -> dict[str, object]:
    if len(args.certificates) < 2:
        raise ValueError("at least two field regulators are required")
    sources = []
    for path in args.certificates:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("uses_target_trajectory") or payload.get("uses_target_a_or_D"):
            raise RuntimeError(f"target-contaminated source: {path}")
        if not payload["hydrodynamic_coordinates"].get("joint_scaled_input"):
            raise ValueError(f"source is not joint-scaled: {path}")
        sources.append((float(payload["regulator"]["field"]), path, payload))
    sources.sort(key=lambda item: item[0], reverse=True)

    reference_q = None
    reference_tau = None
    rows = []
    for h, path, payload in sources:
        coordinates = payload["hydrodynamic_coordinates"]
        q = float(coordinates["scaled_wave_step_q_equals_k_over_h2"])
        tau = np.asarray(coordinates["scaled_times_tau_equals_t_h3"], dtype=float)
        if reference_q is None:
            reference_q = q
            reference_tau = tau
        elif not np.isclose(q, reference_q) or not np.allclose(tau, reference_tau):
            raise ValueError("all sources must share fixed q and tau grids")
        times = tau / h**3
        wave = q * h**2
        khat = 2.0 * np.sin(0.5 * wave)
        qhat = khat / h**2
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

        evaluations: list[dict[str, float]] = []

        def fixed_point_residual(gamma: float) -> float:
            frequency = gamma * abs(khat) ** 1.5
            solved = krylov_spin_mori_resolvent(
                modes["velocity"],
                modes["diffusion_operator"],
                modes["static_covariance"],
                modes["noise_covariance"],
                modes["spin_projection"],
                wave,
                frequency,
            )
            if int(solved["gmres_info"]) != 0:
                raise RuntimeError(f"GMRES failed at h={h}, Gamma={gamma}")
            linear = float(complex(solved["continuity_memory"]).real)
            damped_memory = _internal_damped_memory(payload, gamma)
            colored = float(
                np.trapezoid(np.exp(-frequency * times) * damped_memory, times)
            )
            rhs = np.sqrt(qhat) * h * (linear + colored)
            evaluations.append(
                {
                    "gamma": gamma,
                    "scaled_frequency_p": frequency / h**3,
                    "scaled_linear_hK": h * linear,
                    "scaled_colored_hDeltaK": h * colored,
                    "fixed_point_rhs": rhs,
                    "residual": rhs - gamma,
                }
            )
            return rhs - gamma

        lower, upper = map(float, args.gamma_bracket)
        lower_residual = fixed_point_residual(lower)
        upper_residual = fixed_point_residual(upper)
        if not lower_residual > 0.0 > upper_residual:
            raise RuntimeError(
                f"Gamma root not bracketed at h={h}: {lower_residual}, {upper_residual}"
            )
        gamma = float(
            brentq(
                fixed_point_residual,
                lower,
                upper,
                xtol=args.root_tolerance,
                rtol=args.root_tolerance,
            )
        )
        fixed_point_residual(gamma)
        final = evaluations[-1]
        rows.append(
            {
                "field": h,
                "source": str(path),
                "source_sha256": _sha256(path),
                "mode_count": int(modes["mode_count"]),
                "susceptibility_captured_fraction": float(
                    payload["static_susceptibility_captured_fraction"]
                ),
                "self_consistent_gamma": gamma,
                "scaled_frequency_p_at_fixed_point": final["scaled_frequency_p"],
                "scaled_linear_hK_at_fixed_point": final["scaled_linear_hK"],
                "scaled_colored_hDeltaK_at_fixed_point": final[
                    "scaled_colored_hDeltaK"
                ],
                "fixed_point_residual": final["residual"],
                "function_evaluations": len(evaluations),
            }
        )

    gamma = np.asarray([row["self_consistent_gamma"] for row in rows])
    fields = np.asarray([row["field"] for row in rows])
    last_relative_change = abs(gamma[-1] - gamma[-2]) / max(
        abs(gamma[-1]), abs(gamma[-2]), 1.0e-300
    )
    extrapolations = []
    for power in (1.0 / 3.0, 0.5, 2.0 / 3.0, 1.0):
        design = np.column_stack((np.ones_like(fields), fields**power))
        limit, slope = np.linalg.lstsq(design, gamma, rcond=None)[0]
        prediction = design @ np.asarray([limit, slope])
        extrapolations.append(
            {
                "correction_power": power,
                "zero_field_limit": float(limit),
                "slope": float(slope),
                "relative_residual": float(
                    np.linalg.norm(prediction - gamma) / np.linalg.norm(gamma)
                ),
            }
        )
    limits = np.asarray([row["zero_field_limit"] for row in extrapolations])
    return {
        "schema": 1,
        "method": "self_consistent_scalar_kpz_line_dressing_of_full_mode_fghd_loop",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "scaled_variables": {
            "q_equals_k_over_h2": reference_q,
            "tau_equals_t_h3": reference_tau.tolist(),
        },
        "closure": {
            "internal_line_factor": "exp[-Gamma (|p_hat|^(3/2)+|q_hat|^(3/2)) t]",
            "fixed_point_equation": "Gamma=sqrt(qhat)*h*(K_linear+DeltaK_Gamma)",
            "white_contact_removed": True,
            "exact_kpz_scaling_function_used": False,
            "finite_mode_or_second_field_assumed": False,
        },
        "rows": rows,
        "last_field_step_relative_gamma_change": float(last_relative_change),
        "zero_field_extrapolation_schemes": extrapolations,
        "zero_field_extrapolation_envelope": [
            float(np.min(limits)),
            float(np.max(limits)),
        ],
        "gates": {
            "fixed_point_found_every_field": True,
            "last_field_step_below_two_percent": bool(last_relative_change < 0.02),
            "field_limit_converged": False,
            "exact_kpz_shape_resummation_complete": False,
            "physical_finite_window_kernel_certified": False,
        },
        "interpretation": (
            "Scalar KPZ line dressing removes the bare power divergence, but its "
            "remaining field and closure dependence must converge before the "
            "result can normalize a physical wall."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificates", nargs="+", type=Path)
    parser.add_argument("--string-xi-cutoff", type=float, default=6.0)
    parser.add_argument("--string-xi-buffer", type=float, default=3.0)
    parser.add_argument("--scaled-rapidity-extent", type=float, default=12.0)
    parser.add_argument("--scaled-rapidity-map-alpha", type=float, default=4.0)
    parser.add_argument("--nodes-per-string", type=int, default=12)
    parser.add_argument("--kernel-theta-step", type=float, default=1.0)
    parser.add_argument("--gamma-bracket", nargs=2, type=float, default=[0.05, 20.0])
    parser.add_argument("--root-tolerance", type=float, default=1.0e-8)
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
