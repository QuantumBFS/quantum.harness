"""Cubic Edwards-Anderson Ising model with iid binary bonds."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EABonds:
    """Positive-axis bonds for a periodic cubic lattice.

    ``values[x, y, z, axis]`` couples a site to its positive neighbor along
    ``axis``. Each periodic bond is therefore stored exactly once.
    """

    values: np.ndarray

    def __post_init__(self) -> None:
        raw = np.asarray(self.values)
        if (
            raw.ndim != 4
            or raw.shape[-1] != 3
            or raw.shape[0] != raw.shape[1]
            or raw.shape[1] != raw.shape[2]
        ):
            raise ValueError("bond values must have cubic shape (L, L, L, 3)")
        if raw.shape[0] < 2:
            raise ValueError("bond length must be at least two")
        if not np.all((raw == -1) | (raw == 1)):
            raise ValueError("bond values must contain only -1 and +1")
        values = np.array(raw, dtype=np.int8, copy=True)
        values.setflags(write=False)
        object.__setattr__(self, "values", values)

    @property
    def length(self) -> int:
        return int(self.values.shape[0])

    @classmethod
    def sample(cls, length: int, rng: np.random.Generator) -> "EABonds":
        if isinstance(length, (bool, np.bool_)) or not isinstance(
            length, (int, np.integer)
        ):
            raise ValueError("length must be an integer")
        length = int(length)
        if length < 2:
            raise ValueError("length must be at least two")
        if not isinstance(rng, np.random.Generator):
            raise TypeError("rng must be a numpy.random.Generator")
        bits = rng.integers(
            0,
            2,
            size=(length, length, length, 3),
            dtype=np.int8,
        )
        return cls(2 * bits - 1)


def _validated_spins(spins: np.ndarray, bonds: EABonds) -> np.ndarray:
    if not isinstance(bonds, EABonds):
        raise TypeError("bonds must be an EABonds instance")
    values = np.asarray(spins)
    expected_shape = (bonds.length, bonds.length, bonds.length)
    if values.shape != expected_shape:
        raise ValueError(f"spins must have shape {expected_shape}")
    if not np.all((values == -1) | (values == 1)):
        raise ValueError("spins must contain only -1 and +1")
    return values


def energy(spins: np.ndarray, bonds: EABonds) -> int:
    """Return H_J(s) = -sum_(x,mu) J_(x,mu) s_x s_(x+mu)."""
    values = _validated_spins(spins, bonds)
    total = 0
    for axis in range(3):
        shifted = np.roll(values, -1, axis=axis)
        total -= int(
            np.sum(
                bonds.values[..., axis] * values * shifted,
                dtype=np.int64,
            )
        )
    return total


def delta_energy(
    spins: np.ndarray,
    bonds: EABonds,
    site: tuple[int, int, int],
) -> int:
    """Return the exact energy change caused by flipping one spin."""
    values = _validated_spins(spins, bonds)
    if len(site) != 3 or any(
        isinstance(index, (bool, np.bool_))
        or not isinstance(index, (int, np.integer))
        for index in site
    ):
        raise ValueError("site must contain three integer coordinates")
    coordinates = tuple(int(index) for index in site)
    if any(index < 0 or index >= bonds.length for index in coordinates):
        raise ValueError("site coordinates are outside the lattice")

    local_field = 0
    for axis in range(3):
        plus = list(coordinates)
        minus = list(coordinates)
        plus[axis] = (plus[axis] + 1) % bonds.length
        minus[axis] = (minus[axis] - 1) % bonds.length
        local_field += int(
            bonds.values[coordinates + (axis,)] * values[tuple(plus)]
        )
        local_field += int(
            bonds.values[tuple(minus) + (axis,)] * values[tuple(minus)]
        )
    return 2 * int(values[coordinates]) * local_field


def three_color_sites(length: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Partition a periodic cubic lattice into three independent color sets."""
    if isinstance(length, (bool, np.bool_)) or not isinstance(
        length, (int, np.integer)
    ):
        raise ValueError("length must be an integer")
    length = int(length)
    if length < 3:
        raise ValueError("length must be at least three")
    if length % 3:
        raise ValueError("periodic three-coloring requires length divisible by three")
    coordinates = np.indices(
        (length, length, length),
        dtype=np.int64,
    ).reshape(3, -1).T
    labels = np.sum(coordinates, axis=1, dtype=np.int64) % 3
    return (
        coordinates[labels == 0].copy(),
        coordinates[labels == 1].copy(),
        coordinates[labels == 2].copy(),
    )
