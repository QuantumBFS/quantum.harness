#!/usr/bin/env python3
"""Self-consistent full-mode GHD using low-rank Mori response actions.

The auxiliary Wick vectors required by every internal momentum contraction are
fixed once.  For each Fourier momentum the code propagates only ``G_k(t) X_k``
for that source pool and the physical source ``C g``.  Quadratic-force
covariances remain sums of rank-one outer products and are applied by the
low-rank Volterra solver.  No dense nonlinear memory or dense response matrix
is stored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.linalg import expm, hadamard


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    full_diffusion_noise_directional_frechet_derivative,
    full_diffusion_operator_field_adaptive_rapidity,
)
from src.full_mode_analytic_certificates import (  # noqa: E402
    full_fdt_noise_covariance,
    linear_ghd_generator,
    propagate_low_rank_matrix_mori_actions,
)


def _pairs(values: np.ndarray) -> list[list[float]]:
    return [[float(value.real), float(value.imag)] for value in values]


def _covariance_root(covariance: np.ndarray) -> np.ndarray:
    hermitian = 0.5 * (covariance + covariance.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    if float(np.min(eigenvalues)) < -1.0e-11 * scale:
        raise ValueError("covariance must be positive semidefinite")
    return (eigenvectors * np.sqrt(np.maximum(eigenvalues, 0.0))) @ (
        eigenvectors.conj().T
    )


def _trace_pair(
    root: np.ndarray, samples: int, seed: int, distribution: str
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    shape = (root.shape[0], samples)
    if distribution == "gaussian":
        x = rng.normal(size=shape)
        y = rng.normal(size=shape)
    elif distribution == "orthogonal_gaussian":
        # A Haar orthonormal frame scaled by sqrt(N) preserves
        # E[x_j x_j^T]=I for every column while removing within-batch overlap.
        # This is the without-replacement analogue of Gaussian Hutchinson
        # sampling and substantially reduces trace variance at fixed rank.
        x, _ = np.linalg.qr(rng.normal(size=shape), mode="reduced")
        y, _ = np.linalg.qr(rng.normal(size=shape), mode="reduced")
        x *= np.sqrt(float(root.shape[0]))
        y *= np.sqrt(float(root.shape[0]))
    elif distribution == "rademacher":
        x = 2.0 * rng.integers(0, 2, size=shape) - 1.0
        y = 2.0 * rng.integers(0, 2, size=shape) - 1.0
    elif distribution == "srht_rademacher":
        # Subsample columns without replacement from a randomized Hadamard
        # frame.  Every entry remains exactly +/-1, the one-column second
        # moment is I after the independent row signs, and within-batch probe
        # overlap is strongly suppressed relative to iid Rademacher vectors.
        frame_size = 1 << (root.shape[0] - 1).bit_length()
        if samples > frame_size:
            raise ValueError("SRHT sample count exceeds the padded frame size")
        frame = hadamard(frame_size, dtype=float)[: root.shape[0]]
        x_columns = rng.choice(frame_size, size=samples, replace=False)
        y_columns = rng.choice(frame_size, size=samples, replace=False)
        x_sign = 2.0 * rng.integers(0, 2, size=(root.shape[0], 1)) - 1.0
        y_sign = 2.0 * rng.integers(0, 2, size=(root.shape[0], 1)) - 1.0
        x = x_sign * frame[:, x_columns]
        y = y_sign * frame[:, y_columns]
    else:
        raise ValueError("unknown trace distribution")
    return root @ x, root @ y


def derive(args: argparse.Namespace) -> dict[str, object]:
    times = np.asarray(args.times, dtype=float)
    if times.size < 2 or times[0] != 0.0 or not np.allclose(
        np.diff(times), np.diff(times)[0]
    ):
        raise ValueError("times must be a uniform grid beginning at zero")
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
    vertex = np.asarray(modes["velocity_vertex"])
    mode_count = covariance.shape[0]
    wave_count = args.fourier_points
    waves = args.wave_step * (np.fft.fftfreq(wave_count) * wave_count)
    symbol = (
        (lambda wave: 2.0 * np.sin(0.5 * wave))
        if args.lattice_wave_number
        else (lambda wave: wave)
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
    cell_length = 2.0 * np.pi / (wave_count * args.wave_step)
    fourier_covariance = covariance / cell_length
    susceptibility = float(projection @ fourier_covariance @ projection)
    root = _covariance_root(fourier_covariance)
    normalization = np.sqrt(float(wave_count))
    velocity_coefficient = -0.5j / normalization
    diffusion_coefficient = -0.25 / normalization
    requested_momentum_samples = int(getattr(args, "momentum_samples", 0))
    if requested_momentum_samples < 0:
        raise ValueError("momentum samples must be non-negative")
    momentum_sampling_exact = (
        requested_momentum_samples == 0
        or requested_momentum_samples >= wave_count
    )
    momentum_sample_count = (
        wave_count if momentum_sampling_exact else requested_momentum_samples
    )
    trace_pairing_count = int(getattr(args, "trace_pairing_count", 1))
    if not 1 <= trace_pairing_count <= args.samples:
        raise ValueError("trace pairing count must lie between one and the trace sample count")
    selected_p_by_k: list[list[int]] = []
    for k_index in range(wave_count):
        if momentum_sampling_exact:
            selected_p_by_k.append(list(range(wave_count)))
        else:
            rng = np.random.default_rng(args.seed + 7_919_191 * (k_index + 1))
            selected_p_by_k.append(
                rng.integers(0, wave_count, size=momentum_sample_count).tolist()
            )

    def directional(vector: np.ndarray) -> np.ndarray:
        return np.asarray(
            full_diffusion_noise_directional_frechet_derivative(
                modes, vector
            )["diffusion_directional_derivative"]
        )

    # Every wave receives one physical column and stochastic covariance
    # sources.  In the legacy pairwise layout each (external k, internal p)
    # pair has its own trace vectors.  The shared-wave layout reuses x_p and
    # y_q wherever the same internal momentum occurs.  This remains unbiased:
    # the memory is a sum of per-p outer products and concatenation never
    # creates cross terms between different p blocks.  It reduces the source
    # count per wave from 1+2*F*S to 1+2*S.
    source_blocks: list[list[np.ndarray]] = [
        [fourier_covariance @ projection[:, None]] for _ in range(wave_count)
    ]
    x_slices: dict[tuple[int, int], tuple[int, slice]] = {}
    y_slices: dict[tuple[int, int], tuple[int, slice]] = {}
    zero_pairs: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
    source_offsets = [1 for _ in range(wave_count)]
    trace_source_layout = getattr(args, "trace_source_layout", "pairwise")
    if not momentum_sampling_exact and trace_source_layout != "shared_wave":
        raise ValueError("stochastic momentum sampling requires shared-wave trace sources")
    if trace_source_layout == "shared_wave":
        x_by_wave = []
        y_by_wave = []
        x_slice_by_wave = []
        y_slice_by_wave = []
        for wave_index in range(wave_count):
            x_zero, y_zero = _trace_pair(
                root,
                args.samples,
                args.seed + 9176 * wave_index,
                args.trace_distribution,
            )
            x_slice = slice(source_offsets[wave_index], source_offsets[wave_index] + args.samples)
            source_offsets[wave_index] += args.samples
            source_blocks[wave_index].append(x_zero)
            y_slice = slice(source_offsets[wave_index], source_offsets[wave_index] + args.samples)
            source_offsets[wave_index] += args.samples
            source_blocks[wave_index].append(y_zero)
            x_by_wave.append(x_zero)
            y_by_wave.append(y_zero)
            x_slice_by_wave.append(x_slice)
            y_slice_by_wave.append(y_slice)
        for k_index in range(wave_count):
            for p_index in range(wave_count):
                q_index = (k_index - p_index) % wave_count
                x_slices[(k_index, p_index)] = (p_index, x_slice_by_wave[p_index])
                y_slices[(k_index, p_index)] = (q_index, y_slice_by_wave[q_index])
                zero_pairs[(k_index, p_index)] = (x_by_wave[p_index], y_by_wave[q_index])
    elif trace_source_layout == "pairwise":
        for k_index in range(wave_count):
            for p_index in range(wave_count):
                q_index = (k_index - p_index) % wave_count
                seed = args.seed + 1_000_003 * k_index + 9176 * p_index
                x_zero, y_zero = _trace_pair(
                    root, args.samples, seed, args.trace_distribution
                )
                x_slice = slice(
                    source_offsets[p_index], source_offsets[p_index] + args.samples
                )
                source_offsets[p_index] += args.samples
                source_blocks[p_index].append(x_zero)
                y_slice = slice(
                    source_offsets[q_index], source_offsets[q_index] + args.samples
                )
                source_offsets[q_index] += args.samples
                source_blocks[q_index].append(y_zero)
                x_slices[(k_index, p_index)] = (p_index, x_slice)
                y_slices[(k_index, p_index)] = (q_index, y_slice)
                zero_pairs[(k_index, p_index)] = (x_zero, y_zero)
    else:
        raise ValueError("unknown trace source layout")
    if len(set(source_offsets)) != 1:
        raise RuntimeError("internal source-pool construction is unbalanced")
    sources = np.asarray(
        [np.concatenate(blocks, axis=1) for blocks in source_blocks]
    )
    source_count = sources.shape[2]
    actions = np.empty(
        (wave_count, times.size, mode_count, source_count), dtype=complex
    )
    for wave_index in range(wave_count):
        for time_index, time in enumerate(times):
            actions[wave_index, time_index] = (
                expm(float(time) * generators[wave_index]) @ sources[wave_index]
            )

    def force_pair(
        x: np.ndarray,
        y: np.ndarray,
        p_symbol: float,
        q_symbol: float,
    ) -> np.ndarray:
        velocity_force = velocity_coefficient * (
            q_symbol * (vertex @ x) * y
            + p_symbol * x * (vertex @ y)
        )
        diffusion_force = np.empty_like(velocity_force)
        for sample in range(args.samples):
            d_x = directional(x[:, sample])
            d_y = directional(y[:, sample])
            diffusion_force[:, sample] = diffusion_coefficient * (
                q_symbol**2 * (d_x @ y[:, sample])
                + p_symbol**2 * (d_y @ x[:, sample])
            )
        return velocity_force + diffusion_force

    def paired_force(
        x: np.ndarray,
        y: np.ndarray,
        p_symbol: float,
        q_symbol: float,
    ) -> np.ndarray:
        """Reuse one propagated frame through unbiased cyclic x--y pairings.

        The x and y frames are generated independently.  Hence every cyclic
        pair ``(x_i, y_{i+r})`` has the same product measure as the legacy
        ``(x_i, y_i)`` estimator.  Concatenating several shifts changes only
        within-batch correlations; it does not change the Wick expectation or
        require additional linear-GHD source columns.
        """

        blocks = [
            force_pair(x, np.roll(y, -shift, axis=1), p_symbol, q_symbol)
            for shift in range(trace_pairing_count)
        ]
        return np.concatenate(blocks, axis=1)

    zero_forces: dict[tuple[int, int], np.ndarray] = {}
    required_pairs = {
        (k_index, p_index)
        for k_index in range(wave_count)
        for p_index in selected_p_by_k[k_index]
    }
    for key in required_pairs:
        x_zero, y_zero = zero_pairs[key]
        _, p_index = key
        q_index = (key[0] - p_index) % wave_count
        zero_forces[key] = paired_force(
            x_zero,
            y_zero,
            float(symbol(float(waves[p_index]))),
            float(symbol(float(waves[q_index]))),
        )

    relaxation = args.dyson_relaxation
    anderson_depth = int(getattr(args, "anderson_depth", 0))
    if anderson_depth < 0:
        raise ValueError("anderson_depth must be non-negative")
    iteration_rows = []
    final_memory_ranks = []
    mapped_history: list[np.ndarray] = []
    residual_history: list[np.ndarray] = []
    final_projected_continuity_memory = np.zeros(
        (wave_count, times.size), dtype=complex
    )
    stop_on_convergence = bool(getattr(args, "stop_on_convergence", False))
    for iteration in range(args.dyson_iterations):
        input_actions = actions
        mapped = input_actions.copy()
        memory_ranks = []
        for k_index in range(1, wave_count):
            left_by_time = []
            right_by_time = []
            for time_index in range(times.size):
                left_blocks = []
                right_blocks = []
                for p_index in selected_p_by_k[k_index]:
                    q_index = (k_index - p_index) % wave_count
                    _, x_slice = x_slices[(k_index, p_index)]
                    _, y_slice = y_slices[(k_index, p_index)]
                    x_time = input_actions[p_index, time_index, :, x_slice]
                    y_time = input_actions[q_index, time_index, :, y_slice]
                    force_time = paired_force(
                        x_time,
                        y_time,
                        float(symbol(float(waves[p_index]))),
                        float(symbol(float(waves[q_index]))),
                    )
                    factor_scale = np.sqrt(
                        2.0
                        * float(wave_count)
                        / float(
                            momentum_sample_count
                            * args.samples
                            * trace_pairing_count
                        )
                    )
                    left_blocks.append(factor_scale * force_time)
                    right_blocks.append(
                        factor_scale * zero_forces[(k_index, p_index)]
                    )
                left_by_time.append(np.concatenate(left_blocks, axis=1))
                right_by_time.append(np.concatenate(right_blocks, axis=1))
            left_factors = np.asarray(left_by_time)
            right_factors = np.asarray(right_by_time)
            # The same low-rank factors used by the matrix Volterra solver
            # also give the physical density-force autocorrelation without
            # forming the dense mode-space memory.  If
            # M_k(t)=L_k(t)R_k(t)^dagger, then
            #
            #   K_spin(k,t)=p^T M_k(t) p / (chi khat_k^2).
            #
            # This is the colored hydrodynamic contribution that may be used
            # as a deep Mori--Lanczos terminator.  The white multiplicative
            # noise contact is deliberately absent: the exact microscopic
            # Mori prefix supplies the regular short-time completion.
            projected_left = np.einsum(
                "m,tmr->tr", projection, left_factors, optimize=True
            )
            projected_right = np.einsum(
                "m,tmr->tr", projection, right_factors, optimize=True
            )
            external_symbol = float(symbol(float(waves[k_index])))
            final_projected_continuity_memory[k_index] = np.sum(
                projected_left * projected_right.conj(), axis=1
            ) / (susceptibility * external_symbol**2)
            propagated = propagate_low_rank_matrix_mori_actions(
                generators[k_index],
                fourier_covariance,
                times,
                left_factors,
                right_factors,
                sources[k_index],
            )["response_actions"]
            mapped[k_index] = propagated
            memory_ranks.append(int(left_factors.shape[2]))
        # The conserved zero mode acts as the identity on every source.
        mapped[0] = sources[0][None, :, :]
        residual = mapped - input_actions
        raw_denominator = np.maximum(
            np.linalg.norm(mapped, axis=(2, 3)), np.finfo(float).tiny
        )
        maximum_fixed_point_residual = float(
            np.max(np.linalg.norm(residual, axis=(2, 3)) / raw_denominator)
        )
        mapped_history.append(mapped.copy())
        residual_history.append(residual.copy())
        if len(mapped_history) > max(1, anderson_depth):
            mapped_history.pop(0)
            residual_history.pop(0)
        anderson_coefficients = [1.0]
        candidate = mapped
        if anderson_depth > 0 and len(mapped_history) >= 2:
            history_size = len(mapped_history)
            gram = np.empty((history_size, history_size), dtype=float)
            for row in range(history_size):
                for column in range(history_size):
                    gram[row, column] = float(
                        np.vdot(
                            residual_history[row], residual_history[column]
                        ).real
                    )
            regularizer = 1.0e-12 * max(
                float(np.trace(gram)) / history_size,
                np.finfo(float).tiny,
            )
            gram += regularizer * np.eye(history_size)
            system = np.block(
                [
                    [gram, np.ones((history_size, 1))],
                    [np.ones((1, history_size)), np.zeros((1, 1))],
                ]
            )
            rhs = np.concatenate([np.zeros(history_size), np.ones(1)])
            solution = np.linalg.solve(system, rhs)
            coefficients = solution[:history_size]
            candidate = np.zeros_like(mapped)
            for coefficient, history_value in zip(
                coefficients, mapped_history
            ):
                candidate += coefficient * history_value
            anderson_coefficients = coefficients.tolist()
        updated = (
            (1.0 - relaxation) * input_actions + relaxation * candidate
        )
        updated[0] = sources[0][None, :, :]
        difference = np.linalg.norm(updated - input_actions, axis=(2, 3))
        denominator = np.maximum(
            np.linalg.norm(updated, axis=(2, 3)), np.finfo(float).tiny
        )
        physical_structure = np.asarray(
            [
                [
                    projection @ updated[k_index, time_index, :, 0]
                    / susceptibility
                    for time_index in range(times.size)
                ]
                for k_index in range(wave_count)
            ]
        )
        iteration_rows.append(
            {
                "iteration": iteration + 1,
                "maximum_relative_action_change": float(
                    np.max(difference / denominator)
                ),
                "maximum_relative_fixed_point_residual": (
                    maximum_fixed_point_residual
                ),
                "anderson_coefficients": anderson_coefficients,
                "external_q_step_structure_factor_over_chi": _pairs(
                    physical_structure[1]
                ),
            }
        )
        actions = updated
        final_memory_ranks = memory_ranks
        if (
            stop_on_convergence
            and iteration >= 1
            and maximum_fixed_point_residual
            <= args.dyson_convergence_tolerance
        ):
            break

    structure = np.asarray(
        [
            [
                projection @ actions[k_index, time_index, :, 0]
                / susceptibility
                for time_index in range(times.size)
            ]
            for k_index in range(wave_count)
        ]
    )
    for positive_index in range(1, (wave_count + 1) // 2):
        negative_index = (-positive_index) % wave_count
        paired = 0.5 * (
            structure[positive_index] + structure[negative_index].conj()
        )
        structure[positive_index] = paired
        structure[negative_index] = paired.conj()
        paired_memory = 0.5 * (
            final_projected_continuity_memory[positive_index]
            + final_projected_continuity_memory[negative_index].conj()
        )
        final_projected_continuity_memory[positive_index] = paired_memory
        final_projected_continuity_memory[negative_index] = paired_memory.conj()
    fdt = full_fdt_noise_covariance(generators[1], fourier_covariance)
    fdt_noise = np.asarray(fdt["noise_covariance"])
    diffusion_off_diagonal = diffusion - np.diag(np.diag(diffusion))
    noise_off_diagonal = fdt_noise - np.diag(np.diag(fdt_noise))
    diffusion_norm = float(np.linalg.norm(diffusion))
    noise_norm = float(np.linalg.norm(fdt_noise))
    thermodynamic_metric_commutator = (
        diffusion @ fourier_covariance
        - fourier_covariance @ diffusion.T
    )
    captured = float(projection @ covariance @ projection)
    exact_susceptibility = float(1.0 / (4.0 * np.cosh(args.field) ** 2))
    final_change = iteration_rows[-1][
        "maximum_relative_fixed_point_residual"
    ]
    converged = bool(
        len(iteration_rows) >= 2
        and final_change <= args.dyson_convergence_tolerance
    )
    dense_response_bytes = (
        wave_count * times.size * mode_count**2 * np.dtype(complex).itemsize
    )
    action_bytes = int(actions.nbytes)
    return {
        "schema": 1,
        "method": "low_rank_action_self_consistent_full_mode_mori",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "regulator": {
            "field": args.field,
            "active_strings": int(modes["active_strings"]),
            "mode_count": int(mode_count),
            "nodes_per_string": args.nodes_per_string,
            "string_xi_cutoff": args.string_xi_cutoff,
            "string_xi_buffer": args.string_xi_buffer,
            "scaled_rapidity_extent": args.scaled_rapidity_extent,
            "scaled_rapidity_map_alpha": args.scaled_rapidity_map_alpha,
            "kernel_theta_step": args.kernel_theta_step,
            "fourier_points": wave_count,
            "wave_step": args.wave_step,
            "samples_per_internal_wave": args.samples,
            "trace_pairings_per_frame": trace_pairing_count,
            "trace_pairing_strategy": "cyclic_bipartite",
            "complete_cartesian_trace_pairing": bool(
                trace_pairing_count == args.samples
            ),
            "momentum_samples_per_external_wave": momentum_sample_count,
            "internal_momentum_sum_exact": momentum_sampling_exact,
            "trace_distribution": args.trace_distribution,
            "trace_source_layout": trace_source_layout,
            "lattice_wave_number": args.lattice_wave_number,
            "seed": args.seed,
            "dyson_iterations": args.dyson_iterations,
            "dyson_iterations_completed": len(iteration_rows),
            "anderson_depth": anderson_depth,
        },
        "times": times.tolist(),
        "scaled_times_tau_equals_t_h3": (times * args.field**3).tolist(),
        "waves": waves.tolist(),
        "scaled_waves_q_equals_k_over_h2": (waves / args.field**2).tolist(),
        "static_susceptibility_captured_fraction": (
            captured / exact_susceptibility
        ),
        "fdt": {
            "minimum_eigenvalue": fdt["minimum_eigenvalue"],
            "positive_semidefinite": fdt[
                "positive_semidefinite_within_roundoff"
            ],
            "relative_lyapunov_residual": fdt["relative_lyapunov_residual"],
        },
        "matrix_diagnostics": {
            "diffusion_frobenius_norm": diffusion_norm,
            "diffusion_off_diagonal_frobenius_fraction": float(
                np.linalg.norm(diffusion_off_diagonal)
                / max(diffusion_norm, np.finfo(float).tiny)
            ),
            "fdt_noise_frobenius_norm": noise_norm,
            "fdt_noise_off_diagonal_frobenius_fraction": float(
                np.linalg.norm(noise_off_diagonal)
                / max(noise_norm, np.finfo(float).tiny)
            ),
            "diffusion_static_metric_commutator_relative_norm": float(
                np.linalg.norm(thermodynamic_metric_commutator)
                / max(
                    np.linalg.norm(diffusion @ fourier_covariance),
                    np.finfo(float).tiny,
                )
            ),
        },
        "iteration": {
            "rows": iteration_rows,
            "converged": converged,
            "convergence_tolerance": args.dyson_convergence_tolerance,
            "zero_mode_action_residual": float(
                np.linalg.norm(actions[0] - sources[0][None, :, :])
            ),
        },
        "structure_factors_over_chi_by_wave_then_time": [
            _pairs(row) for row in structure
        ],
        "projected_colored_continuity_memory_by_wave_then_time": [
            _pairs(row) for row in final_projected_continuity_memory
        ],
        "storage": {
            "source_columns_per_wave": int(source_count),
            "force_memory_rank_per_nonzero_wave": final_memory_ranks,
            "response_action_bytes": action_bytes,
            "corresponding_dense_response_bytes": int(dense_response_bytes),
            "dense_to_action_storage_ratio": float(
                dense_response_bytes / max(action_bytes, 1)
            ),
            "dense_nonlinear_memory_stored": False,
            "dense_response_matrix_stored": False,
        },
        "scope": {
            "all_retained_modes": True,
            "all_nonzero_fourier_momenta": True,
            "full_non_diagonal_diffusion": True,
            "full_background_fdt_noise_covariance": True,
            "quadratic_velocity_diffusion_and_cross_forces": True,
            "shared_wave_trace_reuse_unbiased_by_outer_product_linearity": (
                trace_source_layout == "shared_wave"
            ),
            "cyclic_trace_pairing_unbiased_by_product_measure": True,
            "complete_cartesian_trace_pairing_is_conditional_pairing_average": bool(
                trace_pairing_count == args.samples
            ),
            "stochastic_internal_momentum_sampling_unbiased": (
                not momentum_sampling_exact
            ),
            "finite_regulator_fixed_point_reached": converged,
            "multiplicative_noise_contact_uv_matched": False,
            "colored_memory_available_for_exact_mori_prefix_matching": True,
            "white_noise_contact_inserted_into_colored_memory": False,
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
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument(
        "--trace-pairing-count",
        type=int,
        default=1,
        help=(
            "cyclic x--y Wick pairings reused per propagated trace frame; "
            "must not exceed --samples"
        ),
    )
    parser.add_argument(
        "--momentum-samples",
        type=int,
        default=0,
        help="internal momenta sampled with replacement per external wave; 0 keeps the exact sum",
    )
    parser.add_argument("--seed", type=int, default=265)
    parser.add_argument(
        "--trace-distribution",
        choices=["gaussian", "rademacher", "orthogonal_gaussian", "srht_rademacher"],
        default="rademacher",
    )
    parser.add_argument(
        "--trace-source-layout",
        choices=("pairwise", "shared_wave"),
        default="pairwise",
    )
    parser.add_argument("--dyson-iterations", type=int, default=3)
    parser.add_argument("--dyson-relaxation", type=float, default=1.0)
    parser.add_argument("--anderson-depth", type=int, default=0)
    parser.add_argument("--stop-on-convergence", action="store_true")
    parser.add_argument("--dyson-convergence-tolerance", type=float, default=1.0e-3)
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
