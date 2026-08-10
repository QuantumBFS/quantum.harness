from fractions import Fraction

import numpy as np

from xxzcert.model import finite_xxz
from xxzcert.optimality import (
    contiguous_words,
    ground_optimality_matrix,
    stationarity_constraints,
)
from xxzcert.pauli_words import PauliWord, local_derivation, polynomial_matrix


def test_pauli_derivation_has_finite_expanded_support():
    result = local_derivation(Fraction(1), PauliWord.from_dict({0: "X"}))
    assert result.support == {-1, 0, 1}


def test_derivation_of_identity_is_zero():
    assert not local_derivation(Fraction(1), PauliWord()).terms


def test_finite_ground_state_satisfies_bulk_stationarity():
    sites = 6
    hamiltonian = finite_xxz(1.0, sites, periodic=False)
    _, vectors = np.linalg.eigh(hamiltonian)
    ground = vectors[:, 0]
    # A word supported at sites 2,3 only sees bonds 1..3 and therefore its
    # local derivation equals the commutator with the full open Hamiltonian.
    word = PauliWord.from_dict({2: "X", 3: "Z"})
    polynomial = local_derivation(Fraction(1), word)
    matrix = polynomial_matrix(polynomial, sites, origin=0)
    assert abs(np.vdot(ground, matrix @ ground)) < 1e-10


def test_stationarity_generation_is_deduplicated():
    constraints = stationarity_constraints(Fraction(1), 2)
    keys = [tuple(sorted(item.terms.items())) for item in constraints]
    assert len(keys) == len(set(keys))
    assert len(contiguous_words(2)) == 15


def test_ground_optimality_matrix_is_hermitian_on_a_physical_ground_state():
    sites = 6
    hamiltonian = finite_xxz(1.0, sites, periodic=False)
    _, vectors = np.linalg.eigh(hamiltonian)
    ground = vectors[:, 0]
    basis, entries = ground_optimality_matrix(Fraction(1), 1)
    numeric = np.empty((len(basis), len(basis)), dtype=complex)
    # Shift the one-site test words to bulk site 2.
    for row in range(len(basis)):
        for col in range(len(basis)):
            shifted_terms = {
                word.shifted(2): coefficient
                for word, coefficient in entries[row][col].terms.items()
            }
            matrix = polynomial_matrix(
                type(entries[row][col])(shifted_terms), sites
            )
            numeric[row, col] = np.vdot(ground, matrix @ ground)
    assert np.allclose(numeric, numeric.conj().T, atol=1e-10)
    assert np.linalg.eigvalsh(numeric)[0] > -1e-10
