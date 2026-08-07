from __future__ import annotations

import numpy as np

from oracle.fock_cp import (
    conditional_cp_certificate,
    cp_map_certificate,
    fock_tensorization_order,
    kraus_superoperator,
    liouville_to_choi,
    tensorize_fock_operator,
)


def test_identity_liouville_matrix_has_rank_one_positive_choi_matrix() -> None:
    operator_dimension = 3
    identity_map = np.eye(operator_dimension**2)
    choi = liouville_to_choi(
        identity_map,
        operator_dimension=operator_dimension,
    )
    eigenvalues = np.linalg.eigvalsh(choi)

    assert np.count_nonzero(eigenvalues > 1e-12) == 1
    assert np.isclose(eigenvalues[-1], operator_dimension)
    assert eigenvalues[0] >= -1e-12


def test_kraus_superoperator_reshuffles_to_positive_choi_matrix() -> None:
    kraus = (
        np.asarray([[1.0, 2.0], [0.0, -1.0j]]),
        np.asarray([[0.0, 1.0j], [0.5, 0.0]]),
    )
    superoperator = kraus_superoperator(kraus)
    certificate = cp_map_certificate(superoperator)

    assert certificate.hermiticity_residual < 1e-12
    assert certificate.minimum_eigenvalue >= -1e-12
    assert certificate.is_completely_positive


def test_transpose_map_is_positive_but_not_completely_positive() -> None:
    operator_dimension = 2
    transpose = np.zeros((4, 4))
    for row in range(operator_dimension):
        for column in range(operator_dimension):
            source = row + operator_dimension * column
            target = column + operator_dimension * row
            transpose[target, source] = 1.0
    certificate = cp_map_certificate(transpose)

    assert certificate.hermiticity_residual < 1e-12
    assert certificate.minimum_eigenvalue < -0.9
    assert not certificate.is_completely_positive


def test_generalized_lindblad_generators_are_conditionally_cp() -> None:
    identity = np.eye(2)
    drift = np.asarray([[0.2, 0.7], [-0.1j, -0.3]])
    drift_generator = (
        np.kron(identity, drift)
        + np.kron(drift.conj(), identity)
    )
    jump = np.asarray([[0.0, 1.0], [0.3j, 0.0]])
    jump_generator = kraus_superoperator((jump,))

    drift_certificate = conditional_cp_certificate(drift_generator)
    jump_certificate = conditional_cp_certificate(jump_generator)

    assert drift_certificate.hermiticity_residual < 1e-12
    assert drift_certificate.minimum_conditional_eigenvalue >= -1e-12
    assert drift_certificate.is_conditionally_completely_positive
    assert jump_certificate.hermiticity_residual < 1e-12
    assert jump_certificate.minimum_conditional_eigenvalue >= -1e-12
    assert jump_certificate.is_conditionally_completely_positive


def test_fock_tensorization_order_is_a_bijection_with_column_major_index() -> None:
    order = fock_tensorization_order(
        modes=4,
        ket_modes=(0, 2),
    )

    assert order == (0b0000, 0b0001, 0b0100, 0b0101,
                     0b0010, 0b0011, 0b0110, 0b0111,
                     0b1000, 0b1001, 0b1100, 0b1101,
                     0b1010, 0b1011, 0b1110, 0b1111)
    assert sorted(order) == list(range(16))


def test_tensorized_fock_identity_is_the_identity_cp_map() -> None:
    fock_identity = np.eye(64)
    tensorized = tensorize_fock_operator(
        fock_identity,
        ket_modes=(0, 2, 4),
    )
    certificate = cp_map_certificate(tensorized)

    assert np.array_equal(tensorized, fock_identity)
    assert certificate.is_completely_positive
