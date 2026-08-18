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
    certified_query_to_target: int | None = None
    cycles_completed: int | None = None


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
    certified_query_to_target: int | None = None,
    cycles_completed: int | None = None,
    selected_params: np.ndarray | None = None,
) -> ClosedLoopResult:
    if not device.history:
        raise ValueError("closed-loop optimizer made no device queries")
    best_reported = max(
        device.history, key=lambda record: record.reported_fidelity
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
        params=(
            best_reported.params.copy()
            if selected_params is None
            else np.asarray(selected_params, dtype=np.float64).copy()
        ),
        best_reported_fidelity=best_reported.reported_fidelity,
        best_exact_fidelity=best_exact.exact_fidelity,
        query_count=device.query_count,
        shot_count=device.shot_count,
        query_to_target=query_to_target,
        optimizer_success=optimizer_success,
        message=message,
        certified_query_to_target=certified_query_to_target,
        cycles_completed=cycles_completed,
    )


def one_sided_wilson_upper(
    failures: int,
    trials: int,
    *,
    z_score: float = 1.96,
) -> float:
    """One-sided Wilson upper bound for a binomial failure probability."""

    if trials <= 0:
        raise ValueError("trials must be positive")
    if failures < 0 or failures > trials:
        raise ValueError("failures must lie in [0, trials]")
    if z_score <= 0.0:
        raise ValueError("z_score must be positive")
    probability = failures / trials
    z_squared = z_score**2
    denominator = 1.0 + z_squared / trials
    center = probability + z_squared / (2.0 * trials)
    radius = z_score * np.sqrt(
        probability * (1.0 - probability) / trials
        + z_squared / (4.0 * trials**2)
    )
    return float((center + radius) / denominator)


def certify_reported_target(
    device: BlackBoxDevice,
    params: np.ndarray,
    *,
    target_infidelity: float,
    repeats: int,
    z_score: float,
    max_queries: int,
) -> bool:
    """Certify a target using only repeated device-reported measurements."""

    if repeats <= 0:
        raise ValueError("repeats must be positive")
    losses: list[float] = []
    for _ in range(repeats):
        if device.query_count >= max_queries:
            return False
        losses.append(float(device.query(params)))
    if device.shots is None:
        return float(np.mean(losses)) <= target_infidelity
    total_trials = repeats * device.shots
    failures = int(round(float(np.sum(losses)) * device.shots))
    return (
        one_sided_wilson_upper(
            failures,
            total_trials,
            z_score=z_score,
        )
        <= target_infidelity
    )


