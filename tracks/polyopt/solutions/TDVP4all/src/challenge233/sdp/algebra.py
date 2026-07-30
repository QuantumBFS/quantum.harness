from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
from typing import Iterable


@dataclass(frozen=True, order=True)
class GaussianRational:
    real: Fraction = Fraction(0)
    imag: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "real", Fraction(self.real))
        object.__setattr__(self, "imag", Fraction(self.imag))

    def __add__(self, other: GaussianRational) -> GaussianRational:
        if not isinstance(other, GaussianRational):
            return NotImplemented
        return GaussianRational(
            self.real + other.real,
            self.imag + other.imag,
        )

    def __sub__(self, other: GaussianRational) -> GaussianRational:
        if not isinstance(other, GaussianRational):
            return NotImplemented
        return self + (-other)

    def __neg__(self) -> GaussianRational:
        return GaussianRational(-self.real, -self.imag)

    def __mul__(self, other: GaussianRational) -> GaussianRational:
        if not isinstance(other, GaussianRational):
            return NotImplemented
        return GaussianRational(
            self.real * other.real - self.imag * other.imag,
            self.real * other.imag + self.imag * other.real,
        )

    def conjugate(self) -> GaussianRational:
        return GaussianRational(self.real, -self.imag)

    @property
    def is_zero(self) -> bool:
        return self.real == 0 and self.imag == 0


ZERO = GaussianRational()
ONE = GaussianRational(Fraction(1), Fraction(0))
NEG_ONE = GaussianRational(Fraction(-1), Fraction(0))
POS_I = GaussianRational(Fraction(0), Fraction(1))
NEG_I = GaussianRational(Fraction(0), Fraction(-1))
HALF = GaussianRational(Fraction(1, 2), Fraction(0))
NEG_HALF = GaussianRational(Fraction(-1, 2), Fraction(0))


@dataclass(frozen=True, order=True)
class PauliWord:
    factors: tuple = ()

    def __post_init__(self) -> None:
        factors = tuple(
            (int(site), str(label)) for site, label in self.factors
        )
        object.__setattr__(self, "factors", factors)
        sites = tuple(site for site, _ in factors)
        if any(site < 0 for site in sites):
            raise ValueError("site index must be non-negative")
        if sites != tuple(sorted(set(sites))):
            raise ValueError(
                "canonical PauliWord sites must be unique and sorted"
            )
        if any(label not in {"X", "Y", "Z"} for _, label in factors):
            raise ValueError(
                "canonical PauliWord labels must be X, Y, or Z"
            )


@dataclass(frozen=True)
class PauliTerm:
    coefficient: GaussianRational
    word: PauliWord


@dataclass(frozen=True)
class PauliPolynomial:
    terms: tuple = ()

    def __post_init__(self) -> None:
        combined = {}
        for word, coefficient in self.terms:
            if not isinstance(word, PauliWord):
                raise TypeError("polynomial words must be PauliWord values")
            if not isinstance(coefficient, GaussianRational):
                raise TypeError(
                    "polynomial coefficients must be GaussianRational values"
                )
            combined[word] = combined.get(word, ZERO) + coefficient
        normalized = tuple(
            (word, coefficient)
            for word, coefficient in sorted(combined.items())
            if not coefficient.is_zero
        )
        object.__setattr__(self, "terms", normalized)

    @classmethod
    def from_terms(
        cls,
        terms: Iterable,
    ) -> PauliPolynomial:
        return cls(tuple(terms))

    def __neg__(self) -> PauliPolynomial:
        return PauliPolynomial.from_terms(
            (word, -coefficient)
            for word, coefficient in self.terms
        )


_LOCAL_PRODUCT = {
    ("I", "I"): (ONE, "I"),
    ("I", "X"): (ONE, "X"),
    ("I", "Y"): (ONE, "Y"),
    ("I", "Z"): (ONE, "Z"),
    ("X", "I"): (ONE, "X"),
    ("Y", "I"): (ONE, "Y"),
    ("Z", "I"): (ONE, "Z"),
    ("X", "X"): (ONE, "I"),
    ("Y", "Y"): (ONE, "I"),
    ("Z", "Z"): (ONE, "I"),
    ("X", "Y"): (POS_I, "Z"),
    ("Y", "Z"): (POS_I, "X"),
    ("Z", "X"): (POS_I, "Y"),
    ("Y", "X"): (NEG_I, "Z"),
    ("Z", "Y"): (NEG_I, "X"),
    ("X", "Z"): (NEG_I, "Y"),
}


