from __future__ import annotations

import numpy as np
import pytest

from oracle.revival_no_go import (
    common_fock_permutation_gauge,
    diagonal_sign_transform,
    fixed_linf_adjoint_counterexample,
    permutation_matrix,
    reciprocal_parabolic_adjoint_counterexample,
)
from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


def _cyclic_group(size: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple((mode + shift) % size for mode in range(size))
        for shift in range(size)
    )


def test_odd_monomial_groups_have_one_stoquastic_fock_gauge() -> None:
    for modes in (3, 5):
        group = _cyclic_group(modes)
        gauge = common_fock_permutation_gauge(group)
        hamiltonian = np.zeros((1 << modes, 1 << modes))
        for index, permutation in enumerate(group):
            dilation = np.diag(
                np.linspace(0.7 + 0.1 * index, 1.3 + 0.1 * index, modes)
            )
            atom = permutation_matrix(permutation) @ dilation
            fock = number_conserving_gaussian_fock_matrix(atom)
            gauged = diagonal_sign_transform(fock, gauge)
            assert np.min(gauged) >= -1e-13
            hamiltonian -= fock + fock.T
        gauged_hamiltonian = diagonal_sign_transform(hamiltonian, gauge)
        offdiagonal = gauged_hamiltonian.copy()
        np.fill_diagonal(offdiagonal, 0.0)
        assert np.max(offdiagonal) <= 1e-13


def test_even_v4_boundary_has_negative_fock_stabilizer() -> None:
    v4 = tuple(
        tuple(mode ^ element for mode in range(4))
        for element in range(4)
    )
    with pytest.raises(ValueError, match="negative stabilizer"):
        common_fock_permutation_gauge(v4)


def test_fixed_linf_class_fails_adjoint_closure_at_depth_two() -> None:
    certificate = fixed_linf_adjoint_counterexample()
    metric = np.asarray([8.0, 1.0])
    for generator, atom in zip(
        certificate.generators,
        certificate.atoms,
        strict=True,
    ):
        diagonal = np.diag(generator)
        offdiagonal = generator - np.diag(diagonal)
        logarithmic_rows = diagonal + (np.abs(offdiagonal) @ metric) / metric
        weighted_atom_norm = np.max(
            (np.abs(atom) @ metric) / metric
        )
        assert np.max(logarithmic_rows) <= 1e-14
        assert weighted_atom_norm <= 1.0 + 1e-14
    assert abs(certificate.determinant_weight - (-3.3136985846984692)) < 1e-12
    assert certificate.minimum_singular_value > 0.45


def test_reciprocal_parabolic_class_fails_adjoint_closure_exactly() -> None:
    certificate = reciprocal_parabolic_adjoint_counterexample(shear=3.0)
    for generator in certificate.generators:
        assert generator[1, 0] == 0.0
        assert generator[1, 1] == -generator[0, 0]
    assert abs(certificate.determinant_weight - (-5.0)) < 1e-14
    assert np.allclose(
        certificate.product,
        np.asarray([[-8.0, 3.0], [-3.0, 1.0]]),
    )
    assert certificate.minimum_singular_value > 0.5