def optimize_coordinate_scans(
    device: BlackBoxDevice,
    origin: np.ndarray | Array,
    *,
    basis: np.ndarray | Array | None = None,
    max_queries: int = 1000,
    target_infidelity: float = 1e-3,
    max_cycles: int = 4,
    initial_step: float = 0.25,
    step_decay: float = 0.5,
    scan_points: int = 3,
    samples_per_point: int = 1,
    certification_repeats: int = 7,
    certification_z_score: float = 1.96,
    allow_existing_history: bool = False,
) -> ClosedLoopResult:
    """Query-only cyclic line scans in an orthonormal parameter basis.

    Each coordinate uses either a three-point or five-point symmetric stencil.
    When the stencil is locally convex, one extra query tests the fitted
    quadratic vertex.  Target certification uses only repeated finite-shot
    observations; exact fidelity remains an offline scoring diagnostic.
    """

    if device.query_count and not allow_existing_history:
        raise ValueError("device history must be empty at optimizer start")
    if max_queries <= 0 or max_cycles <= 0:
        raise ValueError("query budget and cycles must be positive")
    if initial_step <= 0.0 or not 0.0 < step_decay <= 1.0:
        raise ValueError("invalid scan step schedule")
    if samples_per_point <= 0:
        raise ValueError("samples_per_point must be positive")
    if scan_points not in (3, 5):
        raise ValueError("scan_points must be 3 or 5")

    origin_np = np.asarray(origin, dtype=np.float64)
    if basis is None:
        basis_np = np.eye(origin_np.size, dtype=np.float64)
    else:
        basis_np = np.asarray(basis, dtype=np.float64)
    if basis_np.ndim != 2 or basis_np.shape[0] != origin_np.size:
        raise ValueError("basis must have shape (n_params, dimension)")

    coefficients = np.zeros(basis_np.shape[1], dtype=np.float64)
    certified_query: int | None = None
    cycles_completed = 0
    exhausted = False

    def averaged_loss(candidate: np.ndarray) -> float:
        nonlocal exhausted
        losses = []
        for _ in range(samples_per_point):
            if device.query_count >= max_queries:
                exhausted = True
                return float("inf")
            params = _affine_subspace_point(origin_np, basis_np, candidate)
            losses.append(float(device.query(params)))
        return float(np.mean(losses))

    for cycle in range(max_cycles):
        step = initial_step * step_decay**cycle
        for coordinate in range(coefficients.size):
            center = coefficients.copy()
            candidates = []
            losses = []
            offsets = np.linspace(-step, step, scan_points)
            for offset in offsets:
                candidate = center.copy()
                candidate[coordinate] += offset
                candidates.append(candidate)
                losses.append(averaged_loss(candidate))
                if exhausted:
                    break
            if exhausted:
                break

            quadratic, linear, _ = np.polyfit(offsets, losses, deg=2)
            if quadratic > 0.0:
                vertex_offset = -linear / (2.0 * quadratic)
                if 1e-12 < abs(vertex_offset) < step:
                    vertex = center.copy()
                    vertex[coordinate] += vertex_offset
                    vertex_loss = averaged_loss(vertex)
                    if not exhausted:
                        candidates.append(vertex)
                        losses.append(vertex_loss)
            coefficients = candidates[int(np.argmin(losses))]
            if exhausted:
                break

        cycles_completed = cycle + 1
        if exhausted:
            break
        current = _affine_subspace_point(origin_np, basis_np, coefficients)
        if certify_reported_target(
            device,
            current,
            target_infidelity=target_infidelity,
            repeats=certification_repeats,
            z_score=certification_z_score,
            max_queries=max_queries,
        ):
            certified_query = device.query_count
            break

    success = certified_query is not None
    if success:
        message = "finite-shot target certified"
    elif exhausted or device.query_count >= max_queries:
        message = "query budget exhausted"
    else:
        message = "maximum coordinate-scan cycles completed"
    return _closed_loop_summary(
        device,
        target_infidelity=target_infidelity,
        optimizer_success=success,
        message=message,
        certified_query_to_target=certified_query,
        cycles_completed=cycles_completed,
        selected_params=_affine_subspace_point(
            origin_np,
            basis_np,
            coefficients,
        ),
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
) -> ClosedLoopResult:
    """Run a SciPy derivative-free optimizer against the query-only device."""

    if device.query_count and not allow_existing_history:
        raise ValueError("device history must be empty at optimizer start")
    if max_queries <= 0:
        raise ValueError("max_queries must be positive")

    origin_np = np.asarray(origin, dtype=np.float64)
    if basis is None:
        basis_np = np.eye(origin_np.size, dtype=np.float64)
    else:
        basis_np = np.asarray(basis, dtype=np.float64)
    initial = np.zeros(basis_np.shape[1], dtype=np.float64)

    def objective(coefficients: np.ndarray) -> float:
        if device.query_count >= max_queries:
            raise QueryBudgetExhausted
        return device.query(
            _affine_subspace_point(origin_np, basis_np, coefficients)
        )

    options: dict[str, object] = {
        "maxiter": max_queries,
        "maxfev": max_queries,
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

    return _closed_loop_summary(
        device,
        target_infidelity=target_infidelity,
        optimizer_success=success,
        message=message,
    )


def optimize_cma_es(
    device: BlackBoxDevice,
    origin: np.ndarray | Array,
    *,
    basis: np.ndarray | Array | None = None,
    max_queries: int = 2000,
    target_infidelity: float = 1e-3,
    initial_sigma: float = 0.25,
    population_size: int | None = None,
    seed: int = 0,
    minimum_axis_std: float = 1e-7,
    certification_repeats: int = 0,
    certification_z_score: float = 1.96,
    allow_existing_history: bool = False,
) -> ClosedLoopResult:
    """Full-covariance CMA-ES against a query-only scalar device.

    The implementation follows the standard rank-one plus rank-mu covariance
    update.  It is intentionally self-contained so cluster runs do not depend
    on a separately installed CMA package.  For noisy devices, a single
    apparently good sample never terminates the search; callers perform the
    repeated-shot certificate after the optimization allocation.
    """

    if device.query_count and not allow_existing_history:
        raise ValueError("device history must be empty at optimizer start")
    if max_queries <= 0:
        raise ValueError("max_queries must be positive")
    if initial_sigma <= 0.0 or minimum_axis_std <= 0.0:
        raise ValueError("CMA-ES scales must be positive")
    if certification_repeats < 0:
        raise ValueError("certification repeats must be nonnegative")

    origin_np = np.asarray(origin, dtype=np.float64)
    if basis is None:
        basis_np = np.eye(origin_np.size, dtype=np.float64)
    else:
        basis_np = np.asarray(basis, dtype=np.float64)
    if basis_np.ndim != 2 or basis_np.shape[0] != origin_np.size:
        raise ValueError("basis must have shape (n_params, dimension)")

    dimension = int(basis_np.shape[1])
    if dimension <= 0:
        raise ValueError("CMA-ES dimension must be positive")
    if population_size is None:
        population_size = 4 + int(np.floor(3.0 * np.log(dimension)))
    if population_size < 2:
        raise ValueError("population size must be at least two")

    mu = population_size // 2
    raw_weights = np.log(mu + 0.5) - np.log(
        np.arange(1, mu + 1, dtype=np.float64)
    )
    weights = raw_weights / np.sum(raw_weights)
    mu_effective = 1.0 / np.sum(weights**2)

    c_sigma = (mu_effective + 2.0) / (
        dimension + mu_effective + 5.0
    )
    d_sigma = (
        1.0
        + 2.0
        * max(
            0.0,
            np.sqrt((mu_effective - 1.0) / (dimension + 1.0))
            - 1.0,
        )
        + c_sigma
    )
    c_c = (4.0 + mu_effective / dimension) / (
        dimension + 4.0 + 2.0 * mu_effective / dimension
    )
    c_one = 2.0 / (
        (dimension + 1.3) ** 2 + mu_effective
    )
    c_mu = min(
        1.0 - c_one,
        2.0
        * (mu_effective - 2.0 + 1.0 / mu_effective)
        / ((dimension + 2.0) ** 2 + mu_effective),
    )
    expected_norm = np.sqrt(dimension) * (
        1.0
        - 1.0 / (4.0 * dimension)
        + 1.0 / (21.0 * dimension**2)
    )

    rng = np.random.default_rng(seed)
    mean = np.zeros(dimension, dtype=np.float64)
    covariance = np.eye(dimension, dtype=np.float64)
    path_sigma = np.zeros(dimension, dtype=np.float64)
    path_covariance = np.zeros(dimension, dtype=np.float64)
    sigma = float(initial_sigma)
    best_loss = float("inf")
    best_coefficients = mean.copy()
    generations = 0
    stopped_for_scale = False
    stopped_for_numerics = False
    certified_query: int | None = None

    while device.query_count < max_queries:
        remaining = max_queries - device.query_count
        generation_size = min(population_size, remaining)
        if generation_size < mu:
            break

        if not np.all(np.isfinite(covariance)):
            stopped_for_numerics = True
            break
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        largest_eigenvalue = max(float(np.max(eigenvalues)), 1e-16)
        eigenvalue_floor = largest_eigenvalue * 1e-12
        axis_scales = np.sqrt(
            np.maximum(eigenvalues, eigenvalue_floor)
        )
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            transform = eigenvectors * axis_scales[np.newaxis, :]
            inverse_transform = (
                eigenvectors * (1.0 / axis_scales)[np.newaxis, :]
            ) @ eigenvectors.T
        if not (
            np.all(np.isfinite(transform))
            and np.all(np.isfinite(inverse_transform))
        ):
            stopped_for_numerics = True
            break

        normal_steps = rng.normal(
            size=(generation_size, dimension)
        )
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            correlated_steps = normal_steps @ transform.T
        if not np.all(np.isfinite(correlated_steps)):
            stopped_for_numerics = True
            break
        candidates = mean + sigma * correlated_steps
        losses = np.empty(generation_size, dtype=np.float64)
        for index, coefficients in enumerate(candidates):
            params = _affine_subspace_point(
                origin_np,
                basis_np,
                coefficients,
            )
            losses[index] = float(device.query(params))

        order = np.argsort(losses)
        if float(losses[order[0]]) < best_loss:
            best_loss = float(losses[order[0]])
            best_coefficients = candidates[order[0]].copy()

        selected = order[:mu]
        old_mean = mean.copy()
        mean = np.sum(
            weights[:, np.newaxis] * candidates[selected],
            axis=0,
        )
        weighted_step = (mean - old_mean) / sigma
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            whitened_step = inverse_transform @ weighted_step
        if not np.all(np.isfinite(whitened_step)):
            stopped_for_numerics = True
            break

        path_sigma = (
            (1.0 - c_sigma) * path_sigma
            + np.sqrt(c_sigma * (2.0 - c_sigma) * mu_effective)
            * whitened_step
        )
        generations += 1
        normalized_path = np.linalg.norm(path_sigma) / np.sqrt(
            1.0 - (1.0 - c_sigma) ** (2 * generations)
        )
        h_sigma = float(
            normalized_path / expected_norm
            < 1.4 + 2.0 / (dimension + 1.0)
        )
        path_covariance = (
            (1.0 - c_c) * path_covariance
            + h_sigma
            * np.sqrt(c_c * (2.0 - c_c) * mu_effective)
            * weighted_step
        )

        selected_steps = (
            candidates[selected] - old_mean[np.newaxis, :]
        ) / sigma
        rank_mu = np.einsum(
            "i,ij,ik->jk",
            weights,
            selected_steps,
            selected_steps,
        )
        covariance = (
            (
                1.0
                - c_one
                - c_mu
                + c_one * (1.0 - h_sigma) * c_c * (2.0 - c_c)
            )
            * covariance
            + c_one * np.outer(path_covariance, path_covariance)
            + c_mu * rank_mu
        )
        covariance = 0.5 * (covariance + covariance.T)
        trace_scale = float(np.trace(covariance) / dimension)
        if not np.isfinite(trace_scale) or trace_scale <= 0.0:
            stopped_for_numerics = True
            break
        covariance /= trace_scale
        sigma *= np.sqrt(trace_scale)
        sigma *= np.exp(
            (c_sigma / d_sigma)
            * (np.linalg.norm(path_sigma) / expected_norm - 1.0)
        )

        if (
            certification_repeats > 0
            and best_loss <= target_infidelity
        ):
            best_params = _affine_subspace_point(
                origin_np,
                basis_np,
                best_coefficients,
            )
            if certify_reported_target(
                device,
                best_params,
                target_infidelity=target_infidelity,
                repeats=certification_repeats,
                z_score=certification_z_score,
                max_queries=max_queries,
            ):
                certified_query = device.query_count
                break

        largest_axis_std = sigma * float(np.max(axis_scales))
        if largest_axis_std <= minimum_axis_std:
            stopped_for_scale = True
            break
        if device.shots is None and best_loss <= target_infidelity:
            break

    if stopped_for_numerics:
        message = "CMA-ES stopped at covariance numerical guard"
    elif stopped_for_scale:
        message = "CMA-ES axis scale converged"
    else:
        message = f"CMA-ES completed {generations} generations"
    return _closed_loop_summary(
        device,
        target_infidelity=target_infidelity,
        optimizer_success=(
            certified_query is not None or generations > 0
        ),
        message=message,
        certified_query_to_target=certified_query,
        cycles_completed=generations,
        selected_params=_affine_subspace_point(
            origin_np,
            basis_np,
            best_coefficients,
        ),
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
