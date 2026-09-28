from __future__ import annotations

import argparse

import numpy as np

from scripts.derive_full_matrix_mode_coupling import derive as derive_dense
from scripts.derive_low_rank_self_consistent_full_matrix import (
    _trace_pair,
    derive as derive_low_rank,
)


def _arguments() -> argparse.Namespace:
    return argparse.Namespace(
        field=0.25,
        string_xi_cutoff=0.5,
        string_xi_buffer=0.5,
        scaled_rapidity_extent=2.0,
        scaled_rapidity_map_alpha=2.0,
        nodes_per_string=8,
        kernel_theta_step=0.25,
        fourier_points=4,
        wave_step=0.1,
        times=[0.0, 0.125, 0.25, 0.375, 0.5],
        samples=2,
        seed=265,
        trace_distribution="rademacher",
        dyson_iterations=2,
        dyson_relaxation=1.0,
        dyson_convergence_tolerance=1.0e-3,
        lattice_wave_number=False,
    )


def _complex_array(rows) -> np.ndarray:
    return np.asarray(
        [[complex(*pair) for pair in wave_row] for wave_row in rows]
    )


def test_low_rank_response_actions_reproduce_dense_matrix_iteration() -> None:
    dense = derive_dense(_arguments())
    low_rank = derive_low_rank(_arguments())
    dense_structure = _complex_array(
        dense["all_fourier_structure_factors_over_chi"][
            "values_by_wave_then_time"
        ]
    )
    low_rank_structure = _complex_array(
        low_rank["structure_factors_over_chi_by_wave_then_time"]
    )
    low_rank_memory = _complex_array(
        low_rank["projected_colored_continuity_memory_by_wave_then_time"]
    )
    assert np.allclose(
        low_rank_structure,
        dense_structure,
        rtol=2.0e-10,
        atol=2.0e-10,
    )
    assert np.allclose(low_rank_memory[0], 0.0)
    assert np.allclose(low_rank_memory[1], low_rank_memory[-1].conj())
    assert low_rank_memory[1, 0].real > 0.0
    assert low_rank["scope"][
        "colored_memory_available_for_exact_mori_prefix_matching"
    ]
    assert not low_rank["scope"][
        "white_noise_contact_inserted_into_colored_memory"
    ]
    assert not low_rank["storage"]["dense_nonlinear_memory_stored"]
    assert not low_rank["storage"]["dense_response_matrix_stored"]
    assert all(
        "maximum_relative_fixed_point_residual" in row
        for row in low_rank["iteration"]["rows"]
    )
    assert low_rank["matrix_diagnostics"][
        "diffusion_off_diagonal_frobenius_fraction"
    ] > 0
    assert low_rank["matrix_diagnostics"][
        "fdt_noise_off_diagonal_frobenius_fraction"
    ] > 0
    assert np.isfinite(
        low_rank["matrix_diagnostics"][
            "diffusion_static_metric_commutator_relative_norm"
        ]
    )


def test_orthogonal_gaussian_trace_frame_has_unbiased_second_moment() -> None:
    root = np.diag([0.7, 1.1, 0.9, 0.5])
    moment = np.zeros((4, 4))
    repeats = 4000
    for seed in range(repeats):
        x, _ = _trace_pair(root, 2, seed, "orthogonal_gaussian")
        moment += x @ x.T / 2.0
    moment /= repeats
    assert np.allclose(moment, root @ root.T, rtol=0.035, atol=0.015)


def test_srht_rademacher_frame_has_unbiased_second_moment() -> None:
    root = np.diag([0.7, 1.1, 0.9, 0.5, 0.8])
    moment = np.zeros((5, 5))
    repeats = 3000
    for seed in range(repeats):
        x, _ = _trace_pair(root, 3, seed, "srht_rademacher")
        moment += x @ x.T / 3.0
    moment /= repeats
    assert np.allclose(moment, root @ root.T, rtol=0.035, atol=0.015)


def test_shared_wave_trace_layout_removes_extra_fourier_source_factor() -> None:
    arguments = _arguments()
    arguments.trace_source_layout = "shared_wave"
    arguments.dyson_iterations = 1
    result = derive_low_rank(arguments)
    assert result["regulator"]["trace_source_layout"] == "shared_wave"
    assert result["storage"]["source_columns_per_wave"] == 1 + 2 * arguments.samples


def test_cyclic_trace_pairings_increase_memory_rank_without_more_sources() -> None:
    arguments = _arguments()
    arguments.trace_source_layout = "shared_wave"
    arguments.trace_pairing_count = 2
    arguments.dyson_iterations = 1
    result = derive_low_rank(arguments)
    assert result["regulator"]["trace_pairings_per_frame"] == 2
    assert result["storage"]["source_columns_per_wave"] == 1 + 2 * arguments.samples
    assert result["storage"]["force_memory_rank_per_nonzero_wave"] == [
        2 * arguments.fourier_points * arguments.samples
    ] * (arguments.fourier_points - 1)


def test_trace_pairing_count_cannot_exceed_frame_size() -> None:
    arguments = _arguments()
    arguments.trace_pairing_count = arguments.samples + 1
    with np.testing.assert_raises_regex(ValueError, "trace pairing count"):
        derive_low_rank(arguments)


def test_stochastic_internal_momentum_sampling_reduces_memory_rank() -> None:
    arguments = _arguments()
    arguments.trace_source_layout = "shared_wave"
    arguments.momentum_samples = 2
    arguments.dyson_iterations = 1
    result = derive_low_rank(arguments)
    assert not result["regulator"]["internal_momentum_sum_exact"]
    assert result["regulator"]["momentum_samples_per_external_wave"] == 2
    assert set(result["storage"]["force_memory_rank_per_nonzero_wave"]) == {
        2 * arguments.samples
    }
    assert result["scope"]["stochastic_internal_momentum_sampling_unbiased"]
