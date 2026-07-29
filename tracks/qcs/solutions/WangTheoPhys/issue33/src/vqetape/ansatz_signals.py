"""Exact zero-insertion signals for adaptive VQE operators."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any

from jax import Array
import jax.numpy as jnp

from vqetape.ansatz import (
    AnsatzOperator,
    apply_ansatz_generator,
)
from vqetape.kernels import tfim_hamiltonian_action
from vqetape.spec import TFIMVQESpec


@dataclass(frozen=True)
class AnsatzSignal:
    """Energy derivative and diagonal quantum metric of one insertion."""

    operator: AnsatzOperator
    gradient: float
    metric: float
    normalized_signal: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["operator"] = self.operator.to_dict()
        return payload

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> AnsatzSignal:
        values = dict(payload)
        values["operator"] = AnsatzOperator.from_dict(
            values["operator"]
        )
        return cls(**values)


def candidate_signal(
    state: Array,
    operator: AnsatzOperator,
    spec: TFIMVQESpec,
    *,
    metric_epsilon: float = 1e-12,
) -> AnsatzSignal:
    """Evaluate exact gradient and Fubini-Study diagonal at alpha=0."""

    if state.shape != (1 << spec.nqubits,):
        raise ValueError("state shape does not match workload")
    if metric_epsilon <= 0 or not isfinite(metric_epsilon):
        raise ValueError(
            "metric_epsilon must be finite and positive"
        )
    generator_state = apply_ansatz_generator(
        state,
        operator,
        spec,
    )
    hamiltonian_state = tfim_hamiltonian_action(
        state,
        spec,
    )
    overlap = jnp.vdot(generator_state, state)
    gradient = -jnp.imag(
        jnp.vdot(generator_state, hamiltonian_state)
    )
    metric = jnp.maximum(
        0.0,
        0.25 * (1.0 - jnp.real(overlap) ** 2),
    )
    gradient_value = float(gradient)
    metric_value = float(metric)
    return AnsatzSignal(
        operator=operator,
        gradient=gradient_value,
        metric=metric_value,
        normalized_signal=(
            gradient_value**2
            / (metric_value + metric_epsilon)
        ),
    )


def pool_signals(
    state: Array,
    operators: tuple[AnsatzOperator, ...],
    spec: TFIMVQESpec,
    *,
    metric_epsilon: float = 1e-12,
) -> tuple[AnsatzSignal, ...]:
    """Evaluate the complete operator pool without pruning."""

    return tuple(
        candidate_signal(
            state,
            operator,
            spec,
            metric_epsilon=metric_epsilon,
        )
        for operator in operators
    )
