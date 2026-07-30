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
    best_successful_audited_infidelity: float | None = None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "cumulative_best_by_optimizer_query": list(
                self.cumulative_best_by_optimizer_query
            ),
            "best_successful_audited_infidelity": (
                self.best_successful_audited_infidelity
            ),
            "initial_infidelity": self.initial_infidelity,
        }


@dataclass(frozen=True, slots=True)
class RestrictedOptimizationResult:
    attained_infidelity_upper_bound: float
    starting_infidelity_upper_bound: float
    max_iterations: int
    max_evaluations: int
    gradient_tolerance: float
    consistency_tolerance: float
    nfev: int
    nit: int
    solver_success: bool
    solver_status: int
    solver_message_code: str
    solver_output_finite: bool
    termination: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "cached_solver_attained_infidelity_upper_bound": (
                self.attained_infidelity_upper_bound
            ),
            "cached_solver_starting_infidelity_upper_bound": (
                self.starting_infidelity_upper_bound
            ),
            "certified": self.termination == "converged",
            "consistency_tolerance": self.consistency_tolerance,
            "gradient_tolerance": self.gradient_tolerance,
            "max_evaluations": self.max_evaluations,
            "max_iterations": self.max_iterations,
            "nfev": self.nfev,
            "nit": self.nit,
            "solver": "L-BFGS-B",
            "solver_message_code": self.solver_message_code,
            "solver_output_finite": self.solver_output_finite,
            "solver_status": self.solver_status,
            "solver_success": self.solver_success,
            "termination": self.termination,
        }


@dataclass(frozen=True, slots=True)
class GeometryDiagnostics:
    rank_thresholds: tuple[float, ...]
    model_effective_ranks: tuple[int, ...]
    truth_effective_ranks: tuple[int, ...]
    model_eigenvalues: np.ndarray
    truth_eigenvalues: np.ndarray
    model_eigenvectors: np.ndarray
    truth_eigenvectors: np.ndarray

    @property
    def signed_eigenvalue_gaps(self) -> tuple[float, ...]:
        return tuple(
            float(value)
            for value in self.truth_eigenvalues - self.model_eigenvalues
        )

    @property
    def principal_angles_radians(self) -> tuple[float, ...]:
        return self.slice(len(self.model_eigenvalues)).principal_angles_radians

    def slice(self, top_k: int) -> GeometrySlice:
        if type(top_k) is not int or not 0 < top_k <= len(self.model_eigenvalues):
            raise ValueError("geometry top_k must fit the available spectrum")
        model_top = np.asarray(
            self.model_eigenvectors[:, :top_k],
            dtype=np.float64,
        )
        truth_top = np.asarray(
            self.truth_eigenvectors[:, :top_k],
            dtype=np.float64,
        )
        angles = np.asarray(subspace_angles(model_top, truth_top), dtype=np.float64)
        if not np.all(np.isfinite(angles)):
            raise ValueError("principal angles must be finite")
        return GeometrySlice(
            rank_thresholds=self.rank_thresholds,
            model_effective_ranks=self.model_effective_ranks,
            truth_effective_ranks=self.truth_effective_ranks,
            signed_leading_eigenvalue_gaps=tuple(
                float(value)
                for value in (
                    self.truth_eigenvalues[:top_k]
                    - self.model_eigenvalues[:top_k]
                )
            ),
            principal_angles_radians=tuple(float(value) for value in angles),
            model_top_subspace=model_top,
            truth_top_subspace=truth_top,
        )


@dataclass(frozen=True, slots=True)
class GeometrySlice:
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
    best_successful: float | None = None
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
            best_successful = (
                infidelity
                if best_successful is None
                else min(best_successful, infidelity)
            )
            best = min(best, infidelity)
        values.append(float(best))
    return ExactInfidelityTrajectory(
        float(initial),
        tuple(values),
        None if best_successful is None else float(best_successful),
    )


