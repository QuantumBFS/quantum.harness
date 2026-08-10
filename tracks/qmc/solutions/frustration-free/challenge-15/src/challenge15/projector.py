from __future__ import annotations

from math import pi

import jax
import jax.numpy as jnp
import numpy as np

from challenge15.projection_data import (
    ProjectionBlock,
    ProjectionGrid,
    StaticProjectionBlocks,
    coordinate_euler_substitutions,
    wigner_d_m0,
)
from challenge15.spec import SphereSpec


def project_m0(
    amplitude,
    spinors,
    spec: SphereSpec,
    target_l: int,
    *,
    grid: ProjectionGrid | None = None,
    block_size: int = 64,
):
    """Evaluate the exact pointwise ``P^L_00`` projection of an M=0 carrier."""

    return _project_components(
        amplitude,
        spinors,
        spec,
        target_l,
        components=(0,),
        grid=grid,
        block_size=block_size,
    )[0]


def project_multiplet(
    amplitude,
    spinors,
    spec: SphereSpec,
    target_l: int,
    *,
    grid: ProjectionGrid | None = None,
    block_size: int = 64,
) -> dict[int, jax.Array]:
    """Evaluate all ``P^L_M0`` components from one shared carrier callable."""

    components = tuple(range(-target_l, target_l + 1))
    values = _project_components(
        amplitude,
        spinors,
        spec,
        target_l,
        components=components,
        grid=grid,
        block_size=block_size,
    )
    return dict(zip(components, values, strict=True))


def _project_components(
    amplitude,
    spinors,
    spec: SphereSpec,
    target_l: int,
    *,
    components: tuple[int, ...],
    grid: ProjectionGrid | None,
    block_size: int,
) -> tuple[jax.Array, ...]:
    _validate_target_l(spec, target_l)
    _validate_block_size(block_size)
    active_grid = ProjectionGrid.exact(spec, target_l) if grid is None else grid
    _validate_grid(active_grid, spec, target_l)
    spinors_array = jnp.asarray(spinors, dtype=jnp.complex128)
    if spinors_array.shape != (spec.particles, 2):
        raise ValueError("spinors must have shape (spec.particles, 2)")

    prefactor = (2 * target_l + 1) / (4.0 * pi)
    accumulators: list[jax.Array | None] = [None] * len(components)
    for block in active_grid.iter_blocks(block_size):
        rotations = jnp.asarray(
            coordinate_euler_substitutions(block.alpha_nodes, block.beta_nodes),
            dtype=jnp.complex128,
        )
        rotated_spinors = jnp.einsum("kab,ib->kia", rotations, spinors_array)
        amplitudes = jax.vmap(amplitude)(rotated_spinors)
        for index, m in enumerate(components):
            kernel = (
                prefactor
                * block.weights
                * wigner_d_m0(target_l, m, block.beta_nodes)
                * np.exp(1j * m * block.alpha_nodes)
            )
            contribution = jnp.tensordot(
                jnp.asarray(kernel, dtype=jnp.complex128),
                amplitudes,
                axes=((0,), (0,)),
            )
            accumulators[index] = (
                contribution
                if accumulators[index] is None
                else accumulators[index] + contribution
            )
    return tuple(jnp.asarray(value) for value in accumulators)


def _validate_grid(grid: ProjectionGrid, spec: SphereSpec, target_l: int) -> None:
    if grid.target_l != target_l or grid.l_max != spec.l_max:
        raise ValueError("grid must match the supplied SphereSpec and target_l")
    if grid.n_alpha < 2 * spec.l_max + 1:
        raise ValueError("alpha rule does not satisfy the exact finite-band bound")
    if 2 * grid.n_beta - 1 < spec.l_max + target_l:
        raise ValueError("beta rule does not satisfy the exact polynomial bound")


def _validate_target_l(spec: SphereSpec, target_l: int) -> None:
    if not isinstance(target_l, int) or isinstance(target_l, bool):
        raise ValueError("target_l must be a Python integer")
    if target_l < 0 or target_l > spec.l_max:
        raise ValueError("target_l must satisfy 0 <= target_l <= spec.l_max")


def _validate_block_size(block_size: int) -> None:
    if (
        not isinstance(block_size, int)
        or isinstance(block_size, bool)
        or block_size <= 0
    ):
        raise ValueError("block_size must be a positive Python integer")
