from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterator


def _strict_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


@dataclass(frozen=True)
class ModelSpec:
    length: int
    sigma: float
    kappa: float

    def __post_init__(self) -> None:
        length = _strict_int(self.length, "length")
        if length < 2 or length % 2:
            raise ValueError("length must be even and at least two")
        if (
            isinstance(self.sigma, bool)
            or not isinstance(self.sigma, (int, float))
            or not math.isfinite(float(self.sigma))
            or float(self.sigma) <= 0.0
        ):
            raise ValueError("sigma must be finite and positive")
        if (
            isinstance(self.kappa, bool)
            or not isinstance(self.kappa, (int, float))
            or not math.isfinite(float(self.kappa))
            or float(self.kappa) < 0.0
        ):
            raise ValueError("kappa must be finite and nonnegative")


@dataclass(frozen=True)
class DistanceClass:
    distance: int
    multiplicity: int


def distance_classes(length: int) -> tuple[DistanceClass, ...]:
    length = _strict_int(length, "length")
    if length < 2 or length % 2:
        raise ValueError("length must be even and at least two")
    return tuple(
        DistanceClass(
            distance=distance,
            multiplicity=length if distance < length // 2 else length // 2,
        )
        for distance in range(1, length // 2 + 1)
    )


def canonical_edge(length: int, distance: int, offset: int) -> tuple[int, int]:
    matching = {item.distance: item for item in distance_classes(length)}
    if distance not in matching:
        raise ValueError("distance is outside the canonical range")
    if isinstance(offset, bool) or not isinstance(offset, int):
        raise ValueError("offset must be an integer")
    if not 0 <= offset < matching[distance].multiplicity:
        raise ValueError("offset is outside the distance class")
    left = offset
    right = (offset + distance) % length
    return (left, right) if left < right else (right, left)


def iter_unordered_edges(length: int) -> Iterator[tuple[int, int]]:
    distance_classes(length)
    for left in range(length):
        for right in range(left + 1, length):
            yield left, right
