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


MISMATCHES = {
    "small": MismatchConfig("small", 0.02, 0.02, 0.00, 0.00),
    "medium": MismatchConfig("medium", 0.06, 0.05, 0.02, 0.03),
    "large": MismatchConfig("large", 0.12, 0.08, 0.05, 0.14),
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


class QueryOnlyDevice:
    def __init__(self, true_system: SystemModel, seed: int) -> None:
        self._system = true_system
        self._rng = np.random.default_rng(seed)
        self._query_count = 0
        self._shot_count = 0

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
        fidelity = float(gate_fidelity(pulse_parameters, self._system))
        fidelity = min(1.0, max(0.0, fidelity))
        successes = rng.binomial(int(shots), fidelity)
        self._query_count += 1
        self._shot_count += int(shots)
        return float(1.0 - successes / float(shots))


class AuditEvaluator:
    def __init__(self, true_system: SystemModel) -> None:
        self._system = true_system

    def exact_fidelity(self, pulse_parameters) -> float:
        return float(gate_fidelity(pulse_parameters, self._system))

    def exact_infidelity(self, pulse_parameters) -> float:
        return 1.0 - self.exact_fidelity(pulse_parameters)
