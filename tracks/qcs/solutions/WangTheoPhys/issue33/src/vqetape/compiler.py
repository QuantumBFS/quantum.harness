"""End-to-end VQETape prototype compiler orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from vqetape.benchmark import benchmark_candidate
from vqetape.candidates import enumerate_candidates
from vqetape.programs import ValueAndGradFunction, build_value_and_grad
from vqetape.selection import (
    CandidateResult,
    correctness_error,
    pareto_frontier,
    select_for_horizon,
)
from vqetape.spec import CompileRequest, CorrectnessTolerance, ProgramConfig


@dataclass(frozen=True)
class CompileResult:
    request: CompileRequest
    selected: CandidateResult
    pareto: tuple[CandidateResult, ...]
    candidates: tuple[CandidateResult, ...]
    executable: ValueAndGradFunction

    def to_report(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "selected": self.selected.to_dict(),
            "pareto": [candidate.to_dict() for candidate in self.pareto],
            "candidates": [
                candidate.to_dict() for candidate in self.candidates
            ],
            "measurement_notes": {
                "compile_seconds": (
                    "JAX lowering plus compilation in a fresh worker process"
                ),
                "first_execute_seconds": (
                    "first synchronized execution after explicit compilation"
                ),
                "warm_seconds": (
                    "median and MAD of synchronized repeated executions"
                ),
                "peak_rss": "process peak RSS, not GPU peak memory",
                "jax_memory_analysis": (
                    "compiler-reported executable fields when available"
                ),
            },
        }


def _measure(
    request: CompileRequest,
    config: ProgramConfig,
) -> CandidateResult:
    return benchmark_candidate(
        spec=request.spec,
        config=config,
        seed=request.seed,
        warm_repeats=request.warm_repeats,
        timeout_seconds=request.timeout_seconds,
    )


def _validate_candidate(
    candidate: CandidateResult,
    reference: CandidateResult,
    tolerance: CorrectnessTolerance,
) -> CandidateResult:
    if not candidate.valid:
        return candidate
    if (
        candidate.energy is None
        or candidate.gradient is None
        or reference.energy is None
        or reference.gradient is None
    ):
        return replace(
            candidate,
            valid=False,
            failure="worker result did not contain energy and gradient",
        )
    energy_error, gradient_error = correctness_error(
        candidate.energy,
        candidate.gradient,
        reference.energy,
        reference.gradient,
    )
    finite = np.isfinite(energy_error) and np.isfinite(gradient_error)
    within_tolerance = (
        energy_error <= tolerance.energy_atol
        and gradient_error <= tolerance.gradient_rtol
    )
    failure = candidate.failure
    if not finite:
        failure = "candidate produced non-finite correctness error"
    elif not within_tolerance:
        failure = (
            "correctness tolerance exceeded: "
            f"energy={energy_error:.6g}, gradient={gradient_error:.6g}"
        )
    return replace(
        candidate,
        energy_abs_error=energy_error,
        gradient_relative_l2_error=gradient_error,
        valid=bool(finite and within_tolerance),
        failure=failure,
    )


def compile_vqe(request: CompileRequest) -> CompileResult:
    """Benchmark, validate, select, and rebuild one VQE executable."""

    configs = enumerate_candidates(request)
    reference_config = ProgramConfig(
        control_flow="unrolled",
        adjoint="default",
        unroll=1,
    )
    if reference_config not in configs:
        raise ValueError(
            "memory budget excludes the unrolled correctness reference"
        )

    reference = _measure(request, reference_config)
    if not reference.valid:
        raise RuntimeError(
            f"correctness reference failed: {reference.failure}"
        )
    reference = replace(
        reference,
        energy_abs_error=0.0,
        gradient_relative_l2_error=0.0,
    )
    tolerance = CorrectnessTolerance.for_dtype(request.spec.dtype)
    measured = [reference]
    for config in configs:
        if config == reference_config:
            continue
        measured.append(
            _validate_candidate(
                _measure(request, config),
                reference,
                tolerance,
            )
        )

    frontier = pareto_frontier(
        measured,
        memory_budget_bytes=request.memory_budget_bytes,
    )
    selected = select_for_horizon(
        measured,
        expected_vqe_steps=request.expected_vqe_steps,
        memory_budget_bytes=request.memory_budget_bytes,
    )
    executable = build_value_and_grad(request.spec, selected.config)
    return CompileResult(
        request=request,
        selected=selected,
        pareto=tuple(frontier),
        candidates=tuple(measured),
        executable=executable,
    )
