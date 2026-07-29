from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import math

import jax
import jax.numpy as jnp
import numpy as np
from scipy.linalg import subspace_angles
from scipy.optimize import minimize

from qcontrol.closed_loop import SearchSpace
from qcontrol.device import Observation
from qcontrol.objectives import normalized_infidelity
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem


@dataclass(frozen=True, slots=True)
class ExactInfidelityTrajectory:
    initial_infidelity: float
    cumulative_best_by_optimizer_query: tuple[float, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "cumulative_best_by_optimizer_query": list(
                self.cumulative_best_by_optimizer_query
            ),
            "initial_infidelity": self.initial_infidelity,
        }


@dataclass(frozen=True, slots=True)
class RestrictedOptimizationResult:
    attained_infidelity_upper_bound: float
    starting_infidelity_upper_bound: float
    max_iterations: int
    gradient_tolerance: float
    consistency_tolerance: float
    function_evaluations: int
    iterations: int
    converged: bool
    termination: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "attained_infidelity_upper_bound": self.attained_infidelity_upper_bound,
            "consistency_tolerance": self.consistency_tolerance,
            "converged": self.converged,
            "function_evaluations": self.function_evaluations,
            "gradient_tolerance": self.gradient_tolerance,
            "iterations": self.iterations,
            "max_iterations": self.max_iterations,
            "solver": "L-BFGS-B",
            "starting_infidelity_upper_bound": self.starting_infidelity_upper_bound,
            "termination": self.termination,
        }


@dataclass(frozen=True, slots=True)
class GeometryDiagnostics:
    rank_thresholds: tuple[float, ...]
    model_effective_ranks: tuple[int, ...]
    truth_effective_ranks: tuple[int, ...]
    signed_leading_eigenvalue_gaps: tuple[float, ...]
    principal_angles_radians: tuple[float, ...]
    model_top_subspace: np.ndarray
    truth_top_subspace: np.ndarray


def make_offline_evaluator(
    truth: ControlSystem,
    space: PulseSpace,
) -> Callable[[object], float]:
    """Build an exact evaluator for analysis code outside the device API."""
    if not isinstance(truth, ControlSystem):
        raise ValueError("truth must be a ControlSystem")
    if not isinstance(space, PulseSpace):
        raise ValueError("space must be a PulseSpace")
    if len(truth.controls) != space.control_count:
        raise ValueError("pulse space control count does not match the truth system")
    if tuple(truth.amplitude_scales) != tuple(space.amplitude_scales):
        raise ValueError("pulse space amplitude scales do not match the truth system")

    def evaluate(normalized_pulse: object) -> float:
        loss = float(normalized_infidelity(normalized_pulse, truth, space))
        fidelity = float(np.clip(1.0 - loss, 0.0, 1.0))
        if not math.isfinite(fidelity):
            raise ValueError("truth evaluation did not produce a finite fidelity")
        return fidelity

    return evaluate


def _finite_probability(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite probability")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be a finite probability")
    return result


def cumulative_best_exact_infidelity(
    evaluator: Callable[[object], float],
    *,
    initial_pulse: object,
    audited_queries: Sequence[tuple[object, Observation | None]],
) -> ExactInfidelityTrajectory:
    if not callable(evaluator):
        raise ValueError("evaluator must be callable")
    initial = 1.0 - _finite_probability(
        evaluator(initial_pulse),
        name="initial exact fidelity",
    )
    best = initial
    values: list[float] = []
    for expected_query, (pulse, observation) in enumerate(audited_queries, start=1):
        if observation is not None:
            if (
                not isinstance(observation, Observation)
                or observation.validation
                or observation.optimizer_query_index != expected_query
            ):
                raise ValueError("audited observation is not query-aligned")
            infidelity = 1.0 - _finite_probability(
                evaluator(pulse),
                name="offline exact fidelity",
            )
            best = min(best, infidelity)
        values.append(float(best))
    return ExactInfidelityTrajectory(float(initial), tuple(values))


