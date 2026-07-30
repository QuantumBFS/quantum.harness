from __future__ import annotations

from collections.abc import Iterable, Iterator

import jax
import jax.numpy as jnp

from challenge15.fermions import DeterminantBasis
from challenge15.monopole import raw_north_lll_polynomials
from challenge15.pfaffian import _trusted_bordered_pfaffian, _trusted_pfaffian
from challenge15.physics_data import pair_channel_indices
from challenge15.spec import SphereSpec

_SKEW_TOLERANCE = 1e-12


def _channel_indices(spec: SphereSpec):
    return pair_channel_indices(spec)


def _validate_pair_weights(spec: SphereSpec, pair_weights) -> jax.Array:
    weights = jnp.asarray(pair_weights, dtype=jnp.complex128)
    channel_count = len(_channel_indices(spec)[0])
    if weights.shape != (channel_count,):
        raise ValueError(
            f"pair_weights must have one entry per positive-m channel ({channel_count})"
        )
    return weights


def _orbital_pair_matrix(spec: SphereSpec, pair_weights) -> jax.Array:
    weights = _validate_pair_weights(spec, pair_weights)
    positive, negative = _channel_indices(spec)
    matrix = jnp.zeros(
        (spec.orbital_count, spec.orbital_count), dtype=jnp.complex128
    )
    matrix = matrix.at[jnp.asarray(positive), jnp.asarray(negative)].set(weights)
    matrix = matrix.at[jnp.asarray(negative), jnp.asarray(positive)].set(-weights)
    return matrix


def _validate_generated_skew(matrix: jax.Array) -> None:
    if not isinstance(matrix, jax.core.Tracer):
        skew_error = jnp.max(jnp.abs(matrix + matrix.T))
        if bool(skew_error > _SKEW_TOLERANCE):
            raise ValueError("generated carrier matrix is not skew-symmetric")


def carrier_amplitudes(
    spinors,
    spec: SphereSpec,
    pair_weights,
    border_weight=1.0,
) -> jax.Array:
    """Evaluate one carrier or a leading-axis bank of carriers."""
    spinors_array = jnp.asarray(spinors)
    if spinors_array.ndim != 2 or spinors_array.shape != (spec.particles, 2):
        raise ValueError("spinors must have shape (spec.particles, 2)")
    weights_array = jnp.asarray(pair_weights, dtype=jnp.complex128)
    if weights_array.ndim == 1:
        return _single_carrier_amplitude(
            spinors_array, spec, weights_array, border_weight
        )
    channel_count = len(_channel_indices(spec)[0])
    if weights_array.ndim != 2 or weights_array.shape[1] != channel_count:
        raise ValueError(
            f"pair_weights must have one entry per positive-m channel ({channel_count})"
        )
    borders = jnp.asarray(border_weight, dtype=jnp.complex128)
    if borders.ndim == 0:
        borders = jnp.broadcast_to(borders, (weights_array.shape[0],))
    if borders.shape != (weights_array.shape[0],):
        raise ValueError("border_weight must be scalar or have one entry per carrier")
    return jax.vmap(
        lambda weights, border: _single_carrier_amplitude(
            spinors_array, spec, weights, border
        )
    )(weights_array, borders)


def batched_carrier_amplitudes(
    spinors,
    spec: SphereSpec,
    pair_weights,
    border_weight=1.0,
) -> jax.Array:
    """Evaluate a static walker/carrier block with shape ``[W, C]``."""

    spinors_array = jnp.asarray(spinors, dtype=jnp.complex128)
    if (
        spinors_array.ndim != 3
        or spinors_array.shape[1:] != (spec.particles, 2)
    ):
        raise ValueError("spinors must have shape (walkers, spec.particles, 2)")
    weights_array = jnp.asarray(pair_weights, dtype=jnp.complex128)
    if weights_array.ndim != 2:
        raise ValueError("pair_weights must contain a leading carrier axis")
    return jax.vmap(
        lambda walker: carrier_amplitudes(
            walker,
            spec,
            weights_array,
            border_weight=border_weight,
        )
    )(spinors_array)


def _single_carrier_amplitude(
    spinors: jax.Array,
    spec: SphereSpec,
    pair_weights,
    border_weight,
) -> jax.Array:
    orbitals = raw_north_lll_polynomials(spinors, spec)
    weights = _validate_pair_weights(spec, pair_weights)
    positive, negative = _channel_indices(spec)
    positive_values = orbitals[:, jnp.asarray(positive)]
    negative_values = orbitals[:, jnp.asarray(negative)]

    forward = jnp.einsum(
        "ik,k,jk->ij", positive_values, weights, negative_values
    )
    pair_matrix = forward - forward.T
    _validate_generated_skew(pair_matrix)

    if spec.particles % 2 == 0:
        return _trusted_pfaffian(pair_matrix)

    zero_orbital = spec.two_m_values.index(0)
    border = jnp.asarray(border_weight, dtype=jnp.complex128) * orbitals[:, zero_orbital]
    return _trusted_bordered_pfaffian(pair_matrix, border)


