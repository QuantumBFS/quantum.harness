from __future__ import annotations

import math
from numbers import Real

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


def _duration_value(duration: object) -> float:
    if isinstance(duration, (bool, np.bool_)) or not isinstance(duration, Real):
        raise ValueError("duration must be a finite nonnegative number")
    result = float(duration)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError("duration must be a finite nonnegative number")
    return result


def propagate(
    system: ControlSystem,
    physical_pulse: object,
    duration: float = 1.0,
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
    try:
        concrete = np.asarray(pulse)
    except jax.errors.TracerArrayConversionError:
        pass
    else:
        if not np.all(np.isfinite(concrete)):
            raise ValueError("physical pulse must contain only finite values")

    drift = jnp.asarray(system.drift, dtype=jnp.complex128)
    controls = jnp.stack(
        tuple(jnp.asarray(control, dtype=jnp.complex128) for control in system.controls)
    )
    return _propagate_kernel(
        drift,
        controls,
        pulse,
        jnp.asarray(_duration_value(duration), dtype=jnp.float64),
    )