def optimize_restricted_noiseless_upper_bound(
    truth: ControlSystem,
    pulse_space: PulseSpace,
    search_space: SearchSpace,
    *,
    candidate_pulses: Sequence[object],
    max_iterations: int = 100,
    gradient_tolerance: float = 1e-9,
    consistency_tolerance: float = 1e-10,
) -> RestrictedOptimizationResult:
    if not isinstance(truth, ControlSystem) or not isinstance(pulse_space, PulseSpace):
        raise ValueError("restricted optimization requires truth and pulse space")
    if not isinstance(search_space, SearchSpace):
        raise ValueError("restricted optimization requires a SearchSpace")
    if type(max_iterations) is not int or max_iterations <= 0:
        raise ValueError("max_iterations must be a positive integer")
    if (
        not math.isfinite(gradient_tolerance)
        or gradient_tolerance <= 0.0
        or not math.isfinite(consistency_tolerance)
        or consistency_tolerance < 0.0
    ):
        raise ValueError("restricted optimization tolerances must be finite")

    evaluator = make_offline_evaluator(truth, pulse_space)
    pulses = [np.asarray(search_space.origin, dtype=np.float64)]
    pulses.extend(np.asarray(pulse, dtype=np.float64) for pulse in candidate_pulses)
    infidelities = np.asarray(
        [1.0 - evaluator(pulse) for pulse in pulses],
        dtype=np.float64,
    )
    if not np.all(np.isfinite(infidelities)):
        raise ValueError("restricted starting values are not finite")
    best_index = int(np.argmin(infidelities))
    starting = float(infidelities[best_index])
    coordinates = search_space.basis.T @ (pulses[best_index] - search_space.origin)
    coordinates = np.clip(
        coordinates,
        search_space.lower_bounds,
        search_space.upper_bounds,
    )
    origin = jnp.asarray(search_space.origin, dtype=jnp.float64)
    basis = jnp.asarray(search_space.basis, dtype=jnp.float64)

    def objective(raw_coordinates: jax.Array) -> jax.Array:
        pulse = jnp.clip(origin + basis @ raw_coordinates, -1.0, 1.0)
        return normalized_infidelity(pulse, truth, pulse_space)

    value_and_gradient = jax.jit(jax.value_and_grad(objective))

    def scipy_objective(raw_coordinates: np.ndarray) -> tuple[float, np.ndarray]:
        value, gradient = value_and_gradient(
            jnp.asarray(raw_coordinates, dtype=jnp.float64)
        )
        return float(value), np.asarray(gradient, dtype=np.float64)

    solved = minimize(
        scipy_objective,
        coordinates,
        method="L-BFGS-B",
        jac=True,
        bounds=list(
            zip(
                search_space.lower_bounds.tolist(),
                search_space.upper_bounds.tolist(),
            )
        ),
        options={
            "ftol": consistency_tolerance,
            "gtol": gradient_tolerance,
            "maxiter": max_iterations,
            "maxls": 50,
        },
    )
    solved_value = float(solved.fun)
    if (
        not math.isfinite(solved_value)
        or not np.all(np.isfinite(solved.x))
        or solved_value < -consistency_tolerance
    ):
        raise ValueError("restricted solver produced inconsistent non-finite output")
    attained = float(np.clip(min(starting, solved_value), 0.0, 1.0))
    return RestrictedOptimizationResult(
        attained_infidelity_upper_bound=float(attained),
        starting_infidelity_upper_bound=starting,
        max_iterations=max_iterations,
        gradient_tolerance=float(gradient_tolerance),
        consistency_tolerance=float(consistency_tolerance),
        function_evaluations=int(solved.nfev),
        iterations=int(solved.nit),
        converged=bool(solved.success),
        termination="converged" if solved.success else "iteration_budget",
    )


def compute_geometry_diagnostics(
    model: ControlSystem,
    truth: ControlSystem,
    pulse_space: PulseSpace,
    origin: object,
    *,
    top_k: int,
    rank_thresholds: tuple[float, ...] = (1e-6, 1e-8, 1e-10),
) -> GeometryDiagnostics:
    point = jnp.asarray(origin, dtype=jnp.float64)
    if point.ndim != 1 or type(top_k) is not int or not 0 < top_k <= point.size:
        raise ValueError("geometry top_k must fit the pulse dimension")

    def hessian(system: ControlSystem) -> np.ndarray:
        matrix = np.asarray(
            jax.hessian(
                lambda pulse: normalized_infidelity(pulse, system, pulse_space)
            )(point),
            dtype=np.float64,
        )
        return np.asarray(0.5 * (matrix + matrix.T), dtype=np.float64)

    model_hessian = hessian(model)
    truth_hessian = hessian(truth)
    if not np.all(np.isfinite(model_hessian)) or not np.all(np.isfinite(truth_hessian)):
        raise ValueError("geometry Hessians must be finite")
    model_values, model_vectors = np.linalg.eigh(model_hessian)
    truth_values, truth_vectors = np.linalg.eigh(truth_hessian)
    model_order = np.argsort(np.abs(model_values))[::-1]
    truth_order = np.argsort(np.abs(truth_values))[::-1]
    model_values = model_values[model_order]
    truth_values = truth_values[truth_order]
    model_top = np.asarray(model_vectors[:, model_order[:top_k]], dtype=np.float64)
    truth_top = np.asarray(truth_vectors[:, truth_order[:top_k]], dtype=np.float64)
    angles = np.asarray(subspace_angles(model_top, truth_top), dtype=np.float64)
    gaps = np.asarray(truth_values[:top_k] - model_values[:top_k], dtype=np.float64)
    if not np.all(np.isfinite(angles)) or not np.all(np.isfinite(gaps)):
        raise ValueError("geometry diagnostics must be finite")
    return GeometryDiagnostics(
        rank_thresholds=rank_thresholds,
        model_effective_ranks=tuple(
            int(np.count_nonzero(np.abs(model_values) > threshold))
            for threshold in rank_thresholds
        ),
        truth_effective_ranks=tuple(
            int(np.count_nonzero(np.abs(truth_values) > threshold))
            for threshold in rank_thresholds
        ),
        signed_leading_eigenvalue_gaps=tuple(float(value) for value in gaps),
        principal_angles_radians=tuple(float(value) for value in angles),
        model_top_subspace=model_top,
        truth_top_subspace=truth_top,
    )
