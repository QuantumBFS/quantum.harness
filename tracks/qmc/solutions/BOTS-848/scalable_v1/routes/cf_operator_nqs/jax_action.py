"""Exact JAX/x64 pair-Casimir action on analytic JK cofactor seeds."""

from __future__ import annotations

from typing import Callable, Literal

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp
import numpy as np

from .local_jets import local_pair_seed_jets
from .pair_casimir import pair_casimir_decomposition
from .seeds import JKCFSeedFamily


Sector = Literal["l0", "l2", "family"]
_SECTORS: dict[str, tuple[int, ...]] = {
    "l0": (0,),
    "l2": (1, 2, 3, 4, 5),
    "family": (0, 1, 2, 3, 4, 5),
}
_RANKS = (2, 3, 4)
_GENERATOR_Z = np.asarray(((0.5, 0.0), (0.0, -0.5)), dtype=np.complex128)
_GENERATOR_PLUS = np.asarray(((0.0, 0.0), (1.0, 0.0)), dtype=np.complex128)
_GENERATOR_MINUS = np.asarray(((0.0, 1.0), (0.0, 0.0)), dtype=np.complex128)


def _selected_device(platform: str) -> jax.Device:
    if not isinstance(platform, str) or not platform:
        raise TypeError("platform must be a nonempty string")
    try:
        devices = jax.devices(platform)
    except Exception as error:
        raise RuntimeError(f"requested JAX platform is unavailable: {platform}") from error
    if not devices or any(device.platform != platform for device in devices):
        raise RuntimeError(f"requested JAX platform is unavailable: {platform}")
    return devices[0]


def _pair_casimir_tables(
    family: JKCFSeedFamily,
) -> tuple[np.ndarray, np.ndarray, float]:
    ranks = tuple(ell for ell in _RANKS if ell <= family.two_q)
    decompositions = tuple(
        pair_casimir_decomposition(two_q=family.two_q, ell=ell) for ell in ranks
    )
    scale = decompositions[0].scale
    if not all(
        np.isclose(item.scale, scale, rtol=0.0, atol=1.0e-13)
        for item in decompositions
    ):
        raise ValueError("pair-Casimir scales are inconsistent")
    coefficients = np.zeros((len(ranks), 5), dtype=np.complex128)
    for row, item in enumerate(decompositions):
        coefficients[row, : len(item.coefficients)] = item.coefficients
    self_scalars = np.asarray(
        [item.self_scalar for item in decompositions],
        dtype=np.complex128,
    )
    return coefficients, self_scalars, scale


def _local_generator_matrix(
    spinor: jax.Array,
    generator: jax.Array,
    *,
    homogeneous_degree: int,
) -> jax.Array:
    u, v = spinor[0], spinor[1]
    frame = jnp.asarray(((u, -jnp.conj(v)), (v, jnp.conj(u))))
    inverse = jnp.asarray(((jnp.conj(u), jnp.conj(v)), (-v, u)))
    transformed = inverse @ generator @ frame
    indices = jnp.arange(5)
    result = jnp.zeros((5, 5), dtype=jnp.complex128)
    diagonal = (
        (homogeneous_degree - indices) * transformed[0, 0]
        + indices * transformed[1, 1]
    )
    result = result.at[indices, indices].set(diagonal)
    upper_rows = jnp.arange(4)
    result = result.at[upper_rows, upper_rows + 1].set(
        (upper_rows + 1) * transformed[1, 0]
    )
    lower_rows = jnp.arange(1, 5)
    result = result.at[lower_rows, lower_rows - 1].set(
        (homogeneous_degree - lower_rows + 1) * transformed[0, 1]
    )
    return result


