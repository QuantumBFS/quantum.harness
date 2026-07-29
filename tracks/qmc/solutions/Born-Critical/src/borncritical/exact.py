"""Exact spin enumeration and row-transfer oracles for short cylinders.

The transverse direction is periodic.  Bonds are represented by directed
lattice slots ``(y, x) -> (y, (x+1) mod nx)`` and
``(y, x) -> (y+1, x)``.  Thus ``nx=2`` intentionally contains the two
parallel horizontal slots of a circumference-two periodic square lattice.

For the weak self-dual oracle, ``s`` changes the Ising coupling sign and
``t=-1`` inserts a factor ``sigma_i sigma_j``:

    Z(s,t) = sum_sigma exp(K sum_b s_b sigma_i sigma_j)
                       prod_b (sigma_i sigma_j)^((1-t_b)/2).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterator

import numpy as np
from numpy.typing import NDArray

IntArray = NDArray[np.int8]
FloatArray = NDArray[np.float64]


def _binary_array(name: str, value: NDArray[np.integer]) -> IntArray:
    array = np.asarray(value, dtype=np.int8)
    if array.ndim != 2:
        raise ValueError(f"{name} must be a rank-2 array")
    if not np.all((array == 1) | (array == -1)):
        raise ValueError(f"{name} must contain only +1 or -1")
    array = array.copy()
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class BondFields:
    """Binary ``s`` and ``t`` fields on a finite square-lattice cylinder."""

    s_horizontal: IntArray
    s_vertical: IntArray
    t_horizontal: IntArray | None = None
    t_vertical: IntArray | None = None

    def __post_init__(self) -> None:
        s_horizontal = _binary_array("s_horizontal", self.s_horizontal)
        s_vertical = _binary_array("s_vertical", self.s_vertical)
        ny, nx = s_horizontal.shape
        if nx < 2 or ny < 1:
            raise ValueError("BondFields requires nx >= 2 and ny >= 1")
        if s_vertical.shape != (ny - 1, nx):
            raise ValueError(
                "s_vertical must have shape "
                f"{(ny - 1, nx)}, received {s_vertical.shape}"
            )

        t_horizontal_value = (
            np.ones_like(s_horizontal)
            if self.t_horizontal is None
            else self.t_horizontal
        )
        t_vertical_value = (
            np.ones_like(s_vertical) if self.t_vertical is None else self.t_vertical
        )
        t_horizontal = _binary_array("t_horizontal", t_horizontal_value)
        t_vertical = _binary_array("t_vertical", t_vertical_value)
        if t_horizontal.shape != s_horizontal.shape:
            raise ValueError("t_horizontal and s_horizontal shapes must match")
        if t_vertical.shape != s_vertical.shape:
            raise ValueError("t_vertical and s_vertical shapes must match")

        object.__setattr__(self, "s_horizontal", s_horizontal)
        object.__setattr__(self, "s_vertical", s_vertical)
        object.__setattr__(self, "t_horizontal", t_horizontal)
        object.__setattr__(self, "t_vertical", t_vertical)

    @property
    def ny(self) -> int:
        return int(self.s_horizontal.shape[0])

    @property
    def nx(self) -> int:
        return int(self.s_horizontal.shape[1])

    @property
    def edge_slots(self) -> int:
        return int(self.s_horizontal.size + self.s_vertical.size)

    @classmethod
    def clean(cls, nx: int, ny: int) -> "BondFields":
        if nx < 2 or ny < 1:
            raise ValueError("clean cylinder requires nx >= 2 and ny >= 1")
        return cls(
            s_horizontal=np.ones((ny, nx), dtype=np.int8),
            s_vertical=np.ones((ny - 1, nx), dtype=np.int8),
        )


def spin_rows(nx: int) -> IntArray:
    """Return all row configurations in deterministic binary order."""

    if nx < 1:
        raise ValueError("nx must be positive")
    integers = np.arange(1 << nx, dtype=np.uint64)[:, None]
    bits = (integers >> np.arange(nx, dtype=np.uint64)[None, :]) & 1
    return (2 * bits.astype(np.int8) - 1).astype(np.int8)


def spin_configurations(nx: int, ny: int) -> Iterator[IntArray]:
    """Yield all ``ny * nx`` spin configurations."""

    count = nx * ny
    if count >= 63:
        raise ValueError("exact spin enumeration is limited to fewer than 63 spins")
    for integer in range(1 << count):
        bits = ((integer >> np.arange(count)) & 1).astype(np.int8)
        yield (2 * bits - 1).reshape(ny, nx)


def _configuration_log_weight(
    fields: BondFields, spins: IntArray, coupling: float
) -> tuple[int, float]:
    horizontal_products = spins * np.roll(spins, shift=-1, axis=1)
    vertical_products = spins[:-1] * spins[1:]

    log_abs = coupling * (
        np.sum(fields.s_horizontal * horizontal_products, dtype=np.float64)
        + np.sum(fields.s_vertical * vertical_products, dtype=np.float64)
    )

    sign = 1
    if np.any(fields.t_horizontal == -1):
        sign *= int(
            np.prod(
                horizontal_products[fields.t_horizontal == -1], dtype=np.int64
            )
        )
    if np.any(fields.t_vertical == -1):
        sign *= int(
            np.prod(vertical_products[fields.t_vertical == -1], dtype=np.int64)
        )
    return sign, float(log_abs)


def _signed_logsumexp(signs: list[int], logs: list[float]) -> tuple[int, float]:
    finite = [value for value in logs if math.isfinite(value)]
    if not finite:
        return 0, -math.inf
    offset = max(finite)
    scaled_sum = math.fsum(
        sign * math.exp(log_value - offset)
        for sign, log_value in zip(signs, logs, strict=True)
        if sign != 0
    )
    if scaled_sum == 0.0:
        return 0, -math.inf
    return (1 if scaled_sum > 0.0 else -1), offset + math.log(abs(scaled_sum))


def direct_amplitude(fields: BondFields, coupling: float) -> tuple[int, float]:
    """Return ``(sign, log(abs(Z)))`` by explicit spin summation."""

    signs: list[int] = []
    logs: list[float] = []
    for spins in spin_configurations(fields.nx, fields.ny):
        sign, log_abs = _configuration_log_weight(fields, spins, coupling)
        signs.append(sign)
        logs.append(log_abs)
    return _signed_logsumexp(signs, logs)


def _row_factors(
    fields: BondFields, rows: IntArray, y: int, coupling: float
) -> tuple[IntArray, FloatArray]:
    products = rows * np.roll(rows, shift=-1, axis=1)
    logs = coupling * np.sum(
        products * fields.s_horizontal[y][None, :], axis=1, dtype=np.float64
    )
    selected = fields.t_horizontal[y] == -1
    if np.any(selected):
        signs = np.prod(products[:, selected], axis=1, dtype=np.int64).astype(
            np.int8
        )
    else:
        signs = np.ones(rows.shape[0], dtype=np.int8)
    return signs, logs


def _vertical_factors(
    fields: BondFields, rows: IntArray, y: int, coupling: float
) -> tuple[IntArray, FloatArray]:
    products = rows[:, None, :] * rows[None, :, :]
    logs = coupling * np.sum(
        products * fields.s_vertical[y][None, None, :],
        axis=2,
        dtype=np.float64,
    )
    selected = fields.t_vertical[y] == -1
    if np.any(selected):
        signs = np.prod(products[:, :, selected], axis=2, dtype=np.int64).astype(
            np.int8
        )
    else:
        signs = np.ones(logs.shape, dtype=np.int8)
    return signs, logs


def row_transfer_amplitude(
    fields: BondFields, coupling: float
) -> tuple[int, float]:
    """Return ``(sign, log(abs(Z)))`` from a stabilized row contraction."""

    rows = spin_rows(fields.nx)
    row_signs, row_logs = _row_factors(fields, rows, 0, coupling)
    row_offset = float(np.max(row_logs))
    vector = row_signs.astype(np.float64) * np.exp(row_logs - row_offset)
    log_scale = row_offset

    for y in range(fields.ny - 1):
        vertical_signs, vertical_logs = _vertical_factors(
            fields, rows, y, coupling
        )
        vertical_offset = float(np.max(vertical_logs))
        transfer = vertical_signs * np.exp(vertical_logs - vertical_offset)

        next_row_signs, next_row_logs = _row_factors(
            fields, rows, y + 1, coupling
        )
        next_row_offset = float(np.max(next_row_logs))
        vector = (vector @ transfer) * next_row_signs * np.exp(
            next_row_logs - next_row_offset
        )
        log_scale += vertical_offset + next_row_offset

        scale = float(np.max(np.abs(vector)))
        if scale == 0.0:
            return 0, -math.inf
        vector /= scale
        log_scale += math.log(scale)

    total = math.fsum(float(value) for value in vector)
    if total == 0.0:
        return 0, -math.inf
    return (1 if total > 0.0 else -1), log_scale + math.log(abs(total))


def gauge_transform(fields: BondFields, site_gauge: IntArray) -> BondFields:
    """Apply ``s_ij -> eta_i s_ij eta_j`` to a pure RBIM field."""

    if not np.all(fields.t_horizontal == 1) or not np.all(fields.t_vertical == 1):
        raise ValueError("gauge_transform currently requires t=+1 on every bond")
    eta = _binary_array("site_gauge", site_gauge)
    if eta.shape != (fields.ny, fields.nx):
        raise ValueError(
            f"site_gauge must have shape {(fields.ny, fields.nx)}, "
            f"received {eta.shape}"
        )
    horizontal = (
        fields.s_horizontal * eta * np.roll(eta, shift=-1, axis=1)
    ).astype(np.int8)
    vertical = (fields.s_vertical * eta[:-1] * eta[1:]).astype(np.int8)
    return BondFields(s_horizontal=horizontal, s_vertical=vertical)
