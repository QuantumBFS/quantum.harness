"""Exact finite-support Pauli algebra for infinite-chain local constraints."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class GaussianFraction:
    real: Fraction = Fraction(0)
    imag: Fraction = Fraction(0)

    def __add__(self, other: "GaussianFraction") -> "GaussianFraction":
        return GaussianFraction(self.real + other.real, self.imag + other.imag)

    def __neg__(self) -> "GaussianFraction":
        return GaussianFraction(-self.real, -self.imag)

    def __sub__(self, other: "GaussianFraction") -> "GaussianFraction":
        return self + (-other)

    def __mul__(
        self, other: "GaussianFraction | Fraction | int"
    ) -> "GaussianFraction":
        if not isinstance(other, GaussianFraction):
            other = GaussianFraction(Fraction(other))
        return GaussianFraction(
            self.real * other.real - self.imag * other.imag,
            self.real * other.imag + self.imag * other.real,
        )

    __rmul__ = __mul__

    def conjugate(self) -> "GaussianFraction":
        return GaussianFraction(self.real, -self.imag)

    def as_complex(self) -> complex:
        return complex(float(self.real), float(self.imag))

    @property
    def is_zero(self) -> bool:
        return self.real == 0 and self.imag == 0


ONE = GaussianFraction(Fraction(1))
I = GaussianFraction(Fraction(0), Fraction(1))
MINUS_I = GaussianFraction(Fraction(0), Fraction(-1))

_SAME_SITE: dict[tuple[str, str], tuple[GaussianFraction, str | None]] = {
    ("X", "Y"): (I, "Z"),
    ("Y", "X"): (MINUS_I, "Z"),
    ("Y", "Z"): (I, "X"),
    ("Z", "Y"): (MINUS_I, "X"),
    ("Z", "X"): (I, "Y"),
    ("X", "Z"): (MINUS_I, "Y"),
}


@dataclass(frozen=True, order=True)
class PauliWord:
    """Canonical Pauli word as sorted nonidentity site-letter pairs."""

    operators: tuple[tuple[int, str], ...] = ()

    def __post_init__(self) -> None:
        sites = [site for site, _ in self.operators]
        if sites != sorted(sites) or len(set(sites)) != len(sites):
            raise ValueError("operators must have unique sorted sites")
        if any(letter not in {"X", "Y", "Z"} for _, letter in self.operators):
            raise ValueError("invalid Pauli letter")

    @classmethod
    def from_dict(cls, operators: dict[int, str]) -> "PauliWord":
        return cls(tuple(sorted((site, letter) for site, letter in operators.items())))

    @property
    def support(self) -> frozenset[int]:
        return frozenset(site for site, _ in self.operators)

    def shifted(self, amount: int) -> "PauliWord":
        return PauliWord(tuple((site + amount, letter) for site, letter in self.operators))

    def dagger(self) -> "PauliWord":
        return self

    def multiply(self, other: "PauliWord") -> tuple[GaussianFraction, "PauliWord"]:
        left = dict(self.operators)
        phase = ONE
        for site, right_letter in other.operators:
            left_letter = left.get(site)
            if left_letter is None:
                left[site] = right_letter
            elif left_letter == right_letter:
                del left[site]
            else:
                factor, result = _SAME_SITE[(left_letter, right_letter)]
                phase = phase * factor
                left[site] = result  # type: ignore[assignment]
        return phase, PauliWord.from_dict(left)


class PauliPolynomial:
    def __init__(
        self, terms: dict[PauliWord, GaussianFraction] | None = None
    ) -> None:
        self.terms = {
            word: coefficient
            for word, coefficient in (terms or {}).items()
            if not coefficient.is_zero
        }

    @property
    def support(self) -> frozenset[int]:
        return frozenset().union(*(word.support for word in self.terms))

    def add_term(self, word: PauliWord, coefficient: GaussianFraction) -> None:
        updated = self.terms.get(word, GaussianFraction()) + coefficient
        if updated.is_zero:
            self.terms.pop(word, None)
        else:
            self.terms[word] = updated

    def __add__(self, other: "PauliPolynomial") -> "PauliPolynomial":
        result = PauliPolynomial(dict(self.terms))
        for word, coefficient in other.terms.items():
            result.add_term(word, coefficient)
        return result

    def __mul__(self, other: "PauliPolynomial") -> "PauliPolynomial":
        result = PauliPolynomial()
        for left, left_coefficient in self.terms.items():
            for right, right_coefficient in other.terms.items():
                phase, word = left.multiply(right)
                result.add_term(
                    word, left_coefficient * right_coefficient * phase
                )
        return result

    def scaled(self, scalar: GaussianFraction | Fraction | int) -> "PauliPolynomial":
        if not isinstance(scalar, GaussianFraction):
            scalar = GaussianFraction(Fraction(scalar))
        return PauliPolynomial(
            {word: scalar * coefficient for word, coefficient in self.terms.items()}
        )


def word_polynomial(word: PauliWord, coefficient: Fraction = Fraction(1)) -> PauliPolynomial:
    return PauliPolynomial({word: GaussianFraction(coefficient)})


def local_derivation(delta: Fraction, word: PauliWord) -> PauliPolynomial:
    """Return [sum_i h_i, word], whose support is finite for local ``word``."""
    if not word.support:
        return PauliPolynomial()
    result = PauliPolynomial()
    first = min(word.support) - 1
    last = max(word.support)
    for bond in range(first, last + 1):
        if not ({bond, bond + 1} & set(word.support)):
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
            target = word_polynomial(word)
            commutator = interaction * target + (target * interaction).scaled(-1)
            result = result + commutator
    return result


def polynomial_matrix(
    polynomial: PauliPolynomial, sites: int, origin: int = 0
) -> np.ndarray:
    """Represent a local polynomial on sites ``origin..origin+sites-1``."""
    paulis = {
        "I": np.eye(2, dtype=complex),
        "X": np.array([[0, 1], [1, 0]], dtype=complex),
        "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
        "Z": np.array([[1, 0], [0, -1]], dtype=complex),
    }
    result = np.zeros((1 << sites, 1 << sites), dtype=complex)
    for word, coefficient in polynomial.terms.items():
        mapping = dict(word.operators)
        factors = []
        for site in range(origin, origin + sites):
            factors.append(paulis[mapping.get(site, "I")])
        matrix = factors[0]
        for factor in factors[1:]:
            matrix = np.kron(matrix, factor)
        result += coefficient.as_complex() * matrix
    return result
