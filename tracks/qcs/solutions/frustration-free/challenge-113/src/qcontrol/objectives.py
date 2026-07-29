from __future__ import annotations

import jax
import jax.numpy as jnp

from qcontrol.propagation import propagate
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem


def _unclipped_process_infidelity(
    unitary: object,
    target: object,
) -> jax.Array:
    unitary_array = jnp.asarray(unitary, dtype=jnp.complex128)
    target_array = jnp.asarray(target, dtype=jnp.complex128)
    if unitary_array.ndim != 2 or unitary_array.shape[0] != unitary_array.shape[1]:
        raise ValueError("unitary must be a square matrix")
    if target_array.shape != unitary_array.shape:
        raise ValueError("target must match the unitary shape")

    dimension = unitary_array.shape[0]
    overlap = jnp.trace(target_array.conj().T @ unitary_array)
    fidelity = jnp.real(overlap.conj() * overlap) / jnp.float64(dimension**2)
    return jnp.asarray(1.0 - fidelity, dtype=jnp.float64)


def process_infidelity_from_unitary(
    unitary: object,
    target: object,
) -> jax.Array:
    loss = _unclipped_process_infidelity(unitary, target)
    return jnp.clip(loss, jnp.float64(0.0), jnp.float64(1.0))


def normalized_infidelity(
    normalized: object,
    system: ControlSystem,
    space: PulseSpace,
) -> jax.Array:
    if not isinstance(system, ControlSystem):
        raise ValueError("system must be a ControlSystem")
    if not isinstance(space, PulseSpace):
        raise ValueError("space must be a PulseSpace")
    if len(system.controls) != space.control_count:
        raise ValueError("pulse space control count does not match the system")

    physical_pulse = space.to_physical(normalized)
    unitary = propagate(system, physical_pulse)
    return _unclipped_process_infidelity(unitary, system.target)
