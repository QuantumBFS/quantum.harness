from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np

from qcontrol.systems import ControlSystem


jax.config.update("jax_enable_x64", True)


@jax.jit
def _propagate_kernel(
    drift: jax.Array,
    controls: jax.Array,
    physical_pulse: jax.Array,
    duration: jax.Array,
) -> jax.Array:
    segment_duration = duration / physical_pulse.shape[1]
    identity = jnp.eye(drift.shape[0], dtype=jnp.complex128)

    def apply_segment(unitary: jax.Array, amplitudes: jax.Array) -> tuple[jax.Array, None]:
        hamiltonian = drift + jnp.tensordot(amplitudes, controls, axes=1)
        segment = jax.scipy.linalg.expm(-1.0j * segment_duration * hamiltonian)
        return segment @ unitary, None

    unitary, _ = jax.lax.scan(apply_segment, identity, physical_pulse.T)
    return unitary


def _raise_for_invalid_eager_pulse(pulse: jax.Array) -> None:
    if isinstance(pulse, jax.core.Tracer):
        return
    if not np.all(np.isfinite(np.asarray(pulse))):
        raise ValueError("physical pulse must contain only finite values")


def _raise_for_invalid_eager_duration(array: jax.Array) -> None:
    if isinstance(array, jax.core.Tracer):
        return
    value = float(np.asarray(array))
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError("duration must be a positive finite number")


def propagate(
    system: ControlSystem,
    physical_pulse: object,
    duration: float | None = None,
) -> jax.Array:
    if not isinstance(system, ControlSystem):
        raise ValueError("system must be a ControlSystem")
    pulse = jnp.asarray(physical_pulse)
    if jnp.iscomplexobj(pulse):
        raise ValueError("physical pulse must be real")
    if pulse.ndim != 2 or pulse.shape[0] != len(system.controls) or pulse.shape[1] <= 0:
        raise ValueError(
            "physical pulse must have shape (control_count, positive_segments)"
        )
    pulse = jnp.asarray(pulse, dtype=jnp.float64)
    _raise_for_invalid_eager_pulse(pulse)

    resolved_duration = system.duration if duration is None else duration
    duration_array = jnp.asarray(resolved_duration)
    if duration_array.shape != () or jnp.iscomplexobj(duration_array):
        raise ValueError("duration must be a real scalar")
    if jnp.issubdtype(duration_array.dtype, jnp.bool_):
        raise ValueError("duration must be a positive finite number")
    duration_array = jnp.asarray(duration_array, dtype=jnp.float64)
    _raise_for_invalid_eager_duration(duration_array)

    valid = (
        jnp.all(jnp.isfinite(pulse))
        & jnp.isfinite(duration_array)
        & (duration_array > 0.0)
    )
    safe_pulse = jnp.where(valid, pulse, jnp.zeros_like(pulse))
    safe_duration = jnp.where(valid, duration_array, jnp.float64(0.0))

    drift = jnp.asarray(system.drift, dtype=jnp.complex128)
    controls = jnp.stack(
        tuple(jnp.asarray(control, dtype=jnp.complex128) for control in system.controls)
    )
    unitary = _propagate_kernel(
        drift,
        controls,
        safe_pulse,
        safe_duration,
    )
    invalid = jnp.full_like(unitary, jnp.nan + 1.0j * jnp.nan)
    return jnp.where(valid, unitary, invalid)
