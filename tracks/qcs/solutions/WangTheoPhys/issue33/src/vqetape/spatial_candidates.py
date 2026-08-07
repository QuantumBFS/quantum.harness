"""Joint search over exact spatial-transfer and global-MPO programs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import sqrt
from typing import Any

import numpy as np

from vqetape.ad_analysis import (
    SpatialDifferentiatedCost,
    analyze_spatial_transfer,
)
from vqetape.benchmark import (
    benchmark_candidate,
    benchmark_spatial_candidate,
    benchmark_tn_candidate,
)
from vqetape.selection import (
    CandidateResult,
    correctness_error,
    pareto_frontier,
    select_for_horizon,
)
from vqetape.spatial_plan import plan_spatial_transfer
from vqetape.spec import (
    CompileRequest,
    CorrectnessTolerance,
    ProgramConfig,
    SpatialProgramConfig,
    TensorProgramConfig,
)
from vqetape.tn_program import PathStrategy, plan_contraction
from vqetape.tn_template import build_mpo_expectation_template
from vqetape.symmetry import z2_symmetry_applicability


@dataclass(frozen=True)
class SpatialSearchResult:
    request: CompileRequest
    selected: CandidateResult
    pareto: tuple[CandidateResult, ...]
    candidates: tuple[CandidateResult, ...]
    reference: CandidateResult

    def to_report(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "selected": self.selected.to_dict(),
            "pareto": [item.to_dict() for item in self.pareto],
            "candidates": [
                item.to_dict() for item in self.candidates
            ],
            "reference": self.reference.to_dict(),
            "measurement_notes": {
                "representations": (
                    "global MPO controls and spatial-transfer candidates "
                    "share one correctness and selection protocol"
                ),
                "peak_rss": "process peak RSS, not GPU peak memory",
                "jax_memory_analysis": (
                    "compiler-reported executable fields when available"
                ),
                "residual_profile": (
                    "byte-accounted values retained by JAX reverse mode; "
                    "this is logical tape size, not liveness-aware peak memory"
                ),
                "modeled_checkpoint_bytes": (
                    "boundary-count model, not measured device peak memory"
                ),
            },
        }


@dataclass(frozen=True)
class RankedSpatialConfig:
    """One spatial configuration and its deterministic AD cost."""

    config: SpatialProgramConfig
    ad_cost: SpatialDifferentiatedCost


def rank_spatial_candidates_by_ad_cost(
    request: CompileRequest,
    candidates: tuple[SpatialProgramConfig, ...],
) -> tuple[RankedSpatialConfig, ...]:
    """Return every candidate sorted by differentiated static cost."""

    ranked = []
    for config in candidates:
        transfer = plan_spatial_transfer(
            request.spec,
            config.path_strategy,
            explicit_paths=config.column_paths,
            block_width=config.block_width,
        )
        ranked.append(
            RankedSpatialConfig(
                config=config,
                ad_cost=analyze_spatial_transfer(transfer),
            )
        )
    ranked.sort(
        key=lambda item: (
            item.ad_cost.static_score,
            item.ad_cost.total_backward_flops,
            item.config.label,
        )
    )
    return tuple(ranked)


def enumerate_spatial_candidates(
    request: CompileRequest,
    strategies: tuple[PathStrategy, ...] = (
        "greedy",
        "random-greedy",
        "auto-hq",
    ),
) -> tuple[SpatialProgramConfig, ...]:
    """Generate deterministic spatial path and adjoint candidates."""

    interior_count = request.spec.nqubits - 2
    candidates: set[SpatialProgramConfig] = set()
    for strategy in strategies:
        max_block_width = max(
            1,
            min(4, interior_count),
        )
        for block_width in range(1, max_block_width + 1):
            transfer = plan_spatial_transfer(
                request.spec,
                strategy,
                block_width=block_width,
            )
            column_paths = tuple(
                program.path
                for program in (
                    transfer.first,
                    transfer.bulk,
                    transfer.tail,
                    transfer.last,
                )
                if program is not None
            )
            if transfer.bulk_block_count == 0:
                for adjoint in ("default", "explicit"):
                    candidates.add(
                        SpatialProgramConfig(
                            strategy,
                            adjoint,
                            unroll=1,
                            block_width=block_width,
                            column_paths=column_paths,
                        )
                    )
                continue

            unrolls = {
                min(raw_unroll, transfer.bulk_block_count)
                for raw_unroll in (1, 2, 4)
            }
            for unroll in unrolls:
                candidates.add(
                    SpatialProgramConfig(
                        strategy,
                        "default",
                        unroll=unroll,
                        block_width=block_width,
                        column_paths=column_paths,
                    )
                )
                candidates.add(
                    SpatialProgramConfig(
                        strategy,
                        "remat",
                        unroll=unroll,
                        block_width=block_width,
                        column_paths=column_paths,
                    )
                )
            for unroll in {
                1,
                max(unrolls),
            }:
                candidates.add(
                    SpatialProgramConfig(
                        strategy,
                        "explicit",
                        unroll=unroll,
                        block_width=block_width,
                        column_paths=column_paths,
                    )
                )
            if block_width != 1:
                continue
            candidates.add(
                SpatialProgramConfig(
                    strategy,
                    "segmented",
                    unroll=1,
                    block_width=block_width,
                    segment_length=max(
                        1,
                        round(
                            sqrt(
                                transfer.bulk_block_count
                            )
                        ),
                    ),
                    column_paths=column_paths,
                )
            )
    return tuple(sorted(candidates, key=lambda item: item.label))


def enumerate_symmetry_candidates(
    request: CompileRequest,
    strategies: tuple[PathStrategy, ...] = (
        "greedy",
        "random-greedy",
        "auto-hq",
    ),
) -> tuple[SpatialProgramConfig, ...]:
    """Generate fixed-path dense/reference/native Z2 triples."""

    applicable, reason = z2_symmetry_applicability(
        request.spec
    )
    if not applicable:
        raise ValueError(
            f"symmetry search is not applicable: {reason}"
        )

    interior_count = request.spec.nqubits - 2
    candidates: set[SpatialProgramConfig] = set()
    for strategy in strategies:
        max_block_width = max(
            1,
            min(4, interior_count),
        )
        for block_width in range(
            1,
            max_block_width + 1,
        ):
            transfer = plan_spatial_transfer(
                request.spec,
                strategy,
                block_width=block_width,
            )
            column_paths = tuple(
                program.path
                for program in (
                    transfer.first,
                    transfer.bulk,
                    transfer.tail,
                    transfer.last,
                )
                if program is not None
            )
            unrolls = {1}
            if transfer.bulk_block_count:
                unrolls.add(
                    min(
                        4,
                        transfer.bulk_block_count,
                    )
                )
            for unroll in unrolls:
                for symmetry in (
                    "none",
                    "z2-reference",
                    "z2-native",
                ):
                    candidates.add(
                        SpatialProgramConfig(
                            strategy,
                            "default",
                            unroll=unroll,
                            block_width=block_width,
                            symmetry=symmetry,
                            column_paths=column_paths,
                        )
                    )
    return tuple(
        sorted(candidates, key=lambda item: item.label)
    )


def _validate(
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
                f"energy={energy_error:.6g}, "
                f"gradient={gradient_error:.6g}"
            )
        ),
    )


def _global_mpo_configs(
    request: CompileRequest,
    strategies: tuple[PathStrategy, ...],
) -> tuple[TensorProgramConfig, ...]:
    template = build_mpo_expectation_template(
        request.spec,
        gate_representation="dense",
    )
    configs = []
    for strategy in strategies:
        program = plan_contraction(template, strategy)
        configs.append(
            TensorProgramConfig(
                strategy,
                "none",
                path=program.path,
                gate_representation="dense",
                hamiltonian_representation="mpo",
            )
        )
    return tuple(configs)


def search_spatial_candidates(
    request: CompileRequest,
    strategies: tuple[PathStrategy, ...] = (
        "greedy",
        "random-greedy",
        "auto-hq",
    ),
) -> SpatialSearchResult:
    """Benchmark and select across spatial and global exact MPO programs."""

    reference = benchmark_candidate(
        spec=request.spec,
        config=ProgramConfig("unrolled", "default"),
        seed=request.seed,
        warm_repeats=request.warm_repeats,
        timeout_seconds=request.timeout_seconds,
    )
    if not reference.valid:
        raise RuntimeError(
            f"state-vector reference failed: {reference.failure}"
        )
    tolerance = CorrectnessTolerance.for_dtype(request.spec.dtype)
    measured: list[CandidateResult] = []
    for config in _global_mpo_configs(request, strategies):
        measured.append(
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
        )
    for config in enumerate_spatial_candidates(request, strategies):
        measured.append(
            _validate(
                benchmark_spatial_candidate(
                    spec=request.spec,
                    config=config,
                    seed=request.seed,
                    warm_repeats=request.warm_repeats,
                    timeout_seconds=request.timeout_seconds,
                ),
                reference,
                tolerance,
            )
        )

    measured.sort(key=lambda item: item.config.label)
    frontier = pareto_frontier(
        measured,
        memory_budget_bytes=request.memory_budget_bytes,
    )
    selected = select_for_horizon(
        measured,
        request.expected_vqe_steps,
        request.memory_budget_bytes,
    )
    return SpatialSearchResult(
        request=request,
        selected=selected,
        pareto=tuple(frontier),
        candidates=tuple(measured),
        reference=reference,
    )


def search_symmetry_candidates(
    request: CompileRequest,
    strategies: tuple[PathStrategy, ...] = (
        "greedy",
        "random-greedy",
        "auto-hq",
    ),
) -> SpatialSearchResult:
    """Benchmark exact dense/reference/native symmetry triples."""

    reference = benchmark_candidate(
        spec=request.spec,
        config=ProgramConfig("unrolled", "default"),
        seed=request.seed,
        warm_repeats=request.warm_repeats,
        timeout_seconds=request.timeout_seconds,
    )
    if not reference.valid:
        raise RuntimeError(
            f"state-vector reference failed: {reference.failure}"
        )
    tolerance = CorrectnessTolerance.for_dtype(
        request.spec.dtype
    )
    measured: list[CandidateResult] = []
    for config in _global_mpo_configs(request, strategies):
        measured.append(
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
        )
    for config in enumerate_symmetry_candidates(
        request,
        strategies,
    ):
        measured.append(
            _validate(
                benchmark_spatial_candidate(
                    spec=request.spec,
                    config=config,
                    seed=request.seed,
                    warm_repeats=request.warm_repeats,
                    timeout_seconds=request.timeout_seconds,
                ),
                reference,
                tolerance,
            )
        )

    measured.sort(key=lambda item: item.config.label)
    frontier = pareto_frontier(
        measured,
        memory_budget_bytes=request.memory_budget_bytes,
    )
    selected = select_for_horizon(
        measured,
        request.expected_vqe_steps,
        request.memory_budget_bytes,
    )
    return SpatialSearchResult(
        request=request,
        selected=selected,
        pareto=tuple(frontier),
        candidates=tuple(measured),
        reference=reference,
    )
