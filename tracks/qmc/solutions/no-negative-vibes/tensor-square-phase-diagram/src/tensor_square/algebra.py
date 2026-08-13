"""Frozen tensor-square determinant oracle and direct regression path."""

from __future__ import annotations

from itertools import combinations

import numpy as np


def _real_square_matrix(x: np.ndarray) -> np.ndarray:
    array = np.asarray(x, dtype=np.float64)
    if array.ndim != 2 or array.shape[0] != array.shape[1]:
        raise ValueError("expected a real square matrix")
    if not np.all(np.isfinite(array)):
        raise ValueError("matrix contains a non-finite entry")
    return array


def kron_sum(a: np.ndarray) -> np.ndarray:
    """Return A⊗I + I⊗A in the fixed row-major tensor basis."""
    matrix = _real_square_matrix(a)
    identity = np.eye(matrix.shape[0])
    return np.kron(matrix, identity) + np.kron(identity, matrix)


def exterior_square(x: np.ndarray) -> np.ndarray:
    """Matrix of ∧²X in the lexicographic e_i∧e_j basis."""
    matrix = _real_square_matrix(x)
    pairs = np.asarray(
        list(combinations(range(matrix.shape[0]), 2)), dtype=np.int64
    )
    if len(pairs) == 0:
        return np.empty((0, 0), dtype=np.float64)
    i = pairs[:, 0][:, None]
    j = pairs[:, 1][:, None]
    k = pairs[:, 0][None, :]
    ell = pairs[:, 1][None, :]
    return matrix[i, k] * matrix[j, ell] - matrix[i, ell] * matrix[j, k]


def tensor_square_weight_direct(x: np.ndarray) -> float:
    """Independent dense determinant det(I + X⊗X)."""
    matrix = _real_square_matrix(x)
    operator = np.eye(matrix.size) + np.kron(matrix, matrix)
    return float(np.linalg.det(operator))


def tensor_square_weight_factorized(x: np.ndarray) -> float:
    """Frozen exterior-power identity from MODEL.md."""
    matrix = _real_square_matrix(x)
    complex_factor = np.linalg.det(np.eye(matrix.shape[0]) + 1j * matrix)
    wedge = exterior_square(matrix)
    wedge_factor = np.linalg.det(np.eye(wedge.shape[0]) + wedge)
    return float(abs(complex_factor) ** 2 * wedge_factor**2)


def tensor_square_weight_eigenvalues(x: np.ndarray) -> float:
    """Frozen eigenvalue product identity from MODEL.md."""
    eigenvalues = np.linalg.eigvals(_real_square_matrix(x)).astype(np.complex128)
    value = np.prod(1.0 + eigenvalues**2)
    for i, j in combinations(range(len(eigenvalues)), 2):
        value *= (1.0 + eigenvalues[i] * eigenvalues[j]) ** 2
    scale = max(1.0, abs(value))
    if abs(value.imag) > 2.0e-10 * scale:
        raise FloatingPointError(
            f"eigenvalue product has imaginary residue {value.imag}"
        )
    return float(value.real)


def relative_error(actual: float, reference: float) -> float:
    return abs(actual - reference) / max(1.0, abs(reference))
