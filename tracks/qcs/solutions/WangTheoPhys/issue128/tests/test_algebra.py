from fractions import Fraction

import numpy as np

from trottercert.algebra import (
    PauliString,
    PauliSum,
    QComplex,
    commutator,
    to_dense,
    pauli_strings_commute,
)


def term(site: int, op: str) -> PauliSum:
    return PauliSum.term(PauliString({site: op}))


def test_single_qubit_pauli_phase_table() -> None:
    x, y, z = term(0, "X"), term(0, "Y"), term(0, "Z")
    assert x * y == z.scale(QComplex(0, 1))
    assert y * x == z.scale(QComplex(0, -1))
    assert commutator(x, y) == z.scale(QComplex(0, 2))
    assert not pauli_strings_commute(PauliString({0: "X"}), PauliString({0: "Y"}))
    assert pauli_strings_commute(PauliString({0: "X"}), PauliString({1: "Y"}))


def test_multiqubit_multiplication_and_merging() -> None:
    xx = PauliSum.term(PauliString({0: "X", 2: "X"}), Fraction(1, 4))
    yy = PauliSum.term(PauliString({0: "Y", 2: "Y"}), Fraction(1, 4))
    product = xx * yy
    assert product == PauliSum.term(PauliString({0: "Z", 2: "Z"}), Fraction(-1, 16))
    assert xx - xx == PauliSum.zero()


def test_dense_agrees_with_exact_algebra() -> None:
    left = term(0, "X") + term(1, "Z").scale(Fraction(2, 3))
    right = term(0, "Y") * term(1, "X")
    expected = to_dense(left, 2) @ to_dense(right, 2)
    assert np.allclose(to_dense(left * right, 2), expected)


def test_dagger_and_l1() -> None:
    op = PauliSum.term(PauliString({0: "X"}), QComplex(Fraction(1, 2), Fraction(1, 3)))
    assert op.dagger().terms[PauliString({0: "X"})] == QComplex(
        Fraction(1, 2), Fraction(-1, 3)
    )
    assert np.isclose(op.pauli_l1(), np.hypot(0.5, 1 / 3))