def carrier_determinant_coefficients(
    spec: SphereSpec,
    pair_weights,
    border_weight=1.0,
    states: Iterable[int] | None = None,
    *,
    block_size: int = 256,
) -> jax.Array:
    """Return analytic coefficients in ordered orbital-determinant convention.

    By default coefficients follow ``DeterminantBasis.with_two_m(spec, 0)``.
    Optional ``states`` permits the same evaluation in another caller-defined
    ordering.
    """
    blocks = tuple(
        iter_carrier_determinant_coefficient_blocks(
            spec,
            pair_weights,
            border_weight=border_weight,
            states=states,
            block_size=block_size,
        )
    )
    weights_array = jnp.asarray(pair_weights, dtype=jnp.complex128)
    if not blocks:
        shape = (0,) if weights_array.ndim == 1 else (weights_array.shape[0], 0)
        return jnp.empty(shape, dtype=jnp.complex128)
    return jnp.concatenate(blocks, axis=-1)


def iter_carrier_determinant_coefficient_blocks(
    spec: SphereSpec,
    pair_weights,
    border_weight=1.0,
    states: Iterable[int] | None = None,
    *,
    block_size: int = 256,
) -> Iterator[jax.Array]:
    """Yield analytic determinant coefficients in bounded state blocks."""

    if (
        not isinstance(block_size, int)
        or isinstance(block_size, bool)
        or block_size <= 0
    ):
        raise ValueError("block_size must be a positive Python integer")
    ordered_states = (
        DeterminantBasis.with_two_m(spec, 0).states
        if states is None
        else tuple(states)
    )
    weights_array = jnp.asarray(pair_weights, dtype=jnp.complex128)
    if weights_array.ndim == 1:
        _validate_pair_weights(spec, weights_array)
        for start in range(0, len(ordered_states), block_size):
            yield _single_determinant_coefficients(
                spec,
                weights_array,
                border_weight,
                ordered_states[start : start + block_size],
            )
        return
    channel_count = len(_channel_indices(spec)[0])
    if weights_array.ndim != 2 or weights_array.shape[1] != channel_count:
        raise ValueError(
            f"pair_weights must have one entry per positive-m channel ({channel_count})"
        )
    borders = jnp.asarray(border_weight, dtype=jnp.complex128)
    if borders.ndim == 0:
        borders = jnp.broadcast_to(borders, (weights_array.shape[0],))
    if borders.shape != (weights_array.shape[0],):
        raise ValueError("border_weight must be scalar or have one entry per carrier")
    for start in range(0, len(ordered_states), block_size):
        state_block = ordered_states[start : start + block_size]
        yield jax.vmap(
            lambda weights, border: _single_determinant_coefficients(
                spec, weights, border, state_block
            )
        )(weights_array, borders)


def iter_orbital_pfaffian_coefficient_blocks(
    spec: SphereSpec,
    pair_matrix,
    border_vector,
    *,
    states: Iterable[int] | None = None,
    block_size: int = 256,
) -> Iterator[jax.Array]:
    """Yield coefficients from already-built orbital Pfaffian data."""

    if (
        not isinstance(block_size, int)
        or isinstance(block_size, bool)
        or block_size <= 0
    ):
        raise ValueError("block_size must be a positive Python integer")
    matrix = jnp.asarray(pair_matrix, dtype=jnp.complex128)
    if matrix.shape != (spec.orbital_count, spec.orbital_count):
        raise ValueError("pair_matrix must have one row and column per orbital")
    _validate_generated_skew(matrix)
    border = jnp.asarray(border_vector, dtype=jnp.complex128)
    if border.shape != (spec.orbital_count,):
        raise ValueError("border_vector must have one entry per orbital")
    ordered_states = (
        DeterminantBasis.with_two_m(spec, 0).states
        if states is None
        else tuple(states)
    )
    for start in range(0, len(ordered_states), block_size):
        yield _orbital_pfaffian_coefficients(
            spec,
            matrix,
            border,
            ordered_states[start : start + block_size],
        )


def _orbital_pfaffian_coefficients(
    spec: SphereSpec,
    pair_matrix: jax.Array,
    border_vector: jax.Array,
    ordered_states: tuple[int, ...],
) -> jax.Array:
    coefficients = []
    for state in ordered_states:
        if not isinstance(state, int) or isinstance(state, bool):
            raise ValueError("states must contain integer bit patterns")
        occupied = tuple(
            orbital
            for orbital in range(spec.orbital_count)
            if state & (1 << orbital)
        )
        if len(occupied) != spec.particles:
            raise ValueError("each state must occupy spec.particles orbitals")
        occupied_indices = jnp.asarray(occupied)
        restricted = pair_matrix[
            occupied_indices[:, None], occupied_indices[None, :]
        ]
        if spec.particles % 2 == 0:
            coefficients.append(_trusted_pfaffian(restricted))
        else:
            coefficients.append(
                _trusted_bordered_pfaffian(
                    restricted,
                    border_vector[occupied_indices],
                )
            )
    if not coefficients:
        return jnp.empty((0,), dtype=jnp.complex128)
    return jnp.stack(coefficients)


def _single_determinant_coefficients(
    spec: SphereSpec,
    pair_weights,
    border_weight,
    ordered_states: tuple[int, ...],
) -> jax.Array:
    pair_matrix = _orbital_pair_matrix(spec, pair_weights)
    _validate_generated_skew(pair_matrix)
    border = jnp.zeros((spec.orbital_count,), dtype=jnp.complex128)
    if spec.particles % 2:
        zero_orbital = spec.two_m_values.index(0)
        border = border.at[zero_orbital].set(
            jnp.asarray(border_weight, dtype=jnp.complex128)
        )
    return _orbital_pfaffian_coefficients(
        spec, pair_matrix, border, ordered_states
    )
