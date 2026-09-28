#!/usr/bin/env python3
"""Propagate the full non-diagonal fluctuating-GHD regulator sequence.

This is deliberately not a two-mode calculation.  For every positive field,
all retained string/rapidity nodes are whitened and rotated so the first
coordinate is physical magnetization.  The entire orthogonal complement and
the complete diffusion/noise cross blocks are propagated.  Results at finite
field are regulators; the JSON reports whether selected scalar invariants are
stable under the declared joint-cutoff sequence and otherwise fails closed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    full_diffusion_operator_field,
    full_diffusion_operator_field_adaptive_rapidity,
)
from src.infinite_mode_fluctuating_ghd import (  # noqa: E402
    complement_invariants,
    direct_full_noise_spin_covariance,
    exact_spin_mori_resolvent,
    krylov_spin_mori_resolvent,
    krylov_spin_structure_factor,
    physical_spin_basis,
    physical_spin_invariants,
    stationary_spin_structure_factor,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fields", type=float, nargs="+", default=[0.25, 0.125])
    parser.add_argument("--string-xi-cutoff", type=float, default=3.0)
    parser.add_argument("--string-xi-buffer", type=float, default=3.0)
    parser.add_argument("--rapidity-u-extent", type=float, default=6.0)
    parser.add_argument("--rapidity-points", type=int, default=24)
    parser.add_argument(
        "--rapidity-quadrature",
        choices=("uniform-u", "adaptive-string"),
        default="uniform-u",
    )
    parser.add_argument("--scaled-rapidity-extent", type=float, default=12.0)
    parser.add_argument("--scaled-rapidity-map-alpha", type=float, default=3.0)
    parser.add_argument("--nodes-per-string", type=int, default=40)
    parser.add_argument("--kernel-theta-step", type=float, default=0.125)
    parser.add_argument("--operator-only", action="store_true")
    parser.add_argument("--wave-numbers", type=float, nargs="+", default=[0.04])
    parser.add_argument("--times", type=float, nargs="+", default=[0, 50, 100, 150, 200])
    parser.add_argument(
        "--laplace-frequencies", type=float, nargs="+", default=[0.005, 0.01, 0.02]
    )
    parser.add_argument(
        "--scaled-wave-numbers",
        type=float,
        nargs="+",
        help="hold q=k/h^2 fixed in the giant-string hydrodynamic limit",
    )
    parser.add_argument(
        "--scaled-times",
        type=float,
        nargs="+",
        help="hold tau=t*h^3 fixed in the giant-string hydrodynamic limit",
    )
    parser.add_argument(
        "--scaled-laplace-frequencies",
        type=float,
        nargs="+",
        help="hold p=z/h^3 fixed in the giant-string hydrodynamic limit",
    )
    parser.add_argument("--propagation-maximum-modes", type=int, default=1200)
    parser.add_argument("--krylov-maximum-modes", type=int, default=5000)
    parser.add_argument("--krylov-relative-tolerance", type=float, default=1.0e-10)
    parser.add_argument("--basis-maximum-modes", type=int, default=1200)
    parser.add_argument("--direct-noise-maximum-modes", type=int, default=1200)
    parser.add_argument("--direct-noise-quadrature-order", type=int, default=8)
    parser.add_argument("--relative-stability-tolerance", type=float, default=0.1)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _serializable(value):
    if isinstance(value, np.ndarray):
        if np.iscomplexobj(value):
            return {"real": value.real.tolist(), "imag": value.imag.tolist()}
        return value.tolist()
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serializable(item) for item in value]
    return value


def main() -> None:
    args = _arguments()
    if any(field <= 0.0 for field in args.fields):
        raise ValueError("all fields must be positive")
    rows = []
    for field in args.fields:
        field_waves = (
            [value * field**2 for value in args.scaled_wave_numbers]
            if args.scaled_wave_numbers is not None
            else args.wave_numbers
        )
        field_times = (
            [value / field**3 for value in args.scaled_times]
            if args.scaled_times is not None
            else args.times
        )
        field_frequencies = (
            [value * field**3 for value in args.scaled_laplace_frequencies]
            if args.scaled_laplace_frequencies is not None
            else args.laplace_frequencies
        )
        if args.rapidity_quadrature == "adaptive-string":
            raw = full_diffusion_operator_field_adaptive_rapidity(
                field,
                string_xi_cutoff=args.string_xi_cutoff,
                string_xi_buffer=args.string_xi_buffer,
                scaled_rapidity_extent=args.scaled_rapidity_extent,
                scaled_rapidity_map_alpha=args.scaled_rapidity_map_alpha,
                nodes_per_string=args.nodes_per_string,
                kernel_theta_step=args.kernel_theta_step,
                string_boundary="robin",
                operator_only=args.operator_only,
            )
        else:
            raw = full_diffusion_operator_field(
                field,
                string_xi_cutoff=args.string_xi_cutoff,
                string_xi_buffer=args.string_xi_buffer,
                rapidity_u_extent=args.rapidity_u_extent,
                rapidity_points=args.rapidity_points,
                string_boundary="robin",
            )
        mode_count = int(np.asarray(raw["velocity"]).size)
        if mode_count <= args.basis_maximum_modes:
            basis = physical_spin_basis(
                raw["diffusion_operator"],
                raw["static_covariance"],
                raw["noise_covariance"],
                raw["spin_projection"],
                velocity=raw["velocity"],
            )
            basis_status = "exact_dense_rotation"
        else:
            basis = physical_spin_invariants(
                raw["diffusion_operator"],
                raw["static_covariance"],
                raw["noise_covariance"],
                raw["spin_projection"],
                velocity=raw["velocity"],
            )
            basis_status = "exact_invariants_without_explicit_complement_basis"
        propagation = {}
        direct_noise_propagation = {}
        mori = {}
        if (
            mode_count <= args.propagation_maximum_modes
            and basis_status == "exact_dense_rotation"
        ):
            for wave in field_waves:
                propagated = stationary_spin_structure_factor(
                    basis["velocity"],
                    basis["diffusion"],
                    basis["noise_covariance"],
                    wave,
                    np.asarray(field_times),
                )
                propagation[str(wave)] = {
                    "times": propagated["times"],
                    "structure_factor_over_susceptibility": propagated[
                        "structure_factor_over_susceptibility"
                    ],
                    "stationarity_residual": propagated["stationarity_residual"],
                    "equal_time_covariance_from_initial_state": propagated.get(
                        "equal_time_covariance_from_initial_state"
                    ),
                    "equal_time_covariance_from_accumulated_full_noise": propagated.get(
                        "equal_time_covariance_from_accumulated_full_noise"
                    ),
                    "total_equal_time_covariance": propagated.get(
                        "total_equal_time_covariance"
                    ),
                }
                mori[str(wave)] = {
                    str(frequency): exact_spin_mori_resolvent(
                        basis["velocity"],
                        basis["diffusion"],
                        wave,
                        frequency,
                    )
                    for frequency in field_frequencies
                }
                if mode_count <= args.direct_noise_maximum_modes:
                    direct_noise_propagation[str(wave)] = (
                        direct_full_noise_spin_covariance(
                            raw["velocity"],
                            raw["diffusion_operator"],
                            raw["static_covariance"],
                            raw["noise_covariance"],
                            raw["spin_projection"],
                            wave,
                            np.asarray(field_times),
                            quadrature_order=args.direct_noise_quadrature_order,
                        )
                    )
            propagation_status = "exact_dense"
        elif mode_count <= args.krylov_maximum_modes:
            for wave in field_waves:
                propagated = krylov_spin_structure_factor(
                    raw["velocity"],
                    raw["diffusion_operator"],
                    raw["static_covariance"],
                    raw["noise_covariance"],
                    raw["spin_projection"],
                    wave,
                    np.asarray(field_times),
                )
                propagation[str(wave)] = {
                    "times": propagated["times"],
                    "structure_factor_over_susceptibility": propagated[
                        "structure_factor_over_susceptibility"
                    ],
                    "stationarity_residual": propagated["stationarity_residual"],
                    "method": propagated["method"],
                    "equal_time_covariance_from_initial_state": propagated[
                        "equal_time_covariance_from_initial_state"
                    ],
                    "equal_time_covariance_from_accumulated_full_noise": propagated[
                        "equal_time_covariance_from_accumulated_full_noise"
                    ],
                    "total_equal_time_covariance": propagated[
                        "total_equal_time_covariance"
                    ],
                }
                mori[str(wave)] = {
                    str(frequency): krylov_spin_mori_resolvent(
                        raw["velocity"],
                        raw["diffusion_operator"],
                        raw["static_covariance"],
                        raw["noise_covariance"],
                        raw["spin_projection"],
                        wave,
                        frequency,
                        relative_tolerance=args.krylov_relative_tolerance,
                    )
                    for frequency in field_frequencies
                }
                if mode_count <= args.direct_noise_maximum_modes:
                    direct_noise_propagation[str(wave)] = (
                        direct_full_noise_spin_covariance(
                            raw["velocity"],
                            raw["diffusion_operator"],
                            raw["static_covariance"],
                            raw["noise_covariance"],
                            raw["spin_projection"],
                            wave,
                            np.asarray(field_times),
                            quadrature_order=args.direct_noise_quadrature_order,
                        )
                    )
            propagation_status = "full_mode_krylov_without_complement_closure"
        else:
            propagation_status = (
                "omitted_above_declared_krylov_mode_limit"
            )
        rows.append(
            {
                "field": field,
                "active_strings": raw["active_strings"],
                "mode_count": mode_count,
                "susceptibility": basis["susceptibility"],
                "exact_finite_field_susceptibility": float(
                    1.0 / (4.0 * np.cosh(field) ** 2)
                ),
                "susceptibility_captured_fraction": float(
                    basis["susceptibility"]
                    / (1.0 / (4.0 * np.cosh(field) ** 2))
                ),
                "fdt_residual": basis["fdt_residual"],
                "spin_diffusion": basis["spin_diffusion"],
                "h_times_spin_diffusion": field * basis["spin_diffusion"],
                "spin_noise": basis["spin_noise"],
                "diffusion_complement": (
                    complement_invariants(basis["diffusion"])
                    if basis_status == "exact_dense_rotation"
                    else {
                        "spin_to_complement_norm": basis[
                            "spin_to_orthogonal_diffusion_norm"
                        ],
                        "complement_to_spin_norm": basis[
                            "orthogonal_to_spin_diffusion_norm"
                        ],
                        "spectrum_status": "not_formed",
                    }
                ),
                "noise_complement": (
                    complement_invariants(basis["noise_covariance"])
                    if basis_status == "exact_dense_rotation"
                    else {
                        "spin_to_complement_norm": basis[
                            "spin_orthogonal_noise_norm"
                        ],
                        "complement_to_spin_norm": basis[
                            "spin_orthogonal_noise_norm"
                        ],
                        "spectrum_status": "not_formed",
                    }
                ),
                "velocity_complement": (
                    complement_invariants(basis["velocity"])
                    if basis_status == "exact_dense_rotation"
                    else {
                        "spin_to_complement_norm": basis[
                            "spin_orthogonal_velocity_norm"
                        ],
                        "complement_to_spin_norm": basis[
                            "spin_orthogonal_velocity_norm"
                        ],
                        "spectrum_status": "not_formed",
                    }
                ),
                "propagation": propagation,
                "direct_full_noise_propagation": direct_noise_propagation,
                "exact_full_complement_mori_resolvent": mori,
                "propagation_status": propagation_status,
                "basis_status": basis_status,
                "hydrodynamic_coordinates": {
                    "wave_numbers": field_waves,
                    "times": field_times,
                    "laplace_frequencies": field_frequencies,
                    "scaled_wave_numbers_k_over_h2": (
                        args.scaled_wave_numbers
                        if args.scaled_wave_numbers is not None
                        else None
                    ),
                    "scaled_times_t_h3": (
                        args.scaled_times if args.scaled_times is not None else None
                    ),
                    "scaled_laplace_frequencies_z_over_h3": (
                        args.scaled_laplace_frequencies
                        if args.scaled_laplace_frequencies is not None
                        else None
                    ),
                },
            }
        )

    sequence = np.asarray([row["h_times_spin_diffusion"] for row in rows])
    cross_sequence = np.asarray(
        [
            row["field"]
            * row["diffusion_complement"]["spin_to_complement_norm"]
            for row in rows
        ]
    )
    if sequence.size > 1:
        relative_step = np.abs(np.diff(sequence)) / np.maximum(
            np.abs(sequence[1:]), np.finfo(float).tiny
        )
        cross_relative_step = np.abs(np.diff(cross_sequence)) / np.maximum(
            np.abs(cross_sequence[1:]), np.finfo(float).tiny
        )
        stable = bool(np.all(relative_step <= args.relative_stability_tolerance))
    else:
        relative_step = np.asarray([])
        cross_relative_step = np.asarray([])
        stable = False
    payload = {
        "schema": 1,
        "method": "full_non_diagonal_fghd_joint_zero_field_regulator",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "two_mode_or_finite_pole_closure": False,
        "regulators": {
            "fields": args.fields,
            "string_xi_cutoff": args.string_xi_cutoff,
            "string_xi_buffer": args.string_xi_buffer,
            "rapidity_u_extent": args.rapidity_u_extent,
            "rapidity_points": args.rapidity_points,
            "rapidity_quadrature": args.rapidity_quadrature,
            "scaled_rapidity_extent": args.scaled_rapidity_extent,
            "scaled_rapidity_map_alpha": args.scaled_rapidity_map_alpha,
            "nodes_per_string": args.nodes_per_string,
            "kernel_theta_step": args.kernel_theta_step,
            "operator_only": args.operator_only,
            "propagation_maximum_modes": args.propagation_maximum_modes,
            "basis_maximum_modes": args.basis_maximum_modes,
            "direct_noise_maximum_modes": args.direct_noise_maximum_modes,
            "direct_noise_quadrature_order": args.direct_noise_quadrature_order,
            "giant_string_joint_scaling": {
                "scaled_wave_numbers_k_over_h2": args.scaled_wave_numbers,
                "scaled_times_t_h3": args.scaled_times,
                "scaled_laplace_frequencies_z_over_h3": (
                    args.scaled_laplace_frequencies
                ),
            },
        },
        "rows": rows,
        "joint_limit_audit": {
            "h_times_spin_diffusion_relative_steps": relative_step,
            "h_times_spin_complement_coupling": cross_sequence,
            "h_times_spin_complement_coupling_relative_steps": cross_relative_step,
            "declared_relative_tolerance": args.relative_stability_tolerance,
            "selected_scalar_stable": stable,
            "infinite_mode_limit_accepted": False,
            "reason": (
                "one scalar regulator sequence is stable, but accepting the infinite-mode "
                "limit additionally requires independent xi/u/grid tails and nonlinear "
                "magnetic-boundary propagation"
                if stable
                else "the declared finite-field regulator sequence is not stable"
            ),
        },
    }
    text = json.dumps(_serializable(payload), indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")


if __name__ == "__main__":
    main()
