#!/usr/bin/env python3
"""Propagate complete retained-mode FDT and iterated matrix Mori updates.

The calculation keeps every retained string/rapidity component, the complete
non-diagonal GHD diffusion matrix, and its full FDT noise covariance.  The
quadratic velocity and diffusion forces are contracted into an
``N_mode x N_mode`` memory matrix without first projecting onto spin.  That
matrix is then propagated by a matrix Volterra equation and only the final
two-time covariance is projected onto physical magnetization.

At finite field/string/rapidity/Fourier cutoffs this is a reproducible
calculation.  The first iteration uses linear internal propagators; later
iterations rebuild every nonzero-momentum memory from the previous complete
matrix response.  Iteration convergence and the joint regulator limit remain
separate requirements before this can represent nonlinear infinite-mode
fluctuating GHD.
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
    full_diffusion_noise_directional_frechet_derivative,
    full_diffusion_operator_field_adaptive_rapidity,
    symmetric_noise_root_frechet_setup,
)
from src.full_mode_analytic_certificates import (  # noqa: E402
    exact_ou_covariance,
    full_fdt_noise_covariance,
    linear_ghd_generator,
    propagate_matrix_mori_volterra,
    randomized_full_vector_multiplicative_noise_contact,
    randomized_full_vector_velocity_diffusion_wick_pair,
    randomized_noise_contact_trace,
    randomized_velocity_diffusion_wick_pair,
)


def _complex_pairs(values: np.ndarray) -> list[list[float]]:
    array = np.asarray(values)
    return [[float(value.real), float(value.imag)] for value in array]


def derive(args: argparse.Namespace) -> dict[str, object]:
    times = np.asarray(args.times, dtype=float)
    if times.size < 2 or times[0] != 0.0:
        raise ValueError("times must begin at zero and contain at least two points")
    if not np.allclose(np.diff(times), np.diff(times)[0]):
        raise ValueError("times must be uniform for matrix Volterra propagation")
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
    velocity_vertex = np.asarray(modes["velocity_vertex"])
    projection = np.asarray(modes["spin_projection"])
    modes_count = covariance.shape[0]
    waves = args.wave_step * (
        np.fft.fftfreq(args.fourier_points) * args.fourier_points
    )
    external_index = 1
    external_wave = float(waves[external_index])
    symbol = (
        (lambda wave: 2.0 * np.sin(0.5 * wave))
        if args.lattice_wave_number
        else (lambda wave: wave)
    )
    khat = float(symbol(external_wave))
    cell_length = 2.0 * np.pi / (args.fourier_points * args.wave_step)
    fourier_covariance = covariance / cell_length
    susceptibility = float(projection @ fourier_covariance @ projection)
    fourier_normalization = np.sqrt(float(args.fourier_points))

    noise_root_setup = symmetric_noise_root_frechet_setup(
        np.asarray(modes["noise_covariance"])
    )

    def directional(vector: np.ndarray) -> np.ndarray:
        return np.asarray(
            full_diffusion_noise_directional_frechet_derivative(
                modes, vector
            )["diffusion_directional_derivative"]
        )

    def noise_root_directional(vector: np.ndarray) -> np.ndarray:
        noise_direction = full_diffusion_noise_directional_frechet_derivative(
            modes, vector
        )["noise_covariance_directional_derivative"]
        return np.asarray(
            apply_symmetric_noise_root_frechet(
                noise_root_setup, noise_direction
            )["noise_root_directional_derivative"]
        )

    noise_contact = randomized_full_vector_multiplicative_noise_contact(
        noise_root_directional,
        fourier_covariance,
        samples=args.samples,
        seed=args.seed + 4_826_311,
        trace_distribution=args.trace_distribution,
    )
    scalar_noise_contact = randomized_noise_contact_trace(
        lambda vector: noise_root_directional(vector).T @ projection,
        fourier_covariance,
        samples=args.samples,
        seed=args.seed + 4_826_311,
        trace_distribution=args.trace_distribution,
    )

    generators = np.asarray(
        [
            linear_ghd_generator(
                float(wave),
                velocity,
                diffusion,
                lattice_wave_number=(
                    symbol if args.lattice_wave_number else None
                ),
            )
            for wave in waves
        ]
    )
    linear_responses = np.asarray(
        [
            [expm(float(time) * generator) for time in times]
            for generator in generators
        ]
    )
    responses = linear_responses.copy()
    dyson_iterations = int(getattr(args, "dyson_iterations", 1))
    relaxation = float(getattr(args, "dyson_relaxation", 1.0))
    if dyson_iterations < 1:
        raise ValueError("dyson_iterations must be at least one")
    if not 0.0 < relaxation <= 1.0:
        raise ValueError("dyson_relaxation must lie in (0,1]")
    iteration_rows: list[dict[str, object]] = []
    force_memories: dict[str, np.ndarray] | None = None
    error_squares: dict[str, np.ndarray] | None = None
    scalar_projection_memories: dict[str, np.ndarray] | None = None
    scalar_projection_error_squares: dict[str, np.ndarray] | None = None

    for iteration in range(dyson_iterations):
        input_responses = responses
        updated_responses = input_responses.copy()
        target_force_memories = None
        target_error_squares = None
        target_scalar_memories = None
        target_scalar_error_squares = None
        for k_index in range(1, args.fourier_points):
            memories = {
                name: np.zeros(
                    (times.size, modes_count, modes_count), dtype=complex
                )
                for name in ("velocity", "diffusion", "cross", "total")
            }
            errors = {
                name: np.zeros(times.size, dtype=float) for name in memories
            }
            scalar_memories = {
                name: np.zeros(times.size, dtype=complex) for name in memories
            }
            scalar_errors = {
                name: np.zeros(times.size, dtype=float) for name in memories
            }
            for time_index, _time in enumerate(times):
                for p_index, p_wave in enumerate(waves):
                    q_index = (k_index - p_index) % args.fourier_points
                    q_wave = float(waves[q_index])
                    random_seed = (
                        args.seed + 1_000_003 * k_index + 9176 * p_index
                    )
                    contraction = (
                        randomized_full_vector_velocity_diffusion_wick_pair(
                            velocity_vertex,
                            directional,
                            fourier_covariance,
                            input_responses[p_index, time_index],
                            input_responses[q_index, time_index],
                            float(symbol(float(p_wave))),
                            float(symbol(q_wave)),
                            fourier_normalization=fourier_normalization,
                            samples=args.samples,
                            seed=random_seed,
                            trace_distribution=args.trace_distribution,
                        )
                    )
                    for name in memories:
                        memories[name][time_index] += contraction[
                            "matrix_estimates"
                        ][name]
                        errors[name][time_index] += float(
                            contraction["frobenius_standard_errors"][name]
                        ) ** 2
                    if k_index == external_index:
                        scalar_contraction = randomized_velocity_diffusion_wick_pair(
                            lambda vector: (
                                projection[:, None] * velocity_vertex
                            )
                            @ vector,
                            lambda vector: directional(vector).T @ projection,
                            fourier_covariance,
                            input_responses[p_index, time_index],
                            input_responses[q_index, time_index],
                            float(symbol(float(p_wave))),
                            float(symbol(q_wave)),
                            fourier_normalization=fourier_normalization,
                            samples=args.samples,
                            seed=random_seed,
                            trace_distribution=args.trace_distribution,
                        )
                        for name in memories:
                            scalar_memories[name][time_index] += complex(
                                scalar_contraction["estimates"][name]
                            )
                            scalar_errors[name][time_index] += float(
                                scalar_contraction[
                                    "standard_error_complex_norms"
                                ][name]
                            ) ** 2
            propagated = propagate_matrix_mori_volterra(
                generators[k_index],
                fourier_covariance,
                times,
                memories["total"],
            )["response"]
            updated_responses[k_index] = (
                (1.0 - relaxation) * input_responses[k_index]
                + relaxation * propagated
            )
            if k_index == external_index:
                target_force_memories = memories
                target_error_squares = errors
                target_scalar_memories = scalar_memories
                target_scalar_error_squares = scalar_errors

        # Exact conservation: the k=0 occupation vector does not evolve.
        updated_responses[0] = np.eye(modes_count, dtype=complex)[None, :, :]
        # Enforce the exact real-field relation G(-k,t)=G(k,t)^*.  Independent
        # randomized traces at the paired Fourier indices otherwise leave an
        # avoidable anti-Hermitian sampling residue in the physical profile.
        for positive_index in range(1, (args.fourier_points + 1) // 2):
            negative_index = (-positive_index) % args.fourier_points
            paired = 0.5 * (
                updated_responses[positive_index]
                + updated_responses[negative_index].conj()
            )
            updated_responses[positive_index] = paired
            updated_responses[negative_index] = paired.conj()
        differences = np.linalg.norm(
            updated_responses - input_responses, axis=(2, 3)
        )
        denominators = np.maximum(
            np.linalg.norm(updated_responses, axis=(2, 3)),
            np.finfo(float).tiny,
        )
        maximum_relative_change = float(np.max(differences / denominators))
        target_structure = np.einsum(
            "a,tab,b->t",
            projection,
            updated_responses[external_index] @ fourier_covariance,
            projection,
        ) / susceptibility
        iteration_rows.append(
            {
                "iteration": iteration + 1,
                "maximum_relative_response_change": maximum_relative_change,
                "external_structure_factor_over_chi": _complex_pairs(
                    target_structure
                ),
            }
        )
        responses = updated_responses
        force_memories = target_force_memories
        error_squares = target_error_squares
        scalar_projection_memories = target_scalar_memories
        scalar_projection_error_squares = target_scalar_error_squares

    assert force_memories is not None
    assert error_squares is not None
    assert scalar_projection_memories is not None
    assert scalar_projection_error_squares is not None

    external_generator = linear_ghd_generator(
        external_wave,
        velocity,
        diffusion,
        lattice_wave_number=symbol if args.lattice_wave_number else None,
    )
    fdt = full_fdt_noise_covariance(external_generator, fourier_covariance)
    expected_noise = (
        khat**2 * np.asarray(modes["noise_covariance"]) / cell_length
    )
    fdt_operator_residual = float(
        np.linalg.norm(fdt["noise_covariance"] - expected_noise)
        / max(np.linalg.norm(expected_noise), np.finfo(float).tiny)
    )
    stationary = exact_ou_covariance(
        external_generator,
        fourier_covariance,
        fourier_covariance,
        times,
    )
    linear_response = linear_responses[external_index]
    linear_structure = np.einsum(
        "a,tab,b->t", projection, linear_response @ fourier_covariance, projection
    ) / susceptibility
    dressed_structure = np.einsum(
        "a,tab,b->t",
        projection,
        responses[external_index] @ fourier_covariance,
        projection,
    ) / susceptibility
    all_dressed_structures = np.einsum(
        "a,ktab,b->kt",
        projection,
        responses @ fourier_covariance,
        projection,
    ) / susceptibility
    projected_memory = np.einsum(
        "a,tab,b->t", projection, force_memories["total"], projection
    ) / (susceptibility * khat**2)
    projected_error = np.sqrt(scalar_projection_error_squares["total"]) / (
        susceptibility * khat**2
    )
    scalar_projected_memory = scalar_projection_memories["total"] / (
        susceptibility * khat**2
    )
    projection_identity_residual = float(
        np.max(np.abs(projected_memory - scalar_projected_memory))
    )
    noise_contact_matrix = np.asarray(noise_contact["matrix_estimate"])
    projected_noise_contact = complex(
        projection @ noise_contact_matrix @ projection
        / (cell_length * susceptibility)
    )
    scalar_projected_noise_contact = float(
        scalar_noise_contact["estimate"] / (cell_length * susceptibility)
    )

    covariance_diagonal = np.diag(covariance)
    captured = float(projection @ covariance @ projection)
    exact_susceptibility = float(1.0 / (4.0 * np.cosh(args.field) ** 2))
    off_diagonal_diffusion = diffusion - np.diag(np.diag(diffusion))
    noise = np.asarray(fdt["noise_covariance"])
    off_diagonal_noise = noise - np.diag(np.diag(noise))
    convergence_tolerance = float(
        getattr(args, "dyson_convergence_tolerance", 1.0e-3)
    )
    iteration_converged = bool(
        dyson_iterations >= 2
        and iteration_rows[-1]["maximum_relative_response_change"]
        <= convergence_tolerance
    )
    return {
        "schema": 1,
        "method": "full_mode_matrix_fdt_iterated_dyson",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "regulator": {
            "field": args.field,
            "active_strings": int(modes["active_strings"]),
            "mode_count": int(modes_count),
            "nodes_per_string": args.nodes_per_string,
            "string_xi_cutoff": args.string_xi_cutoff,
            "fourier_points": args.fourier_points,
            "wave_step": args.wave_step,
            "external_wave": external_wave,
            "samples_per_internal_wave": args.samples,
            "dyson_iterations": dyson_iterations,
            "dyson_relaxation": relaxation,
        },
        "times": times.tolist(),
        "matrix_dyson_iteration": {
            "rows": iteration_rows,
            "final_maximum_relative_response_change": iteration_rows[-1][
                "maximum_relative_response_change"
            ],
            "convergence_tolerance": convergence_tolerance,
            "converged": iteration_converged,
            "all_nonzero_fourier_momenta_updated_each_iteration": True,
            "zero_mode_conservation_residual": float(
                np.linalg.norm(
                    responses[0]
                    - np.eye(modes_count, dtype=complex)[None, :, :]
                )
            ),
        },
        "static_susceptibility_captured_fraction": captured / exact_susceptibility,
        "full_operator_certificates": {
            "diffusion_off_diagonal_frobenius_fraction": float(
                np.linalg.norm(off_diagonal_diffusion)
                / max(np.linalg.norm(diffusion), np.finfo(float).tiny)
            ),
            "noise_off_diagonal_frobenius_fraction": float(
                np.linalg.norm(off_diagonal_noise)
                / max(np.linalg.norm(noise), np.finfo(float).tiny)
            ),
            "fdt_noise_minimum_eigenvalue": fdt["minimum_eigenvalue"],
            "fdt_noise_positive_semidefinite": fdt[
                "positive_semidefinite_within_roundoff"
            ],
            "fdt_lyapunov_residual": fdt["relative_lyapunov_residual"],
            "fdt_operator_identity_residual": fdt_operator_residual,
            "stationary_covariance_maximum_residual": float(
                np.max(
                    np.linalg.norm(
                        stationary["covariances"]
                        - fourier_covariance[None, :, :],
                        axis=(1, 2),
                    )
                )
            ),
        },
        "matrix_memory": {
            "total_frobenius_norms": [
                float(np.linalg.norm(matrix))
                for matrix in force_memories["total"]
            ],
            "velocity_frobenius_norms": [
                float(np.linalg.norm(matrix))
                for matrix in force_memories["velocity"]
            ],
            "diffusion_frobenius_norms": [
                float(np.linalg.norm(matrix))
                for matrix in force_memories["diffusion"]
            ],
            "cross_frobenius_norms": [
                float(np.linalg.norm(matrix))
                for matrix in force_memories["cross"]
            ],
            "total_frobenius_standard_errors": np.sqrt(
                error_squares["total"]
            ).tolist(),
            "physical_continuity_projection": _complex_pairs(projected_memory),
            "direct_scalar_continuity_projection": _complex_pairs(
                scalar_projected_memory
            ),
            "matrix_to_scalar_projection_identity_maximum_residual": (
                projection_identity_residual
            ),
            "physical_projection_standard_errors": projected_error.tolist(),
        },
        "multiplicative_noise_contact": {
            "bare_continuity_matrix_frobenius_norm": float(
                np.linalg.norm(noise_contact_matrix / cell_length)
            ),
            "bare_physical_continuity_projection": [
                projected_noise_contact.real,
                projected_noise_contact.imag,
            ],
            "direct_scalar_projection": scalar_projected_noise_contact,
            "matrix_to_scalar_projection_identity_residual": float(
                abs(projected_noise_contact - scalar_projected_noise_contact)
            ),
            "frobenius_standard_error_before_cell_normalization": float(
                noise_contact["frobenius_standard_error"]
            ),
            "inserted_into_matrix_volterra_generator": False,
            "reason_not_inserted": (
                "the bare hydrodynamic delta contact must first be matched to "
                "the regular microscopic Mori short-time expansion"
            ),
        },
        "structure_factor_over_chi": {
            "linear_full_mode": _complex_pairs(linear_structure),
            "iterated_full_matrix_dyson": _complex_pairs(dressed_structure),
        },
        "all_fourier_structure_factors_over_chi": {
            "waves": waves.tolist(),
            "scaled_waves_q_equals_k_over_h2": (
                waves / args.field**2
            ).tolist(),
            "values_by_wave_then_time": [
                _complex_pairs(row) for row in all_dressed_structures
            ],
            "maximum_conjugate_pair_residual": float(
                max(
                    np.max(
                        np.abs(
                            all_dressed_structures[index]
                            - all_dressed_structures[
                                (-index) % args.fourier_points
                            ].conj()
                        )
                    )
                    for index in range(args.fourier_points)
                    if not (
                        args.fourier_points % 2 == 0
                        and index == args.fourier_points // 2
                    )
                )
            ),
        },
        "scope": {
            "all_retained_modes_propagated_before_spin_projection": True,
            "full_non_diagonal_diffusion_propagated": True,
            "full_fdt_noise_covariance_propagated": True,
            "background_fdt_noise_is_additive": True,
            "multiplicative_noise_vertex_contracted_as_full_matrix": True,
            "multiplicative_noise_contact_uv_matched": False,
            "quadratic_velocity_vertex_retained": True,
            "quadratic_diffusion_vertex_retained": True,
            "velocity_diffusion_cross_retained": True,
            "rank_three_diffusion_vertex_stored": False,
            "linear_internal_propagators_in_first_iteration": True,
            "dressed_internal_propagators_after_first_iteration": bool(
                dyson_iterations > 1
            ),
            "finite_regulator_matrix_fixed_point_reached": iteration_converged,
            "self_consistent_matrix_resummation_complete": False,
            "joint_zero_field_infinite_string_limit_complete": False,
            "physical_a_or_D_identified": False,
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
    parser.add_argument("--times", type=float, nargs="+", default=[0.0, 0.25, 0.5])
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--dyson-iterations", type=int, default=1)
    parser.add_argument("--dyson-relaxation", type=float, default=1.0)
    parser.add_argument(
        "--dyson-convergence-tolerance", type=float, default=1.0e-3
    )
    parser.add_argument("--seed", type=int, default=265)
    parser.add_argument(
        "--trace-distribution",
        choices=["gaussian", "rademacher"],
        default="rademacher",
    )
    parser.add_argument("--lattice-wave-number", action="store_true")
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
