"""Sound blockade-support localizers for Ky Fan effect moments."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from challenge233.sdp.algebra import (
    PauliPolynomial,
    PauliWord,
    adjoint_polynomial,
    expand_word,
    multiply_polynomials,
    polynomial_from_word,
)
from challenge233.sdp.constraints import blockade_polynomial


SAFE_LABELS = frozenset({"F", "Z", "P", "n"})


@dataclass(frozen=True, order=True)
class SafeWord:
    """Ordered product of operators that preserve the blockade subspace."""

    factors: tuple = ()

    def __post_init__(self) -> None:
        normalized = tuple(
            (int(site), str(label))
            for site, label in self.factors
        )
        if any(label not in SAFE_LABELS for _, label in normalized):
            raise ValueError("safe words use only F, Z, P, and n")
        object.__setattr__(self, "factors", normalized)


@dataclass(frozen=True)
class SupportLocalizer:
    """One-sided support equation ``a C_i = 0`` or ``C_i a = 0``."""

    site: int
    side: str
    test_index: int
    polynomial: PauliPolynomial


@dataclass(frozen=True)
class SandwichLocalizer:
    """Safe equation ``u† C_i v = 0`` with blockade-preserving u and v."""

    site: int
    row: int
    column: int
    polynomial: PauliPolynomial


def _validate_size(size: int) -> int:
    size = int(size)
    if size < 4:
        raise ValueError("localizer size must be at least 4")
    return size


def _validate_sites(sites, size: int) -> tuple[int, ...]:
    normalized = tuple(int(site) for site in sites)
    if len(set(normalized)) != len(normalized):
        raise ValueError("localizer sites must be unique")
    if any(not 0 <= site < size for site in normalized):
        raise ValueError("localizer site must lie in range(size)")
    return normalized


def _safe_factor(site: int, label: str, size: int) -> PauliPolynomial:
    site %= size
    if label == "F":
        return expand_word(
            (
                ((site - 1) % size, "P"),
                (site, "X"),
                ((site + 1) % size, "P"),
            )
        )
    return expand_word(((site, label),))


def expand_safe_word(word: SafeWord, size: int) -> PauliPolynomial:
    """Expand a typed blockade-preserving word into exact Pauli form."""
    if not isinstance(word, SafeWord):
        raise TypeError("word must be a SafeWord")
    size = _validate_size(size)
    result = polynomial_from_word(PauliWord())
    for site, label in word.factors:
        result = multiply_polynomials(
            result,
            _safe_factor(site, label, size),
        )
    return result


@lru_cache(maxsize=200_000)
def _multiply_cached(
    left: PauliPolynomial,
    right: PauliPolynomial,
) -> PauliPolynomial:
    return multiply_polynomials(left, right)


def build_support_localizers(
    size: int,
    test_basis,
    sites,
) -> tuple[SupportLocalizer, ...]:
    """Build all sound one-sided rows for arbitrary Pauli test words."""
    size = _validate_size(size)
    basis = tuple(test_basis)
    if any(not isinstance(word, PauliWord) for word in basis):
        raise TypeError("support test basis must contain PauliWord values")
    for word in basis:
        if any(not 0 <= site < size for site, _ in word.factors):
            raise ValueError("support test site must lie in range(size)")
    selected_sites = _validate_sites(sites, size)

    tests = tuple(polynomial_from_word(word) for word in basis)
    rows = []
    for site in selected_sites:
        blockade = blockade_polynomial(site, size)
        for test_index, test in enumerate(tests):
            rows.append(
                SupportLocalizer(
                    site=site,
                    side="left",
                    test_index=test_index,
                    polynomial=multiply_polynomials(
                        blockade,
                        test,
                    ),
                )
            )
            rows.append(
                SupportLocalizer(
                    site=site,
                    side="right",
                    test_index=test_index,
                    polynomial=multiply_polynomials(
                        test,
                        blockade,
                    ),
                )
            )
    return tuple(rows)


def build_safe_sandwich_localizers(
    size: int,
    safe_basis,
    sites,
) -> tuple[SandwichLocalizer, ...]:
    """Build the Hermitian upper triangle of each safe zero matrix."""
    size = _validate_size(size)
    basis = tuple(safe_basis)
    if any(not isinstance(word, SafeWord) for word in basis):
        raise TypeError("safe sandwich basis must contain SafeWord values")
    selected_sites = _validate_sites(sites, size)
    expanded = tuple(expand_safe_word(word, size) for word in basis)
    adjoints = tuple(adjoint_polynomial(value) for value in expanded)
    rows = []
    for site in selected_sites:
        blockade = blockade_polynomial(site, size)
        left_products = tuple(
            _multiply_cached(adjoint, blockade)
            for adjoint in adjoints
        )
        for row, left in enumerate(left_products):
            for column in range(row, len(basis)):
                rows.append(
                    SandwichLocalizer(
                        site=site,
                        row=row,
                        column=column,
                        polynomial=_multiply_cached(
                            left,
                            expanded[column],
                        ),
                    )
                )
    return tuple(rows)
