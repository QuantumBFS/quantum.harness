"""Replica-overlap measurements for the three-dimensional spin glass."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


def _binary_cube(values: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(values)
    if (
        array.ndim != 3
        or array.shape[0] != array.shape[1]
        or array.shape[1] != array.shape[2]
        or array.shape[0] < 2
    ):
        raise ValueError(f"{name} must have cubic shape (L, L, L)")
    if not np.all((array == -1) | (array == 1)):
        raise ValueError(f"{name} must contain only -1 and +1")
    return array.astype(np.int8, copy=False)


@dataclass(frozen=True)
class ReplicaPair:
    """Two independently stored real replicas sharing one quenched disorder."""

    a: np.ndarray
    b: np.ndarray

    def __post_init__(self) -> None:
        raw_a = np.asarray(self.a)
        raw_b = np.asarray(self.b)
        if np.shares_memory(raw_a, raw_b):
            raise ValueError("replica arrays must not share memory")
        a = _binary_cube(raw_a, "replica a")
        b = _binary_cube(raw_b, "replica b")
        if a.shape != b.shape:
            raise ValueError("replica arrays must have the same shape")
        object.__setattr__(self, "a", a)
        object.__setattr__(self, "b", b)

    @property
    def length(self) -> int:
        return int(self.a.shape[0])

    def swapped(self) -> "ReplicaPair":
        return ReplicaPair(self.b, self.a)

    def flip_both(self) -> "ReplicaPair":
        return ReplicaPair(-self.a, -self.b)

    def flip_a(self) -> "ReplicaPair":
        return ReplicaPair(-self.a, self.b)

    def flip_b(self) -> "ReplicaPair":
        return ReplicaPair(self.a, -self.b)


@dataclass(frozen=True)
class OverlapMeasurement:
    length: int
    q: float
    q2: float
    q4: float
    abs_qk2: tuple[float, float, float]

    def __post_init__(self) -> None:
        values = (self.q, self.q2, self.q4, *self.abs_qk2)
        if self.length < 2 or len(self.abs_qk2) != 3:
            raise ValueError("overlap measurement has invalid geometry")
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("overlap measurement must be finite")
        if self.q2 < 0.0 or self.q4 < 0.0 or any(
            value < 0.0 for value in self.abs_qk2
        ):
            raise ValueError("overlap powers must be nonnegative")


@dataclass(frozen=True)
class DisorderRecord:
    """One thermally averaged record for one quenched J sample and temperature."""

    j_id: str
    temperature: float
    length: int
    measurement_count: int
    q_mean: float
    q2: float
    q4: float
    qk2_axes: tuple[float, float, float]

    def __post_init__(self) -> None:
        if not isinstance(self.j_id, str) or not self.j_id:
            raise ValueError("j_id must be a nonempty string")
        if not math.isfinite(self.temperature) or self.temperature <= 0.0:
            raise ValueError("temperature must be positive and finite")
        if self.length < 2 or self.measurement_count < 1:
            raise ValueError("record geometry and measurement count must be positive")
        if len(self.qk2_axes) != 3:
            raise ValueError("record must retain three axial k_min values")
        values = (self.q_mean, self.q2, self.q4, *self.qk2_axes)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("record values must be finite")
        if self.q2 < 0.0 or self.q4 < 0.0 or any(
            value < 0.0 for value in self.qk2_axes
        ):
            raise ValueError("record powers must be nonnegative")

    @property
    def qk2_mean(self) -> float:
        return float(sum(self.qk2_axes) / 3.0)


def overlap_field(pair: ReplicaPair) -> np.ndarray:
    """Return q_i = s_i^(a) s_i^(b) as an owned int8 array."""
    if not isinstance(pair, ReplicaPair):
        raise TypeError("pair must be a ReplicaPair")
    return np.multiply(pair.a, pair.b, dtype=np.int8)


def measure_sample(pair: ReplicaPair) -> OverlapMeasurement:
    field = overlap_field(pair)
    q = float(np.mean(field, dtype=np.float64))
    spectrum = np.fft.fftn(field.astype(np.float64)) / field.size
    axial = (
        float(abs(spectrum[1, 0, 0]) ** 2),
        float(abs(spectrum[0, 1, 0]) ** 2),
        float(abs(spectrum[0, 0, 1]) ** 2),
    )
    return OverlapMeasurement(
        length=pair.length,
        q=q,
        q2=q * q,
        q4=q**4,
        abs_qk2=axial,
    )


class ThermalOverlapAccumulator:
    """Thermally average measurements before emitting one whole-J record."""

    def __init__(self, length: int) -> None:
        if isinstance(length, (bool, np.bool_)) or not isinstance(
            length, (int, np.integer)
        ):
            raise ValueError("length must be an integer")
        if int(length) < 2:
            raise ValueError("length must be at least two")
        self.length = int(length)
        self._count = 0
        self._q = 0.0
        self._q2 = 0.0
        self._q4 = 0.0
        self._qk2 = np.zeros(3, dtype=np.float64)
        self._finalized = False

    def update(self, measurement: OverlapMeasurement) -> None:
        if self._finalized:
            raise RuntimeError("accumulator is already finalized")
        if not isinstance(measurement, OverlapMeasurement):
            raise TypeError("measurement must be an OverlapMeasurement")
        if measurement.length != self.length:
            raise ValueError("measurement length does not match accumulator")
        self._count += 1
        self._q += measurement.q
        self._q2 += measurement.q2
        self._q4 += measurement.q4
        self._qk2 += np.asarray(measurement.abs_qk2, dtype=np.float64)

    def finalize(self, j_id: str, temperature: float) -> DisorderRecord:
        if self._finalized:
            raise RuntimeError("accumulator is already finalized")
        if self._count == 0:
            raise RuntimeError("cannot finalize an empty accumulator")
        inverse_count = 1.0 / self._count
        record = DisorderRecord(
            j_id=j_id,
            temperature=float(temperature),
            length=self.length,
            measurement_count=self._count,
            q_mean=self._q * inverse_count,
            q2=self._q2 * inverse_count,
            q4=self._q4 * inverse_count,
            qk2_axes=tuple(float(value * inverse_count) for value in self._qk2),
        )
        self._finalized = True
        return record
