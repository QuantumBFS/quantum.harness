#!/usr/bin/env python3
"""Estimate the adaptive full-mode diffusion-vertex Mori memory matrix-free.

This is a target-free implementation certificate for the nonlinear tier.  It
uses every retained string/rapidity mode and the complete non-diagonal
diffusion operator, but never allocates ``dD[l,i,j]`` in its production path.
The auxiliary Gaussian or Rademacher samples are randomized trace vectors for
a Wick contraction, not spin-chain trajectories.  A small optional dense
check evaluates the same contraction from explicit matrices/tensors.

The output contains the complete velocity-plus-diffusion colored quadratic
force (including the cross term) and the instantaneous multiplicative-FDT-
noise contact.  Observable and Mori/UV matching terms must still be added
before the result can define a physical ``F1`` or Burgers coefficients.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.linalg import expm


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    apply_symmetric_noise_root_frechet,
    full_diffusion_noise_frechet_derivatives,
    full_diffusion_noise_directional_frechet_derivative,
    full_diffusion_operator_field_adaptive_rapidity,
    projected_diffusion_vertex_action,
    projected_noise_root_vertex_action,
    symmetric_noise_root_frechet_derivatives,
    symmetric_noise_root_frechet_setup,
)
from src.full_mode_analytic_certificates import (  # noqa: E402
    linear_ghd_generator,
    matrix_free_multiplicative_noise_observable_contact_correction,
    randomized_noise_contact_trace,
    randomized_symmetric_quadratic_wick_pair,
    randomized_velocity_diffusion_wick_pair,
)


def derive(args: argparse.Namespace) -> dict[str, object]:
    joint_scaled = args.scaled_wave_step is not None or args.scaled_times is not None
    if joint_scaled:
        if args.scaled_wave_step is None or args.scaled_times is None:
            raise ValueError(
                "scaled-wave-step and scaled-times must be supplied together"
            )
        wave_step = float(args.scaled_wave_step) * args.field**2
        output_times = np.asarray(args.scaled_times, dtype=float) / args.field**3
        scaled_contact_step = (
            args.scaled_contact_time_step
            if args.scaled_contact_time_step is not None
            else args.contact_time_step * args.field**3
        )
        contact_time_step = float(scaled_contact_step) / args.field**3
    else:
        wave_step = float(args.wave_step)
        output_times = np.asarray(args.times, dtype=float)
        contact_time_step = float(args.contact_time_step)
    if contact_time_step <= 0.0 or not np.isfinite(contact_time_step):
        raise ValueError("contact-time-step must be positive and finite")
    modes = full_diffusion_operator_field_adaptive_rapidity(
        args.field,
        string_xi_cutoff=args.string_xi_cutoff,
        string_xi_buffer=args.string_xi_buffer,
        scaled_rapidity_extent=args.scaled_rapidity_extent,
        scaled_rapidity_map_alpha=args.scaled_rapidity_map_alpha,
        nodes_per_string=args.nodes_per_string,
        kernel_theta_step=args.kernel_theta_step,
        string_boundary="robin",
    )
    velocity = np.asarray(modes["velocity"])
    diffusion = np.asarray(modes["diffusion_operator"])
    covariance = np.asarray(modes["static_covariance"])
    projection = np.asarray(modes["spin_projection"])
    velocity_action_matrix = projection[:, None] * np.asarray(
        modes["velocity_vertex"]
    )
    spin_hessian = np.asarray(modes["spin_hessian"])
    waves = wave_step * (
        np.fft.fftfreq(args.fourier_points) * args.fourier_points
    )
    external_index = 1
    external_wave = float(waves[external_index])
    if args.lattice_wave_number:
        symbol = lambda wave: 2.0 * np.sin(0.5 * wave)
    else:
        symbol = lambda wave: wave
    khat = float(symbol(external_wave))
    fourier_normalization = np.sqrt(float(args.fourier_points))
    cell_length = 2.0 * np.pi / (args.fourier_points * wave_step)
    fourier_covariance = covariance / cell_length
    susceptibility = float(
        np.real(projection @ fourier_covariance @ projection)
    )
    noise_covariance = np.asarray(modes["noise_covariance"])
    noise_root_setup = symmetric_noise_root_frechet_setup(noise_covariance)

    dense_vertex = None
    dense_projected_noise = None
    if args.dense_check:
        derivatives = full_diffusion_noise_frechet_derivatives(modes)
        dense_vertex = np.einsum(
            "a,laj->jl", projection, derivatives["diffusion_derivative"]
        )
        dense_root = symmetric_noise_root_frechet_derivatives(
            noise_covariance,
            derivatives["noise_covariance_derivative"],
        )
        dense_projected_noise = np.einsum(
            "a,lar->lr",
            projection,
            dense_root["noise_root_derivative"],
        )

    def action(vector: np.ndarray) -> np.ndarray:
        return projected_diffusion_vertex_action(modes, projection, vector)

    def velocity_action(vector: np.ndarray) -> np.ndarray:
        return velocity_action_matrix @ vector

    def observable_action(vector: np.ndarray) -> np.ndarray:
        return spin_hessian @ vector

    noise_nullspace_residuals: list[float] = []

    def noise_action(vector: np.ndarray) -> np.ndarray:
        applied = projected_noise_root_vertex_action(
            modes, projection, vector, noise_root_setup
        )
        noise_nullspace_residuals.append(
            float(applied["relative_nullspace_residual"])
        )
        return np.asarray(applied["projected_noise_root_vertex_action"])

    randomized_noise = randomized_noise_contact_trace(
        noise_action,
        fourier_covariance,
        samples=args.samples,
        seed=args.seed + 4_826_311,
        trace_distribution=args.trace_distribution,
    )
    noise_normalization = cell_length * susceptibility
    noise_contact = float(randomized_noise["estimate"]) / noise_normalization
    noise_contact_error = (
        float(randomized_noise["standard_error"]) / noise_normalization
    )
    dense_noise_contact = None
    if dense_projected_noise is not None:
        dense_noise_contact = float(
            np.einsum(
                "lr,lm,mr->",
                dense_projected_noise,
                fourier_covariance,
                dense_projected_noise.conj(),
            ).real
            / noise_normalization
        )

    mixed_contact_residuals: list[float] = []

    def noise_root_directional_action(vector: np.ndarray) -> np.ndarray:
        q_derivative = full_diffusion_noise_directional_frechet_derivative(
            modes, vector
        )["noise_covariance_directional_derivative"]
        applied = apply_symmetric_noise_root_frechet(
            noise_root_setup, q_derivative
        )
        mixed_contact_residuals.append(
            float(applied["relative_nullspace_residual"])
        )
        return np.asarray(applied["noise_root_directional_derivative"])

    contact_indices = np.rint(
        output_times / contact_time_step
    ).astype(int)
    if not np.allclose(
        output_times,
        contact_indices * contact_time_step,
        rtol=1.0e-10,
        atol=1.0e-12,
    ):
        raise ValueError("all output times must be multiples of contact-time-step")
    contact_grid = contact_time_step * np.arange(
        max(1, int(np.max(contact_indices))) + 1
    )
    mixed_contact = matrix_free_multiplicative_noise_observable_contact_correction(
        waves,
        external_index,
        velocity,
        diffusion,
        covariance,
        np.asarray(noise_root_setup["noise_root"]),
        noise_root_directional_action,
        projection,
        spin_hessian,
        contact_grid,
        output_times,
        spatial_cell_length=cell_length,
        lattice_wave_number=symbol if args.lattice_wave_number else None,
    )

    rows = []
    for time_index, time in enumerate(output_times):
        estimate_sums = {
            name: 0.0j for name in ("velocity", "diffusion", "cross", "total")
        }
        variance_sums = {
            name: 0.0 for name in ("velocity", "diffusion", "cross", "total")
        }
        dense_sums = {
            name: 0.0j for name in ("velocity", "diffusion", "cross", "total")
        }
        observable_estimate_sum = 0.0j
        observable_variance_sum = 0.0
        observable_dense_sum = 0.0j
        internal_rows = []
        for p_index, p_wave in enumerate(waves):
            q_index = (external_index - p_index) % args.fourier_points
            q_wave = float(waves[q_index])
            p_symbol = float(symbol(float(p_wave)))
            q_symbol = float(symbol(q_wave))
            generator_p = linear_ghd_generator(
                float(p_wave),
                velocity,
                diffusion,
                lattice_wave_number=symbol if args.lattice_wave_number else None,
            )
            generator_q = linear_ghd_generator(
                q_wave,
                velocity,
                diffusion,
                lattice_wave_number=symbol if args.lattice_wave_number else None,
            )
            propagator_p = expm(float(time) * generator_p)
            propagator_q = expm(float(time) * generator_q)
            randomized = randomized_velocity_diffusion_wick_pair(
                velocity_action,
                action,
                fourier_covariance,
                propagator_p,
                propagator_q,
                p_symbol,
                q_symbol,
                fourier_normalization=fourier_normalization,
                samples=args.samples,
                # Reuse the same trace vectors at every time for a fixed
                # internal wave.  This common-random-number construction does
                # not change a marginal estimator but strongly reduces noise
                # in time differences and Laplace quadrature.
                seed=args.seed + 9176 * p_index,
                trace_distribution=args.trace_distribution,
            )
            randomized_observable = randomized_symmetric_quadratic_wick_pair(
                observable_action,
                fourier_covariance,
                propagator_p,
                propagator_q,
                fourier_normalization=fourier_normalization,
                samples=args.samples,
                seed=args.seed + 9176 * p_index + 2_413_177,
                trace_distribution=args.trace_distribution,
            )
            estimates = {
                name: complex(value)
                for name, value in randomized["estimates"].items()
            }
            standard_errors = {
                name: float(value)
                for name, value in randomized[
                    "standard_error_complex_norms"
                ].items()
            }
            for name in estimate_sums:
                estimate_sums[name] += estimates[name]
                variance_sums[name] += standard_errors[name] ** 2
            observable_estimate = complex(randomized_observable["estimate"])
            observable_standard_error = float(
                randomized_observable["standard_error_complex_norm"]
            )
            observable_estimate_sum += observable_estimate
            observable_variance_sum += observable_standard_error**2
            dense_values = None
            dense_observable = None
            if dense_vertex is not None:
                gamma_velocity = -0.5j / fourier_normalization * (
                    q_symbol * velocity_action_matrix.T
                    + p_symbol * velocity_action_matrix
                )
                gamma_diffusion = -0.25 / fourier_normalization * (
                    q_symbol**2 * dense_vertex.T
                    + p_symbol**2 * dense_vertex
                )
                s_p = propagator_p @ fourier_covariance
                s_q = propagator_q @ fourier_covariance

                def dense_wick(gamma: np.ndarray) -> complex:
                    return complex(
                        2.0
                        * np.sum(
                            (s_p.T @ gamma) * (gamma.conj() @ s_q.T)
                        )
                    )

                dense_velocity = dense_wick(gamma_velocity)
                dense_diffusion = dense_wick(gamma_diffusion)
                dense_total = dense_wick(gamma_velocity + gamma_diffusion)
                dense_values = {
                    "velocity": dense_velocity,
                    "diffusion": dense_diffusion,
                    "cross": dense_total - dense_velocity - dense_diffusion,
                    "total": dense_total,
                }
                for name in dense_sums:
                    dense_sums[name] += dense_values[name]
                gamma_observable = 0.5 * spin_hessian / fourier_normalization
                dense_observable = dense_wick(gamma_observable)
                observable_dense_sum += dense_observable
            internal_rows.append(
                {
                    "p_wave": float(p_wave),
                    "q_wave": q_wave,
                    "estimates": {
                        name: [value.real, value.imag]
                        for name, value in estimates.items()
                    },
                    "standard_error_complex_norms": standard_errors,
                    "quadratic_observable_estimate": [
                        observable_estimate.real,
                        observable_estimate.imag,
                    ],
                    "quadratic_observable_standard_error_complex_norm": (
                        observable_standard_error
                    ),
                    "quadratic_observable_dense_check": (
                        None
                        if dense_observable is None
                        else [dense_observable.real, dense_observable.imag]
                    ),
                    "dense_checks": (
                        None
                        if dense_values is None
                        else {
                            name: [value.real, value.imag]
                            for name, value in dense_values.items()
                        }
                    ),
                }
            )
        normalization = susceptibility * khat**2
        continuity_estimates = {
            name: value / normalization
            for name, value in estimate_sums.items()
        }
        total_standard_errors = {
            name: np.sqrt(value) / normalization
            for name, value in variance_sums.items()
        }
        continuity_dense = None
        if dense_vertex is not None:
            continuity_dense = {
                name: value / normalization for name, value in dense_sums.items()
            }
        observable_estimate_normalized = observable_estimate_sum / susceptibility
        observable_standard_error_normalized = (
            np.sqrt(observable_variance_sum) / susceptibility
        )
        observable_dense_normalized = (
            None
            if dense_vertex is None
            else observable_dense_sum / susceptibility
        )
        rows.append(
            {
                "time": float(time),
                "continuity_memory_estimates": {
                    name: [value.real, value.imag]
                    for name, value in continuity_estimates.items()
                },
                "standard_error_complex_norms": total_standard_errors,
                "dense_checks": (
                    None
                    if continuity_dense is None
                    else {
                        name: [value.real, value.imag]
                        for name, value in continuity_dense.items()
                    }
                ),
                "absolute_dense_differences": (
                    None
                    if continuity_dense is None
                    else {
                        name: float(
                            abs(continuity_estimates[name] - continuity_dense[name])
                        )
                        for name in continuity_estimates
                    }
                ),
                "quadratic_spin_observable_structure_correction": {
                    "estimate": [
                        observable_estimate_normalized.real,
                        observable_estimate_normalized.imag,
                    ],
                    "standard_error_complex_norm": float(
                        observable_standard_error_normalized
                    ),
                    "dense_check": (
                        None
                        if observable_dense_normalized is None
                        else [
                            observable_dense_normalized.real,
                            observable_dense_normalized.imag,
                        ]
                    ),
                    "absolute_dense_difference": (
                        None
                        if observable_dense_normalized is None
                        else float(
                            abs(
                                observable_estimate_normalized
                                - observable_dense_normalized
                            )
                        )
                    ),
                },
                "internal_wave_rows": internal_rows,
            }
        )

    covariance_diagonal = np.diag(covariance)
    captured = float(projection @ covariance @ projection)
    exact = float(1.0 / (4.0 * np.cosh(args.field) ** 2))
    return {
        "schema": 1,
        "method": "matrix_free_adaptive_full_mode_velocity_diffusion_noise",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "randomized_trace_not_physical_sampling": True,
        "regulator": {
            "field": args.field,
            "active_strings": int(modes["active_strings"]),
            "mode_count": int(modes["mode_count"]),
            "nodes_per_string": args.nodes_per_string,
            "string_xi_cutoff": args.string_xi_cutoff,
            "scaled_rapidity_extent": args.scaled_rapidity_extent,
            "fourier_points": args.fourier_points,
            "samples_per_internal_wave": args.samples,
            "trace_distribution": args.trace_distribution,
            "dense_check": args.dense_check,
        },
        "hydrodynamic_coordinates": {
            "joint_scaled_input": joint_scaled,
            "physical_wave_step": wave_step,
            "physical_times": output_times.tolist(),
            "physical_contact_time_step": contact_time_step,
            "scaled_wave_step_q_equals_k_over_h2": (
                None if not joint_scaled else float(args.scaled_wave_step)
            ),
            "scaled_times_tau_equals_t_h3": (
                None
                if not joint_scaled
                else [float(value) for value in args.scaled_times]
            ),
            "scaled_contact_time_step": (
                None if not joint_scaled else float(scaled_contact_step)
            ),
        },
        "static_susceptibility_captured_fraction": captured / exact,
        "fdt_residual": float(
            np.linalg.norm(
                np.asarray(modes["noise_covariance"])
                - 0.5
                * (
                    diffusion * covariance_diagonal[None, :]
                    + covariance_diagonal[:, None] * diffusion.T
                )
            )
            / max(
                np.linalg.norm(np.asarray(modes["noise_covariance"])),
                np.finfo(float).tiny,
            )
        ),
        "multiplicative_noise_delta_memory": {
            "estimate": noise_contact,
            "standard_error": noise_contact_error,
            "dense_check": dense_noise_contact,
            "absolute_dense_difference": (
                None
                if dense_noise_contact is None
                else abs(noise_contact - dense_noise_contact)
            ),
            "maximum_root_sylvester_nullspace_residual": (
                None
                if not noise_nullspace_residuals
                else max(noise_nullspace_residuals)
            ),
            "samples": args.samples,
            "trace_distribution": args.trace_distribution,
            "interpretation": "coefficient multiplying delta(t) before microscopic Mori/UV contact matching",
        },
        "multiplicative_noise_quadratic_observable_contact": {
            "times": [float(value) for value in output_times],
            "right_leg": [
                [complex(value).real, complex(value).imag]
                for value in mixed_contact["right_observable_leg_contact"]
            ],
            "left_leg": [
                [complex(value).real, complex(value).imag]
                for value in mixed_contact["left_observable_leg_contact"]
            ],
            "total": [
                [complex(value).real, complex(value).imag]
                for value in mixed_contact[
                    "total_multiplicative_noise_H_structure_correction"
                ]
            ],
            "stochastic_convention": mixed_contact["stochastic_convention"],
            "root_directional_action_calls": mixed_contact[
                "noise_root_directional_action_calls"
            ],
            "maximum_root_sylvester_nullspace_residual": (
                None
                if not mixed_contact_residuals
                else max(mixed_contact_residuals)
            ),
            "rank_three_noise_root_derivative_stored": False,
            "microscopic_convention_matching_complete": False,
        },
        "rows": rows,
        "scope": {
            "full_non_diagonal_diffusion_vertex": True,
            "rank_three_derivative_tensor_in_production_path": False,
            "velocity_vertex_included": True,
            "velocity_diffusion_cross_included": True,
            "multiplicative_noise_contact_included": True,
            "quadratic_observable_included": True,
            "multiplicative_noise_observable_contact_included": True,
            "microscopic_mori_contact_matched": False,
            "physical_F1_certified": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field", type=float, default=0.25)
    parser.add_argument("--string-xi-cutoff", type=float, default=0.5)
    parser.add_argument("--string-xi-buffer", type=float, default=0.5)
    parser.add_argument("--scaled-rapidity-extent", type=float, default=2.0)
    parser.add_argument("--scaled-rapidity-map-alpha", type=float, default=2.0)
    parser.add_argument("--nodes-per-string", type=int, default=8)
    parser.add_argument("--kernel-theta-step", type=float, default=0.25)
    parser.add_argument("--fourier-points", type=int, default=4)
    parser.add_argument("--wave-step", type=float, default=0.1)
    parser.add_argument("--times", type=float, nargs="+", default=[0.0, 1.0])
    parser.add_argument("--contact-time-step", type=float, default=0.1)
    parser.add_argument(
        "--scaled-wave-step",
        type=float,
        help="joint giant-string q step; sets physical wave-step=q-step*h^2",
    )
    parser.add_argument(
        "--scaled-times",
        type=float,
        nargs="+",
        help="joint giant-string tau=t*h^3 output times",
    )
    parser.add_argument(
        "--scaled-contact-time-step",
        type=float,
        help="joint giant-string contact grid step Delta-tau=Delta-t*h^3",
    )
    parser.add_argument("--samples", type=int, default=512)
    parser.add_argument("--seed", type=int, default=265)
    parser.add_argument(
        "--trace-distribution",
        choices=["gaussian", "rademacher"],
        default="rademacher",
    )
    parser.add_argument("--lattice-wave-number", action="store_true")
    parser.add_argument("--dense-check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = derive(args)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
