from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math

import numba
import numpy as np
import numpy.typing as npt

from .model import ModelSpec, distance_classes


F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]
U64 = npt.NDArray[np.uint64]


@dataclass(frozen=True)
class AliasTable:
    probability: F64
    alias: I64
    multiplicity: U64
    class_weight: F64
    total_rate: float
    kernel_sha256: str
    normalized_residual: float


def _freeze(array: np.ndarray) -> np.ndarray:
    frozen = np.ascontiguousarray(array).copy()
    frozen.setflags(write=False)
    return frozen


def build_distance_alias(
    length: int,
    sigma: float,
    kernel: F64,
    kernel_sha256: str,
) -> AliasTable:
    ModelSpec(length=length, sigma=sigma, kappa=0.0)
    values = np.asarray(kernel, dtype=np.float64)
    class_count = length // 2
    if values.shape != (class_count,):
        raise ValueError(
            f"kernel must have exact shape ({class_count},)"
        )
    values = np.ascontiguousarray(values).copy()
    if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("kernel must contain finite positive values")
    actual_sha256 = sha256(values.tobytes()).hexdigest()
    if (
        not isinstance(kernel_sha256, str)
        or kernel_sha256 != actual_sha256
    ):
        raise ValueError("kernel SHA-256 does not match kernel values")

    multiplicity = np.fromiter(
        (item.multiplicity for item in distance_classes(length)),
        dtype=np.uint64,
        count=class_count,
    )
    class_weight = np.multiply(
        multiplicity, values, dtype=np.float64
    )
    if (
        not np.all(np.isfinite(class_weight))
        or np.any(class_weight <= 0.0)
    ):
        raise ValueError("class weights must be finite and positive")
    total_rate = math.fsum(float(value) for value in class_weight)
    if not math.isfinite(total_rate) or total_rate <= 0.0:
        raise ValueError("total rate must be finite and positive")

    normalized = class_weight / total_rate
    normalized_residual = (
        math.fsum(float(value) for value in normalized) - 1.0
    )
    scaled = normalized * float(class_count)
    probability = np.empty(class_count, dtype=np.float64)
    alias = np.arange(class_count, dtype=np.int64)

    capacity = 2 * class_count
    small = np.empty(capacity, dtype=np.int64)
    large = np.empty(capacity, dtype=np.int64)
    small_head = 0
    small_tail = 0
    large_head = 0
    large_tail = 0
    for index in range(class_count):
        if scaled[index] < 1.0:
            small[small_tail] = index
            small_tail += 1
        else:
            large[large_tail] = index
            large_tail += 1

    while small_head < small_tail and large_head < large_tail:
        small_index = int(small[small_head])
        small_head += 1
        large_index = int(large[large_head])
        large_head += 1
        probability[small_index] = scaled[small_index]
        alias[small_index] = large_index
        scaled[large_index] -= 1.0 - scaled[small_index]
        if scaled[large_index] < 1.0:
            small[small_tail] = large_index
            small_tail += 1
        else:
            large[large_tail] = large_index
            large_tail += 1

    while small_head < small_tail:
        index = int(small[small_head])
        small_head += 1
        probability[index] = 1.0
        alias[index] = index
    while large_head < large_tail:
        index = int(large[large_head])
        large_head += 1
        probability[index] = 1.0
        alias[index] = index

    tolerance = 8.0 * np.finfo(np.float64).eps
    if np.any(probability < -tolerance) or np.any(
        probability > 1.0 + tolerance
    ):
        raise ValueError("alias probability exceeds roundoff tolerance")
    np.clip(probability, 0.0, 1.0, out=probability)
    if np.any(alias < 0) or np.any(alias >= class_count):
        raise ValueError("alias index is outside the distance classes")

    return AliasTable(
        probability=_freeze(probability),
        alias=_freeze(alias),
        multiplicity=_freeze(multiplicity),
        class_weight=_freeze(class_weight),
        total_rate=total_rate,
        kernel_sha256=actual_sha256,
        normalized_residual=normalized_residual,
    )


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def draw_alias(
    probability: F64,
    alias: I64,
    column_word: np.uint32,
    threshold_word: np.uint32,
) -> int:
    """Draw using a column word already accepted by Lemire rejection."""
    class_count = len(probability)
    column = np.int64(
        (
            np.uint64(column_word) * np.uint64(class_count)
        ) >> np.uint64(32)
    )
    threshold = (float(threshold_word) + 0.5) * (2.0**-32)
    if threshold <= probability[column]:
        return column
    return alias[column]
