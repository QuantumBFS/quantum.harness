"""Deterministic first-prototype candidate generation."""

from __future__ import annotations

from math import ceil, floor, sqrt

from vqetape.estimate import estimate_program
from vqetape.spec import CompileRequest, ProgramConfig


def segment_lengths(depth: int) -> tuple[int, ...]:
    """Return endpoints, divisors, and checkpoint lengths near sqrt(depth)."""

    if depth < 1:
        raise ValueError("depth must be positive")
    values = {1, depth, floor(sqrt(depth)), ceil(sqrt(depth))}
    for candidate in range(1, floor(sqrt(depth)) + 1):
        if depth % candidate == 0:
            values.add(candidate)
            values.add(depth // candidate)
    return tuple(sorted(value for value in values if 1 <= value <= depth))


def _unroll_factors(depth: int) -> tuple[int, ...]:
    return tuple(sorted({1, min(2, depth), min(4, depth)}))


def enumerate_candidates(request: CompileRequest) -> tuple[ProgramConfig, ...]:
    """Enumerate unique statically memory-feasible prototype programs."""

    candidates: set[ProgramConfig] = {
        ProgramConfig(control_flow="unrolled", adjoint="default", unroll=1)
    }
    for unroll in _unroll_factors(request.spec.depth):
        candidates.add(
            ProgramConfig(
                control_flow="scan",
                adjoint="default",
                unroll=unroll,
            )
        )
        candidates.add(
            ProgramConfig(
                control_flow="scan",
                adjoint="remat",
                unroll=unroll,
            )
        )
        for segment_length in segment_lengths(request.spec.depth):
            candidates.add(
                ProgramConfig(
                    control_flow="scan",
                    adjoint="segmented",
                    unroll=unroll,
                    segment_length=segment_length,
                )
            )

    feasible = [
        config
        for config in candidates
        if estimate_program(
            request.spec,
            config,
        ).saved_boundary_upper_bound_bytes
        <= request.memory_budget_bytes
    ]
    return tuple(sorted(feasible, key=lambda config: config.label))
