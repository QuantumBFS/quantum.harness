from __future__ import annotations

from itertools import product

import sympy as sp

from .algebra import commutator
from .hamiltonian import four_matching_fragments
from .lattice import SquareLattice


def degree_three_four_matching_rank(length: int = 4) -> tuple[int, int, int]:
    """Exact rational rank of all ``[Ha,[Hb,Hc]]`` operator images."""

    lattice = SquareLattice(length)
    fragments = four_matching_fragments(lattice)
    keys = tuple(product(range(4), repeat=3))
    operators = tuple(
        commutator(
            fragments[first],
            commutator(fragments[second], fragments[third]),
        )
        for first, second, third in keys
    )
    paulis = tuple(sorted(set().union(*(operator.terms for operator in operators))))
    row = {pauli: index for index, pauli in enumerate(paulis)}
    matrix = sp.MutableSparseMatrix(len(paulis), len(keys), {})
    for column, operator in enumerate(operators):
        for pauli, coefficient in operator.terms.items():
            if coefficient.imag:
                raise ArithmeticError("degree-three image should be Hermitian")
            matrix[row[pauli], column] = sp.Rational(
                coefficient.real.numerator,
                coefficient.real.denominator,
            )
    return int(matrix.rank()), len(keys), len(paulis)
