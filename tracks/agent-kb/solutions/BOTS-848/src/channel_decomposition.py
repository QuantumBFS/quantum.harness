"""Operator-channel decomposition used by the BOTS:848 prototype.

The input is a finite Hermitian operator in a localized orthonormal basis. Site
blocks must form an exact partition of that basis. The decomposition is

    D = D_charge + D_internal + D_nonlocal,

where the charge part is proportional to the identity in every on-site block,
the internal part is the traceless remainder of each block, and the nonlocal
part contains all inter-site blocks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from numbers import Number


CHANNELS = ("charge", "internal", "nonlocal")
_TOLERANCE = 1.0e-10


def _as_square_matrix(operator: Sequence[Sequence[Number]]) -> list[list[complex]]:
    try:
        rows = [list(row) for row in operator]
    except TypeError as exc:
        raise ValueError("operator must be a square matrix") from exc
    if not rows or any(len(row) != len(rows) for row in rows):
        raise ValueError("operator must be a nonempty square matrix")
    try:
        return [[complex(value) for value in row] for row in rows]
    except (TypeError, ValueError) as exc:
        raise ValueError("operator entries must be numeric") from exc


def _validate_hermitian(matrix: Sequence[Sequence[complex]]) -> None:
    size = len(matrix)
    for row in range(size):
        for column in range(size):
            if abs(matrix[row][column] - matrix[column][row].conjugate()) > _TOLERANCE:
                raise ValueError("operator must be Hermitian")


def _validate_site_blocks(site_blocks: Sequence[Sequence[int]], size: int) -> list[list[int]]:
    try:
        blocks = [list(block) for block in site_blocks]
    except TypeError as exc:
        raise ValueError("site_blocks must form a partition of basis indices") from exc
    if not blocks or any(not block for block in blocks):
        raise ValueError("site_blocks must form a partition of basis indices")
    flat = [index for block in blocks for index in block]
    if any(isinstance(index, bool) or not isinstance(index, int) for index in flat):
        raise ValueError("site_blocks must form a partition of basis indices")
    if len(flat) != size or set(flat) != set(range(size)):
        raise ValueError("site_blocks must form a partition of basis indices")
    return blocks


def _zeros(size: int) -> list[list[complex]]:
    return [[0.0j for _ in range(size)] for _ in range(size)]


def _frobenius_squared(matrix: Sequence[Sequence[complex]]) -> float:
    return float(sum(abs(value) ** 2 for row in matrix for value in row))


def _project_matrix(
    matrix: Sequence[Sequence[complex]],
    basis_vectors: Sequence[Sequence[Number]],
) -> list[list[complex]]:
    size = len(matrix)
    try:
        vectors = [[complex(value) for value in row] for row in basis_vectors]
    except (TypeError, ValueError) as exc:
        raise ValueError("basis_vectors must be a numeric matrix with vectors in columns") from exc
    if len(vectors) != size or not vectors or not vectors[0]:
        raise ValueError("basis_vectors must have one row per operator basis function")
    width = len(vectors[0])
    if any(len(row) != width for row in vectors):
        raise ValueError("basis_vectors must be rectangular")

    for left in range(width):
        for right in range(width):
            overlap = sum(
                vectors[row][left].conjugate() * vectors[row][right]
                for row in range(size)
            )
            target = 1.0 if left == right else 0.0
            if abs(overlap - target) > _TOLERANCE:
                raise ValueError("basis_vectors columns must be orthonormal")

    return [
        [
            sum(
                vectors[row][left].conjugate()
                * matrix[row][column]
                * vectors[column][right]
                for row in range(size)
                for column in range(size)
            )
            for right in range(width)
        ]
        for left in range(width)
    ]


def decompose_operator(
    operator: Sequence[Sequence[Number]],
    site_blocks: Sequence[Sequence[int]],
) -> dict[str, list[list[complex]]]:
    """Decompose a localized Hermitian operator into three physical channels."""

    matrix = _as_square_matrix(operator)
    _validate_hermitian(matrix)
    blocks = _validate_site_blocks(site_blocks, len(matrix))

    charge = _zeros(len(matrix))
    internal = _zeros(len(matrix))

    for block in blocks:
        common_shift = sum(matrix[index][index] for index in block) / len(block)
        for row in block:
            charge[row][row] = common_shift
            for column in block:
                internal[row][column] = matrix[row][column]
            internal[row][row] -= common_shift

    nonlocal_part = [
        [matrix[row][column] - charge[row][column] - internal[row][column] for column in range(len(matrix))]
        for row in range(len(matrix))
    ]
    return {
        "charge": charge,
        "internal": internal,
        "nonlocal": nonlocal_part,
    }


def channel_weights(
    channels: Mapping[str, Sequence[Sequence[Number]]],
    basis_vectors: Sequence[Sequence[Number]] | None = None,
) -> dict[str, float]:
    """Return normalized squared Frobenius weight for each channel.

    If ``basis_vectors`` is supplied, its orthonormal columns define a target
    low-energy subspace and each operator is projected into that subspace before
    its norm is measured.
    """

    if set(channels) != set(CHANNELS):
        raise ValueError(f"channels must contain exactly {', '.join(CHANNELS)}")
    matrices = {name: _as_square_matrix(channels[name]) for name in CHANNELS}
    sizes = {len(matrix) for matrix in matrices.values()}
    if len(sizes) != 1:
        raise ValueError("all channel matrices must have the same shape")

    strengths = {}
    for name, matrix in matrices.items():
        measured = _project_matrix(matrix, basis_vectors) if basis_vectors is not None else matrix
        strengths[name] = _frobenius_squared(measured)

    total = sum(strengths.values())
    if total <= _TOLERANCE:
        return {name: 0.0 for name in CHANNELS}
    return {name: strengths[name] / total for name in CHANNELS}
