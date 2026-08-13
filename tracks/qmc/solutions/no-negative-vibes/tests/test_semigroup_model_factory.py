from __future__ import annotations

import numpy as np
from scipy.linalg import expm

from oracle.semigroup_model_factory import (
    enumerate_semigroup_words,
    hermitian_semigroup_model,
    semigroup_word_weight,
)


def _tensor_square_atoms() -> tuple[np.ndarray, ...]:
    bases = (
        expm(np.asarray([[0.1, 0.35], [0.35, -0.2]])),
        expm(np.asarray([[-0.3, -0.25], [-0.25, 0.4]])),
    )
    scale = 1.0 / max(np.linalg.norm(base, 2) for base in bases)
    return tuple(
        np.kron(scale * base, scale * base)
        for base in bases
    )


def _asymmetric_tn_atom() -> np.ndarray:
    generator = np.asarray(
        [
            [0.1, 0.45, 0.0],
            [0.2, -0.3, 0.6],
            [0.0, 0.35, 0.2],
        ]
    )
    return expm(generator)


def test_factory_applies_directly_to_an_asymmetric_tn_atom() -> None:
    atom = _asymmetric_tn_atom()
    model = hermitian_semigroup_model((atom,), coefficients=(0.8,))
    weights = tuple(enumerate_semigroup_words(model, maximum_depth=7))

    assert not np.allclose(atom, atom.T, atol=1e-12)
    assert np.allclose(model.hamiltonian, model.hamiltonian.T, atol=1e-13)
    assert len(weights) == sum(2**depth for depth in range(1, 8))
    assert min(weight.determinant_trace for weight in weights) >= 1.0
    assert max(weight.trace_identity_residual for weight in weights) < 1e-10


def test_factory_hamiltonian_is_hermitian_and_number_conserving() -> None:
    model = hermitian_semigroup_model(
        _tensor_square_atoms(),
        coefficients=(0.7, 0.4),
    )
    fock_dimension = model.hamiltonian.shape[0]
    particle_number = np.diag(
        [state.bit_count() for state in range(fock_dimension)]
    )

    assert np.allclose(model.hamiltonian, model.hamiltonian.T, atol=1e-13)
    assert np.linalg.norm(
        model.hamiltonian @ particle_number
        - particle_number @ model.hamiltonian
    ) < 1e-12


def test_every_short_tensor_square_branch_word_is_nonnegative() -> None:
    model = hermitian_semigroup_model(
        _tensor_square_atoms(),
        coefficients=(0.7, 0.4),
    )
    weights = tuple(
        enumerate_semigroup_words(model, maximum_depth=5)
    )

    assert len(weights) == sum(4**depth for depth in range(1, 6))
    assert min(weight.determinant_trace for weight in weights) > 0.0
    assert min(weight.total_weight for weight in weights) > 0.0
    assert max(weight.trace_identity_residual for weight in weights) < 1e-10


def test_word_trace_is_the_determinant_of_the_one_particle_word() -> None:
    model = hermitian_semigroup_model(
        _tensor_square_atoms(),
        coefficients=(0.7, 0.4),
    )
    certificate = semigroup_word_weight(
        model,
        ((0, False), (1, True), (0, True), (1, False)),
    )

    assert certificate.scalar_coefficient == 0.7 * 0.4 * 0.7 * 0.4
    assert certificate.trace_identity_residual < 1e-11
    assert certificate.determinant_trace > 0.0


def test_factory_generically_produces_interacting_fock_terms() -> None:
    model = hermitian_semigroup_model(
        _tensor_square_atoms(),
        coefficients=(0.7, 0.4),
    )
    hamiltonian = model.hamiltonian

    vacuum = hamiltonian[0, 0]
    one_first = hamiltonian[0b0001, 0b0001]
    one_last = hamiltonian[0b1000, 0b1000]
    pair = hamiltonian[0b1001, 0b1001]
    connected_two_body = pair - one_first - one_last + vacuum

    assert abs(connected_two_body) > 1e-3
