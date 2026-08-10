from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np

from qcontrol.propagation import propagate
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem


def _raise_for_nonfinite_eager(array: jax.Array, name: str) -> None:
    if isinstance(array, jax.core.Tracer):
        return
    if not np.all(np.isfinite(np.asarray(array))):
        raise ValueError(f"{name} must contain only finite values")


def _guarded_unclipped_process_infidelity(
    unitary: object,
    target: object,
) -> tuple[jax.Array, jax.Array]:
    unitary_array = jnp.asarray(unitary, dtype=jnp.complex128)
    target_array = jnp.asarray(target, dtype=jnp.complex128)
    if (
        unitary_array.ndim != 2
        or unitary_array.shape[0] == 0
        or unitary_array.shape[0] != unitary_array.shape[1]
    ):
        raise ValueError("unitary must be a nonempty square matrix")
    if target_array.shape != unitary_array.shape:
        raise ValueError("target must match the unitary shape")
    _raise_for_nonfinite_eager(unitary_array, "unitary")
    _raise_for_nonfinite_eager(target_array, "target")

    dimension = unitary_array.shape[0]
    valid = jnp.all(jnp.isfinite(unitary_array)) & jnp.all(
        jnp.isfinite(target_array)
    )
    safe_unitary = jnp.where(valid, unitary_array, jnp.zeros_like(unitary_array))
    safe_target = jnp.where(valid, target_array, jnp.zeros_like(target_array))
    overlap = jnp.trace(safe_target.conj().T @ safe_unitary)
    fidelity = jnp.real(overlap.conj() * overlap) / jnp.float64(dimension**2)
    loss = jnp.asarray(1.0 - fidelity, dtype=jnp.float64)
    return jnp.where(valid, loss, jnp.float64(jnp.inf)), valid


def process_infidelity_from_unitary(
    unitary: object,
    target: object,
) -> jax.Array:
    loss, valid = _guarded_unclipped_process_infidelity(unitary, target)
    reported = jnp.clip(loss, jnp.float64(0.0), jnp.float64(1.0))
    return jnp.where(valid, reported, jnp.float64(jnp.inf))


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
    if tuple(space.amplitude_scales) != tuple(system.amplitude_scales):
        raise ValueError("pulse space amplitude scales do not match the system")

    normalized_array = jnp.asarray(normalized)
    if jnp.iscomplexobj(normalized_array):
        raise ValueError("normalized pulse must be real")
    expected_shape = (space.control_count * space.segments,)
    if normalized_array.shape != expected_shape:
        raise ValueError(
            "normalized pulse shape does not match the PulseSpace segment count"
        )
    normalized_array = jnp.asarray(normalized_array, dtype=jnp.float64)

    if not isinstance(normalized_array, jax.core.Tracer):
        concrete = np.asarray(normalized_array)
        if not np.all(np.isfinite(concrete)):
            raise ValueError("normalized pulse must contain only finite values")
        if np.any(np.abs(concrete) > 1.0):
            raise ValueError("normalized pulse exceeds the hard [-1, 1] bounds")

    valid = jnp.all(jnp.isfinite(normalized_array)) & jnp.all(
        jnp.abs(normalized_array) <= 1.0
    )
    safe_normalized = jnp.where(
        valid,
        normalized_array,
        jnp.zeros_like(normalized_array),
    )
    physical_pulse = space.to_physical(safe_normalized)
    unitary = propagate(system, physical_pulse)
    loss, propagation_valid = _guarded_unclipped_process_infidelity(
        unitary,
        system.target,
    )
    return jnp.where(
        valid & propagation_valid,
        loss,
        jnp.float64(jnp.inf),
    )
