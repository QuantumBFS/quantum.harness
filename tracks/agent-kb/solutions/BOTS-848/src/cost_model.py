"""Cost accounting for DFPT with sparse or dense higher-level corrections."""

from __future__ import annotations

import math
from numbers import Number


def _positive_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _nonnegative_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _cost(value: object, name: str, *, strictly_positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Number):
        raise ValueError(f"{name} must be a finite real cost")
    numeric = complex(value)
    if numeric.imag != 0.0 or not math.isfinite(numeric.real):
        raise ValueError(f"{name} must be a finite real cost")
    if numeric.real < 0.0 or (strictly_positive and numeric.real == 0.0):
        qualifier = "positive" if strictly_positive else "nonnegative"
        raise ValueError(f"{name} must be {qualifier}")
    return float(numeric.real)


def compare_corrected_to_baselines(
    *,
    full_points: int,
    dfpt_cost_per_point: Number,
    high_level_anchors: int,
    high_level_cost_per_point: Number,
    inference_cost_per_point: Number = 0.0,
    training_cost: Number = 0.0,
    campaigns: int = 1,
) -> dict[str, float | bool]:
    """Compare an executable correction path with DFPT and dense references."""

    full_count = _positive_integer(full_points, "full_points")
    campaign_count = _positive_integer(campaigns, "campaigns")
    high_level_count = _positive_integer(high_level_anchors, "high_level_anchors")
    if high_level_count > full_count:
        raise ValueError("high_level_anchors cannot exceed full_points")

    dfpt_cost = _cost(dfpt_cost_per_point, "dfpt_cost_per_point", strictly_positive=True)
    inference_cost = _cost(inference_cost_per_point, "inference_cost_per_point")
    reference_cost = _cost(high_level_cost_per_point, "high_level_cost_per_point")
    one_time_training_cost = _cost(training_cost, "training_cost")

    dfpt_only_cost = campaign_count * full_count * dfpt_cost
    dense_high_level_cost = campaign_count * full_count * (dfpt_cost + reference_cost)
    corrected_cost_per_campaign = full_count * (dfpt_cost + inference_cost)
    corrected_cost = (
        one_time_training_cost
        + high_level_count * reference_cost
        + campaign_count * corrected_cost_per_campaign
    )
    return {
        "dfpt_only_cost": dfpt_only_cost,
        "dense_high_level_cost": dense_high_level_cost,
        "corrected_cost": corrected_cost,
        "speedup_vs_dense_high_level": dense_high_level_cost / corrected_cost,
        "is_faster_than_dense_high_level": corrected_cost < dense_high_level_cost,
        "is_faster_than_dfpt": corrected_cost < dfpt_only_cost,
        "overhead_vs_dfpt": corrected_cost - dfpt_only_cost,
    }