def _pair_functionals(
    first_spinors: jax.Array,
    second_spinors: jax.Array,
    coefficients: jax.Array,
    scale: jax.Array,
    *,
    homogeneous_degree: int,
) -> jax.Array:
    generators = jnp.asarray(
        (_GENERATOR_Z, _GENERATOR_PLUS, _GENERATOR_MINUS),
        dtype=jnp.complex128,
    )

    def matrices(spinor: jax.Array) -> jax.Array:
        return jax.vmap(
            lambda generator: _local_generator_matrix(
                spinor,
                generator,
                homogeneous_degree=homogeneous_degree,
            )
        )(generators)

    first = jax.vmap(jax.vmap(matrices))(first_spinors)
    second = jax.vmap(jax.vmap(matrices))(second_spinors)

    def adjoint_pair_dot(functional: jax.Array) -> jax.Array:
        zz = jnp.einsum(
            "...ia,...ij,...jb->...ab",
            first[..., 0, :, :],
            functional,
            second[..., 0, :, :],
        )
        plus_minus = jnp.einsum(
            "...ia,...ij,...jb->...ab",
            first[..., 1, :, :],
            functional,
            second[..., 2, :, :],
        )
        minus_plus = jnp.einsum(
            "...ia,...ij,...jb->...ab",
            first[..., 2, :, :],
            functional,
            second[..., 1, :, :],
        )
        return zz + 0.5 * (plus_minus + minus_plus)

    functional = jnp.zeros((*first_spinors.shape[:2], 5, 5), dtype=jnp.complex128)
    functional = functional.at[..., 0, 0].set(1.0)
    powers = [functional]
    for _ in range(4):
        functional = adjoint_pair_dot(functional) / scale
        powers.append(functional)
    stacked = jnp.stack(powers, axis=0)
    return jnp.einsum("rk,k...ab->r...ab", coefficients, stacked)


def build_family_action_kernel(
    family: JKCFSeedFamily,
    *,
    platform: str,
    sector: Sector,
) -> Callable[[object], tuple[jax.Array, jax.Array]]:
    """Build a whole-batch exact seed/action kernel on one explicit device."""

    if not isinstance(family, JKCFSeedFamily):
        raise TypeError("family must be a JKCFSeedFamily")
    if sector not in _SECTORS:
        raise ValueError("sector must be 'l0', 'l2', or 'family'")
    device = _selected_device(platform)
    raw_coefficients, raw_self_scalars, raw_scale = _pair_casimir_tables(family)
    coefficients = jnp.asarray(raw_coefficients, dtype=jnp.complex128)
    self_scalars = jnp.asarray(raw_self_scalars, dtype=jnp.complex128)
    scale = jnp.asarray(raw_scale, dtype=jnp.float64)
    selected = jnp.asarray(_SECTORS[sector], dtype=jnp.int32)
    pairs = jnp.asarray(
        [
            (first, second)
            for first in range(family.n_electrons)
            for second in range(first + 1, family.n_electrons)
        ],
        dtype=jnp.int32,
    )

    def batch_function(configs: jax.Array) -> tuple[jax.Array, jax.Array]:
        seed_jets = jnp.take(
            local_pair_seed_jets(family, configs, pairs),
            selected,
            axis=0,
        )
        seed_values = jnp.transpose(seed_jets[:, :, 0, 0, 0], (1, 0))
        first_spinors = configs[:, pairs[:, 0], :]
        second_spinors = configs[:, pairs[:, 1], :]
        functionals = _pair_functionals(
            first_spinors,
            second_spinors,
            coefficients,
            scale,
            homogeneous_degree=family.two_q,
        )
        pair_actions = jnp.einsum(
            "rbpij,sbpij->srbp",
            functionals,
            seed_jets,
        )
        summed = jnp.sum(pair_actions, axis=-1)
        actions = jnp.transpose(summed, (2, 0, 1)) + (
            family.n_electrons * seed_values[:, :, None] * self_scalars[None, None, :]
        )
        return seed_values, actions

    compiled = jax.jit(batch_function)

    def placed_kernel(configs: object) -> tuple[jax.Array, jax.Array]:
        placed = jax.device_put(
            jnp.asarray(configs, dtype=jnp.complex128),
            device,
        )
        return compiled(placed)

    return placed_kernel


__all__ = ["build_family_action_kernel"]
