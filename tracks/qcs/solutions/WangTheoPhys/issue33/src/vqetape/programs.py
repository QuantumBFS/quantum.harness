"""Forward-control-flow and reverse-schedule program builders."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil

import jax
import jax.numpy as jnp
from jax import Array

from vqetape.kernels import apply_layer, initial_state, tfim_energy, unrolled_energy
from vqetape.spec import ProgramConfig, TFIMVQESpec

EnergyFunction = Callable[[Array], Array]
ValueAndGradFunction = Callable[[Array], tuple[Array, Array]]


def _scan_energy_function(
    spec: TFIMVQESpec,
    config: ProgramConfig,
) -> EnergyFunction:
    def layer_body(state: Array, theta_layer: Array) -> tuple[Array, None]:
        return apply_layer(state, theta_layer, spec), None

    body = jax.checkpoint(layer_body) if config.adjoint == "remat" else layer_body

    def energy(theta: Array) -> Array:
        final_state, _ = jax.lax.scan(
            body,
            initial_state(spec),
            theta,
            unroll=min(config.unroll, spec.depth),
        )
        return tfim_energy(final_state, spec)

    return energy


def _segmented_energy_function(
    spec: TFIMVQESpec,
    config: ProgramConfig,
) -> EnergyFunction:
    """Build an energy function with a sparse-checkpoint custom state VJP."""

    assert config.segment_length is not None
    segment_length = config.segment_length
    segment_count = ceil(spec.depth / segment_length)
    padded_depth = segment_count * segment_length
    padding_layers = padded_depth - spec.depth
    segment_unroll = min(config.unroll, segment_length)

    def layer_body(state: Array, theta_layer: Array) -> tuple[Array, None]:
        return apply_layer(state, theta_layer, spec), None

    def run_segment(state: Array, theta_segment: Array) -> Array:
        final_state, _ = jax.lax.scan(
            layer_body,
            state,
            theta_segment,
            unroll=segment_unroll,
        )
        return final_state

    def prepare_segments(theta: Array) -> Array:
        if padding_layers:
            theta = jnp.pad(
                theta,
                ((0, padding_layers), (0, 0), (0, 0)),
            )
        return theta.reshape(
            segment_count,
            segment_length,
            2,
            spec.nqubits,
        )

    def evolve_with_checkpoints(theta: Array) -> tuple[Array, Array, Array]:
        segments = prepare_segments(theta)

        def segment_body(
            state: Array,
            theta_segment: Array,
        ) -> tuple[Array, Array]:
            next_state = run_segment(state, theta_segment)
            return next_state, state

        final_state, checkpoints = jax.lax.scan(
            segment_body,
            initial_state(spec),
            segments,
        )
        return final_state, segments, checkpoints

    @jax.custom_vjp
    def segmented_state(theta: Array) -> Array:
        final_state, _, _ = evolve_with_checkpoints(theta)
        return final_state

    def segmented_state_fwd(theta: Array):
        final_state, segments, checkpoints = evolve_with_checkpoints(theta)
        return final_state, (segments, checkpoints)

    def segmented_state_bwd(residual, final_state_cotangent: Array):
        segments, checkpoints = residual

        def reverse_segment(
            state_cotangent: Array,
            inputs: tuple[Array, Array],
        ) -> tuple[Array, Array]:
            theta_segment, left_state = inputs
            _, pullback = jax.vjp(run_segment, left_state, theta_segment)
            left_cotangent, theta_cotangent = pullback(state_cotangent)
            return left_cotangent, theta_cotangent

        _, segment_cotangents = jax.lax.scan(
            reverse_segment,
            final_state_cotangent,
            (segments, checkpoints),
            reverse=True,
        )
        theta_cotangent = segment_cotangents.reshape(
            padded_depth,
            2,
            spec.nqubits,
        )[: spec.depth]
        return (theta_cotangent,)

    segmented_state.defvjp(segmented_state_fwd, segmented_state_bwd)

    def energy(theta: Array) -> Array:
        return tfim_energy(segmented_state(theta), spec)

    return energy


def build_energy_function(
    spec: TFIMVQESpec,
    config: ProgramConfig,
) -> EnergyFunction:
    """Build an un-jitted scalar energy function for one program choice."""

    if config.adjoint == "segmented":
        return _segmented_energy_function(spec, config)
    if config.control_flow == "unrolled":
        if config.adjoint != "default":
            raise ValueError("unrolled program supports only default adjoint")
        return lambda theta: unrolled_energy(theta, spec)
    return _scan_energy_function(spec, config)


def build_value_and_grad(
    spec: TFIMVQESpec,
    config: ProgramConfig,
) -> ValueAndGradFunction:
    """Build a JIT-compiled exact VQE value-and-gradient executable."""

    energy = build_energy_function(spec, config)
    return jax.jit(jax.value_and_grad(energy))
