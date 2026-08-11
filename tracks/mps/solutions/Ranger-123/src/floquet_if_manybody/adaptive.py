"""Ordered, resumable refinement of PT-TEMPO numerical controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import trapezoid

from .convergence import ConvergenceCache, state_residual
from .n3_heat import N3HeatPoint

Parameter = Literal[
    "memory_steps",
    "steps_per_period",
    "epsrel",
    "phase_samples",
]
Runner = Callable[[N3HeatPoint, ConvergenceCache | None], dict[str, Any]]


@dataclass(frozen=True)
class AdaptiveSchedule:
    memory_steps: tuple[int, ...] = (3, 4, 5)
    steps_per_period: tuple[int, ...] = (12, 16, 20)
    epsrel: tuple[float, ...] = (1e-5, 3e-6)
    state_threshold: float = 5e-2
    correlation_threshold: float = 5e-2
    heat_threshold: float = 5e-2
    phase_threshold: float = 1e-3
    trace_threshold: float = 5e-3

    def __post_init__(self) -> None:
        if any(value <= 0 for value in self.memory_steps + self.steps_per_period):
            raise ValueError("integer refinement controls must be positive")
        if any(not 0 < value < 1 for value in self.epsrel):
            raise ValueError("epsrel refinements must lie between zero and one")
        if tuple(sorted(self.memory_steps)) != self.memory_steps:
            raise ValueError("memory_steps must increase")
        if tuple(sorted(self.steps_per_period)) != self.steps_per_period:
            raise ValueError("steps_per_period must increase")
        if tuple(sorted(self.epsrel, reverse=True)) != self.epsrel:
            raise ValueError("epsrel must decrease")


@dataclass(frozen=True)
class UniformAdaptiveSchedule:
    """Refinement controls for a uniform infinite process tensor."""

    steps_per_period: tuple[int, ...] = (60, 90, 120)
    tolerances: tuple[float, ...] = (3e-7, 1e-7, 3e-8)
    phase_samples: tuple[int, ...] = (3, 15)
    state_threshold: float = 5e-2
    correlation_threshold: float = 8e-2
    heat_threshold: float = 8e-2
    phase_threshold: float = 1e-3
    trace_threshold: float = 5e-3
    hermiticity_threshold: float = 5e-3

    def __post_init__(self) -> None:
        if any(value < 2 for value in self.steps_per_period):
            raise ValueError("steps_per_period values must be at least two")
        if any(not 0 < value < 1 for value in self.tolerances):
            raise ValueError("tolerances must lie between zero and one")
        if any(value < 2 for value in self.phase_samples):
            raise ValueError("phase_samples values must be at least two")
        if tuple(sorted(self.steps_per_period)) != self.steps_per_period:
            raise ValueError("steps_per_period must increase")
        if tuple(sorted(self.tolerances, reverse=True)) != self.tolerances:
            raise ValueError("tolerances must decrease")
        if tuple(sorted(self.phase_samples)) != self.phase_samples:
            raise ValueError("phase_samples must increase")
        if any(
            steps % samples != 0
            for steps in self.steps_per_period
            for samples in self.phase_samples
        ):
            raise ValueError(
                "every phase_samples value must divide every timestep refinement"
            )


@dataclass(frozen=True)
class RefinementEvidence:
    parameter: Parameter
    coarse_fingerprint: str
    refined_fingerprint: str
    coarse_value: float
    refined_value: float
    state_residual: float
    correlation_residual: float
    heat_residual: float
    passed: bool
    coarse_bond_dimension: int | None = None
    refined_bond_dimension: int | None = None
    coarse_steps_per_period: int | None = None
    refined_steps_per_period: int | None = None
    coarse_tolerance: float | None = None
    refined_tolerance: float | None = None
    coarse_phase_samples: int | None = None
    refined_phase_samples: int | None = None


@dataclass(frozen=True)
class AdaptiveResult:
    converged: bool
    status: Literal["converged", "resource_ceiling", "backend_failure"]
    final_point: N3HeatPoint
    final_result: dict[str, Any]
    evidence: tuple[RefinementEvidence, ...]
    failed_parameter: Parameter | None = None


def _complex_array(value: dict[str, Any]) -> NDArray[np.complex128]:
    return cast(
        NDArray[np.complex128],
        np.asarray(value["real"], dtype=float)
        + 1j * np.asarray(value["imag"], dtype=float),
    )


def _aligned_residual(
    candidate_grid: NDArray[np.float64],
    candidate: NDArray[np.complex128] | NDArray[np.float64],
    reference_grid: NDArray[np.float64],
    reference: NDArray[np.complex128] | NDArray[np.float64],
) -> float:
    """Compare curves on the coarser grid over their common domain."""
    lower = max(float(candidate_grid[0]), float(reference_grid[0]))
    upper = min(float(candidate_grid[-1]), float(reference_grid[-1]))
    common = candidate_grid[
        (candidate_grid >= lower - 1e-14) & (candidate_grid <= upper + 1e-14)
    ]
    if len(common) < 2:
        raise ValueError("curve grids do not share a usable interval")
    candidate_common = np.interp(common, candidate_grid, np.real(candidate)) + 1j * np.interp(
        common, candidate_grid, np.imag(candidate)
    )
    reference_common = np.interp(common, reference_grid, np.real(reference)) + 1j * np.interp(
        common, reference_grid, np.imag(reference)
    )
    numerator = float(trapezoid(abs(candidate_common - reference_common), common))
    denominator = float(trapezoid(abs(reference_common), common)) + 1e-15
    return numerator / denominator


def _residuals(
    coarse: dict[str, Any], refined: dict[str, Any]
) -> tuple[float, float, float]:
    state = state_residual(
        _complex_array(coarse["phase_state"]),
        _complex_array(refined["phase_state"]),
    )
    coarse_correlation = _complex_array(coarse["correlation"]["connected"])
    refined_correlation = _complex_array(refined["correlation"]["connected"])
    correlation = _aligned_residual(
        np.asarray(coarse["correlation"]["delay"], dtype=float),
        coarse_correlation,
        np.asarray(refined["correlation"]["delay"], dtype=float),
        refined_correlation,
    )
    heat = _aligned_residual(
        np.asarray(coarse["frequency"], dtype=float),
        np.asarray(coarse["continuous"], dtype=float),
        np.asarray(refined["frequency"], dtype=float),
        np.asarray(refined["continuous"], dtype=float),
    )
    return state, correlation, heat


def _refinement_values(
    point: N3HeatPoint, schedule: AdaptiveSchedule, parameter: Parameter
) -> tuple[int | float, ...]:
    if parameter == "memory_steps":
        values: tuple[int | float, ...] = schedule.memory_steps
        current: int | float = point.memory_steps
    elif parameter == "steps_per_period":
        values = schedule.steps_per_period
        current = point.steps_per_period
    else:
        values = schedule.epsrel
        current = point.epsrel
    if current in values:
        return values[values.index(current) :]
    if parameter != "epsrel":
        return current, *tuple(value for value in values if value > current)
    return current, *tuple(value for value in values if value < current)


def _replace_parameter(
    point: N3HeatPoint, parameter: Parameter, value: int | float
) -> N3HeatPoint:
    if parameter == "memory_steps":
        return replace(point, memory_steps=int(value))
    if parameter == "steps_per_period":
        steps = int(value)
        memory = max(
            point.memory_steps,
            int(round(point.memory_steps * steps / point.steps_per_period)),
        )
        return replace(point, steps_per_period=steps, memory_steps=memory)
    return replace(point, epsrel=float(value))


def run_adaptive(
    point: N3HeatPoint,
    schedule: AdaptiveSchedule,
    runner: Runner,
    cache: ConvergenceCache | None,
) -> AdaptiveResult:
    """Refine memory, timestep, and SVD tolerance in that order."""
    current_point = point
    current_result = runner(current_point, cache)
    evidence: list[RefinementEvidence] = []
    if not bool(current_result.get("converged", False)):
        return AdaptiveResult(
            False, "backend_failure", current_point, current_result, tuple(evidence)
        )

    for parameter in ("memory_steps", "steps_per_period", "epsrel"):
        typed_parameter: Parameter = parameter
        values = _refinement_values(current_point, schedule, typed_parameter)
        if len(values) < 2:
            return AdaptiveResult(
                False,
                "resource_ceiling",
                current_point,
                current_result,
                tuple(evidence),
                typed_parameter,
            )
        parameter_passed = False
        for value in values[1:]:
            refined_point = _replace_parameter(current_point, typed_parameter, value)
            refined_result = runner(refined_point, cache)
            if not bool(refined_result.get("converged", False)):
                return AdaptiveResult(
                    False,
                    "backend_failure",
                    refined_point,
                    refined_result,
                    tuple(evidence),
                    typed_parameter,
                )
            state, correlation, heat = _residuals(current_result, refined_result)
            passed = (
                state <= schedule.state_threshold
                and correlation <= schedule.correlation_threshold
                and heat <= schedule.heat_threshold
            )
            evidence.append(
                RefinementEvidence(
                    typed_parameter,
                    str(current_result["fingerprint"]),
                    str(refined_result["fingerprint"]),
                    float(getattr(current_point, typed_parameter)),
                    float(value),
                    state,
                    correlation,
                    heat,
                    passed,
                )
            )
            current_point = refined_point
            current_result = refined_result
            if passed:
                parameter_passed = True
                break
        if not parameter_passed:
            return AdaptiveResult(
                False,
                "resource_ceiling",
                current_point,
                current_result,
                tuple(evidence),
                typed_parameter,
            )

    diagnostics = current_result.get("diagnostics", {})
    final_checks = (
        float(diagnostics.get("phase_residual", np.inf))
        <= schedule.phase_threshold
        and float(diagnostics.get("trace_error", np.inf))
        <= schedule.trace_threshold
        and float(diagnostics.get("minimum_density_eigenvalue", -np.inf)) >= -5e-3
        and float(diagnostics.get("connected_tail_amplitude", np.inf)) <= 5e-2
    )
    return AdaptiveResult(
        final_checks,
        "converged" if final_checks else "backend_failure",
        current_point,
        current_result,
        tuple(evidence),
    )


def _schedule_tail(
    current: int | float,
    values: tuple[int, ...] | tuple[float, ...],
    *,
    increasing: bool,
) -> tuple[int | float, ...]:
    if current in values:
        return values[values.index(current) :]
    if increasing:
        return current, *tuple(value for value in values if value > current)
    return current, *tuple(value for value in values if value < current)


def _uniform_refined_point(
    point: N3HeatPoint,
    parameter: Parameter,
    value: int | float,
) -> N3HeatPoint:
    if parameter == "steps_per_period":
        return replace(point, steps_per_period=int(value))
    if parameter == "phase_samples":
        return replace(point, phase_samples=int(value))
    if parameter == "epsrel":
        return replace(point, epsrel=float(value))
    raise ValueError(f"unsupported uniform refinement parameter {parameter}")


def _bond_dimension(result: dict[str, Any]) -> int | None:
    value = result.get("diagnostics", {}).get("bond_dimension")
    if value is None:
        return None
    return int(value)


def _uniform_physical_checks(
    result: dict[str, Any],
    schedule: UniformAdaptiveSchedule,
) -> bool:
    diagnostics = result.get("diagnostics", {})
    return bool(
        float(diagnostics.get("phase_residual", np.inf))
        <= schedule.phase_threshold
        and float(diagnostics.get("trace_error", np.inf))
        <= schedule.trace_threshold
        and float(diagnostics.get("hermiticity_error", np.inf))
        <= schedule.hermiticity_threshold
        and float(diagnostics.get("minimum_density_eigenvalue", -np.inf)) >= -5e-3
        and float(diagnostics.get("connected_tail_amplitude", np.inf)) <= 5e-2
    )


def run_uniform_adaptive(
    point: N3HeatPoint,
    schedule: UniformAdaptiveSchedule,
    runner: Runner,
    cache: ConvergenceCache | None,
) -> AdaptiveResult:
    """Converge compression at every timestep, then refine phase quadrature.

    Compression and Trotter errors are coupled: a tolerance that is adequate on
    one time grid need not be adequate on the next.  Each timestep candidate is
    therefore converged across the tolerance ladder before two adjacent
    timestep candidates are compared.
    """
    if point.backend != "uniform_tempo":
        raise ValueError("uniform adaptive runner requires backend='uniform_tempo'")
    current_phase_samples = point.phase_samples
    if current_phase_samples is None:
        raise ValueError("uniform adaptive runner requires explicit phase_samples")

    evidence: list[RefinementEvidence] = []
    timestep_values = _schedule_tail(
        point.steps_per_period,
        schedule.steps_per_period,
        increasing=True,
    )
    tolerance_values = _schedule_tail(
        point.epsrel,
        schedule.tolerances,
        increasing=False,
    )
    if len(timestep_values) < 2 or len(tolerance_values) < 2:
        failed: Parameter = (
            "steps_per_period" if len(timestep_values) < 2 else "epsrel"
        )
        initial_result = runner(point, cache)
        return AdaptiveResult(
            False,
            "resource_ceiling",
            point,
            initial_result,
            tuple(evidence),
            failed,
        )

    previous_timestep_point: N3HeatPoint | None = None
    previous_timestep_result: dict[str, Any] | None = None
    previous_compression_passed = False
    current_point = point
    current_result: dict[str, Any] | None = None
    timestep_passed = False

    for step_index, step_value in enumerate(timestep_values):
        compression_point = replace(
            point,
            steps_per_period=int(step_value),
            epsrel=float(tolerance_values[0]),
        )
        compression_result = runner(compression_point, cache)
        if not bool(compression_result.get("complete", False)):
            return AdaptiveResult(
                False,
                "backend_failure",
                compression_point,
                compression_result,
                tuple(evidence),
                "epsrel",
            )

        compression_passed = False
        for tolerance in tolerance_values[1:]:
            refined_point = replace(
                compression_point,
                epsrel=float(tolerance),
            )
            refined_result = runner(refined_point, cache)
            if not bool(refined_result.get("complete", False)):
                return AdaptiveResult(
                    False,
                    "backend_failure",
                    refined_point,
                    refined_result,
                    tuple(evidence),
                    "epsrel",
                )
            state, correlation, heat = _residuals(
                compression_result,
                refined_result,
            )
            passed = (
                state <= schedule.state_threshold
                and correlation <= schedule.correlation_threshold
                and heat <= schedule.heat_threshold
            )
            evidence.append(
                RefinementEvidence(
                    "epsrel",
                    str(compression_result["fingerprint"]),
                    str(refined_result["fingerprint"]),
                    float(compression_point.epsrel),
                    float(tolerance),
                    state,
                    correlation,
                    heat,
                    passed,
                    _bond_dimension(compression_result),
                    _bond_dimension(refined_result),
                    compression_point.steps_per_period,
                    refined_point.steps_per_period,
                    compression_point.epsrel,
                    refined_point.epsrel,
                    compression_point.phase_samples,
                    refined_point.phase_samples,
                )
            )
            compression_point = refined_point
            compression_result = refined_result
            if passed:
                compression_passed = True
                break
        current_point = compression_point
        current_result = compression_result
        if not compression_passed and step_index == len(timestep_values) - 1:
            return AdaptiveResult(
                False,
                "resource_ceiling",
                current_point,
                current_result,
                tuple(evidence),
                "epsrel",
            )

        if previous_timestep_point is not None and previous_timestep_result is not None:
            state, correlation, heat = _residuals(
                previous_timestep_result,
                current_result,
            )
            passed = (
                previous_compression_passed
                and compression_passed
                and state <= schedule.state_threshold
                and correlation <= schedule.correlation_threshold
                and heat <= schedule.heat_threshold
                and _uniform_physical_checks(current_result, schedule)
            )
            evidence.append(
                RefinementEvidence(
                    "steps_per_period",
                    str(previous_timestep_result["fingerprint"]),
                    str(current_result["fingerprint"]),
                    float(previous_timestep_point.steps_per_period),
                    float(current_point.steps_per_period),
                    state,
                    correlation,
                    heat,
                    passed,
                    _bond_dimension(previous_timestep_result),
                    _bond_dimension(current_result),
                    previous_timestep_point.steps_per_period,
                    current_point.steps_per_period,
                    previous_timestep_point.epsrel,
                    current_point.epsrel,
                    previous_timestep_point.phase_samples,
                    current_point.phase_samples,
                )
            )
            if passed:
                timestep_passed = True
                break
        previous_timestep_point = current_point
        previous_timestep_result = current_result
        previous_compression_passed = compression_passed

    if current_result is None:
        raise RuntimeError("uniform adaptive refinement produced no result")
    if not timestep_passed:
        return AdaptiveResult(
            False,
            "resource_ceiling",
            current_point,
            current_result,
            tuple(evidence),
            "steps_per_period",
        )

    phase_values = _schedule_tail(
        current_phase_samples,
        schedule.phase_samples,
        increasing=True,
    )
    if len(phase_values) < 2:
        return AdaptiveResult(
            False,
            "resource_ceiling",
            current_point,
            current_result,
            tuple(evidence),
            "phase_samples",
        )
    phase_passed = False
    for phase_value in phase_values[1:]:
        refined_point = replace(current_point, phase_samples=int(phase_value))
        refined_result = runner(refined_point, cache)
        if not bool(refined_result.get("complete", False)):
            return AdaptiveResult(
                False,
                "backend_failure",
                refined_point,
                refined_result,
                tuple(evidence),
                "phase_samples",
            )
        state, correlation, heat = _residuals(current_result, refined_result)
        passed = (
            state <= schedule.state_threshold
            and correlation <= schedule.correlation_threshold
            and heat <= schedule.heat_threshold
            and _uniform_physical_checks(refined_result, schedule)
        )
        evidence.append(
            RefinementEvidence(
                "phase_samples",
                str(current_result["fingerprint"]),
                str(refined_result["fingerprint"]),
                float(current_point.phase_samples or current_phase_samples),
                float(phase_value),
                state,
                correlation,
                heat,
                passed,
                _bond_dimension(current_result),
                _bond_dimension(refined_result),
                current_point.steps_per_period,
                refined_point.steps_per_period,
                current_point.epsrel,
                refined_point.epsrel,
                current_point.phase_samples,
                refined_point.phase_samples,
            )
        )
        current_point = refined_point
        current_result = refined_result
        if passed:
            phase_passed = True
            break
    if not phase_passed:
        return AdaptiveResult(
            False,
            "resource_ceiling",
            current_point,
            current_result,
            tuple(evidence),
            "phase_samples",
        )

    final_checks = _uniform_physical_checks(current_result, schedule)
    return AdaptiveResult(
        final_checks,
        "converged" if final_checks else "backend_failure",
        current_point,
        current_result,
        tuple(evidence),
    )


def run_uniform_compression_audit(
    point: N3HeatPoint,
    schedule: UniformAdaptiveSchedule,
    runner: Runner,
    cache: ConvergenceCache | None,
) -> AdaptiveResult:
    """Converge only MPO compression and record a timestep resource ceiling.

    This is used for explicitly exploratory points whose next timestep grid is
    outside the declared local budget.  It never returns ``converged``.
    """
    if point.backend != "uniform_tempo":
        raise ValueError("uniform compression audit requires backend='uniform_tempo'")
    tolerance_values = _schedule_tail(
        point.epsrel,
        schedule.tolerances,
        increasing=False,
    )
    current_point = point
    current_result = runner(current_point, cache)
    evidence: list[RefinementEvidence] = []
    if not bool(current_result.get("complete", False)):
        return AdaptiveResult(
            False,
            "backend_failure",
            current_point,
            current_result,
            tuple(evidence),
            "epsrel",
        )
    for tolerance in tolerance_values[1:]:
        refined_point = replace(current_point, epsrel=float(tolerance))
        refined_result = runner(refined_point, cache)
        if not bool(refined_result.get("complete", False)):
            return AdaptiveResult(
                False,
                "backend_failure",
                refined_point,
                refined_result,
                tuple(evidence),
                "epsrel",
            )
        state, correlation, heat = _residuals(current_result, refined_result)
        passed = (
            state <= schedule.state_threshold
            and correlation <= schedule.correlation_threshold
            and heat <= schedule.heat_threshold
        )
        evidence.append(
            RefinementEvidence(
                "epsrel",
                str(current_result["fingerprint"]),
                str(refined_result["fingerprint"]),
                current_point.epsrel,
                refined_point.epsrel,
                state,
                correlation,
                heat,
                passed,
                _bond_dimension(current_result),
                _bond_dimension(refined_result),
                current_point.steps_per_period,
                refined_point.steps_per_period,
                current_point.epsrel,
                refined_point.epsrel,
                current_point.phase_samples,
                refined_point.phase_samples,
            )
        )
        current_point = refined_point
        current_result = refined_result
        if passed:
            return AdaptiveResult(
                False,
                "resource_ceiling",
                current_point,
                current_result,
                tuple(evidence),
                "steps_per_period",
            )
    return AdaptiveResult(
        False,
        "resource_ceiling",
        current_point,
        current_result,
        tuple(evidence),
        "epsrel",
    )
