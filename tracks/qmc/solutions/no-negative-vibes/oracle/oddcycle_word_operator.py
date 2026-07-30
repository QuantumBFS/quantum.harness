"""Exact normal-ordered coordinates for number-conserving Fock operators."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import combinations, product

import sympy as sp

from oracle.exterior_inverse_hs import exact_gaussian_fock_lift
from oracle.fock_basis import annihilation_operator, creation_operator
from oracle.oddcycle_pair_physical import leading_pair_matrices


TRANSPOSE_SYMBOL = (1, 0, 3, 2)


@dataclass(frozen=True, order=True)
class NormalOrderedLabel:
    """A number-conserving monomial ``c†_create c_annihilate`` label."""

    create: tuple[int, ...]
    annihilate: tuple[int, ...]

    @property
    def body_order(self) -> int:
        return len(self.create)

    @property
    def support(self) -> frozenset[int]:
        return frozenset((*self.create, *self.annihilate))


@dataclass(frozen=True)
class WordPairColumn:
    """One transpose-paired same-alphabet word ray."""

    word: tuple[int, ...]
    transpose_word: tuple[int, ...]
    matrix_orbit_key: tuple[tuple[int, int], ...]
    fock_pair: sp.ImmutableMatrix
    coordinates: Mapping[NormalOrderedLabel, sp.Expr]


def _validate_modes(modes: int) -> None:
    if not isinstance(modes, int) or isinstance(modes, bool) or modes <= 0:
        raise ValueError("modes must be a positive integer")


def _validate_label(label: NormalOrderedLabel, modes: int) -> None:
    if not isinstance(label, NormalOrderedLabel):
        raise TypeError("label must be a NormalOrderedLabel")
    if len(label.create) != len(label.annihilate):
        raise ValueError("creation and annihilation orders must agree")
    for indices in (label.create, label.annihilate):
        if any(not isinstance(index, int) or isinstance(index, bool) for index in indices):
            raise TypeError("label indices must be integers")
        if tuple(sorted(indices)) != indices or len(set(indices)) != len(indices):
            raise ValueError("label indices must be sorted and unique")
        if any(index < 0 or index >= modes for index in indices):
            raise ValueError("label indices must lie in the requested modes")


@cache
def normal_ordered_labels(modes: int) -> tuple[NormalOrderedLabel, ...]:
    """Return the complete normal-ordered number-conserving basis."""

    _validate_modes(modes)
    return tuple(
        NormalOrderedLabel(create, annihilate)
        for order in range(modes + 1)
        for create in combinations(range(modes), order)
        for annihilate in combinations(range(modes), order)
    )


@cache
def normal_ordered_monomial(
    modes: int, label: NormalOrderedLabel
) -> sp.ImmutableSparseMatrix:
    """Construct one CAR normal-ordered monomial exactly."""

    _validate_modes(modes)
    _validate_label(label, modes)
    result = sp.eye(1 << modes)
    for index in label.create:
        result *= creation_operator(modes, index)
    for index in reversed(label.annihilate):
        result *= annihilation_operator(modes, index)
    return sp.ImmutableSparseMatrix(result)


def normal_ordered_coordinates(
    operator: sp.MatrixBase, modes: int
) -> dict[NormalOrderedLabel, sp.Expr]:
    """Compile an operator into the ascending-sector normal-ordered basis."""

    _validate_modes(modes)
    dimension = 1 << modes
    if not isinstance(operator, sp.MatrixBase) or operator.shape != (dimension, dimension):
        raise ValueError("operator has the wrong Fock dimension")
    residual = sp.MutableSparseMatrix(operator)
    coordinates: dict[NormalOrderedLabel, sp.Expr] = {}
    for label in normal_ordered_labels(modes):
        monomial = normal_ordered_monomial(modes, label)
        row = sum(1 << index for index in label.create)
        column = sum(1 << index for index in label.annihilate)
        pivot = monomial[row, column]
        if pivot not in (-1, 1):
            raise ArithmeticError("normal-ordered pivot is not a unit")
        coefficient = sp.cancel(residual[row, column] / pivot)
        coordinates[label] = coefficient
        if coefficient:
            residual -= coefficient * monomial
    if residual != sp.zeros(dimension):
        raise ArithmeticError("normal-ordered reconstruction left a residual")
    return coordinates


def reconstruct_normal_ordered(
    coordinates: Mapping[NormalOrderedLabel, sp.Expr], modes: int
) -> sp.ImmutableSparseMatrix:
    """Reconstruct an exact Fock operator from normal-ordered coordinates."""

    _validate_modes(modes)
    if not isinstance(coordinates, Mapping):
        raise TypeError("coordinates must be a mapping")
    result = sp.zeros(1 << modes)
    for label, coefficient in coordinates.items():
        _validate_label(label, modes)
        result += coefficient * normal_ordered_monomial(modes, label)
    return sp.ImmutableSparseMatrix(result)


def leading_oddcycle_letters() -> tuple[sp.ImmutableMatrix, ...]:
    """Return the exact four-letter leading odd-cycle alphabet."""

    b0, b1 = leading_pair_matrices()
    return b0, b0.T, b1, b1.T


def transpose_word(word: Sequence[int]) -> tuple[int, ...]:
    """Return the word representing the transpose one-particle product."""

    normalized = tuple(word)
    if any(symbol not in range(4) for symbol in normalized):
        raise ValueError("word symbols must be in 0,1,2,3")
    return tuple(TRANSPOSE_SYMBOL[symbol] for symbol in reversed(normalized))


def word_matrix(word: Sequence[int]) -> sp.ImmutableMatrix:
    """Return the exact one-particle product represented by ``word``."""

    letters = leading_oddcycle_letters()
    product_matrix = sp.eye(5)
    for symbol in tuple(word):
        product_matrix = letters[symbol] * product_matrix
    return sp.ImmutableMatrix(product_matrix)


def _rational_matrix_key(matrix: sp.MatrixBase) -> tuple[tuple[int, int], ...]:
    result = []
    for value in matrix:
        rational = sp.Rational(value)
        result.append((int(rational.p), int(rational.q)))
    return tuple(result)


def build_word_dictionary(max_length: int) -> tuple[WordPairColumn, ...]:
    """Enumerate transpose-paired word rays through ``max_length`` exactly."""

    if not isinstance(max_length, int) or isinstance(max_length, bool) or max_length < 0:
        raise ValueError("max_length must be a nonnegative integer")

    columns = []
    seen_matrix_orbits = set()
    for length in range(1, max_length + 1):
        for word in product(range(4), repeat=length):
            transposed = transpose_word(word)
            if word > transposed:
                continue
            matrix = word_matrix(word)
            matrix_orbit_key = min(
                _rational_matrix_key(matrix),
                _rational_matrix_key(matrix.T),
            )
            if matrix_orbit_key in seen_matrix_orbits:
                continue
            seen_matrix_orbits.add(matrix_orbit_key)
            fock_pair = sp.ImmutableSparseMatrix(
                exact_gaussian_fock_lift(matrix)
                + exact_gaussian_fock_lift(matrix.T)
            )
            columns.append(
                WordPairColumn(
                    word=word,
                    transpose_word=transposed,
                    matrix_orbit_key=matrix_orbit_key,
                    fock_pair=fock_pair,
                    coordinates=normal_ordered_coordinates(fock_pair, 5),
                )
            )
    return tuple(columns)


__all__ = [
    "NormalOrderedLabel",
    "TRANSPOSE_SYMBOL",
    "WordPairColumn",
    "build_word_dictionary",
    "leading_oddcycle_letters",
    "normal_ordered_coordinates",
    "normal_ordered_labels",
    "normal_ordered_monomial",
    "reconstruct_normal_ordered",
    "transpose_word",
    "word_matrix",
]
