from __future__ import annotations

import numpy as np
from scipy.linalg import expm

from route_d_plus.lll import sphere_quadrature, spinor
from route_d_plus.mother import (
    gmp_quadrupole_tower,
    laughlin_amplitude,
    log_psi_laughlin,
)
from route_d_plus.tensor import (
    angular_momentum_matrices,
    canonical_tensor,
    rotation_matrix,
)

N_ELECTRONS = 6
TWO_Q = 15


def fixed_spinors() -> np.ndarray:
    theta = np.array([0.21, 0.64, 1.08, 1.57, 2.19, 2.81])
    phi = np.array([0.17, 1.32, 2.73, 4.11, 5.27, 3.36])
    u, v = spinor(theta, phi)
    return np.column_stack((u, v))


def test_laughlin_log_amplitude_preserves_nodes_and_exchange_sign() -> None:
    spinors = fixed_spinors()
    log_abs, phase = log_psi_laughlin(spinors)
    assert np.isfinite(log_abs)
    np.testing.assert_allclose(abs(phase), 1.0, atol=2.0e-15)

    swapped = spinors.copy()
    swapped[[1, 4]] = swapped[[4, 1]]
    np.testing.assert_allclose(
        laughlin_amplitude(swapped),
        -laughlin_amplitude(spinors),
        atol=2.0e-15,
    )

    coincident = spinors.copy()
    coincident[3] = coincident[0]
    node_log_abs, node_phase = log_psi_laughlin(coincident)
    assert node_log_abs == -np.inf
    assert node_phase == 0.0j


def test_laughlin_has_fixed_particle_degree_and_is_su2_singlet() -> None:
    spinors = fixed_spinors()
    amplitude = laughlin_amplitude(spinors)
    scale = 1.07 * np.exp(0.19j)
    scaled = spinors.copy()
    scaled[2] *= scale
    np.testing.assert_allclose(
        laughlin_amplitude(scaled),
        (scale**TWO_Q) * amplitude,
        rtol=2.0e-12,
        atol=2.0e-15,
    )

    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]])
    sigma_y = np.array([[0.0, -1.0j], [1.0j, 0.0]])
    sigma_z = np.diag([1.0, -1.0])
    vector = np.array([0.31, -0.27, 0.19])
    fundamental_rotation = expm(
        -0.5j
        * (
            vector[0] * sigma_x
            + vector[1] * sigma_y
            + vector[2] * sigma_z
        )
    )
    rotated = spinors @ fundamental_rotation.T
    np.testing.assert_allclose(
        laughlin_amplitude(rotated),
        amplitude,
        rtol=2.0e-12,
        atol=2.0e-15,
    )


def test_quadrupole_tower_has_five_nonzero_antisymmetric_components() -> None:
    spinors = fixed_spinors()
    grid = sphere_quadrature(TWO_Q)
    tower = gmp_quadrupole_tower(spinors, grid)
    assert tower.shape == (5,)
    assert np.all(np.abs(tower) > 1.0e-14)

    swapped = spinors.copy()
    swapped[[0, 5]] = swapped[[5, 0]]
    np.testing.assert_allclose(
        gmp_quadrupole_tower(swapped, grid),
        -tower,
        rtol=3.0e-11,
        atol=2.0e-15,
    )


def test_quadrupole_tower_preserves_lll_degree() -> None:
    spinors = fixed_spinors()
    grid = sphere_quadrature(TWO_Q)
    tower = gmp_quadrupole_tower(spinors, grid)
    scale = 1.03 * np.exp(-0.11j)
    scaled = spinors.copy()
    scaled[3] *= scale
    np.testing.assert_allclose(
        gmp_quadrupole_tower(scaled, grid),
        (scale**TWO_Q) * tower,
        rtol=4.0e-11,
        atol=3.0e-15,
    )


def test_rank_two_tower_obeys_ladder_and_finite_rotation_identities() -> None:
    jx, jy, _ = angular_momentum_matrices(TWO_Q)
    raising = jx + 1.0j * jy
    lowering = jx - 1.0j * jy
    for m in range(-2, 3):
        tensor = canonical_tensor(TWO_Q, 2, m)
        if m < 2:
            coefficient = np.sqrt(6.0 - m * (m + 1.0))
            np.testing.assert_allclose(
                raising @ tensor - tensor @ raising,
                coefficient * canonical_tensor(TWO_Q, 2, m + 1),
                atol=2.0e-12,
            )
        if m > -2:
            coefficient = np.sqrt(6.0 - m * (m - 1.0))
            np.testing.assert_allclose(
                lowering @ tensor - tensor @ lowering,
                coefficient * canonical_tensor(TWO_Q, 2, m - 1),
                atol=2.0e-12,
            )

    vector = np.array([0.31, -0.27, 0.19])
    single_particle_rotation = rotation_matrix(TWO_Q, vector)
    tensor_rotation = rotation_matrix(4, vector)
    tensors = [canonical_tensor(TWO_Q, 2, m) for m in range(-2, 3)]
    for column, tensor in enumerate(tensors):
        expected = sum(
            tensor_rotation[row, column] * component
            for row, component in enumerate(tensors)
        )
        np.testing.assert_allclose(
            single_particle_rotation
            @ tensor
            @ single_particle_rotation.conj().T,
            expected,
            atol=2.0e-12,
        )

    norms = np.array([np.vdot(tensor, tensor).real for tensor in tensors])
    np.testing.assert_allclose(norms, np.ones(5), atol=2.0e-12)
