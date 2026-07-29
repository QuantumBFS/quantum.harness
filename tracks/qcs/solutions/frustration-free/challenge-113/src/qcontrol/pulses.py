from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral, Real

import jax
import jax.numpy as jnp
import numpy as np

from qcontrol.systems import ControlSystem


def _positive_integer(name: str, value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be a positive integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return result


def _positive_finite(name: str, value: object) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a positive finite number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be a positive finite number")
    return result


def _raise_for_invalid_eager_values(
    array: jax.Array,
    *,
    name: str,
    bound: jax.Array,
) -> None:
    if isinstance(array, jax.core.Tracer):
        return
    concrete = np.asarray(array)
    if not np.all(np.isfinite(concrete)):
        raise ValueError(f"{name} pulse must contain only finite values")
    if np.any(np.abs(concrete) > np.asarray(bound)):
        raise ValueError(f"{name} pulse exceeds its hard amplitude bounds")


@dataclass(frozen=True)
class PulseSpace:
    control_count: int
    segments: int
    amplitude_scales: tuple[float, ...]
    bound: float

    def __post_init__(self) -> None:
        control_count = _positive_integer("control_count", self.control_count)
        segments = _positive_integer("segments", self.segments)
        try:
            raw_scales = tuple(self.amplitude_scales)
        except TypeError:
            raise ValueError("amplitude_scales must be a sequence") from None
        if len(raw_scales) != control_count:
            raise ValueError("each control must have an amplitude scale")
        scales = tuple(
            _positive_finite("amplitude scale", scale) for scale in raw_scales
        )
        bound = _positive_finite("bound", self.bound)
        if bound != 1.0:
            raise ValueError("normalized pulse bound must be exactly 1.0")

        object.__setattr__(self, "control_count", control_count)
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "amplitude_scales", scales)
        object.__setattr__(self, "bound", bound)

    @classmethod
    def from_system(cls, system: ControlSystem, segments: int) -> PulseSpace:
        if not isinstance(system, ControlSystem):
            raise ValueError("system must be a ControlSystem")
        return cls(
            control_count=len(system.controls),
            segments=segments,
            amplitude_scales=system.amplitude_scales,
            bound=1.0,
        )

    @property
    def parameter_count(self) -> int:
        return self.control_count * self.segments

    def to_physical(self, normalized: object) -> jax.Array:
        array = jnp.asarray(normalized)
        if jnp.iscomplexobj(array):
            raise ValueError("normalized pulse must be real")
        if array.shape != (self.parameter_count,):
            raise ValueError(
                f"normalized pulse must have shape ({self.parameter_count},)"
            )
        array = jnp.asarray(array, dtype=jnp.float64)
        normalized_bound = jnp.float64(1.0)
        _raise_for_invalid_eager_values(
            array,
            name="normalized",
            bound=normalized_bound,
        )
        scales = jnp.asarray(self.amplitude_scales, dtype=jnp.float64)[:, None]
        valid = jnp.all(jnp.isfinite(array)) & jnp.all(jnp.abs(array) <= normalized_bound)
        physical = array.reshape(self.control_count, self.segments) * scales
        return jnp.where(valid, physical, jnp.full_like(physical, jnp.nan))

    def to_normalized(self, physical: object) -> jax.Array:
        array = jnp.asarray(physical)
        if jnp.iscomplexobj(array):
            raise ValueError("physical pulse must be real")
        expected_shape = (self.control_count, self.segments)
        if array.shape != expected_shape:
            raise ValueError(f"physical pulse must have shape {expected_shape}")
        array = jnp.asarray(array, dtype=jnp.float64)
        scales = jnp.asarray(self.amplitude_scales, dtype=jnp.float64)[:, None]
        _raise_for_invalid_eager_values(array, name="physical", bound=scales)
        valid = jnp.all(jnp.isfinite(array)) & jnp.all(jnp.abs(array) <= scales)
        normalized = (array / scales).reshape(self.parameter_count)
        return jnp.where(valid, normalized, jnp.full_like(normalized, jnp.nan))
