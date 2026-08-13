from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import sympy as sp


@dataclass(frozen=True)
class QuadraticBasisElement:
    label: str
    kind: str
    i: int
    j: int
    fock: sp.ImmutableSparseMatrix


def _validate_mode_index(modes: int, index: int) -> None:
    if modes <= 0 or not 0 <= index < modes:
        raise ValueError("mode index must satisfy 0 <= index < modes with modes > 0")


def _occupation_sign(state: int, index: int) -> int:
    return (-1) ** ((state & ((1 << index) - 1)).bit_count())


def annihilation_operator(modes: int, index: int) -> sp.ImmutableSparseMatrix:
    _validate_mode_index(modes, index)
    dimension = 1 << modes
    entries: dict[tuple[int, int], int] = {}
    mask = 1 << index
    for source in range(dimension):
        if source & mask:
            entries[(source ^ mask, source)] = _occupation_sign(source, index)
    return sp.ImmutableSparseMatrix(dimension, dimension, entries)


def creation_operator(modes: int, index: int) -> sp.ImmutableSparseMatrix:
    _validate_mode_index(modes, index)
    dimension = 1 << modes
    entries: dict[tuple[int, int], int] = {}
    mask = 1 << index
    for source in range(dimension):
        if not source & mask:
            entries[(source | mask, source)] = _occupation_sign(source, index)
    return sp.ImmutableSparseMatrix(dimension, dimension, entries)


def parity_indices(modes: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if modes <= 0:
        raise ValueError("modes must be positive")
    even = tuple(state for state in range(1 << modes) if state.bit_count() % 2 == 0)
    odd = tuple(state for state in range(1 << modes) if state.bit_count() % 2 == 1)
    return even, odd


def quadratic_term(modes: int, kind: str, i: int, j: int) -> sp.ImmutableSparseMatrix:
    if kind == "hop":
        result = creation_operator(modes, i) * annihilation_operator(modes, j)
    elif kind == "pair_create":
        if not i < j:
            raise ValueError("pair indices must satisfy i < j")
        result = creation_operator(modes, i) * creation_operator(modes, j)
    elif kind == "pair_annihilate":
        if not i < j:
            raise ValueError("pair indices must satisfy i < j")
        result = annihilation_operator(modes, j) * annihilation_operator(modes, i)
    else:
        raise ValueError(f"unknown quadratic term kind: {kind}")
    return sp.ImmutableSparseMatrix(result)


def one_body_operator(matrix: sp.MatrixBase) -> sp.ImmutableSparseMatrix:
    if matrix.rows != matrix.cols:
        raise ValueError("one-body matrix must be square")
    modes = matrix.rows
    if modes <= 0:
        raise ValueError("one-body matrix must be nonempty")
    result = sp.zeros(1 << modes)
    for i in range(modes):
        for j in range(modes):
            result += matrix[i, j] * quadratic_term(modes, "hop", i, j)
    return sp.ImmutableSparseMatrix(result)


def exact_to_numpy(matrix: sp.MatrixBase) -> np.ndarray:
    return np.array(matrix.tolist(), dtype=float)
