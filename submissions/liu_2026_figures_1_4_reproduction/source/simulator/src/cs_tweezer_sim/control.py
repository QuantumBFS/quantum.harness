"""Parameterized public programs and finite-budget controller interfaces.

This module intentionally imports no backend, oracle, QuTiP, fidelity, gradient
or Hessian implementation. Controllers receive only ``ExperimentResult``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from .calibration import public_success_probability
from .contracts import (
    Delay,
    ExperimentProgram,
    ExperimentResult,
    ParallelPlay,
    Play,
)


@dataclass(frozen=True)
class ScalarParameterSpec:
    name: str
    lower: float
    upper: float
    initial: float

    def __post_init__(self) -> None:
        if not self.name or not self.lower <= self.initial <= self.upper:
            raise ValueError("scalar parameter bounds/initial value are invalid")

    def validate(self, value: float) -> float:
        value = float(value)
        if not self.lower <= value <= self.upper:
            raise ValueError(f"{self.name}={value} is outside bounds")
        return value


@dataclass(frozen=True)
class ScalarProgramProblem:
    """One bounded public parameter and its program factory."""

    parameter: ScalarParameterSpec
    expected_outcome: str
    program_factory: Callable[[float], ExperimentProgram]

    def build(self, value: float) -> ExperimentProgram:
        return self.program_factory(self.parameter.validate(value))


@dataclass(frozen=True)
class ExperimentBudget:
    max_queries: int
    max_shots: int
    max_sequence_time_us: float

    def __post_init__(self) -> None:
        if (
            self.max_queries <= 0
            or self.max_shots <= 0
            or self.max_sequence_time_us <= 0
        ):
            raise ValueError("experiment budget must be positive")


@dataclass(frozen=True)
class BudgetUsage:
    queries: int
    shots: int
    sequence_time_us: float


class PublicExecutor(Protocol):
    def execute(
        self, program: ExperimentProgram, *, shots: int
    ) -> ExperimentResult:
        ...


class BudgetExceededError(RuntimeError):
    pass


class BudgetedExperimentClient:
    """Capability-limited wrapper around a public experiment executor."""

    __slots__ = (
        "_execute_public",
        "_budget",
        "_queries",
        "_shots",
        "_sequence_time_us",
    )

    def __init__(
        self, executor: PublicExecutor, budget: ExperimentBudget
    ) -> None:
        self._execute_public = executor.execute
        self._budget = budget
        self._queries = 0
        self._shots = 0
        self._sequence_time_us = 0.0

    @property
    def usage(self) -> BudgetUsage:
        return BudgetUsage(
            self._queries, self._shots, self._sequence_time_us
        )

    def execute(
        self, program: ExperimentProgram, *, shots: int
    ) -> ExperimentResult:
        if shots <= 0:
            raise ValueError("shots must be positive")
        if self._queries + 1 > self._budget.max_queries:
            raise BudgetExceededError("query budget exceeded")
        if self._shots + shots > self._budget.max_shots:
            raise BudgetExceededError("shot budget exceeded")
        duration_us = sum(
            operation.pulse.duration_us
            if isinstance(operation, Play)
            else operation.duration_us
            if isinstance(operation, (ParallelPlay, Delay))
            else 0.0
            for operation in program.operations
        )
        if (
            self._sequence_time_us + shots * duration_us
            > self._budget.max_sequence_time_us
        ):
            raise BudgetExceededError("sequence-time budget exceeded")
        result = self._execute_public(program, shots=shots)
        proposed_time = (
            self._sequence_time_us + result.resources.total_sequence_time_us
        )
        if proposed_time > self._budget.max_sequence_time_us:
            raise BudgetExceededError("sequence-time budget exceeded")
        self._queries += 1
        self._shots += result.resources.shots
        self._sequence_time_us = proposed_time
        return result


@dataclass(frozen=True)
class ControllerQuery:
    parameter_value: float
    observed_success: float
    execution_id: str
    shots: int


@dataclass(frozen=True)
class ScalarControllerResult:
    selected_value: float
    queries: tuple[ControllerQuery, ...]


class ScalarController(Protocol):
    def optimize(
        self,
        problem: ScalarProgramProblem,
        client: BudgetedExperimentClient,
    ) -> ScalarControllerResult:
        ...


@dataclass(frozen=True)
class FivePointScanController:
    """Minimal finite-shot scan used only for the S4-C interface dry run."""

    grid: tuple[float, ...]
    shots_per_query: int

    def optimize(
        self,
        problem: ScalarProgramProblem,
        client: BudgetedExperimentClient,
    ) -> ScalarControllerResult:
        if len(self.grid) != 5 or self.shots_per_query <= 0:
            raise ValueError("five-point scan requires five values and shots")
        queries = []
        for value in self.grid:
            result = client.execute(
                problem.build(value), shots=self.shots_per_query
            )
            queries.append(
                ControllerQuery(
                    float(value),
                    public_success_probability(
                        result, problem.expected_outcome
                    ),
                    result.execution_id,
                    result.resources.shots,
                )
            )
        best = max(query.observed_success for query in queries)
        tied = [
            query.parameter_value
            for query in queries
            if query.observed_success == best
        ]
        return ScalarControllerResult(sum(tied) / len(tied), tuple(queries))


@dataclass(frozen=True)
class HoldController:
    """Matched-query baseline that repeatedly evaluates the initial point."""

    query_count: int
    shots_per_query: int

    def optimize(
        self,
        problem: ScalarProgramProblem,
        client: BudgetedExperimentClient,
    ) -> ScalarControllerResult:
        if self.query_count <= 0 or self.shots_per_query <= 0:
            raise ValueError("hold controller budget must be positive")
        queries = []
        value = problem.parameter.initial
        for _ in range(self.query_count):
            result = client.execute(
                problem.build(value), shots=self.shots_per_query
            )
            queries.append(
                ControllerQuery(
                    value,
                    public_success_probability(
                        result, problem.expected_outcome
                    ),
                    result.execution_id,
                    result.resources.shots,
                )
            )
        return ScalarControllerResult(value, tuple(queries))
