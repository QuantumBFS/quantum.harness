from __future__ import annotations

from dataclasses import dataclass
from math import comb, pi, sqrt

import numpy as np

from challenge15.spec import SphereSpec


CANONICAL_SECTORS: tuple[int, int] = (0, 2)


@dataclass(frozen=True, slots=True)
class OrbitalTable:
    """Immutable north-chart orbital normalization and power data."""

    normalizations: np.ndarray
    u_powers: np.ndarray
    v_powers: np.ndarray

    def __post_init__(self) -> None:
        arrays = (self.normalizations, self.u_powers, self.v_powers)
        if not all(isinstance(array, np.ndarray) for array in arrays):
            raise ValueError("orbital table entries must be NumPy arrays")
        if self.normalizations.dtype != np.complex128:
            raise ValueError("orbital normalizations must use complex128")
        if self.u_powers.dtype != np.int64 or self.v_powers.dtype != np.int64:
            raise ValueError("orbital powers must use int64")
        if (
            self.normalizations.ndim != 1
            or self.u_powers.shape != self.normalizations.shape
            or self.v_powers.shape != self.normalizations.shape
        ):
            raise ValueError("orbital table entries must be matching one-dimensional arrays")
        if not np.all(np.isfinite(self.normalizations)):
            raise ValueError("orbital normalizations must be finite")
        if np.any(self.u_powers < 0) or np.any(self.v_powers < 0):
            raise ValueError("orbital powers must be nonnegative")
        for name in ("normalizations", "u_powers", "v_powers"):
            object.__setattr__(self, name, _sealed_array(getattr(self, name)))


def orbital_table(spec: SphereSpec) -> OrbitalTable:
    """Return canonical north-chart orbital data for ``spec``."""

    u_powers = np.asarray(
        [
            (spec.two_q + two_m) // 2
            for two_m in spec.two_m_values
        ],
        dtype=np.int64,
    )
    v_powers = np.asarray(spec.two_q - u_powers, dtype=np.int64)
    normalizations = np.asarray(
        [
            sqrt(
                (spec.two_q + 1)
                / (4.0 * pi)
                * comb(spec.two_q, int(power_u))
            )
            for power_u in u_powers
        ],
        dtype=np.complex128,
    )
    return OrbitalTable(
        normalizations=normalizations,
        u_powers=u_powers,
        v_powers=v_powers,
    )


def pair_channel_indices(spec: SphereSpec) -> tuple[np.ndarray, np.ndarray]:
    """Return canonical positive- and negative-m pairing indices."""

    positive = np.asarray(
        [
            index
            for index, two_m in enumerate(spec.two_m_values)
            if two_m > 0
        ],
        dtype=np.int64,
    )
    negative = np.asarray(
        [
            spec.two_m_values.index(-spec.two_m_values[int(index)])
            for index in positive
        ],
        dtype=np.int64,
    )
    return _sealed_array(positive), _sealed_array(negative)


def _sealed_array(array: np.ndarray) -> np.ndarray:
    """Copy an array onto an immutable bytes backing store."""

    return np.frombuffer(array.tobytes(order="C"), dtype=array.dtype).reshape(array.shape)