def effective_ranks(
    spectrum: object,
    thresholds: Sequence[float] = (1e-6, 1e-8, 1e-10),
) -> tuple[int, ...]:
    values = np.asarray(spectrum, dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("effective-rank spectrum must be a finite vector")
    resolved_thresholds = tuple(float(value) for value in thresholds)
    if (
        not resolved_thresholds
        or any(
            not math.isfinite(value) or value <= 0.0
            for value in resolved_thresholds
        )
    ):
        raise ValueError("effective-rank thresholds must be finite and positive")
    scale = float(np.max(np.abs(values), initial=0.0))
    if scale == 0.0:
        return tuple(0 for _ in resolved_thresholds)
    return tuple(
        int(np.count_nonzero(np.abs(values) > threshold * scale))
        for threshold in resolved_thresholds
    )


def canonical_solver_message_code(message: object) -> str:
    normalized = str(message).upper()
    if "CONVERGENCE" in normalized:
        return "convergence"
    if "ITERATION" in normalized and "LIMIT" in normalized:
        return "iteration_limit"
    if (
        ("EVALUATION" in normalized or "F AND G" in normalized)
        and ("LIMIT" in normalized or "EXCEED" in normalized)
    ):
        return "evaluation_limit"
    if (
        "LNSRCH" in normalized
        or "LINE SEARCH" in normalized
        or "ABNORMAL" in normalized
    ):
        return "line_search_failure"
    if any(token in normalized for token in ("NAN", "INF", "NUMERICAL")):
        return "numerical_failure"
    return "solver_failure"


def classify_solver_termination(
    *,
    success: bool,
    status: int,
    message_code: str,
    output_finite: bool,
    nit: int,
    nfev: int,
    max_iterations: int,
    max_evaluations: int,
) -> str:
    allowed_codes = {
        "convergence",
        "evaluation_limit",
        "iteration_limit",
        "line_search_failure",
        "numerical_failure",
        "solver_failure",
    }
    if (
        type(success) is not bool
        or type(status) is not int
        or message_code not in allowed_codes
        or type(output_finite) is not bool
        or type(nit) is not int
        or nit < 0
        or type(nfev) is not int
        or nfev <= 0
        or type(max_iterations) is not int
        or max_iterations <= 0
        or type(max_evaluations) is not int
        or max_evaluations <= 0
    ):
        raise ValueError("solver raw facts are invalid")
    if success:
        if status != 0 or message_code != "convergence" or not output_finite:
            raise ValueError("solver success facts are contradictory")
        return "converged"
    if status == 0 or message_code == "convergence":
        raise ValueError("solver status-zero facts are contradictory")
    if not output_finite:
        return "numerical_failure"
    if message_code == "numerical_failure":
        raise ValueError("finite solver output cannot be numerical_failure")
    if message_code == "iteration_limit":
        if status != 1 or nit == 0 or nit < max_iterations:
            raise ValueError("solver iteration-limit facts are contradictory")
        return "iteration_limit"
    if message_code == "evaluation_limit":
        if status != 1 or nfev < max_evaluations:
            raise ValueError("solver evaluation-limit facts are contradictory")
        return "evaluation_limit"
    if message_code == "line_search_failure":
        if status != 2:
            raise ValueError("solver line-search facts are contradictory")
        return "line_search_failure"
    if status == 1:
        raise ValueError("solver limit status lacks a limit message")
    return "solver_failure"


def optimize_restricted_noiseless_upper_bound(
    truth: ControlSystem,
    pulse_space: PulseSpace,
    search_space: SearchSpace,
    *,
    max_iterations: int = 100,
    max_evaluations: int = 1_000,
    gradient_tolerance: float = 1e-9,
    consistency_tolerance: float = 1e-10,
) -> RestrictedOptimizationResult:
    if not isinstance(truth, ControlSystem) or not isinstance(pulse_space, PulseSpace):
        raise ValueError("restricted optimization requires truth and pulse space")
    if not isinstance(search_space, SearchSpace):
        raise ValueError("restricted optimization requires a SearchSpace")
    if type(max_iterations) is not int or max_iterations <= 0:
        raise ValueError("max_iterations must be a positive integer")
    if type(max_evaluations) is not int or max_evaluations <= 0:
        raise ValueError("max_evaluations must be a positive integer")
    if (
        not math.isfinite(gradient_tolerance)
        or gradient_tolerance <= 0.0
        or not math.isfinite(consistency_tolerance)
        or consistency_tolerance < 0.0
    ):
        raise ValueError("restricted optimization tolerances must be finite")

    evaluator = make_offline_evaluator(truth, pulse_space)
    starting = float(1.0 - evaluator(search_space.origin))
    coordinates = np.zeros(search_space.dimension, dtype=np.float64)
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
            "maxfun": max_evaluations,
            "maxiter": max_iterations,
            "maxls": 50,
        },
    )
    output_finite = bool(
        np.all(np.isfinite(np.asarray(solved.fun)))
        and np.all(np.isfinite(np.asarray(solved.x)))
        and np.all(np.isfinite(np.asarray(solved.jac)))
    )
    message_code = canonical_solver_message_code(solved.message)
    termination = classify_solver_termination(
        success=bool(solved.success),
        status=int(solved.status),
        message_code=message_code,
        output_finite=output_finite,
        nit=int(solved.nit),
        nfev=int(solved.nfev),
        max_iterations=max_iterations,
        max_evaluations=max_evaluations,
    )
    solved_value = float(solved.fun)
    finite_solved = (
        math.isfinite(solved_value)
        and solved_value >= -consistency_tolerance
        and np.all(np.isfinite(solved.x))
    )
    attained = float(
        np.clip(
            min(starting, solved_value) if finite_solved else starting,
            0.0,
            1.0,
        )
    )
    return RestrictedOptimizationResult(
        attained_infidelity_upper_bound=float(attained),
        starting_infidelity_upper_bound=starting,
        max_iterations=max_iterations,
        max_evaluations=max_evaluations,
        gradient_tolerance=float(gradient_tolerance),
        consistency_tolerance=float(consistency_tolerance),
        nfev=int(solved.nfev),
        nit=int(solved.nit),
        solver_success=bool(solved.success),
        solver_status=int(solved.status),
        solver_message_code=message_code,
        solver_output_finite=output_finite,
        termination=termination,
    )


