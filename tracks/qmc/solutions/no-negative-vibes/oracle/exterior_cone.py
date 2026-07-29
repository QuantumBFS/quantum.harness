"""Exterior-power cone checks used by the throughput search."""

from __future__ import annotations

from itertools import combinations
from math import comb
from typing import Mapping

import numpy as np


def subset_basis(size: int, grade: int) -> tuple[tuple[int, ...], ...]:
    """Return the lexicographically ordered subsets for one exterior grade."""
    if size < 0 or grade < 0 or grade > size:
        raise ValueError("grade must satisfy 0 <= grade <= size")
    return tuple(combinations(range(size), grade))


def _square_finite_matrix(matrix: np.ndarray, *, name: str) -> np.ndarray:
    array = np.asarray(matrix)
    if array.ndim != 2 or array.shape[0] != array.shape[1]:
        raise ValueError(f"{name} must be square")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite")
    return array


def _validated_tolerance(tolerance: float) -> float:
    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance must be finite and nonnegative")
    return float(tolerance)


def compound_matrix(matrix: np.ndarray, grade: int) -> np.ndarray:
    """Construct the matrix of the declared exterior-power representation."""
    array = _square_finite_matrix(matrix, name="matrix")
    size = array.shape[0]
    basis = subset_basis(size, grade)
    dimension = len(basis)
    result = np.empty((dimension, dimension), dtype=np.result_type(array, float))
    if grade == 0:
        result[0, 0] = 1.0
        return result

    for row_index, rows in enumerate(basis):
        for column_index, columns in enumerate(basis):
            result[row_index, column_index] = np.linalg.det(array[np.ix_(rows, columns)])
    return result


def determinant_from_compound_traces(matrix: np.ndarray) -> complex:
    """Evaluate det(I + matrix) as the sum of exterior-power traces."""
    array = _square_finite_matrix(matrix, name="matrix")
    return complex(
        sum(np.trace(compound_matrix(array, grade)) for grade in range(array.shape[0] + 1))
    )


def transformed_nonnegative_margin(
    matrices: tuple[np.ndarray, ...],
    transform: np.ndarray,
    *,
    tolerance: float,
) -> float | None:
    """Return the shared smallest entry, or reject a non-real/nonpositive cone."""
    threshold = _validated_tolerance(tolerance)
    if not matrices:
        raise ValueError("at least one matrix is required")

    checked = tuple(
        _square_finite_matrix(matrix, name="matrix") for matrix in matrices
    )
    dimension = checked[0].shape[0]
    if any(matrix.shape != (dimension, dimension) for matrix in checked):
        raise ValueError("matrices must have one common square size")

    change_of_basis = _square_finite_matrix(transform, name="transform")
    if change_of_basis.shape != (dimension, dimension):
        raise ValueError("transform must match the matrix dimension")
    if np.linalg.matrix_rank(change_of_basis) != dimension:
        raise ValueError("transform must be invertible")

    minimum = float("inf")
    for matrix in checked:
        with np.errstate(over="ignore", invalid="ignore"):
            product = matrix @ change_of_basis
        if not np.all(np.isfinite(product)):
            return None
        transformed = np.linalg.solve(change_of_basis, product)
        if not np.all(np.isfinite(transformed)):
            return None
        if np.max(np.abs(np.imag(transformed))) > threshold:
            return None
        real_entries = np.real(transformed)
        entry_minimum = float(np.min(real_entries))
        if entry_minimum < -threshold:
            return None
        minimum = min(minimum, entry_minimum)
    return minimum


def common_transform_certificate(
    atoms: tuple[np.ndarray, ...],
    transform_library: Mapping[int, tuple[tuple[str, np.ndarray], ...]],
    *,
    tolerance: float,
) -> dict[str, object] | None:
    """Find one declared transform per exterior grade for every atom."""
    threshold = _validated_tolerance(tolerance)
    if not atoms:
        raise ValueError("at least one atom is required")

    checked_atoms = tuple(
        _square_finite_matrix(atom, name="atom") for atom in atoms
    )
    dimension = checked_atoms[0].shape[0]
    if any(atom.shape != (dimension, dimension) for atom in checked_atoms):
        raise ValueError("atoms must have one common square size")

    grades: list[dict[str, object]] = []
    for grade in range(dimension + 1):
        candidates = transform_library.get(grade)
        if not candidates:
            return None
        compounds = tuple(compound_matrix(atom, grade) for atom in checked_atoms)
        compound_dimension = comb(dimension, grade)
        selected: dict[str, object] | None = None
        for transform_id, transform in candidates:
            candidate = _square_finite_matrix(transform, name="transform")
            if candidate.shape != (compound_dimension, compound_dimension):
                raise ValueError("transform must match the compound dimension")
            if np.max(np.abs(np.imag(candidate))) > threshold:
                raise ValueError("certificate transforms must be real within tolerance")
            serialized_transform = np.real(candidate).astype(float)
            margins = [
                transformed_nonnegative_margin(
                    compounds, serialized_transform, tolerance=threshold
                )
            ]
            margin = margins[0]
            if margin is None:
                continue
            selected = {
                "grade": grade,
                "transform_id": str(transform_id),
                "transform": serialized_transform.tolist(),
                "minimum_entry": float(margin),
            }
            break
        if selected is None:
            return None
        grades.append(selected)

    return {
        "dimension": dimension,
        "basis_convention": "lexicographic-subsets",
        "grades": grades,
    }
