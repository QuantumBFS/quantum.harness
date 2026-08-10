"""Finite-support stationarity constraints for infinite XXZ ground states."""

from __future__ import annotations

from fractions import Fraction
from itertools import product

from .pauli_words import (
    PauliPolynomial,
    PauliWord,
    local_derivation,
    word_polynomial,
)


def contiguous_words(radius: int, max_weight: int | None = None) -> list[PauliWord]:
    if radius < 1:
        raise ValueError("radius must be positive")
    if max_weight is None:
        max_weight = radius
    words: list[PauliWord] = []
    for letters in product(("I", "X", "Y", "Z"), repeat=radius):
        operators = {
            site: letter for site, letter in enumerate(letters) if letter != "I"
        }
        if not operators or len(operators) > max_weight:
            continue
        words.append(PauliWord.from_dict(operators))
    return words


def stationarity_constraints(
    delta: Fraction, radius: int, max_weight: int | None = None
) -> list[PauliPolynomial]:
    """Return exact local polynomials whose ground-state expectation is zero."""
    constraints: list[PauliPolynomial] = []
    seen: set[tuple] = set()
    for word in contiguous_words(radius, max_weight):
        polynomial = local_derivation(delta, word)
        key = tuple(sorted(polynomial.terms.items()))
        if polynomial.terms and key not in seen:
            seen.add(key)
            constraints.append(polynomial)
    return constraints


def ground_optimality_entry(
    delta: Fraction, left: PauliWord, right: PauliWord
) -> PauliPolynomial:
    """Local matrix entry for the ground-state second-variation condition.

    This is

    ``left H right - (H right left + right left H)/2``.

    Terms of the formal infinite Hamiltonian outside the union of the two
    word supports commute and cancel, leaving a finite polynomial.
    """
    support = set(left.support | right.support)
    if not support:
        return PauliPolynomial()
    result = PauliPolynomial()
    first = min(support) - 1
    last = max(support)
    for bond in range(first, last + 1):
        if not ({bond, bond + 1} & support):
            continue
        for letter, coefficient in (
            ("X", Fraction(1, 4)),
            ("Y", Fraction(1, 4)),
            ("Z", delta / 4),
        ):
            interaction = word_polynomial(
                PauliWord.from_dict({bond: letter, bond + 1: letter}),
                coefficient,
            )
            left_poly = word_polynomial(left)
            right_poly = word_polynomial(right)
            result = result + left_poly * interaction * right_poly
            result = result + (interaction * right_poly * left_poly).scaled(
                Fraction(-1, 2)
            )
            result = result + (right_poly * left_poly * interaction).scaled(
                Fraction(-1, 2)
            )
    return result


def ground_optimality_matrix(
    delta: Fraction, radius: int, max_weight: int = 1
) -> tuple[list[PauliWord], list[list[PauliPolynomial]]]:
    basis = contiguous_words(radius, max_weight)
    entries = [
        [ground_optimality_entry(delta, left, right) for right in basis]
        for left in basis
    ]
    return basis, entries
