from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from route_d_plus.lll import monopole_orbitals, sphere_quadrature, spinor
from route_d_plus.tensor import (
    apply_one_body_tensor,
    canonical_tensor,
    one_body_tensor_kernel,
    quadrature_reconstruction_error,
    rotation_matrix,
)

TWO_Q = 15
STRICT_TOLERANCE = 1.0e-12


def test_canonical_tensors_are_hilbert_schmidt_orthonormal() -> None:
    tensors = [
        canonical_tensor(TWO_Q, ell, m)
        for ell in range(TWO_Q + 1)
        for m in range(-ell, ell + 1)
    ]
    flattened = np.stack([tensor.reshape(-1) for tensor in tensors])
    gram = flattened.conj() @ flattened.T

    np.testing.assert_allclose(
        gram,
        np.eye(len(tensors)),
        atol=STRICT_TOLERANCE,
    )


def test_canonical_tensors_obey_spherical_hermiticity() -> None:
    for ell in range(TWO_Q + 1):
        for m in range(-ell, ell + 1):
            np.testing.assert_allclose(
                canonical_tensor(TWO_Q, ell, m).conj().T,
                ((-1) ** m) * canonical_tensor(TWO_Q, ell, -m),
                atol=STRICT_TOLERANCE,
            )


def test_canonical_tensors_obey_finite_rotation_law() -> None:
    rotation_vector = np.array([0.31, -0.27, 0.19])
    single_particle_rotation = rotation_matrix(TWO_Q, rotation_vector)
    for ell in [0, 1, 2, 5, TWO_Q]:
        tensor_rotation = rotation_matrix(2 * ell, rotation_vector)
        tensors = [
            canonical_tensor(TWO_Q, ell, m)
            for m in range(-ell, ell + 1)
        ]
        for column, tensor in enumerate(tensors):
            rotated = (
                single_particle_rotation
                @ tensor
                @ single_particle_rotation.conj().T
            )
            expected = sum(
                tensor_rotation[row, column] * component
                for row, component in enumerate(tensors)
            )
            np.testing.assert_allclose(
                rotated,
                expected,
                atol=2.0e-12,
            )


def test_one_body_tensor_kernel_matches_explicit_orbital_sum() -> None:
    target_u, target_v = spinor(
        np.array([0.23, 1.41, 2.77]),
        np.array([0.71, 3.19, 5.41]),
    )
    source_u, source_v = spinor(
        np.array([0.62, 1.88, 2.31]),
        np.array([5.73, 0.37, 2.22]),
    )
    tensor = canonical_tensor(TWO_Q, 4, -2)
    target_orbitals = monopole_orbitals(TWO_Q, target_u, target_v)
    source_orbitals = monopole_orbitals(TWO_Q, source_u, source_v)
    expected = np.einsum(
        "pa,ab,pb->p",
        target_orbitals,
        tensor,
        source_orbitals.conj(),
    )

    np.testing.assert_allclose(
        one_body_tensor_kernel(
            TWO_Q,
            tensor,
            target_u,
            target_v,
            source_u,
            source_v,
        ),
        expected,
        atol=STRICT_TOLERANCE,
    )


def test_apply_one_body_tensor_matches_orbital_matrix_action() -> None:
    grid = sphere_quadrature(TWO_Q)
    target_u, target_v = spinor(1.13, 2.71)
    spinors = np.array([[target_u, target_v]], dtype=np.complex128)
    coefficients = np.arange(1, TWO_Q + 2, dtype=np.float64)
    coefficients = coefficients + 0.25j * coefficients[::-1]
    tensor = canonical_tensor(TWO_Q, 2, 1)

    def psi_fn(particle_spinors: np.ndarray) -> complex:
        orbitals = monopole_orbitals(
            TWO_Q,
            particle_spinors[0, 0],
            particle_spinors[0, 1],
        )
        return complex(orbitals @ coefficients)

    expected = monopole_orbitals(TWO_Q, target_u, target_v) @ (
        tensor @ coefficients
    )
    actual = apply_one_body_tensor(
        psi_fn,
        spinors,
        0,
        tensor,
        grid,
    )
    np.testing.assert_allclose(actual, expected, atol=STRICT_TOLERANCE)


def test_apply_one_body_tensor_rejects_uncalibrated_quadrature() -> None:
    grid = sphere_quadrature(TWO_Q)
    bad_grid = replace(grid, weights=0.9 * grid.weights)
    assert quadrature_reconstruction_error(TWO_Q, bad_grid) > 1.0e-3

    with pytest.raises(RuntimeError, match="strict LLL reconstruction"):
        apply_one_body_tensor(
            lambda _: 1.0 + 0.0j,
            np.array([[grid.u[0], grid.v[0]]]),
            0,
            canonical_tensor(TWO_Q, 1, 0),
            bad_grid,
        )
