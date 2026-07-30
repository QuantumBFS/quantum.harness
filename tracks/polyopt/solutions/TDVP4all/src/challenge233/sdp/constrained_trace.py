"""Exact Pauli traces on the periodic blockade-constrained subspace."""

from __future__ import annotations

from fractions import Fraction

from challenge233.sdp.algebra import (
    GaussianRational,
    PauliPolynomial,
    PauliWord,
)


def _validate_size(size: int) -> int:
    size = int(size)
    if size < 1:
        raise ValueError("trace size must be positive")
    return size


def _z_cycle_sum(size: int, z_sites: frozenset[int]) -> int:
    total = 0
    for first in (0, 1):
        initial_weight = (
            (1 if first else -1)
            if 0 in z_sites
            else 1
        )
        states = {(first, first): initial_weight}
        for site in range(1, size):
            next_states = {}
            for (fixed_first, previous), weight in states.items():
                for bit in (0, 1):
                    if previous and bit:
                        continue
                    factor = (
                        (1 if bit else -1)
                        if site in z_sites
                        else 1
                    )
                    key = (fixed_first, bit)
                    next_states[key] = (
                        next_states.get(key, 0)
                        + weight * factor
                    )
            states = next_states
        total += sum(
            weight
            for (fixed_first, final), weight in states.items()
            if not (fixed_first and final)
        )
    return total


def periodic_blockade_dimension(size: int) -> int:
    """Return the Lucas-number dimension of the periodic legal basis."""
    size = _validate_size(size)
    return _z_cycle_sum(size, frozenset())


def constrained_pauli_trace(size: int, word: PauliWord) -> int:
    """Return ``Tr(Π_K word)`` without constructing ``Π_K``."""
    size = _validate_size(size)
    if not isinstance(word, PauliWord):
        raise TypeError("word must be a PauliWord")
    if any(not 0 <= site < size for site, _ in word.factors):
        raise ValueError("Pauli-word site must lie in range(size)")
    if any(label in {"X", "Y"} for _, label in word.factors):
        return 0
    z_sites = frozenset(
        site
        for site, label in word.factors
        if label == "Z"
    )
    return _z_cycle_sum(size, z_sites)


def constrained_polynomial_trace(
    size: int,
    polynomial: PauliPolynomial,
) -> GaussianRational:
    """Return the exact Gaussian-rational trace of a Pauli polynomial."""
    size = _validate_size(size)
    if not isinstance(polynomial, PauliPolynomial):
        raise TypeError("polynomial must be a PauliPolynomial")
    total = GaussianRational()
    for word, coefficient in polynomial.terms:
        trace = GaussianRational(
            Fraction(constrained_pauli_trace(size, word)),
            Fraction(0),
        )
        total = total + coefficient * trace
    return total