def canonicalize_word(factors: Iterable) -> PauliTerm:
    phase = ONE
    local = {}
    for site, label in factors:
        site = int(site)
        label = str(label)
        if site < 0:
            raise ValueError("site index must be non-negative")
        if label not in {"I", "X", "Y", "Z"}:
            raise ValueError(f"non-Pauli label in canonicalizer: {label}")
        previous = local.get(site, "I")
        local_phase, result = _LOCAL_PRODUCT[(previous, label)]
        phase = phase * local_phase
        if result == "I":
            local.pop(site, None)
        else:
            local[site] = result
    return PauliTerm(
        phase,
        PauliWord(tuple(sorted(local.items()))),
    )


def polynomial_from_word(word: PauliWord) -> PauliPolynomial:
    if not isinstance(word, PauliWord):
        raise TypeError("word must be a PauliWord")
    return PauliPolynomial(((word, ONE),))


def add_polynomials(*values: PauliPolynomial) -> PauliPolynomial:
    return PauliPolynomial.from_terms(
        term
        for value in values
        for term in value.terms
    )


def scale_polynomial(
    coefficient: GaussianRational,
    value: PauliPolynomial,
) -> PauliPolynomial:
    if not isinstance(coefficient, GaussianRational):
        raise TypeError("coefficient must be GaussianRational")
    return PauliPolynomial.from_terms(
        (word, coefficient * word_coefficient)
        for word, word_coefficient in value.terms
    )


def multiply_polynomials(
    left: PauliPolynomial,
    right: PauliPolynomial,
) -> PauliPolynomial:
    products = []
    for left_word, left_coefficient in left.terms:
        for right_word, right_coefficient in right.terms:
            canonical = canonicalize_word(
                left_word.factors + right_word.factors
            )
            products.append(
                (
                    canonical.word,
                    left_coefficient
                    * right_coefficient
                    * canonical.coefficient,
                )
            )
    return PauliPolynomial.from_terms(products)


def adjoint_polynomial(value: PauliPolynomial) -> PauliPolynomial:
    return PauliPolynomial.from_terms(
        (word, coefficient.conjugate())
        for word, coefficient in value.terms
    )


def _factor_polynomial(site: int, label: str) -> PauliPolynomial:
    if label == "I":
        return polynomial_from_word(PauliWord())
    if label in {"X", "Y", "Z"}:
        return polynomial_from_word(PauliWord(((site, label),)))
    identity = polynomial_from_word(PauliWord())
    z_operator = polynomial_from_word(PauliWord(((site, "Z"),)))
    if label == "P":
        return add_polynomials(
            scale_polynomial(HALF, identity),
            scale_polynomial(NEG_HALF, z_operator),
        )
    if label == "n":
        return add_polynomials(
            scale_polynomial(HALF, identity),
            scale_polynomial(HALF, z_operator),
        )
    raise ValueError(f"unknown operator label: {label}")


def expand_word(factors: Iterable) -> PauliPolynomial:
    result = polynomial_from_word(PauliWord())
    for site, label in factors:
        result = multiply_polynomials(
            result,
            _factor_polynomial(int(site), str(label)),
        )
    return result


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def canonical_relation_table_json() -> str:
    local_products = {}
    for (left, right), (phase, result) in sorted(
        _LOCAL_PRODUCT.items()
    ):
        local_products[f"{left},{right}"] = {
            "phase": {
                "real": _fraction_text(phase.real),
                "imag": _fraction_text(phase.imag),
            },
            "result": result,
        }
    payload = {
        "definitions": {
            "P": "(I-Z)/2",
            "Y": "iXZ",
            "n": "(I+Z)/2",
        },
        "different_site": "commute",
        "local_products": local_products,
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
