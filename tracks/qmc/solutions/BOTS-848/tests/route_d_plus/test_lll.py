from __future__ import annotations

import math

import numpy as np

from route_d_plus.lll import (
    monopole_orbitals,
    orbital_overlap_matrix,
    reconstruct_lll,
    reproducing_kernel,
    sphere_quadrature,
    spinor,
)

TWO_Q = 15
PHASE2_TOLERANCE = 1.0e-12


def test_spinor_uses_the_fixed_gauge_and_has_unit_norm() -> None:
    theta = np.array([0.0, 0.37, 1.41, math.pi])
    phi = np.array([-1.3, 0.0, 2.2, 4.7])
    u, v = spinor(theta, phi)

    np.testing.assert_allclose(
        np.abs(u) ** 2 + np.abs(v) ** 2,
        np.ones(theta.size),
        atol=2.0e-15,
    )
    np.testing.assert_allclose(
        u,
        np.cos(theta / 2.0) * np.exp(0.5j * phi),
        atol=2.0e-15,
    )
    np.testing.assert_allclose(
        v,
        np.sin(theta / 2.0) * np.exp(-0.5j * phi),
        atol=2.0e-15,
    )
    assert u.dtype == np.complex128
    assert v.dtype == np.complex128


def test_monopole_orbitals_are_orthonormal_for_phase2_instance() -> None:
    grid = sphere_quadrature(TWO_Q)
    overlap = orbital_overlap_matrix(TWO_Q, grid)

    np.testing.assert_allclose(
        overlap,
        np.eye(TWO_Q + 1),
        atol=PHASE2_TOLERANCE,
    )


def test_closed_reproducing_kernel_equals_the_orbital_sum() -> None:
    theta = np.array([0.19, 0.83, 1.77])
    phi = np.array([0.31, 2.41, 5.17])
    source_theta = np.array([0.42, 1.23, 2.68, 2.91])
    source_phi = np.array([5.3, 3.2, 1.1, 0.07])
    u, v = spinor(theta, phi)
    source_u, source_v = spinor(source_theta, source_phi)

    basis = monopole_orbitals(TWO_Q, u, v)
    source_basis = monopole_orbitals(TWO_Q, source_u, source_v)
    orbital_sum = basis @ source_basis.conj().T
    closed_form = reproducing_kernel(
        TWO_Q,
        u[:, None],
        v[:, None],
        source_u[None, :],
        source_v[None, :],
    )

    np.testing.assert_allclose(
        closed_form,
        orbital_sum,
        atol=PHASE2_TOLERANCE,
    )


def test_off_grid_orbital_reconstruction_is_below_phase2_tolerance() -> None:
    grid = sphere_quadrature(TWO_Q)
    grid_orbitals = monopole_orbitals(TWO_Q, grid.u, grid.v)
    rng = np.random.default_rng(848)
    coefficients = rng.normal(size=TWO_Q + 1) + 1.0j * rng.normal(
        size=TWO_Q + 1
    )
    sampled_values = grid_orbitals @ coefficients

    target_theta = np.array([0.07, 0.51, 1.02, 1.68, 2.49, 3.03])
    target_phi = np.array([5.91, 0.33, 2.72, 4.81, 1.39, 3.57])
    target_u, target_v = spinor(target_theta, target_phi)
    expected = (
        monopole_orbitals(TWO_Q, target_u, target_v) @ coefficients
    )
    reconstructed = reconstruct_lll(
        TWO_Q,
        grid,
        sampled_values,
        target_u,
        target_v,
    )
    error = float(np.max(np.abs(reconstructed - expected)))

    assert error < PHASE2_TOLERANCE


def test_half_integer_quantum_numbers_use_integer_two_q_two_m() -> None:
    u, v = spinor(0.72, 1.17)
    orbitals = monopole_orbitals(3, u, v)

    assert orbitals.shape == (4,)
    with np.testing.assert_raises(ValueError):
        sphere_quadrature(-1)
