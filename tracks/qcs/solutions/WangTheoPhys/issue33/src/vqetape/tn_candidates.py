"""Candidate generation and fresh-process search for direct-TN programs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from vqetape.benchmark import benchmark_candidate, benchmark_tn_candidate
from vqetape.selection import (
    CandidateResult,
    correctness_error,
    pareto_frontier,
    select_for_horizon,
)
from vqetape.spec import (
    CompileRequest,
    CorrectnessTolerance,
    GateRepresentation,
    HamiltonianRepresentation,
    ProgramConfig,
    TensorProgramConfig,
)
from vqetape.tn_program import ContractionProgram, PathStrategy, plan_contraction
from vqetape.tn_template import (
    build_expectation_template,
    build_mpo_expectation_template,
)


@dataclass(frozen=True)
class TensorSearchResult:
    request: CompileRequest
    selected: CandidateResult
    pareto: tuple[CandidateResult, ...]
    candidates: tuple[CandidateResult, ...]

    def to_report(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "selected": self.selected.to_dict(),
            "pareto": [item.to_dict() for item in self.pareto],
            "candidates": [item.to_dict() for item in self.candidates],
            "measurement_notes": {
                "peak_rss": "process peak RSS, not GPU peak memory",
                "jax_memory_analysis": (
                    "compiler-reported executable fields when available"
                ),
                "residual_profile": (
                    "byte-accounted values retained by JAX reverse mode; "
                    "this is logical tape size, not liveness-aware peak memory"
                ),
            },
        }


def _budgeted_contraction_names(
    program: ContractionProgram,
    fractions: tuple[float, ...] = (0.0, 0.5, 1.0),
) -> tuple[tuple[str, ...], ...]:
    """Choose largest-first named contraction tapes at several byte budgets."""

    step_bytes = tuple(enumerate(program.step_output_bytes))
    if not step_bytes:
        return ((),)
    ranked = sorted(step_bytes, key=lambda item: (-item[1], item[0]))
    total_bytes = sum(program.step_output_bytes)
    choices: set[tuple[str, ...]] = set()
    for fraction in fractions:
        if fraction < 0 or fraction > 1:
            raise ValueError("tape budget fractions must lie in [0, 1]")
        budget = int(total_bytes * fraction)
        used = 0
        saved: list[str] = []
        for step_index, byte_count in ranked:
            if used + byte_count <= budget:
                base = (
                    f"contract:{step_index}:"
                    f"elements{program.steps[step_index].output_elements}"
                )
                saved.extend((f"{base}:real", f"{base}:imag"))
                used += byte_count
        choices.add(tuple(sorted(saved)))
    return tuple(sorted(choices, key=lambda names: (len(names), names)))


def enumerate_tn_candidates(
    request: CompileRequest,
    strategies: tuple[PathStrategy, ...] = (
        "greedy",
        "random-greedy",
        "auto-hq",
    ),
    gate_representations: tuple[GateRepresentation, ...] = ("dense",),
    hamiltonian_representations: tuple[HamiltonianRepresentation, ...] = (
        "pauli_sum",
        "mpo",
    ),
) -> tuple[TensorProgramConfig, ...]:
    """Generate joint Hamiltonian, path, and named-tape candidates."""

    candidates: set[TensorProgramConfig] = set()
    for gate_representation in gate_representations:
        for hamiltonian_representation in hamiltonian_representations:
            template = (
                build_expectation_template(
                    request.spec,
                    gate_representation=gate_representation,
                )
                if hamiltonian_representation == "pauli_sum"
                else build_mpo_expectation_template(
                    request.spec,
                    gate_representation=gate_representation,
                )
            )
            for strategy in strategies:
                program = plan_contraction(template, strategy)
                candidates.add(
                    TensorProgramConfig(
                        strategy,
                        "none",
                        path=program.path,
                        gate_representation=gate_representation,
                        hamiltonian_representation=(
                            hamiltonian_representation
                        ),
                    )
                )
                for save_names in _budgeted_contraction_names(program):
                    candidates.add(
                        TensorProgramConfig(
                            strategy,
                            "named",
                            path=program.path,
                            save_names=save_names,
                            gate_representation=gate_representation,
                            hamiltonian_representation=(
                                hamiltonian_representation
                            ),
                        )
                    )
    return tuple(sorted(candidates, key=lambda item: item.label))


def _validate(
    candidate: CandidateResult,
    reference: CandidateResult,
    tolerance: CorrectnessTolerance,
) -> CandidateResult:
    if not candidate.valid:
        return candidate
    if candidate.energy is None or candidate.gradient is None:
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
    valid = bool(
        np.isfinite(energy_error)
        and np.isfinite(gradient_error)
        and energy_error <= tolerance.energy_atol
        and gradient_error <= tolerance.gradient_rtol
    )
    return replace(
        candidate,
        energy_abs_error=energy_error,
        gradient_relative_l2_error=gradient_error,
        valid=valid,
        failure=(
            None
            if valid
            else (
                "correctness tolerance exceeded: "
                f"energy={energy_error:.6g}, gradient={gradient_error:.6g}"
            )
        ),
    )


def search_tn_candidates(
    request: CompileRequest,
    strategies: tuple[PathStrategy, ...] = (
        "greedy",
        "random-greedy",
        "auto-hq",
    ),
) -> TensorSearchResult:
    """Benchmark and validate a complete direct-TN candidate set."""

    reference = benchmark_candidate(
        spec=request.spec,
        config=ProgramConfig("unrolled", "default"),
        seed=request.seed,
        warm_repeats=request.warm_repeats,
        timeout_seconds=request.timeout_seconds,
    )
    if not reference.valid:
        raise RuntimeError(f"state-vector reference failed: {reference.failure}")
    tolerance = CorrectnessTolerance.for_dtype(request.spec.dtype)
    measured = [
        _validate(
            benchmark_tn_candidate(
                spec=request.spec,
                config=config,
                seed=request.seed,
                warm_repeats=request.warm_repeats,
                timeout_seconds=request.timeout_seconds,
            ),
            reference,
            tolerance,
        )
        for config in enumerate_tn_candidates(request, strategies)
    ]
    frontier = pareto_frontier(
        measured,
        memory_budget_bytes=request.memory_budget_bytes,
    )
    selected = select_for_horizon(
        measured,
        request.expected_vqe_steps,
        request.memory_budget_bytes,
    )
    return TensorSearchResult(
        request=request,
        selected=selected,
        pareto=tuple(frontier),
        candidates=tuple(measured),
    )
