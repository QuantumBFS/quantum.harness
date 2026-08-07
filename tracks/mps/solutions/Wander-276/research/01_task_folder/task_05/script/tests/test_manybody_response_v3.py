"""Tests for the genuine particle-number response backend."""

from __future__ import annotations

import numpy as np
import pytest

from lgeth.lattice import build_kapit_laughlin_parent
from lgeth.manybody_response import (
    ManyBodyCase,
    audit_unregistered_small_case,
    build_site_response_cache,
    dense_resolvent_response,
    registered_fixed_two_qh_cases,
    response_pair_grams,
    rotate_response_target_gauge,
    solve_kernel_frame,
)


def _seeded_unitary(dimension: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(dimension, dimension))
    matrix = matrix + 1j * rng.normal(size=matrix.shape)
    unitary, _ = np.linalg.qr(matrix)
    return unitary


def test_registered_sequence_is_fixed_two_quasiholes() -> None:
    cases = registered_fixed_two_qh_cases()
    assert [
        (case.N, case.n_flux, case.expected_rank)
        for case in cases
    ] == [(3, 8, 16), (4, 10, 25), (5, 12, 36)]
    assert all(case.n_flux == 2 * case.N + 2 for case in cases)


def test_n2_physical_parent_is_rejected_by_counting_gate() -> None:
    audit = audit_unregistered_small_case(
        N=2,
        n_flux=6,
        theta_x=0.17,
        theta_y=0.29,
    )
    assert audit.expected_rank == 9
    assert audit.observed_rank == 12
    assert audit.accepted is False


@pytest.mark.parametrize(
    ("N", "n_flux", "rank"),
    [(3, 8, 16), (4, 10, 25)],
)
def test_dense_kernel_has_registered_rank_and_open_gap(
    N: int,
    n_flux: int,
    rank: int,
) -> None:
    case = ManyBodyCase(N, n_flux, rank, 0.17, 0.29)
    system = build_kapit_laughlin_parent(
        N,
        n_flux,
        case.theta_x,
        case.theta_y,
    )
    kernel = solve_kernel_frame(system, case, seed=20260728301)
    assert kernel.frame.shape == (system.basis.dimension, rank)
    assert kernel.external_gap > 0.0
    assert kernel.residual_norm < 1e-10
    assert kernel.orthonormality_error < 1e-11
    assert kernel.method == "dense"


def test_richardson_response_matches_dense_spectral_inverse() -> None:
    case = registered_fixed_two_qh_cases()[0]
    system = build_kapit_laughlin_parent(
        case.N,
        case.n_flux,
        case.theta_x,
        case.theta_y,
    )
    kernel = solve_kernel_frame(system, case, seed=20260728302)
    cache = build_site_response_cache(
        system,
        kernel,
        relative_shifts=(1e-3, 5e-4),
        site_indices=(0, 3),
    )
    exact = dense_resolvent_response(
        system,
        kernel,
        site_indices=(0, 3),
    )
    relative = np.linalg.norm(cache.solutions - exact) / np.linalg.norm(exact)
    assert relative < 2e-4
    assert cache.maximum_relative_residual < 2e-4
    assert cache.maximum_kernel_leakage < 1e-10


def test_kernel_rotation_does_not_change_site_response_grams() -> None:
    case = registered_fixed_two_qh_cases()[0]
    system = build_kapit_laughlin_parent(
        case.N,
        case.n_flux,
        case.theta_x,
        case.theta_y,
    )
    kernel = solve_kernel_frame(system, case, seed=20260728303)
    cache = build_site_response_cache(
        system,
        kernel,
        relative_shifts=(1e-3, 5e-4),
        site_indices=(0, 1, 2),
    )
    unitary = _seeded_unitary(case.expected_rank, seed=11)
    rotated = rotate_response_target_gauge(cache, unitary)
    original_grams = response_pair_grams(cache.solutions)
    rotated_grams = response_pair_grams(rotated.solutions)
    original_invariant = np.einsum(
        "stij,uvji->stuv",
        original_grams,
        original_grams,
        optimize=True,
    )
    rotated_invariant = np.einsum(
        "stij,uvji->stuv",
        rotated_grams,
        rotated_grams,
        optimize=True,
    )
    np.testing.assert_allclose(
        original_invariant,
        rotated_invariant,
        atol=2e-9,
        rtol=2e-9,
    )
