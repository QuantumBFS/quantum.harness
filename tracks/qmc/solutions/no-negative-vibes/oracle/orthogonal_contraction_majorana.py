"""Majorana double-copy audit for orthogonal one-particle vertices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.linalg import expm

from oracle.majorana import spin_trace_weight


@dataclass(frozen=True)
class MajoranaSquareAudit:
    """Number-conserving determinant versus doubled-Majorana Spin trace."""

    word: tuple[tuple[int, bool], ...]
    determinant_weight: float
    spin_trace: complex
    doubled_majorana_determinant: complex
    expected_square: float
    spin_trace_residual: float
    square_residual: float
    classification: str


def doubled_majorana_generator(generator: np.ndarray) -> np.ndarray:
    """Embed real ``K`` as identical transformations of x/y Majoranas."""

    matrix = np.asarray(generator, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("generator must be square")
    if not np.allclose(matrix.T, -matrix, atol=1e-12):
        raise ValueError("generator must be real skew-symmetric")
    modes = matrix.shape[0]
    doubled = np.zeros((2 * modes, 2 * modes), dtype=complex)
    for left in range(modes):
        for right in range(modes):
            doubled[2 * left, 2 * right] = matrix[left, right]
            doubled[2 * left + 1, 2 * right + 1] = matrix[left, right]
    return doubled


def majorana_square_word_audit(
    generators: Sequence[np.ndarray],
    word: Sequence[tuple[int, bool]],
) -> MajoranaSquareAudit:
    """Audit one oriented word against the existing Spin oracle."""

    matrices = tuple(np.asarray(item, dtype=float) for item in generators)
    if not matrices:
        raise ValueError("at least one generator is required")
    oriented = tuple((int(index), bool(transpose)) for index, transpose in word)
    if not oriented:
        raise ValueError("word must be nonempty")
    modes = matrices[0].shape[0]
    product_matrix = np.eye(modes)
    doubled_word: list[np.ndarray] = []
    for index, transpose in oriented:
        if not 0 <= index < len(matrices):
            raise ValueError("word contains an invalid generator index")
        generator = -matrices[index] if transpose else matrices[index]
        product_matrix = product_matrix @ expm(generator)
        doubled_word.append(doubled_majorana_generator(generator))

    determinant_weight = float(
        np.linalg.det(np.eye(modes) + product_matrix)
    )
    spin = spin_trace_weight(doubled_word)
    expected_square = determinant_weight * determinant_weight
    return MajoranaSquareAudit(
        word=oriented,
        determinant_weight=determinant_weight,
        spin_trace=spin.value,
        doubled_majorana_determinant=spin.determinant_square,
        expected_square=expected_square,
        spin_trace_residual=abs(spin.value - determinant_weight),
        square_residual=abs(
            spin.determinant_square - expected_square
        ),
        classification=spin.classification,
    )
