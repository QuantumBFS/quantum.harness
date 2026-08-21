from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import scipy.sparse as sp

IRREPS = ("A1", "A2", "B1", "B2", "E")
IRREP_DIMS = {"A1": 1, "A2": 1, "B1": 1, "B2": 1, "E": 2}
CHARACTERS = {
    "A1": {"e": 1, "r2": 1, "r": 1, "axis": 1, "diag": 1},
    "A2": {"e": 1, "r2": 1, "r": 1, "axis": -1, "diag": -1},
    "B1": {"e": 1, "r2": 1, "r": -1, "axis": 1, "diag": -1},
    "B2": {"e": 1, "r2": 1, "r": -1, "axis": -1, "diag": 1},
    "E": {"e": 2, "r2": -2, "r": 0, "axis": 0, "diag": 0},
}


@dataclass(frozen=True)
class D4Element:
    name: str
    character_class: str
    permutation: tuple[int, ...]


@dataclass(frozen=True)
class SectorBasis:
    q: sp.csr_matrix
    spectral_multiplicity: int
    recovered_dimension: int


def d4_elements(l: int) -> tuple[D4Element, ...]:
    transforms: tuple[tuple[str, str, Callable[[int, int], tuple[int, int]]], ...] = (
        ("e", "e", lambda x, y: (x, y)),
        ("r90", "r", lambda x, y: (y, l - 1 - x)),
        ("r180", "r2", lambda x, y: (l - 1 - x, l - 1 - y)),
        ("r270", "r", lambda x, y: (l - 1 - y, x)),
        ("axis_x", "axis", lambda x, y: (l - 1 - x, y)),
        ("axis_y", "axis", lambda x, y: (x, l - 1 - y)),
        ("diag_main", "diag", lambda x, y: (y, x)),
        ("diag_anti", "diag", lambda x, y: (l - 1 - y, l - 1 - x)),
    )
    return tuple(
        D4Element(
            name,
            character_class,
            tuple(
                transform(x, y)[0] * l + transform(x, y)[1]
                for x in range(l)
                for y in range(l)
            ),
        )
        for name, character_class, transform in transforms
    )


def state_action(state: int, permutation: tuple[int, ...], flip: bool = False) -> int:
    result = 0
    for source, target in enumerate(permutation):
        result |= ((state >> source) & 1) << target
    if flip:
        result ^= (1 << len(permutation)) - 1
    return result


def _operator_on_orbit(orbit, index, permutation, flip=False):
    matrix = np.zeros((len(orbit), len(orbit)), dtype=np.float64)
    for column, state in enumerate(orbit):
        matrix[index[state_action(state, permutation, flip)], column] = 1.0
    return matrix


def _deterministic_columns(matrix: np.ndarray) -> np.ndarray:
    result = matrix.copy()
    for column in range(result.shape[1]):
        pivot = int(np.argmax(np.abs(result[:, column])))
        if result[pivot, column] < 0:
            result[:, column] *= -1
    return result


def sector_basis(
    l: int,
    irrep: str,
    parity: int,
    *,
    e_reflection: int = 1,
) -> SectorBasis:
    if irrep not in IRREPS or parity not in (-1, 1):
        raise ValueError("invalid D4 x Z2 sector")
    if e_reflection not in (-1, 1):
        raise ValueError("e_reflection must be +1 or -1")
    elements = d4_elements(l)
    reflection = next(item for item in elements if item.name == "axis_x")
    full_dimension = 1 << (l * l)
    unseen = set(range(full_dimension))
    rows: list[int] = []
    columns: list[int] = []
    data: list[float] = []
    output_column = 0
    while unseen:
        seed = min(unseen)
        orbit = sorted({
            state_action(seed, element.permutation, flip)
            for element in elements
            for flip in (False, True)
        })
        unseen.difference_update(orbit)
        index = {state: position for position, state in enumerate(orbit)}
        projector = np.zeros((len(orbit), len(orbit)), dtype=np.float64)
        prefactor = IRREP_DIMS[irrep] / 16.0
        for element in elements:
            for flip in (False, True):
                coefficient = (
                    prefactor
                    * CHARACTERS[irrep][element.character_class]
                    * parity ** int(flip)
                )
                projector += coefficient * _operator_on_orbit(
                    orbit, index, element.permutation, flip
                )
        projector = 0.5 * (projector + projector.T)
        values, vectors = np.linalg.eigh(projector)
        local_basis = vectors[:, values > 0.5]
        if irrep == "E" and local_basis.shape[1]:
            reflection_matrix = _operator_on_orbit(
                orbit, index, reflection.permutation
            )
            restricted = local_basis.T @ reflection_matrix @ local_basis
            reflection_values, reflection_vectors = np.linalg.eigh(
                0.5 * (restricted + restricted.T)
            )
            keep = reflection_values > 0.0 if e_reflection == 1 else reflection_values < 0.0
            local_basis = local_basis @ reflection_vectors[:, keep]
        local_basis = _deterministic_columns(local_basis)
        for local_column in range(local_basis.shape[1]):
            for local_row, state in enumerate(orbit):
                value = float(local_basis[local_row, local_column])
                if abs(value) > 1e-14:
                    rows.append(state)
                    columns.append(output_column)
                    data.append(value)
            output_column += 1
    q = sp.csr_matrix(
        (data, (rows, columns)),
        shape=(full_dimension, output_column),
        dtype=np.float64,
    )
    multiplicity = 2 if irrep == "E" else 1
    return SectorBasis(q, multiplicity, q.shape[1] * multiplicity)
