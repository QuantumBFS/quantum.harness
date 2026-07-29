from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config import require_jax
from dynamics import gate_fidelity
from systems import SystemModel


jax, jnp = require_jax()


@dataclass(frozen=True)
class MismatchConfig:
    name: str
    drift_scale: float
    control_scale: float
    crosstalk: float
    rotate: float
    pulse_smoothing: float = 0.0
    pulse_memory: float = 0.0


MISMATCHES = {
    "small": MismatchConfig("small", 0.02, 0.02, 0.00, 0.00),
    "medium": MismatchConfig("medium", 0.06, 0.05, 0.02, 0.03),
    "large": MismatchConfig("large", 0.12, 0.08, 0.05, 0.14),
    "pulse_distortion": MismatchConfig(
        "pulse_distortion",
        0.08,
        0.06,
        0.03,
        0.06,
        pulse_smoothing=0.20,
        pulse_memory=0.15,
    ),
}


def build_true_system(model_system: SystemModel, mismatch_name: str, seed: int) -> SystemModel:
    mismatch = MISMATCHES[mismatch_name]
    rng = np.random.default_rng(seed)
    drift_noise = _hermitian_noise(model_system.config.hilbert_dim, rng)
    drift = model_system.drift + mismatch.drift_scale * jnp.asarray(drift_noise)
    controls = []
    for index, control in enumerate(model_system.control_hamiltonians):
        scale = 1.0 + mismatch.control_scale * ((-1.0) ** index)
        controls.append(scale * control)
    if mismatch.crosstalk:
        controls = [
            controls[index] + mismatch.crosstalk * controls[(index + 1) % len(controls)]
            for index in range(len(controls))
        ]
    if mismatch.rotate:
        extra = jnp.asarray(_hermitian_noise(model_system.config.hilbert_dim, rng))
        controls = [control + mismatch.rotate * extra / len(controls) for control in controls]
    return SystemModel(
        config=model_system.config,
        target=model_system.target,
        drift=drift,
        control_hamiltonians=tuple(controls),
    )


def _hermitian_noise(dim: int, rng: np.random.Generator) -> np.ndarray:
    raw = rng.normal(size=(dim, dim)) + 1j * rng.normal(size=(dim, dim))
    hermitian = raw + raw.conj().T
    return hermitian / max(1.0, np.linalg.norm(hermitian))


def distort_pulse_parameters(
    pulse_parameters,
    system_config,
    smoothing: float,
    memory: float,
) -> np.ndarray:
    if not 0.0 <= smoothing < 1.0:
        raise ValueError("smoothing must be in [0, 1)")
    if not 0.0 <= memory < 1.0:
        raise ValueError("memory must be in [0, 1)")
    pulse = np.asarray(pulse_parameters, dtype=float)
    if pulse.shape != (system_config.raw_dim,):
        raise ValueError(f"pulse must have shape ({system_config.raw_dim},)")
    segments = pulse.reshape((system_config.segments, system_config.controls))
    smoothed = segments.copy()
    if smoothing:
        for index in range(system_config.segments):
            neighbors = [segments[index]]
            if index > 0:
                neighbors.append(segments[index - 1])
            if index + 1 < system_config.segments:
                neighbors.append(segments[index + 1])
            local_average = np.mean(neighbors, axis=0)
            smoothed[index] = (1.0 - smoothing) * segments[index] + smoothing * local_average
    distorted = smoothed.copy()
    if memory:
        for index in range(1, system_config.segments):
            distorted[index] = (1.0 - memory) * smoothed[index] + memory * distorted[index - 1]
    return np.clip(
        distorted.reshape(system_config.raw_dim),
        -system_config.max_amplitude,
        system_config.max_amplitude,
    )


class QueryOnlyDevice:
    def __init__(self, true_system: SystemModel, seed: int, pulse_transform=None) -> None:
        self._system = true_system
        self._rng = np.random.default_rng(seed)
        self._query_count = 0
        self._shot_count = 0
        self._pulse_transform = pulse_transform

    @property
    def query_count(self) -> int:
        return self._query_count

    @property
    def shot_count(self) -> int:
        return self._shot_count

    def query(self, pulse_parameters, shots: int, seed: int | None = None) -> float:
        if shots <= 0:
            raise ValueError("shots must be positive")
        rng = np.random.default_rng(seed) if seed is not None else self._rng
        evaluated_pulse = (
            self._pulse_transform(pulse_parameters)
            if self._pulse_transform is not None
            else pulse_parameters
        )
        fidelity = float(gate_fidelity(evaluated_pulse, self._system))
        fidelity = min(1.0, max(0.0, fidelity))
        successes = rng.binomial(int(shots), fidelity)
        self._query_count += 1
        self._shot_count += int(shots)
        return float(1.0 - successes / float(shots))


def build_query_device(
    model_system: SystemModel,
    mismatch_name: str,
    seed: int,
    query_seed: int | None = None,
) -> QueryOnlyDevice:
    mismatch = MISMATCHES[mismatch_name]
    true_system = build_true_system(model_system, mismatch_name, seed=seed)
    pulse_transform = None
    if mismatch.pulse_smoothing or mismatch.pulse_memory:
        pulse_transform = lambda pulse: distort_pulse_parameters(
            pulse,
            model_system.config,
            smoothing=mismatch.pulse_smoothing,
            memory=mismatch.pulse_memory,
        )
    return QueryOnlyDevice(
        true_system,
        seed=seed if query_seed is None else query_seed,
        pulse_transform=pulse_transform,
    )


class AuditEvaluator:
    def __init__(self, true_system: SystemModel) -> None:
        self._system = true_system

    def exact_fidelity(self, pulse_parameters) -> float:
        return float(gate_fidelity(pulse_parameters, self._system))

    def exact_infidelity(self, pulse_parameters) -> float:
        return 1.0 - self.exact_fidelity(pulse_parameters)
