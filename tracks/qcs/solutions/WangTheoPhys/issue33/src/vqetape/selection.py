"""Correctness checks and multi-objective candidate selection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import inf, isfinite
from typing import Any

import numpy as np

from vqetape.spec import (
    ProgramConfig,
    SpatialProgramConfig,
    TensorProgramConfig,
)


@dataclass(frozen=True)
class CandidateResult:
    config: ProgramConfig | TensorProgramConfig | SpatialProgramConfig
    compile_seconds: float = inf
    first_execute_seconds: float = inf
    warm_seconds_median: float = inf
    warm_seconds_mad: float = inf
    peak_rss_bytes: int = 0
    energy_abs_error: float = inf
    gradient_relative_l2_error: float = inf
    valid: bool = False
    failure: str | None = None
    worker_pid: int | None = None
    parent_pid: int | None = None
    energy: float | None = None
    gradient: list[Any] | None = None
    jax_memory_analysis: dict[str, int | float | None] = field(default_factory=dict)
    static_estimate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["config"] = self.config.to_dict()
        for name in (
            "compile_seconds",
            "first_execute_seconds",
            "warm_seconds_median",
            "warm_seconds_mad",
            "energy_abs_error",
            "gradient_relative_l2_error",
        ):
            if not isfinite(payload[name]):
                payload[name] = None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CandidateResult:
        values = dict(payload)
        config_payload = values["config"]
        if config_payload.get("representation") == "direct_tn":
            values["config"] = TensorProgramConfig.from_dict(config_payload)
        elif config_payload.get("representation") == "spatial_transfer":
            values["config"] = SpatialProgramConfig.from_dict(config_payload)
        else:
            values["config"] = ProgramConfig.from_dict(config_payload)
        for name in (
            "compile_seconds",
            "first_execute_seconds",
            "warm_seconds_median",
            "warm_seconds_mad",
            "energy_abs_error",
            "gradient_relative_l2_error",
        ):
            if values.get(name) is None:
                values[name] = inf
        return cls(**values)


def correctness_error(
    energy: Any,
    gradient: Any,
    reference_energy: Any,
    reference_gradient: Any,
) -> tuple[float, float]:
    """Return absolute energy and normalized gradient L2 errors."""

    energy_value = np.asarray(energy)
    gradient_value = np.asarray(gradient)
    reference_energy_value = np.asarray(reference_energy)
    reference_gradient_value = np.asarray(reference_gradient)

    energy_error = float(np.abs(energy_value - reference_energy_value))
    numerator = float(np.linalg.norm(gradient_value - reference_gradient_value))
    denominator = max(1.0, float(np.linalg.norm(reference_gradient_value)))
    return energy_error, numerator / denominator


def _dominates(left: CandidateResult, right: CandidateResult) -> bool:
    left_metrics = (
        left.compile_seconds,
        left.warm_seconds_median,
        left.peak_rss_bytes,
    )
    right_metrics = (
        right.compile_seconds,
        right.warm_seconds_median,
        right.peak_rss_bytes,
    )
    return all(a <= b for a, b in zip(left_metrics, right_metrics, strict=True)) and any(
        a < b for a, b in zip(left_metrics, right_metrics, strict=True)
    )


def pareto_frontier(
    candidates: list[CandidateResult] | tuple[CandidateResult, ...],
    memory_budget_bytes: int | None = None,
) -> list[CandidateResult]:
    """Return valid nondominated candidates in deterministic label order."""

    valid = [
        candidate
        for candidate in candidates
        if candidate.valid
        and isfinite(candidate.compile_seconds)
        and isfinite(candidate.warm_seconds_median)
        and candidate.peak_rss_bytes > 0
        and (
            memory_budget_bytes is None
            or candidate.peak_rss_bytes <= memory_budget_bytes
        )
    ]
    frontier = [
        candidate
        for candidate in valid
        if not any(
            other is not candidate and _dominates(other, candidate)
            for other in valid
        )
    ]
    return sorted(frontier, key=lambda candidate: candidate.config.label)


def select_for_horizon(
    candidates: list[CandidateResult] | tuple[CandidateResult, ...],
    expected_vqe_steps: int,
    memory_budget_bytes: int | None = None,
) -> CandidateResult:
    """Select minimum compile-plus-warm-horizon cost from the frontier."""

    if expected_vqe_steps < 1:
        raise ValueError("expected_vqe_steps must be positive")
    frontier = pareto_frontier(candidates, memory_budget_bytes)
    if not frontier:
        raise ValueError("no valid candidate satisfies the constraints")
    return min(
        frontier,
        key=lambda candidate: (
            candidate.compile_seconds
            + expected_vqe_steps * candidate.warm_seconds_median,
            candidate.peak_rss_bytes,
            candidate.config.label,
        ),
    )
