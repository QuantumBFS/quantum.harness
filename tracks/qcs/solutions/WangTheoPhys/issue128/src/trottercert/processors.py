from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import sqrt
from typing import Sequence

import sympy as sp

from .algebra import PauliString, PauliSum, QComplex, commutator
from .hamiltonian import full_heisenberg_hamiltonian, heisenberg_bond
from .lattice import SquareLattice


def spin_chirality(u: int, v: int, w: int) -> PauliSum:
    """Return chi(u,v,w) with [h_uv,h_vw] = -i chi(u,v,w)."""

    return commutator(heisenberg_bond(u, v), heisenberg_bond(v, w)).scale(
        QComplex(0, 1)
    )


def global_chirality_color_basis(
    lattice: SquareLattice,
) -> tuple[tuple[tuple[int, int], PauliSum], ...]:
    """Sums of oriented path chiralities grouped by matching colors.

    Only color pairs ``a < b`` are retained because reversing the path
    orientation changes the sign.
    """

    matchings = lattice.four_matchings()
    neighbor: dict[tuple[int, int], int] = {}
    for color, edges in enumerate(matchings):
        for u, v in edges:
            neighbor[(u, color)] = v
            neighbor[(v, color)] = u
    result: list[tuple[tuple[int, int], PauliSum]] = []
    for first in range(4):
        for second in range(first + 1, 4):
            operator = PauliSum.zero()
            for center in range(lattice.n_sites):
                operator += spin_chirality(
                    neighbor[(center, first)],
                    center,
                    neighbor[(center, second)],
                )
            result.append(((first, second), operator))
    return tuple(result)


def processor_images(
    hamiltonian: PauliSum,
    basis: Sequence[PauliSum],
) -> tuple[PauliSum, ...]:
    """Return i[Q_a,H], a Hermitian operator for every Hermitian Q_a."""

    images = tuple(
        commutator(operator, hamiltonian).scale(QComplex(0, 1))
        for operator in basis
    )
    if not all(image.is_hermitian() for image in images):
        raise ArithmeticError("processor image is not Hermitian")
    return images


@dataclass(frozen=True)
class ProcessorObstruction:
    coefficients: tuple[Fraction, ...]
    residual: PauliSum
    target_l2: float
    residual_l2: float
    exact_solution: bool

    @property
    def relative_l2(self) -> float:
        return self.residual_l2 / self.target_l2 if self.target_l2 else 0.0


def _real_coefficient(operator: PauliSum, pauli: PauliString) -> Fraction:
    coefficient = operator.terms.get(pauli, QComplex())
    if coefficient.imag:
        raise ValueError("processor projection requires Hermitian real Pauli coefficients")
    return coefficient.real


def solve_processor_obstruction(
    target: PauliSum,
    images: Sequence[PauliSum],
) -> ProcessorObstruction:
    """Project ``-target`` onto the exact rational span of processor images.

    The projection metric is the Hilbert--Schmidt/Pauli coefficient
    Euclidean metric. It is used only to diagnose the algebraic obstruction,
    not as an operator-norm certificate.
    """

    paulis = sorted(
        set(target.terms).union(*(set(image.terms) for image in images))
    )
    columns = len(images)
    gram = [[Fraction() for _ in range(columns)] for _ in range(columns)]
    rhs = [Fraction() for _ in range(columns)]
    for pauli in paulis:
        row = [_real_coefficient(image, pauli) for image in images]
        target_value = _real_coefficient(target, pauli)
        for left in range(columns):
            rhs[left] -= row[left] * target_value
            for right in range(columns):
                gram[left][right] += row[left] * row[right]

    matrix = sp.Matrix(
        [[sp.Rational(value.numerator, value.denominator) for value in row] for row in gram]
    )
    vector = sp.Matrix(
        [sp.Rational(value.numerator, value.denominator) for value in rhs]
    )
    solution_set = sp.linsolve((matrix, vector))
    solution_tuple = next(iter(solution_set), ())
    if not solution_tuple:
        coefficients = tuple(Fraction() for _ in images)
    else:
        substitutions = {
            symbol: sp.Integer(0)
            for expression in solution_tuple
            for symbol in expression.free_symbols
        }
        coefficients = tuple(
            Fraction(int(value.p), int(value.q))
            for expression in solution_tuple
            for value in [sp.cancel(expression.subs(substitutions))]
        )

    residual = target.copy()
    for coefficient, image in zip(coefficients, images):
        residual += image.scale(coefficient)

    def squared_l2(operator: PauliSum) -> Fraction:
        total = Fraction()
        for coefficient in operator.terms.values():
            if coefficient.imag:
                total += coefficient.real**2 + coefficient.imag**2
            else:
                total += coefficient.real**2
        return total

    target_l2 = sqrt(float(squared_l2(target)))
    residual_l2 = sqrt(float(squared_l2(residual)))
    return ProcessorObstruction(
        coefficients=coefficients,
        residual=residual,
        target_l2=target_l2,
        residual_l2=residual_l2,
        exact_solution=not residual,
    )


def heisenberg_color_processor_obstruction(
    lattice: SquareLattice,
    target: PauliSum,
) -> tuple[tuple[tuple[int, int], ...], ProcessorObstruction]:
    labeled = global_chirality_color_basis(lattice)
    labels = tuple(label for label, _ in labeled)
    basis = tuple(operator for _, operator in labeled)
    images = processor_images(full_heisenberg_hamiltonian(lattice), basis)
    return labels, solve_processor_obstruction(target, images)
