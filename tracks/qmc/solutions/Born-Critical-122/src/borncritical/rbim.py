"""Fermionic transfer matrices for the square-lattice random-bond Ising model.

The finite-cylinder implementation is an independent NumPy port of the
Gaussian-state algorithm pinned in ``references/rbim-baseline.json``.  The
streaming implementation applies the same local layers to estimate the
quenched infinite-strip free-energy density from QR log-volume increments.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time

import numpy as np
from numpy.typing import NDArray

from .rng import StreamKey, make_rng

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int8]


def _validate_bonds(name: str, bonds: NDArray[np.integer], shape: tuple[int, ...]) -> IntArray:
    array = np.asarray(bonds, dtype=np.int8)
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, received {array.shape}")
    if not np.all((array == 1) | (array == -1)):
        raise ValueError(f"{name} must contain only +1 or -1")
    return array


def free_boundary_state(circumference: int) -> FloatArray:
    if circumference < 2:
        raise ValueError("circumference must be at least two")
    state = np.zeros((2 * circumference, circumference), dtype=np.float64)
    for index in range(circumference):
        state[2 * index : 2 * index + 2, index] = math.sqrt(2.0)
    return state


def _dual_coupling(coupling: float) -> float:
    if coupling <= 0.0 or not math.isfinite(coupling):
        raise ValueError("coupling must be finite and positive")
    return math.atanh(math.exp(-2.0 * coupling))


def _horizontal_log_normalization(coupling: float, circumference: int) -> float:
    dual = _dual_coupling(coupling)
    return -0.5 * circumference * math.log(0.5 * math.sinh(2.0 * dual))


def _apply_vertical(
    state: FloatArray,
    bonds: IntArray,
    coupling: float,
    parity: int,
) -> None:
    circumference = state.shape[1]
    cosh_value = math.cosh(2.0 * coupling)
    sinh_values = math.sinh(2.0 * coupling) * bonds
    for index in range(circumference - 1):
        block = state[2 * index + 1 : 2 * index + 3].copy()
        off_diagonal = -float(sinh_values[index])
        state[2 * index + 1] = cosh_value * block[0] + off_diagonal * block[1]
        state[2 * index + 2] = off_diagonal * block[0] + cosh_value * block[1]
    first = state[0].copy()
    last = state[-1].copy()
    off_diagonal = parity * float(sinh_values[-1])
    state[0] = cosh_value * first + off_diagonal * last
    state[-1] = off_diagonal * first + cosh_value * last


def _apply_horizontal(
    state: FloatArray,
    bonds: IntArray,
    coupling: float,
) -> None:
    circumference = state.shape[1]
    dual = _dual_coupling(coupling)
    cosh_value = math.cosh(2.0 * dual)
    sinh_value = math.sinh(2.0 * dual)
    for index in range(circumference):
        block = state[2 * index : 2 * index + 2].copy()
        diagonal = cosh_value * float(bonds[index])
        off_diagonal = sinh_value * float(bonds[index])
        state[2 * index] = diagonal * block[0] + off_diagonal * block[1]
        state[2 * index + 1] = off_diagonal * block[0] + diagonal * block[1]


def _stabilize(state: FloatArray) -> tuple[FloatArray, float, float]:
    q_matrix, r_matrix = np.linalg.qr(state, mode="reduced")
    diagonal = np.diag(r_matrix)
    if np.any(diagonal == 0.0) or not np.all(np.isfinite(diagonal)):
        raise FloatingPointError("singular or non-finite QR factor")
    log_volume = float(np.sum(np.log(np.abs(diagonal)), dtype=np.float64))
    orthogonality = float(
        np.max(np.abs(q_matrix.T @ q_matrix - np.eye(q_matrix.shape[1])))
    )
    return q_matrix, log_volume, orthogonality


def fermionic_log_partition(
    vertical_bonds: NDArray[np.integer],
    horizontal_bonds: NDArray[np.integer],
    coupling: float,
    *,
    parity: int = 1,
    qr_interval: int = 5,
) -> tuple[float, float]:
    """Return ``(log Z, max orthogonality error)`` for one finite cylinder.

    ``vertical_bonds`` has shape ``(N, L)`` for bonds around each periodic
    row. ``horizontal_bonds`` has shape ``(N-1, L)`` for propagation bonds.
    """

    vertical = np.asarray(vertical_bonds, dtype=np.int8)
    if vertical.ndim != 2:
        raise ValueError("vertical_bonds must be rank two")
    length, circumference = vertical.shape
    if length < 2 or circumference < 2:
        raise ValueError("finite cylinder requires N,L >= 2")
    vertical = _validate_bonds("vertical_bonds", vertical, (length, circumference))
    horizontal = _validate_bonds(
        "horizontal_bonds",
        np.asarray(horizontal_bonds),
        (length - 1, circumference),
    )
    if parity not in (-1, 1):
        raise ValueError("parity must be +1 or -1")
    if qr_interval < 1:
        raise ValueError("qr_interval must be positive")

    free = free_boundary_state(circumference)
    right = free.copy()
    left = free.copy()
    right_log = 0.0
    left_log = 0.0
    maximum_orthogonality = 0.0

    for index in range(length // 2):
        _apply_vertical(right, vertical[index], coupling, parity)
        _apply_horizontal(right, horizontal[index], coupling)

        left_index = length - 1 - index
        _apply_vertical(left, vertical[left_index], coupling, parity)
        if index != length // 2 - 1:
            _apply_horizontal(left, horizontal[length - 2 - index], coupling)

        if (index + 1) % qr_interval == 0:
            right, increment, error = _stabilize(right)
            right_log += increment
            maximum_orthogonality = max(maximum_orthogonality, error)
            left, increment, error = _stabilize(left)
            left_log += increment
            maximum_orthogonality = max(maximum_orthogonality, error)

    if length % 2:
        middle = length // 2
        _apply_vertical(right, vertical[middle], coupling, parity)
        _apply_horizontal(right, horizontal[middle], coupling)

    if (length // 2) % qr_interval != 0:
        right, increment, error = _stabilize(right)
        right_log += increment
        maximum_orthogonality = max(maximum_orthogonality, error)
        left, increment, error = _stabilize(left)
        left_log += increment
        maximum_orthogonality = max(maximum_orthogonality, error)

    sign, overlap_log = np.linalg.slogdet(left.T @ right)
    if sign == 0.0 or not math.isfinite(float(overlap_log)):
        raise FloatingPointError("Gaussian boundary overlap is singular")
    normalization = (length - 1) * _horizontal_log_normalization(
        coupling, circumference
    )
    log_partition = 0.5 * (float(overlap_log) + right_log + left_log) + normalization
    return log_partition, maximum_orthogonality


@dataclass(frozen=True)
class RBIMReplicaResult:
    size: int
    replica: int
    p: float
    coupling: float
    qr_interval: int
    burn_in_rows: int
    measurement_rows: int
    block_size: int
    block_phi: FloatArray
    mean_phi: float
    standard_error_phi: float
    adjacent_block_correlation: float
    maximum_orthogonality_error: float
    rows_per_second: float
    rng_fingerprint: str


class GaussianRBIMStream:
    """One infinite-strip Gaussian state with periodic transverse boundary."""

    def __init__(
        self,
        circumference: int,
        coupling: float,
        *,
        parity: int = 1,
        qr_interval: int = 5,
    ) -> None:
        if circumference < 2:
            raise ValueError("circumference must be at least two")
        if parity not in (-1, 1):
            raise ValueError("parity must be +1 or -1")
        if qr_interval < 1:
            raise ValueError("qr_interval must be positive")
        self.circumference = circumference
        self.coupling = coupling
        self.parity = parity
        self.qr_interval = qr_interval
        self.state = free_boundary_state(circumference)
        self._pending = 0
        self.maximum_orthogonality_error = 0.0
        self.normalization_per_row = _horizontal_log_normalization(
            coupling, circumference
        )

    def push(self, vertical_bonds: IntArray, horizontal_bonds: IntArray) -> float | None:
        vertical = _validate_bonds(
            "vertical_bonds",
            vertical_bonds,
            (self.circumference,),
        )
        horizontal = _validate_bonds(
            "horizontal_bonds",
            horizontal_bonds,
            (self.circumference,),
        )
        _apply_vertical(self.state, vertical, self.coupling, self.parity)
        _apply_horizontal(self.state, horizontal, self.coupling)
        self._pending += 1
        if self._pending < self.qr_interval:
            return None
        self.state, log_volume, error = _stabilize(self.state)
        self.maximum_orthogonality_error = max(
            self.maximum_orthogonality_error, error
        )
        rows = self._pending
        self._pending = 0
        return 0.5 * log_volume + rows * self.normalization_per_row


def _bond_batch(
    rng: np.random.Generator, rows: int, circumference: int, p: float
) -> IntArray:
    return np.where(
        rng.random((rows, circumference)) < p,
        -1,
        1,
    ).astype(np.int8)


def simulate_rbim_replica(
    *,
    size: int,
    replica: int,
    p: float,
    coupling: float,
    base_seed: int,
    qr_interval: int,
    burn_in_rows: int,
    measurement_rows: int,
    block_size: int,
) -> RBIMReplicaResult:
    """Simulate one keyed disorder stream and retain complete block means."""

    if burn_in_rows % qr_interval:
        raise ValueError("burn_in_rows must be divisible by qr_interval")
    if measurement_rows % block_size:
        raise ValueError("measurement_rows must be divisible by block_size")
    if block_size % qr_interval:
        raise ValueError("block_size must be divisible by qr_interval")
    if not 0.0 <= p < 0.5:
        raise ValueError("p must satisfy 0 <= p < 0.5")

    key = StreamKey(base_seed, "nishimori-rbim", size, replica, "bonds")
    rng = make_rng(key)
    stream = GaussianRBIMStream(
        size,
        coupling,
        parity=1,
        qr_interval=qr_interval,
    )
    total_rows = burn_in_rows + measurement_rows
    vertical = _bond_batch(rng, total_rows, size, p)
    horizontal = _bond_batch(rng, total_rows, size, p)
    started = time.perf_counter()

    chunk_sum = 0.0
    block_sum = 0.0
    rows_in_block = 0
    blocks: list[float] = []
    for row in range(total_rows):
        contribution = stream.push(vertical[row], horizontal[row])
        if contribution is None:
            continue
        if row + 1 <= burn_in_rows:
            continue
        chunk_sum = contribution
        block_sum += chunk_sum
        rows_in_block += qr_interval
        if rows_in_block == block_size:
            blocks.append(block_sum / block_size / size)
            block_sum = 0.0
            rows_in_block = 0
    elapsed = time.perf_counter() - started
    block_array = np.asarray(blocks, dtype=np.float64)
    expected_blocks = measurement_rows // block_size
    if block_array.size != expected_blocks:
        raise RuntimeError(
            f"block count mismatch: {block_array.size} != {expected_blocks}"
        )
    if block_array.size < 2:
        raise ValueError("at least two complete blocks are required")
    correlation = float(np.corrcoef(block_array[:-1], block_array[1:])[0, 1])
    if not math.isfinite(correlation):
        correlation = 0.0
    return RBIMReplicaResult(
        size=size,
        replica=replica,
        p=p,
        coupling=coupling,
        qr_interval=qr_interval,
        burn_in_rows=burn_in_rows,
        measurement_rows=measurement_rows,
        block_size=block_size,
        block_phi=block_array,
        mean_phi=float(np.mean(block_array)),
        standard_error_phi=float(
            np.std(block_array, ddof=1) / math.sqrt(block_array.size)
        ),
        adjacent_block_correlation=correlation,
        maximum_orthogonality_error=stream.maximum_orthogonality_error,
        rows_per_second=total_rows / elapsed,
        rng_fingerprint=key.fingerprint(),
    )
