"""Numerical-only ensemble-budget gate for the stochastic two-mode solver."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _relative_change(left: float, right: float) -> float:
    return abs(float(right) - float(left)) / max(abs(float(right)), 1e-30)


def audit_ensemble_budget(
    summaries: Sequence[Mapping[str, Any]],
    *,
    relative_tolerance: float,
    conservation_tolerance: float,
    variance_tolerance: float = 0.02,
    skewness_tolerance: float = 0.05,
    screening_minimum: int = 512,
    final_minimum: int = 2048,
) -> dict[str, Any]:
    """Select screening/final budgets using only solver convergence metrics."""

    if len(summaries) < 2:
        raise ValueError("at least two ensemble summaries are required")
    if min(
        relative_tolerance,
        conservation_tolerance,
        variance_tolerance,
        skewness_tolerance,
    ) <= 0:
        raise ValueError("budget tolerances must be positive")
    ordered = sorted((dict(item) for item in summaries), key=lambda x: int(x["n_ensemble"]))
    counts = [int(item["n_ensemble"]) for item in ordered]
    if len(counts) != len(set(counts)):
        raise ValueError("ensemble counts must be unique")
    comparisons: list[dict[str, Any]] = []
    for previous, current in zip(ordered, ordered[1:]):
        changes = {
            key: _relative_change(previous[key], current[key])
            for key in ("m_variance", "phi_variance")
        }
        comparisons.append(
            {
                "from": int(previous["n_ensemble"]),
                "to": int(current["n_ensemble"]),
                "relative_changes": changes,
                "maximum_relative_change": max(changes.values()),
                "converged": max(changes.values()) <= relative_tolerance,
            }
        )
    screening_candidates = [
        item
        for item in comparisons
        if item["to"] >= screening_minimum and item["converged"]
    ]
    screening = (
        int(screening_candidates[0]["to"]) if screening_candidates else None
    )
    final_comparison = comparisons[-1]
    final_summary = ordered[-1]
    final_numerical_pass = (
        counts[-1] >= final_minimum
        and bool(final_comparison["converged"])
        and float(final_summary["m_variance_relative_error"])
        <= variance_tolerance
        and float(final_summary["phi_variance_relative_error"])
        <= variance_tolerance
        and float(final_summary["max_conservation_error"])
        <= conservation_tolerance
        and abs(float(final_summary["magnetization_current_skewness"]))
        <= skewness_tolerance
    )
    return {
        "status": "pass" if screening is not None and final_numerical_pass else "blocked",
        "screening_ensemble": screening,
        "final_ensemble": counts[-1] if final_numerical_pass else None,
        "requires_extended_budget": (
            counts[-1] >= final_minimum and not final_numerical_pass
        ),
        "comparisons": comparisons,
        "final_checks": {
            "minimum_final_ensemble": counts[-1] >= final_minimum,
            "observable_convergence": bool(final_comparison["converged"]),
            "m_variance": float(final_summary["m_variance_relative_error"])
            <= variance_tolerance,
            "phi_variance": float(final_summary["phi_variance_relative_error"])
            <= variance_tolerance,
            "conservation": float(final_summary["max_conservation_error"])
            <= conservation_tolerance,
            "current_skewness": abs(
                float(final_summary["magnetization_current_skewness"])
            )
            <= skewness_tolerance,
        },
    }
