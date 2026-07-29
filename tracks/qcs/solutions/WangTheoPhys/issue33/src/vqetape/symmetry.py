"""Exact Abelian symmetry metadata for spatial VQE boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import prod
from typing import Any

import jax.numpy as jnp
from jax import Array

from vqetape.spec import TFIMVQESpec

_TFIM_MPO_Z2_CHARGES = (0, 1, 0)


@dataclass(frozen=True)
class Z2BoundarySector:
    """Active positive-parity positions of one dense boundary."""

    dense_shape: tuple[int, ...]
    active_positions: tuple[int, ...]
    forbidden_positions: tuple[int, ...]
    mpo_charges: tuple[int, int, int] = (
        _TFIM_MPO_Z2_CHARGES
    )

    @property
    def active_count(self) -> int:
        return len(self.active_positions)

    @property
    def dense_count(self) -> int:
        return prod(self.dense_shape)

    @property
    def active_fraction(self) -> float:
        return self.active_count / self.dense_count

    @property
    def compression_factor(self) -> float:
        return self.dense_count / self.active_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "symmetry": "global_x_z2",
            "dense_shape": list(self.dense_shape),
            "active_positions": list(self.active_positions),
            "forbidden_positions": list(
                self.forbidden_positions
            ),
            "mpo_charges": list(self.mpo_charges),
            "active_count": self.active_count,
            "dense_count": self.dense_count,
            "active_fraction": self.active_fraction,
            "compression_factor": self.compression_factor,
        }


def _flat_position(
    coordinates: tuple[int, ...],
    shape: tuple[int, ...],
) -> int:
    position = 0
    for coordinate, extent in zip(
        coordinates,
        shape,
        strict=True,
    ):
        position = position * extent + coordinate
    return position


def z2_boundary_sector(
    boundary_shape: tuple[int, ...],
) -> Z2BoundarySector:
    """Derive the exact positive global-X boundary sector."""

    shape = tuple(int(extent) for extent in boundary_shape)
    if (
        len(shape) < 3
        or len(shape) % 2 == 0
        or shape[-1] != 3
        or any(extent != 2 for extent in shape[:-1])
    ):
        raise ValueError(
            "boundary shape must contain an even positive number "
            "of dimension-two circuit legs followed by one "
            "dimension-three TFIM MPO leg"
        )

    circuit_leg_count = len(shape) - 1
    active: list[int] = []
    forbidden: list[int] = []
    for circuit_coordinates in product(
        (0, 1),
        repeat=circuit_leg_count,
    ):
        circuit_charge = 0
        for charge in circuit_coordinates:
            circuit_charge ^= charge
        for mpo_coordinate, mpo_charge in enumerate(
            _TFIM_MPO_Z2_CHARGES
        ):
            coordinates = (
                *circuit_coordinates,
                mpo_coordinate,
            )
            position = _flat_position(coordinates, shape)
            target = (
                active
                if circuit_charge ^ mpo_charge == 0
                else forbidden
            )
            target.append(position)

    return Z2BoundarySector(
        dense_shape=shape,
        active_positions=tuple(sorted(active)),
        forbidden_positions=tuple(sorted(forbidden)),
    )


def z2_symmetry_applicability(
    spec: TFIMVQESpec,
) -> tuple[bool, str]:
    """Return whether the configured workload is in a fixed Z2 sector."""

    if spec.initial_state != "plus":
        return (
            False,
            "global-X Z2 compression requires the plus "
            "product initial state",
        )
    return True, "supported global-X Z2 sector"


def compress_boundary(
    boundary: Array,
    sector: Z2BoundarySector,
) -> Array:
    """Gather the exact active entries of a dense boundary."""

    if tuple(boundary.shape) != sector.dense_shape:
        raise ValueError(
            "dense boundary shape does not match Z2 sector"
        )
    positions = jnp.asarray(
        sector.active_positions,
        dtype=jnp.int32,
    )
    return boundary.reshape(-1)[positions]


def expand_boundary(
    compressed: Array,
    sector: Z2BoundarySector,
) -> Array:
    """Scatter an active-sector carry into its dense boundary shape."""

    expected = (sector.active_count,)
    if tuple(compressed.shape) != expected:
        raise ValueError(
            f"compressed boundary shape must be {expected}, "
            f"got {tuple(compressed.shape)}"
        )
    positions = jnp.asarray(
        sector.active_positions,
        dtype=jnp.int32,
    )
    dense = jnp.zeros(
        (sector.dense_count,),
        dtype=compressed.dtype,
    )
    return dense.at[positions].set(compressed).reshape(
        sector.dense_shape
    )


def forbidden_boundary_norm(
    boundary: Array,
    sector: Z2BoundarySector,
) -> Array:
    """Return the L2 norm of entries excluded by exact symmetry."""

    if tuple(boundary.shape) != sector.dense_shape:
        raise ValueError(
            "dense boundary shape does not match Z2 sector"
        )
    positions = jnp.asarray(
        sector.forbidden_positions,
        dtype=jnp.int32,
    )
    return jnp.linalg.norm(boundary.reshape(-1)[positions])
