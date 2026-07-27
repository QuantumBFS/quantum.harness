"""Differentiable diagnostics and query-only closed-loop optimizers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp
import numpy as np
from scipy.optimize import minimize

from sim_to_real import Array, BlackBoxDevice


@dataclass(frozen=True)
class DifferentiableResult:
    params: np.ndarray
    loss: float
    success: bool
    iterations: int
    evaluations: int
    message: str


@dataclass(frozen=True)
class ClosedLoopResult:
    params: np.ndarray
    best_reported_fidelity: float
    best_exact_fidelity: float
    query_count: int
    shot_count: int
    query_to_target: int | None
    optimizer_success: bool
    message: str


class QueryBudgetExhausted(RuntimeError):
    pass


def _affine_subspace_point(
    origin: np.ndarray,
    basis: np.ndarray,
    coefficients: np.ndarray,
) -> np.ndarray:
    """Form ``origin + basis * coefficients`` without BLAS warning leakage."""

    displacement = np.einsum(
        "ij,j->i", basis, coefficients, optimize=False
    )
    return origin + displacement


def optimize_differentiable(
    loss_fn: Callable[[Array], Array],
    initial_params: np.ndarray | Array,
    *,
    method: str = "BFGS",
    gtol: float = 1e-8,
    maxiter: int = 1000,
) -> DifferentiableResult:
    """Optimize a JAX loss through SciPy with exact model gradients."""

    value_and_grad = jax.jit(jax.value_and_grad(loss_fn))

    def objective(params: np.ndarray) -> tuple[float, np.ndarray]:
        value, gradient = value_and_grad(jnp.asarray(params, dtype=jnp.float64))
        return float(value), np.asarray(gradient, dtype=np.float64)

    result = minimize(
        objective,
        np.asarray(initial_params, dtype=np.float64),
        method=method,
        jac=True,
        options={"gtol": gtol, "maxiter": maxiter},
    )
    return DifferentiableResult(
        params=np.asarray(result.x, dtype=np.float64),
        loss=float(result.fun),
        success=bool(result.success),
        iterations=int(getattr(result, "nit", 0)),
        evaluations=int(getattr(result, "nfev", 0)),
        message=str(result.message),
    )


def optimize_differentiable_subspace(
    loss_fn: Callable[[Array], Array],
    origin: np.ndarray | Array,
    basis: np.ndarray | Array,
    *,
    initial_coefficients: np.ndarray | None = None,
    method: str = "BFGS",
    gtol: float = 1e-8,
    maxiter: int = 1000,
) -> DifferentiableResult:
    """Privileged reachability diagnostic inside a fixed parameter subspace."""

    origin_jax = jnp.asarray(origin, dtype=jnp.float64)
    basis_jax = jnp.asarray(basis, dtype=jnp.float64)
    if initial_coefficients is None:
        initial_coefficients = np.zeros(basis_jax.shape[1], dtype=np.float64)

    coefficient_loss = lambda coefficients: loss_fn(
        origin_jax + basis_jax @ coefficients
    )
    coefficient_result = optimize_differentiable(
        coefficient_loss,
        initial_coefficients,
        method=method,
        gtol=gtol,
        maxiter=maxiter,
    )
    params = np.asarray(
        origin_jax + basis_jax @ jnp.asarray(coefficient_result.params)
    )
    return DifferentiableResult(
        params=params,
        loss=coefficient_result.loss,
        success=coefficient_result.success,
        iterations=coefficient_result.iterations,
        evaluations=coefficient_result.evaluations,
        message=coefficient_result.message,
    )


def _closed_loop_summary(
    device: BlackBoxDevice,
    *,
    target_infidelity: float,
    optimizer_success: bool,
    message: str,
    selection_start: int = 0,
) -> ClosedLoopResult:
    if not device.history:
        raise ValueError("closed-loop optimizer made no device queries")
    selectable_history = device.history[selection_start:]
    if not selectable_history:
        raise ValueError("selection window contains no device queries")
    best_reported = max(
        selectable_history, key=lambda record: record.reported_fidelity
    )
    best_exact = max(device.history, key=lambda record: record.exact_fidelity)
    query_to_target = next(
        (
            record.query
            for record in device.history
            if 1.0 - record.exact_fidelity <= target_infidelity
        ),
        None,
    )
    return ClosedLoopResult(
        params=best_reported.params.copy(),
        best_reported_fidelity=best_reported.reported_fidelity,
        best_exact_fidelity=best_exact.exact_fidelity,
        query_count=device.query_count,
        shot_count=device.shot_count,
        query_to_target=query_to_target,
        optimizer_success=optimizer_success,
        message=message,
    )


def optimize_black_box_scipy(
    device: BlackBoxDevice,
    origin: np.ndarray | Array,
    *,
    basis: np.ndarray | Array | None = None,
    method: str = "Nelder-Mead",
    max_queries: int = 2000,
    target_infidelity: float = 1e-3,
    optimizer_options: dict[str, object] | None = None,
    allow_existing_history: bool = False,
    evaluation_repeats: int = 1,
) -> ClosedLoopResult:
    """Run a SciPy derivative-free optimizer against the query-only device."""

    if device.query_count and not allow_existing_history:
        raise ValueError("device history must be empty at optimizer start")
    if max_queries <= 0 or evaluation_repeats <= 0:
        raise ValueError("query budget and evaluation repeats must be positive")

    origin_np = np.asarray(origin, dtype=np.float64)
    if basis is None:
        basis_np = np.eye(origin_np.size, dtype=np.float64)
    else:
        basis_np = np.asarray(basis, dtype=np.float64)
    initial = np.zeros(basis_np.shape[1], dtype=np.float64)
    query_count_at_start = device.query_count
    best_objective = np.inf
    best_objective_params = origin_np.copy()

    def objective(coefficients: np.ndarray) -> float:
        nonlocal best_objective, best_objective_params
        used = device.query_count - query_count_at_start
        if used + evaluation_repeats > max_queries:
            raise QueryBudgetExhausted
        params = _affine_subspace_point(
            origin_np, basis_np, coefficients
        )
        value = float(
            np.mean(
                [
                    device.query(params)
                    for _ in range(evaluation_repeats)
                ]
            )
        )
        if value < best_objective:
            best_objective = value
            best_objective_params = params.copy()
        return value

    maximum_evaluations = max(1, max_queries // evaluation_repeats)
    options: dict[str, object] = {
        "maxiter": maximum_evaluations,
        "maxfev": maximum_evaluations,
    }
    # A single finite-shot observation below the target is not reliable
    # evidence that the latent device fidelity has reached it.  Only use
    # objective-based early stopping for the noiseless oracle; noisy runs
    # continue until COBYQA converges or exhausts the declared query budget.
    if method.upper() == "COBYQA" and device.shots is None:
        options["f_target"] = target_infidelity
    if optimizer_options is not None:
        options.update(optimizer_options)

    success = False
    message = "query budget exhausted"
    try:
        result = minimize(
            objective,
            initial,
            method=method,
            options=options,
        )
        success = bool(result.success)
        message = str(result.message)
    except QueryBudgetExhausted:
        pass

    summary = _closed_loop_summary(
        device,
        target_infidelity=target_infidelity,
        optimizer_success=success,
        message=message,
        selection_start=query_count_at_start,
    )
    return ClosedLoopResult(
        params=best_objective_params,
        best_reported_fidelity=1.0 - best_objective,
        best_exact_fidelity=summary.best_exact_fidelity,
        query_count=summary.query_count,
        shot_count=summary.shot_count,
        query_to_target=summary.query_to_target,
        optimizer_success=summary.optimizer_success,
        message=summary.message,
    )


def optimize_spsa(
    device: BlackBoxDevice,
    origin: np.ndarray | Array,
    *,
    basis: np.ndarray | Array | None = None,
    iterations: int = 500,
    learning_rate: float = 0.1,
    perturbation: float = 0.05,
    stability: float = 10.0,
    seed: int = 0,
    target_infidelity: float = 1e-3,
) -> ClosedLoopResult:
    """Two-query-per-step SPSA baseline.

    SPSA is included to prevent the full-space baseline from being unfairly
    represented only by simplex methods whose initialization scales with
    dimension.
    """

    if device.query_count:
        raise ValueError("device history must be empty at optimizer start")
    if iterations <= 0:
        raise ValueError("iterations must be positive")

    origin_np = np.asarray(origin, dtype=np.float64)
    if basis is None:
        basis_np = np.eye(origin_np.size, dtype=np.float64)
    else:
        basis_np = np.asarray(basis, dtype=np.float64)

    rng = np.random.default_rng(seed)
    coefficients = np.zeros(basis_np.shape[1], dtype=np.float64)
    for iteration in range(iterations):
        ak = learning_rate / (iteration + 1.0 + stability) ** 0.602
        ck = perturbation / (iteration + 1.0) ** 0.101
        delta = rng.choice(np.asarray([-1.0, 1.0]), size=coefficients.size)
        plus = _affine_subspace_point(
            origin_np, basis_np, coefficients + ck * delta
        )
        minus = _affine_subspace_point(
            origin_np, basis_np, coefficients - ck * delta
        )
        loss_plus = device.query(plus)
        loss_minus = device.query(minus)
        gradient = ((loss_plus - loss_minus) / (2.0 * ck)) * delta
        coefficients = coefficients - ak * gradient

    device.query(_affine_subspace_point(origin_np, basis_np, coefficients))
    return _closed_loop_summary(
        device,
        target_infidelity=target_infidelity,
        optimizer_success=True,
        message="completed fixed SPSA iterations",
    )
