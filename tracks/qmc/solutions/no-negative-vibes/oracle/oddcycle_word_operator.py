"""Exact normal-ordered coordinates for number-conserving Fock operators."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from itertools import combinations

import sympy as sp

from oracle.fock_basis import annihilation_operator, creation_operator


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


__all__ = [
    "NormalOrderedLabel",
    "normal_ordered_coordinates",
    "normal_ordered_labels",
    "normal_ordered_monomial",
    "reconstruct_normal_ordered",
]
