"""End-to-solution training for fixed and dynamically grown ansatzes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
import resource
import sys
import time
from typing import Any, Literal

import jax
import jax.numpy as jnp
import numpy as np

from vqetape.ansatz import (
    AnsatzOperator,
    AnsatzStructure,
    fixed_rzz_rx_structure,
    local_operator_pool,
    ordered_ansatz_energy,
    ordered_ansatz_state,
)
from vqetape.ansatz_cost import (
    AnsatzCostWeights,
    ansatz_cache_key,
    spatial_boundary_dimension,
)
from vqetape.ansatz_selection import (
    AnsatzCandidateScore,
    rank_ansatz_candidates,
)
from vqetape.ansatz_signals import pool_signals
from vqetape.ground_state import tfim_ground_energy
from vqetape.optimizers import (
    OptimizerUnavailable,
    run_lbfgs,
)
from vqetape.spec import TFIMVQESpec

AnsatzGrowthPolicy = Literal[
    "fixed",
    "gradient-only",
    "contraction-aware",
]


def _peak_rss_bytes() -> int:
    peak = int(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    )
    return peak if sys.platform == "darwin" else peak * 1024


@dataclass(frozen=True)
class AnsatzGrowthRequest:
    """One fixed or adaptive ansatz time-to-target experiment."""

    spec: TFIMVQESpec
    policy: AnsatzGrowthPolicy
    target_energy_error: float
    max_growth_rounds: int
    optimizer_steps_per_round: int
    seed: int = 3
    initial_scale: float = 0.15
    metric_epsilon: float = 1e-10
    cost_weights: AnsatzCostWeights = field(
        default_factory=AnsatzCostWeights
    )
    seed_depth: int = 1
    fixed_depth: int = 2

    def __post_init__(self) -> None:
        if self.policy not in (
            "fixed",
            "gradient-only",
            "contraction-aware",
        ):
            raise ValueError(
                f"unsupported ansatz policy: {self.policy}"
            )
        if (
            self.target_energy_error <= 0
            or not isfinite(self.target_energy_error)
        ):
            raise ValueError(
                "target_energy_error must be finite and "
                "positive"
            )
        if self.max_growth_rounds < 0:
            raise ValueError(
                "max_growth_rounds must be nonnegative"
            )
        if self.optimizer_steps_per_round < 1:
            raise ValueError(
                "optimizer_steps_per_round must be positive"
            )
        if (
            self.initial_scale <= 0
            or not isfinite(self.initial_scale)
        ):
            raise ValueError(
                "initial_scale must be finite and positive"
            )
        if (
            self.metric_epsilon <= 0
            or not isfinite(self.metric_epsilon)
        ):
            raise ValueError(
                "metric_epsilon must be finite and positive"
            )
        if self.seed_depth < 1:
            raise ValueError("seed_depth must be positive")
        if self.fixed_depth < self.seed_depth:
            raise ValueError(
                "fixed_depth cannot be shallower than seed"
            )
        fixed_parameters = (
            self.fixed_depth
            * (2 * self.spec.nqubits - 1)
        )
        adaptive_parameters = (
            self.seed_depth
            * (2 * self.spec.nqubits - 1)
            + self.max_growth_rounds
        )
        if fixed_parameters != adaptive_parameters:
            raise ValueError(
                "fixed and adaptive maximum parameter "
                "budgets must match"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "policy": self.policy,
            "target_energy_error": (
                self.target_energy_error
            ),
            "max_growth_rounds": self.max_growth_rounds,
            "optimizer_steps_per_round": (
                self.optimizer_steps_per_round
            ),
            "seed": self.seed,
            "initial_scale": self.initial_scale,
            "metric_epsilon": self.metric_epsilon,
            "cost_weights": asdict(self.cost_weights),
            "seed_depth": self.seed_depth,
            "fixed_depth": self.fixed_depth,
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> AnsatzGrowthRequest:
        values = dict(payload)
        values["spec"] = TFIMVQESpec.from_dict(
            values["spec"]
        )
        values["cost_weights"] = AnsatzCostWeights(
            **values["cost_weights"]
        )
        return cls(**values)


@dataclass(frozen=True)
class AnsatzGrowthRound:
    """One seed/fixed optimization or adaptive addition."""

    round_index: int
    phase: Literal["fixed", "seed", "growth"]
    structure: AnsatzStructure
    selected_operator: AnsatzOperator | None
    candidates: tuple[AnsatzCandidateScore, ...]
    cache_key: str
    compile_seconds: float
    screening_seconds: float
    optimization_seconds: float
    evaluations: int
    optimizer_steps: int
    optimizer_message: str | None
    energy: float
    energy_error: float
    boundary_dimension: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "phase": self.phase,
            "structure": self.structure.to_dict(),
            "selected_operator": (
                self.selected_operator.to_dict()
                if self.selected_operator is not None
                else None
            ),
            "candidates": [
                item.to_dict() for item in self.candidates
            ],
            "cache_key": self.cache_key,
            "compile_seconds": self.compile_seconds,
            "screening_seconds": self.screening_seconds,
            "optimization_seconds": (
                self.optimization_seconds
            ),
            "evaluations": self.evaluations,
            "optimizer_steps": self.optimizer_steps,
            "optimizer_message": self.optimizer_message,
            "energy": self.energy,
            "energy_error": self.energy_error,
            "boundary_dimension": (
                self.boundary_dimension
            ),
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> AnsatzGrowthRound:
        values = dict(payload)
        values["structure"] = AnsatzStructure.from_dict(
            values["structure"]
        )
        if values["selected_operator"] is not None:
            values["selected_operator"] = (
                AnsatzOperator.from_dict(
                    values["selected_operator"]
                )
            )
        values["candidates"] = tuple(
            AnsatzCandidateScore.from_dict(item)
            for item in values["candidates"]
        )
        return cls(**values)


@dataclass(frozen=True)
class AnsatzGrowthResult:
    """Measured fixed/adaptive ansatz outcome."""

    request: AnsatzGrowthRequest
    converged: bool
    ground_energy: float
    target_energy: float
    final_energy: float
    final_parameters: tuple[float, ...]
    final_structure: AnsatzStructure
    rounds: tuple[AnsatzGrowthRound, ...]
    evaluations: int
    compiled_structures: int
    compile_seconds: float
    screening_seconds: float
    optimization_seconds: float
    time_to_target_seconds: float | None
    total_seconds: float
    peak_rss_bytes: int
    failure: str | None = None
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "converged": self.converged,
            "ground_energy": self.ground_energy,
            "target_energy": self.target_energy,
            "final_energy": self.final_energy,
            "final_parameters": list(
                self.final_parameters
            ),
            "final_structure": (
                self.final_structure.to_dict()
            ),
            "rounds": [
                item.to_dict() for item in self.rounds
            ],
            "evaluations": self.evaluations,
            "compiled_structures": (
                self.compiled_structures
            ),
            "compile_seconds": self.compile_seconds,
            "screening_seconds": self.screening_seconds,
            "optimization_seconds": (
                self.optimization_seconds
            ),
            "time_to_target_seconds": (
                self.time_to_target_seconds
            ),
            "total_seconds": self.total_seconds,
            "peak_rss_bytes": self.peak_rss_bytes,
            "failure": self.failure,
            "skipped": self.skipped,
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> AnsatzGrowthResult:
        values = dict(payload)
        values["request"] = AnsatzGrowthRequest.from_dict(
            values["request"]
        )
        values["final_parameters"] = tuple(
            float(item)
            for item in values["final_parameters"]
        )
        values["final_structure"] = (
            AnsatzStructure.from_dict(
                values["final_structure"]
            )
        )
        values["rounds"] = tuple(
            AnsatzGrowthRound.from_dict(item)
            for item in values["rounds"]
        )
        return cls(**values)


@dataclass
class _RunState:
    started: float
    ground_energy: float
    target_error: float
    time_to_target: float | None = None
    evaluations: int = 0
    compile_seconds: float = 0.0
    screening_seconds: float = 0.0
    optimization_seconds: float = 0.0


def _parameter_dtype(spec: TFIMVQESpec):
    return (
        np.float32
        if spec.dtype == "complex64"
        else np.float64
    )


def _optimize_structure(
    structure: AnsatzStructure,
    initial_parameters: np.ndarray,
    request: AnsatzGrowthRequest,
    state: _RunState,
    phase: Literal["fixed", "seed", "growth"],
    round_index: int,
    selected_operator: AnsatzOperator | None,
    candidates: tuple[AnsatzCandidateScore, ...],
    screening_seconds: float,
) -> tuple[
    np.ndarray,
    AnsatzGrowthRound,
    bool,
    str | None,
]:
    key = ansatz_cache_key(structure, request.spec)
    function = jax.jit(
        jax.value_and_grad(
            lambda parameters: ordered_ansatz_energy(
                parameters,
                structure,
                request.spec,
            )
        )
    )
    compile_started = time.perf_counter()
    compiled = function.lower(
        np.asarray(
            initial_parameters,
            dtype=_parameter_dtype(request.spec),
        )
    ).compile()
    compile_seconds = time.perf_counter() - compile_started
    state.compile_seconds += compile_seconds

    round_evaluations = 0
    final_energy = float("nan")

    def evaluate(
        parameters: np.ndarray,
    ) -> tuple[float, np.ndarray]:
        values = np.asarray(
            parameters,
            dtype=_parameter_dtype(request.spec),
        )
        energy, gradient = compiled(values)
        jax.block_until_ready((energy, gradient))
        return (
            float(np.asarray(energy)),
            np.asarray(gradient),
        )

    def observe(
        evaluation: int,
        optimizer_step: int,
        parameters: np.ndarray,
        energy: float,
        gradient: np.ndarray,
        metric_condition: float | None,
    ) -> bool:
        del (
            evaluation,
            optimizer_step,
            parameters,
            gradient,
            metric_condition,
        )
        nonlocal round_evaluations, final_energy
        round_evaluations += 1
        state.evaluations += 1
        final_energy = float(energy)
        reached = (
            energy - state.ground_energy
            <= state.target_error
        )
        if reached and state.time_to_target is None:
            state.time_to_target = (
                time.perf_counter() - state.started
            )
        return reached

    optimization_started = time.perf_counter()
    try:
        outcome = run_lbfgs(
            initial_parameters,
            evaluate,
            observe,
            max_steps=request.optimizer_steps_per_round,
        )
        optimizer_message = outcome.failure
        parameters = np.asarray(outcome.parameters)
        reached = outcome.target_reached
        optimizer_steps = outcome.steps
        if not reached:
            energy, gradient = evaluate(parameters)
            reached = observe(
                outcome.evaluations + 1,
                outcome.steps,
                parameters,
                energy,
                gradient,
                None,
            )
    except OptimizerUnavailable as exc:
        parameters = np.asarray(initial_parameters)
        reached = False
        optimizer_steps = 0
        optimizer_message = str(exc)
        fatal_failure = str(exc)
        energy, gradient = evaluate(parameters)
        reached = observe(
            1,
            0,
            parameters,
            energy,
            gradient,
            None,
        )
    except (
        FloatingPointError,
        ValueError,
        np.linalg.LinAlgError,
    ) as exc:
        parameters = np.asarray(initial_parameters)
        reached = False
        optimizer_steps = 0
        optimizer_message = (
            f"{type(exc).__name__}: {exc}"
        )
        fatal_failure = optimizer_message
    else:
        fatal_failure = None
    optimization_seconds = (
        time.perf_counter() - optimization_started
    )
    state.optimization_seconds += optimization_seconds
    round_result = AnsatzGrowthRound(
        round_index=round_index,
        phase=phase,
        structure=structure,
        selected_operator=selected_operator,
        candidates=candidates,
        cache_key=key,
        compile_seconds=compile_seconds,
        screening_seconds=screening_seconds,
        optimization_seconds=optimization_seconds,
        evaluations=round_evaluations,
        optimizer_steps=optimizer_steps,
        optimizer_message=optimizer_message,
        energy=final_energy,
        energy_error=final_energy - state.ground_energy,
        boundary_dimension=spatial_boundary_dimension(
            structure
        ),
    )
    return parameters, round_result, reached, fatal_failure


def _screen(
    structure: AnsatzStructure,
    parameters: np.ndarray,
    request: AnsatzGrowthRequest,
) -> tuple[
    tuple[AnsatzCandidateScore, ...],
    float,
]:
    started = time.perf_counter()
    state_function = jax.jit(
        lambda values: ordered_ansatz_state(
            values,
            structure,
            request.spec,
        )
    )
    compiled = state_function.lower(
        np.asarray(
            parameters,
            dtype=_parameter_dtype(request.spec),
        )
    ).compile()
    vector = compiled(
        np.asarray(
            parameters,
            dtype=_parameter_dtype(request.spec),
        )
    )
    jax.block_until_ready(vector)
    signals = pool_signals(
        vector,
        local_operator_pool(request.spec.nqubits),
        request.spec,
        metric_epsilon=request.metric_epsilon,
    )
    policy = (
        "gradient-only"
        if request.policy == "gradient-only"
        else "contraction-aware"
    )
    ranked = rank_ansatz_candidates(
        structure,
        signals,
        policy,
        weights=request.cost_weights,
    )
    return ranked, time.perf_counter() - started


def run_ansatz_growth(
    request: AnsatzGrowthRequest,
) -> AnsatzGrowthResult:
    """Run one fully measured fixed or adaptive ansatz solve."""

    started = time.perf_counter()
    ground_energy = tfim_ground_energy(request.spec)
    state = _RunState(
        started=started,
        ground_energy=ground_energy,
        target_error=request.target_energy_error,
    )
    rng = np.random.default_rng(request.seed)
    seed_structure = fixed_rzz_rx_structure(
        request.spec.nqubits,
        request.seed_depth,
    )
    seed_parameters = rng.normal(
        0.0,
        request.initial_scale,
        size=seed_structure.parameter_count,
    )
    rounds: list[AnsatzGrowthRound] = []
    failure: str | None = None
    skipped = False

    if request.policy == "fixed":
        structure = fixed_rzz_rx_structure(
            request.spec.nqubits,
            request.fixed_depth,
        )
        parameters = np.concatenate(
            (
                seed_parameters,
                np.zeros(
                    structure.parameter_count
                    - seed_structure.parameter_count
                ),
            )
        )
        (
            parameters,
            round_result,
            converged,
            failure,
        ) = _optimize_structure(
            structure,
            parameters,
            request,
            state,
            "fixed",
            0,
            None,
            (),
            0.0,
        )
        rounds.append(round_result)
    else:
        structure = seed_structure
        parameters = seed_parameters
        (
            parameters,
            round_result,
            converged,
            failure,
        ) = _optimize_structure(
            structure,
            parameters,
            request,
            state,
            "seed",
            0,
            None,
            (),
            0.0,
        )
        rounds.append(round_result)
        for round_index in range(
            1,
            request.max_growth_rounds + 1,
        ):
            if converged or failure is not None:
                break
            candidates, screening_seconds = _screen(
                structure,
                parameters,
                request,
            )
            state.screening_seconds += screening_seconds
            selected = candidates[0].operator
            structure = structure.append(selected)
            parameters = np.concatenate(
                (parameters, np.zeros(1))
            )
            (
                parameters,
                round_result,
                converged,
                failure,
            ) = _optimize_structure(
                structure,
                parameters,
                request,
                state,
                "growth",
                round_index,
                selected,
                candidates,
                screening_seconds,
            )
            rounds.append(round_result)

    total_seconds = time.perf_counter() - started
    if failure is not None and "requires" in failure:
        skipped = True
    if not converged and failure is None:
        failure = "target not reached within ansatz budget"
    final_energy = rounds[-1].energy
    return AnsatzGrowthResult(
        request=request,
        converged=converged,
        ground_energy=ground_energy,
        target_energy=(
            ground_energy + request.target_energy_error
        ),
        final_energy=final_energy,
        final_parameters=tuple(
            float(item) for item in parameters
        ),
        final_structure=structure,
        rounds=tuple(rounds),
        evaluations=state.evaluations,
        compiled_structures=len(rounds),
        compile_seconds=state.compile_seconds,
        screening_seconds=state.screening_seconds,
        optimization_seconds=state.optimization_seconds,
        time_to_target_seconds=state.time_to_target,
        total_seconds=total_seconds,
        peak_rss_bytes=_peak_rss_bytes(),
        failure=failure,
        skipped=skipped,
    )
