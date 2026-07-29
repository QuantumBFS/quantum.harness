"""Streaming block means with explicit partial-block semantics."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class BlockSummary:
    n_blocks: int
    n_complete_samples: int
    n_total_samples: int
    mean: FloatArray
    standard_deviation: FloatArray
    standard_error: FloatArray


class StreamingBlockAccumulator:
    """Accumulate vector observations and retain only complete block means."""

    def __init__(self, block_size: int, n_observables: int) -> None:
        if block_size < 1:
            raise ValueError("block_size must be positive")
        if n_observables < 1:
            raise ValueError("n_observables must be positive")
        self.block_size = int(block_size)
        self.n_observables = int(n_observables)
        self._current_sum = np.zeros(self.n_observables, dtype=np.float64)
        self._current_count = 0
        self._n_total_samples = 0
        self._completed: list[FloatArray] = []

    @property
    def current_count(self) -> int:
        return self._current_count

    @property
    def n_total_samples(self) -> int:
        return self._n_total_samples

    @property
    def n_blocks(self) -> int:
        return len(self._completed)

    @property
    def n_complete_samples(self) -> int:
        return self.n_blocks * self.block_size

    @property
    def completed_blocks(self) -> FloatArray:
        if not self._completed:
            return np.empty((0, self.n_observables), dtype=np.float64)
        return np.stack(self._completed).astype(np.float64, copy=True)

    @property
    def current_sum(self) -> FloatArray:
        return self._current_sum.copy()

    def add(self, values: NDArray[np.floating] | list[float]) -> None:
        observation = np.asarray(values, dtype=np.float64)
        if observation.shape != (self.n_observables,):
            raise ValueError(
                f"observation must have shape {(self.n_observables,)}, "
                f"received {observation.shape}"
            )
        if not np.all(np.isfinite(observation)):
            raise ValueError("observation must contain only finite values")
        self._current_sum += observation
        self._current_count += 1
        self._n_total_samples += 1
        if self._current_count == self.block_size:
            self._completed.append(self._current_sum / self.block_size)
            self._current_sum = np.zeros(self.n_observables, dtype=np.float64)
            self._current_count = 0

    def add_batch(self, values: NDArray[np.floating]) -> None:
        batch = np.asarray(values, dtype=np.float64)
        if batch.ndim != 2 or batch.shape[1] != self.n_observables:
            raise ValueError(
                "batch must have shape "
                f"(n, {self.n_observables}), received {batch.shape}"
            )
        if not np.all(np.isfinite(batch)):
            raise ValueError("batch must contain only finite values")

        position = 0
        while position < batch.shape[0]:
            available = self.block_size - self._current_count
            take = min(available, batch.shape[0] - position)
            self._current_sum += np.sum(
                batch[position : position + take], axis=0, dtype=np.float64
            )
            self._current_count += take
            self._n_total_samples += take
            position += take
            if self._current_count == self.block_size:
                self._completed.append(self._current_sum / self.block_size)
                self._current_sum = np.zeros(
                    self.n_observables, dtype=np.float64
                )
                self._current_count = 0

    def summary(self) -> BlockSummary:
        if self.n_blocks < 2:
            raise RuntimeError("at least two complete blocks are required")
        blocks = self.completed_blocks
        mean = np.mean(blocks, axis=0)
        standard_deviation = np.std(blocks, axis=0, ddof=1)
        standard_error = standard_deviation / math.sqrt(self.n_blocks)
        return BlockSummary(
            n_blocks=self.n_blocks,
            n_complete_samples=self.n_complete_samples,
            n_total_samples=self.n_total_samples,
            mean=mean,
            standard_deviation=standard_deviation,
            standard_error=standard_error,
        )

    def export_state(self) -> tuple[dict[str, Any], dict[str, FloatArray]]:
        metadata = {
            "block_size": self.block_size,
            "n_observables": self.n_observables,
            "current_count": self.current_count,
            "n_total_samples": self.n_total_samples,
        }
        arrays = {
            "current_sum": self.current_sum,
            "completed_blocks": self.completed_blocks,
        }
        return metadata, arrays

    @classmethod
    def from_state(
        cls,
        metadata: dict[str, Any],
        current_sum: NDArray[np.floating],
        completed_blocks: NDArray[np.floating],
    ) -> "StreamingBlockAccumulator":
        accumulator = cls(
            block_size=int(metadata["block_size"]),
            n_observables=int(metadata["n_observables"]),
        )
        current = np.asarray(current_sum, dtype=np.float64)
        completed = np.asarray(completed_blocks, dtype=np.float64)
        if current.shape != (accumulator.n_observables,):
            raise ValueError("checkpoint current_sum shape mismatch")
        if completed.shape != (0, accumulator.n_observables) and (
            completed.ndim != 2
            or completed.shape[1] != accumulator.n_observables
        ):
            raise ValueError("checkpoint completed_blocks shape mismatch")
        current_count = int(metadata["current_count"])
        total = int(metadata["n_total_samples"])
        if not 0 <= current_count < accumulator.block_size:
            raise ValueError("checkpoint current_count is invalid")
        expected_total = completed.shape[0] * accumulator.block_size + current_count
        if total != expected_total:
            raise ValueError(
                f"checkpoint sample count mismatch: {total} != {expected_total}"
            )
        if not np.all(np.isfinite(current)) or not np.all(np.isfinite(completed)):
            raise ValueError("checkpoint accumulator contains non-finite values")
        accumulator._current_sum = current.copy()
        accumulator._current_count = current_count
        accumulator._n_total_samples = total
        accumulator._completed = [row.copy() for row in completed]
        return accumulator
