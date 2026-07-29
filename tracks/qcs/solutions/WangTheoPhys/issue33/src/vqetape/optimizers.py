"""Classical optimizer kernels for measured VQE training."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from vqetape.kernels import unrolled_state
from vqetape.spec import TFIMVQESpec

Evaluate = Callable[
    [np.ndarray],
    tuple[float, np.ndarray],
]
Observer = Callable[
    [
        int,
        int,
        np.ndarray,
        float,
        np.ndarray,
        float | None,
    ],
    bool,
]
MetricFunction = Callable[[np.ndarray], np.ndarray]


class OptimizerUnavailable(RuntimeError):
    """Raised when an optional optimizer dependency is absent."""


@dataclass(frozen=True)
class OptimizerOutcome:
    """Final state and accounting from one optimizer."""

    parameters: np.ndarray
    evaluations: int
    steps: int
    target_reached: bool
    failure: str | None = None


def active_parameter_mask(spec: TFIMVQESpec) -> np.ndarray:
    """Return one for physical parameters and zero for RZZ padding."""

    mask = np.ones(spec.parameter_shape, dtype=np.float64)
    mask[:, 0, -1] = 0
    return mask


def _normalized_mask(
    parameters: np.ndarray,
    mask: np.ndarray | None,
) -> np.ndarray:
    if mask is None:
        return np.ones_like(parameters, dtype=np.float64)
    normalized = np.asarray(mask, dtype=np.float64)
    if normalized.shape != parameters.shape:
        raise ValueError("optimizer mask shape mismatch")
    return normalized


def _evaluate_finite(
    evaluate: Evaluate,
    parameters: np.ndarray,
) -> tuple[float, np.ndarray]:
    value, gradient = evaluate(parameters)
    value = float(value)
    gradient = np.asarray(
        gradient,
        dtype=parameters.dtype,
    )
    if gradient.shape != parameters.shape:
        raise ValueError("gradient shape mismatch")
    if not np.isfinite(value) or not np.all(
        np.isfinite(gradient)
    ):
        raise FloatingPointError(
            "optimizer evaluation produced NaN or Inf"
        )
    return value, gradient


def run_adam(
    initial_parameters: np.ndarray,
    evaluate: Evaluate,
    observer: Observer,
    *,
    max_steps: int,
    learning_rate: float,
    mask: np.ndarray | None = None,
    beta1: float = 0.9,
    beta2: float = 0.999,
    epsilon: float = 1e-8,
) -> OptimizerOutcome:
    """Run Adam with one recorded evaluation per update."""

    parameters = np.array(
        initial_parameters,
        dtype=np.float64,
        copy=True,
    )
    active = _normalized_mask(parameters, mask)
    first_value, gradient = _evaluate_finite(
        evaluate,
        parameters,
    )
    evaluations = 1
    if observer(
        evaluations,
        0,
        parameters,
        first_value,
        gradient,
        None,
    ):
        return OptimizerOutcome(
            parameters,
            evaluations,
            0,
            True,
        )

    first_moment = np.zeros_like(parameters)
    second_moment = np.zeros_like(parameters)
    for step in range(1, max_steps + 1):
        masked_gradient = gradient * active
        first_moment = (
            beta1 * first_moment
            + (1 - beta1) * masked_gradient
        )
        second_moment = (
            beta2 * second_moment
            + (1 - beta2) * masked_gradient**2
        )
        corrected_first = first_moment / (1 - beta1**step)
        corrected_second = (
            second_moment / (1 - beta2**step)
        )
        parameters = (
            parameters
            - learning_rate
            * corrected_first
            / (np.sqrt(corrected_second) + epsilon)
        )
        parameters = parameters * active + (
            np.asarray(initial_parameters) * (1 - active)
        )
        value, gradient = _evaluate_finite(
            evaluate,
            parameters,
        )
        evaluations += 1
        if observer(
            evaluations,
            step,
            parameters,
            value,
            gradient,
            None,
        ):
            return OptimizerOutcome(
                parameters,
                evaluations,
                step,
                True,
            )
    return OptimizerOutcome(
        parameters,
        evaluations,
        max_steps,
        False,
    )


class _TargetReached(Exception):
    def __init__(
        self,
        parameters: np.ndarray,
        evaluations: int,
        steps: int,
    ) -> None:
        self.parameters = parameters
        self.evaluations = evaluations
        self.steps = steps


def run_lbfgs(
    initial_parameters: np.ndarray,
    evaluate: Evaluate,
    observer: Observer,
    *,
    max_steps: int,
    mask: np.ndarray | None = None,
) -> OptimizerOutcome:
    """Run SciPy L-BFGS-B with a combined value-gradient callback."""

    try:
        from scipy.optimize import minimize
    except ImportError as exc:
        raise OptimizerUnavailable(
            "L-BFGS-B requires the optional scipy dependency"
        ) from exc

    initial = np.asarray(
        initial_parameters,
        dtype=np.float64,
    )
    active_mask = _normalized_mask(initial, mask).reshape(-1)
    active_indices = np.flatnonzero(active_mask)
    base = np.array(initial, copy=True).reshape(-1)
    evaluations = 0
    steps = 0

    def unpack(active_values: np.ndarray) -> np.ndarray:
        flat = np.array(base, copy=True)
        flat[active_indices] = active_values
        return flat.reshape(initial.shape)

    def objective(active_values: np.ndarray):
        nonlocal evaluations
        parameters = unpack(active_values)
        value, gradient = _evaluate_finite(
            evaluate,
            parameters,
        )
        evaluations += 1
        if observer(
            evaluations,
            steps,
            parameters,
            value,
            gradient,
            None,
        ):
            raise _TargetReached(
                parameters,
                evaluations,
                steps,
            )
        return (
            value,
            gradient.reshape(-1)[active_indices],
        )

    def accepted(_: np.ndarray) -> None:
        nonlocal steps
        steps += 1

    try:
        result = minimize(
            objective,
            base[active_indices],
            method="L-BFGS-B",
            jac=True,
            callback=accepted,
            options={
                "maxiter": max_steps,
                "maxls": 40,
                "ftol": 1e-15,
                "gtol": 1e-10,
            },
        )
    except _TargetReached as reached:
        return OptimizerOutcome(
            reached.parameters,
            reached.evaluations,
            reached.steps,
            True,
        )
    parameters = unpack(np.asarray(result.x))
    return OptimizerOutcome(
        parameters,
        evaluations,
        int(result.nit),
        False,
        None if result.success else str(result.message),
    )


def run_natural_gradient(
    initial_parameters: np.ndarray,
    evaluate: Evaluate,
    metric: MetricFunction,
    observer: Observer,
    *,
    max_steps: int,
    learning_rate: float,
    damping: float,
    mask: np.ndarray | None = None,
) -> OptimizerOutcome:
    """Run a damped exact natural-gradient reference."""

    parameters = np.asarray(
        initial_parameters,
        dtype=np.float64,
    ).copy()
    active_mask = _normalized_mask(
        parameters,
        mask,
    ).reshape(-1)
    active_indices = np.flatnonzero(active_mask)
    value, gradient = _evaluate_finite(
        evaluate,
        parameters,
    )
    evaluations = 1
    if observer(
        evaluations,
        0,
        parameters,
        value,
        gradient,
        None,
    ):
        return OptimizerOutcome(
            parameters,
            evaluations,
            0,
            True,
        )

    for step in range(1, max_steps + 1):
        full_metric = np.asarray(
            metric(parameters),
            dtype=np.float64,
        )
        parameter_count = parameters.size
        if full_metric.shape != (
            parameter_count,
            parameter_count,
        ):
            raise ValueError("natural-gradient metric shape mismatch")
        active_metric = full_metric[
            np.ix_(active_indices, active_indices)
        ]
        regularized = active_metric + damping * np.eye(
            active_indices.size
        )
        if not np.all(np.isfinite(regularized)):
            raise FloatingPointError(
                "natural-gradient metric contains NaN or Inf"
            )
        condition = float(np.linalg.cond(regularized))
        direction = np.linalg.solve(
            regularized,
            gradient.reshape(-1)[active_indices],
        )
        flat = parameters.reshape(-1).copy()
        flat[active_indices] -= learning_rate * direction
        parameters = flat.reshape(parameters.shape)
        value, gradient = _evaluate_finite(
            evaluate,
            parameters,
        )
        evaluations += 1
        if observer(
            evaluations,
            step,
            parameters,
            value,
            gradient,
            condition,
        ):
            return OptimizerOutcome(
                parameters,
                evaluations,
                step,
                True,
            )
    return OptimizerOutcome(
        parameters,
        evaluations,
        max_steps,
        False,
    )


def pure_state_qgt(
    parameters: Any,
    spec: TFIMVQESpec,
) -> np.ndarray:
    """Return the exact real pure-state quantum geometric tensor."""

    theta = jnp.asarray(parameters)
    state_function = lambda values: unrolled_state(
        values,
        spec,
    )
    state = state_function(theta)
    jacobian = jax.jacfwd(state_function)(theta)
    matrix = jacobian.reshape(
        state.size,
        theta.size,
    )
    overlap = matrix.conj().T @ matrix
    connection = matrix.conj().T @ state
    metric = jnp.real(
        overlap
        - jnp.outer(
            connection,
            jnp.conj(connection),
        )
    )
    return np.asarray(metric)
