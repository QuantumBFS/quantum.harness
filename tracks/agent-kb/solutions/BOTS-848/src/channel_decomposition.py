"""Operator-channel decomposition used by the BOTS:848 prototype.

The API accepts a finite Hermitian standing-wave/real-space operator in a
localized orthonormal basis. A single non-Hermitian Bloch-q operator is outside
this API. Site blocks must form an exact partition of the basis, and

    D = D_global_charge + D_site_charge + D_internal + D_nonlocal.

The four terms are, respectively, the global identity projection, site-wise
identity shifts relative to that global projection, the traceless remainder of
each on-site block, and all inter-site blocks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from numbers import Number


CHANNELS = ("global_charge", "site_charge", "internal", "nonlocal")
_TOLERANCE = 1.0e-10


def _as_finite_complex(value: Number, label: str) -> complex:
    if isinstance(value, bool) or not isinstance(value, Number):
        raise ValueError(f"{label} entries must be finite numeric values and not booleans")
    try:
        numeric = complex(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} entries must be finite numeric values and not booleans") from exc
    if not math.isfinite(numeric.real) or not math.isfinite(numeric.imag):
        raise ValueError(f"{label} entries must be finite numeric values and not booleans")
    return numeric


def _as_square_matrix(
    operator: Sequence[Sequence[Number]],
    label: str = "operator",
) -> list[list[complex]]:
    try:
        rows = [list(row) for row in operator]
    except TypeError as exc:
        raise ValueError(f"{label} must be a square matrix") from exc
    if not rows or any(len(row) != len(rows) for row in rows):
        raise ValueError(f"{label} must be a nonempty square matrix")
    return [[_as_finite_complex(value, label) for value in row] for row in rows]


def _component_scale(value: complex) -> float:
    """Return a finite max-component magnitude without complex-abs overflow."""

    return max(abs(value.real), abs(value.imag))


def _stable_complex_mean(values: Sequence[complex], label: str) -> complex:
    scale = max(_component_scale(value) for value in values)
    if scale == 0.0:
        return 0.0j
    try:
        mean = complex(
            math.fsum(value.real / scale for value in values) / len(values),
            math.fsum(value.imag / scale for value in values) / len(values),
        )
        result = complex(mean.real * scale, mean.imag * scale)
    except OverflowError as exc:
        raise ValueError(f"{label} must remain finite") from exc
    return _as_finite_complex(result, label)


def _validate_hermitian(matrix: Sequence[Sequence[complex]]) -> None:
    size = len(matrix)
    scale = max(_component_scale(value) for row in matrix for value in row)
    if scale == 0.0:
        return
    for row in range(size):
        for column in range(size):
            difference = (
                matrix[row][column] / scale
                - matrix[column][row].conjugate() / scale
            )
            relative_error = _component_scale(difference)
            if relative_error > _TOLERANCE:
                raise ValueError(
                    "operator must be a standing-wave/real-space Hermitian operator; "
                    "a non-Hermitian Bloch-q operator is unsupported"
                )


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


def _project_matrix(
    matrix: Sequence[Sequence[complex]],
    basis_vectors: Sequence[Sequence[Number]],
) -> list[list[complex]]:
    size = len(matrix)
    try:
        vector_rows = [list(row) for row in basis_vectors]
    except TypeError as exc:
        raise ValueError("basis_vectors must be a finite numeric matrix with vectors in columns") from exc
    if len(vector_rows) != size or not vector_rows or not vector_rows[0]:
        raise ValueError("basis_vectors must have one row per operator basis function")
    width = len(vector_rows[0])
    if any(len(row) != width for row in vector_rows):
        raise ValueError("basis_vectors must be rectangular")
    vectors = [
        [_as_finite_complex(value, "basis_vectors") for value in row]
        for row in vector_rows
    ]

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
    """Decompose a Hermitian standing-wave/real-space operator into four channels."""

    matrix = _as_square_matrix(operator)
    _validate_hermitian(matrix)
    blocks = _validate_site_blocks(site_blocks, len(matrix))

    size = len(matrix)
    global_charge = _zeros(size)
    site_charge = _zeros(size)
    internal = _zeros(size)

    global_shift = _stable_complex_mean(
        [matrix[index][index] for index in range(size)],
        "derived global-charge shift",
    )
    for index in range(size):
        global_charge[index][index] = global_shift

    for block in blocks:
        site_shift = _stable_complex_mean(
            [matrix[index][index] for index in block],
            "derived site-charge shift",
        )
        for row in block:
            site_charge[row][row] = site_shift - global_shift
            for column in block:
                internal[row][column] = matrix[row][column]
            internal[row][row] -= site_shift

    nonlocal_part = [
        [
            matrix[row][column]
            - global_charge[row][column]
            - site_charge[row][column]
            - internal[row][column]
            for column in range(size)
        ]
        for row in range(size)
    ]
    channels = {
        "global_charge": global_charge,
        "site_charge": site_charge,
        "internal": internal,
        "nonlocal": nonlocal_part,
    }
    return {
        name: _as_square_matrix(channel, f"derived {name} channel")
        for name, channel in channels.items()
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
    matrices = {
        name: _as_square_matrix(channels[name], f"{name} channel matrix")
        for name in CHANNELS
    }
    sizes = {len(matrix) for matrix in matrices.values()}
    if len(sizes) != 1:
        raise ValueError("all channel matrices must have the same shape")

    measured_matrices = {}
    for name, matrix in matrices.items():
        measured = (
            _project_matrix(matrix, basis_vectors)
            if basis_vectors is not None
            else matrix
        )
        measured_matrices[name] = _as_square_matrix(
            measured, f"projected {name} channel matrix"
        )

    scale = max(
        _component_scale(value)
        for matrix in measured_matrices.values()
        for row in matrix
        for value in row
    )
    if scale == 0.0:
        return {name: 0.0 for name in CHANNELS}
    strengths = {
        name: float(
            sum(
                (value.real / scale) ** 2 + (value.imag / scale) ** 2
                for row in matrix
                for value in row
            )
        )
        for name, matrix in measured_matrices.items()
    }
    total = sum(strengths.values())
    return {name: strengths[name] / total for name in CHANNELS}