def finalize_restricted_attained_bound(
    cached: RestrictedOptimizationResult,
    exact: ExactInfidelityTrajectory,
) -> dict[str, object]:
    if not isinstance(cached, RestrictedOptimizationResult) or not isinstance(
        exact,
        ExactInfidelityTrajectory,
    ):
        raise ValueError("restricted finalization requires derived metric results")
    evidence = (
        ("initial_origin", exact.initial_infidelity),
        ("audited_candidate", exact.best_successful_audited_infidelity),
        ("restricted_solver", cached.attained_infidelity_upper_bound),
    )
    available = [
        (source, float(value))
        for source, value in evidence
        if value is not None
    ]
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for _, value in available):
        raise ValueError("attained-bound evidence must be finite probabilities")
    minimum = min(value for _, value in available)
    source = next(source for source, value in available if value == minimum)
    return {
        **cached.canonical_dict(),
        "attained_infidelity_upper_bound": minimum,
        "attained_infidelity_source": source,
        "best_successful_audited_exact_infidelity": (
            exact.best_successful_audited_infidelity
        ),
        "initial_exact_infidelity": exact.initial_infidelity,
    }


def compute_geometry_diagnostics(
    model: ControlSystem,
    truth: ControlSystem,
    pulse_space: PulseSpace,
    origin: object,
    *,
    rank_thresholds: tuple[float, ...] = (1e-6, 1e-8, 1e-10),
) -> GeometryDiagnostics:
    point = jnp.asarray(origin, dtype=jnp.float64)
    if point.ndim != 1:
        raise ValueError("geometry origin must be a vector")

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
    model_vectors = np.asarray(model_vectors[:, model_order], dtype=np.float64)
    truth_vectors = np.asarray(truth_vectors[:, truth_order], dtype=np.float64)
    if (
        not np.all(np.isfinite(model_values))
        or not np.all(np.isfinite(truth_values))
        or not np.all(np.isfinite(model_vectors))
        or not np.all(np.isfinite(truth_vectors))
    ):
        raise ValueError("geometry diagnostics must be finite")
    return GeometryDiagnostics(
        rank_thresholds=rank_thresholds,
        model_effective_ranks=effective_ranks(model_values, rank_thresholds),
        truth_effective_ranks=effective_ranks(truth_values, rank_thresholds),
        model_eigenvalues=np.asarray(model_values, dtype=np.float64),
        truth_eigenvalues=np.asarray(truth_values, dtype=np.float64),
        model_eigenvectors=model_vectors,
        truth_eigenvectors=truth_vectors,
    )
