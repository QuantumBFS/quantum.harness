from __future__ import annotations

import numpy as np
import pytest

from route_d_plus.scalar import (
    FockSpace,
    coupled_pair_eigenvalues,
    one_body_casimir,
    one_body_fock_matrix,
    scalar_generator_pair,
    scalar_generator_proof,
    whitening_transform,
)
from route_d_plus.tensor import angular_momentum_matrices


@pytest.fixture(scope="module")
def certification_space() -> FockSpace:
    return FockSpace.build(7, 3)


@pytest.mark.parametrize("ell", [2, 3, 4])
def test_normal_ordering_removes_exact_one_body_casimir(ell: int) -> None:
    coefficient, residual = one_body_casimir(6, ell)
    assert coefficient == pytest.approx(np.sqrt(2 * ell + 1) / 7)
    assert residual < 1.0e-14


@pytest.mark.parametrize("ell", [2, 3, 4])
def test_pair_backend_matches_density_product_definition(
    certification_space: FockSpace,
    ell: int,
) -> None:
    proof = scalar_generator_proof(certification_space, 6, ell)
    production = scalar_generator_pair(certification_space, 6, ell)
    assert np.max(np.abs(proof - production)) < 1.0e-13


@pytest.mark.parametrize("ell", [2, 3, 4])
def test_generators_are_hermitian_lll_scalars(
    certification_space: FockSpace,
    ell: int,
) -> None:
    generator = scalar_generator_pair(certification_space, 6, ell)
    assert np.max(np.abs(generator - generator.conj().T)) < 1.0e-13
    rotations = [
        one_body_fock_matrix(certification_space, component)
        for component in angular_momentum_matrices(6)
    ]
    assert max(
        np.max(np.abs(generator @ rotation - rotation @ generator))
        for rotation in rotations
    ) < 1.0e-12


@pytest.mark.parametrize("ell", [2, 3, 4])
def test_coupled_pair_channels_are_scalar(ell: int) -> None:
    channels, spread = coupled_pair_eigenvalues(6, ell)
    assert set(channels) == {1, 3, 5}
    assert spread < 1.0e-13


def test_whitening_retains_only_algebraically_nonredundant_directions() -> None:
    covariance = np.array(
        [
            [4.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0e-16],
        ]
    )
    retained, transform = whitening_transform(covariance)
    whitened = transform @ covariance @ transform
    assert retained.shape == (2,)
    assert np.max(np.abs(whitened[:2, :2] - np.eye(2))) < 1.0e-13
    assert whitened[2, 2] == 0.0
