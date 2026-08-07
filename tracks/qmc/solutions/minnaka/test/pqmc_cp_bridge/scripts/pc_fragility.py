#!/usr/bin/env python3
"""Reference-free population-control genealogy diagnostics."""

from __future__ import annotations

import math
import statistics
from typing import Mapping, Sequence


def comb_parent_indices(
    weights: Sequence[float], u0: float
) -> tuple[list[int], list[int]]:
    if not weights or not (0.0 <= u0 < 1.0):
        raise ValueError("combing requires weights and u0 in [0,1)")
    values = [float(value) for value in weights]
    if not all(math.isfinite(value) and value >= 0.0 for value in values):
        raise ValueError("combing weights must be finite and nonnegative")
    total = math.fsum(values)
    if total <= 0.0:
        raise ValueError("combing total weight vanishes")
    scale = len(values) / total
    cumulative = []
    running = 0.0
    for value in values:
        running += value * scale
        cumulative.append(running)
    parent = 0
    parents: list[int] = []
    for child in range(len(values)):
        target = u0 + child
        while parent < len(values) - 1 and cumulative[parent] <= target:
            parent += 1
        parents.append(parent)
    offspring = [parents.count(index) for index in range(len(values))]
    return parents, offspring


def propagate_immutable_tags(
    tags: Sequence[bool], parent_indices: Sequence[int]
) -> list[bool]:
    if any(parent < 0 or parent >= len(tags) for parent in parent_indices):
        raise ValueError("population parent index out of range")
    return [bool(tags[parent]) for parent in parent_indices]


def lineage_fragility(
    interval_log_a: Mapping[int, Sequence[float]],
    descendant_counts: Mapping[int, int],
) -> dict[int, dict[str, float | int | None]]:
    result: dict[int, dict[str, float | int | None]] = {}
    for lineage, values_raw in interval_log_a.items():
        values = [float(value) for value in values_raw]
        if not values or not all(math.isfinite(value) for value in values):
            raise ValueError("lineage intervals must be finite and nonempty")
        negative = [value for value in values if value < 0.0]
        first_negative = next(
            (index for index, value in enumerate(values) if value < 0.0),
            None,
        )
        descendants = int(descendant_counts.get(lineage, 0))
        minimum_index = min(range(len(values)), key=values.__getitem__)
        if descendants > 0 and minimum_index + 1 < len(values):
            recovery = max(values[minimum_index + 1:]) - values[minimum_index]
            recovery = max(0.0, recovery)
        else:
            recovery = 0.0
        negative_sum = math.fsum(negative)
        result[lineage] = {
            "min_log_a": min(values),
            "first_interval_log_a_lt_0": first_negative,
            "count_log_a_lt_0": len(negative),
            "sum_min_0_log_a": negative_sum,
            "retention_proxy": math.exp(negative_sum),
            "largest_recovery_after_valley": recovery,
            "descendant_survival": 1 if descendants > 0 else 0,
            "descendant_count": descendants,
        }
    return result


def freeze_growth_reference(
    log_mean_weights: Sequence[Sequence[float]],
    delta_s_ref: Sequence[Sequence[float]],
) -> list[float]:
    if not log_mean_weights or len(log_mean_weights) != len(delta_s_ref):
        raise ValueError("growth reference needs paired training systems")
    lengths = {len(values) for values in log_mean_weights}
    lengths.update(len(values) for values in delta_s_ref)
    if len(lengths) != 1:
        raise ValueError("growth-reference interval lengths differ")
    intervals = lengths.pop()
    return [
        statistics.median(
            float(log_mean_weights[system][interval])
            - float(delta_s_ref[system][interval])
            for system in range(len(log_mean_weights))
        )
        for interval in range(intervals)
    ]


def static_fragility(
    logw_phys_at_boundaries: Sequence[float],
    growth_reference: Sequence[float],
) -> dict[str, float | int]:
    if len(logw_phys_at_boundaries) != len(growth_reference) + 1:
        raise ValueError("static fragility needs one more boundary than intervals")
    increments = [
        float(right) - float(left)
        for left, right in zip(
            logw_phys_at_boundaries, logw_phys_at_boundaries[1:]
        )
    ]
    values = [
        increment - float(reference)
        for increment, reference in zip(increments, growth_reference)
    ]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("static fragility contains non-finite values")
    minimum_index = min(range(len(values)), key=values.__getitem__)
    recovery = (
        max(values[minimum_index + 1:]) - values[minimum_index]
        if minimum_index + 1 < len(values)
        else 0.0
    )
    return {
        "min_log_a_static": values[minimum_index],
        "min_interval": minimum_index,
        "recovery_after_valley": max(0.0, recovery),
    }


def assign_complete_stratum(
    *,
    support: str,
    proposal_low: bool,
    prefix_high: bool,
    pc_fragile: bool,
) -> str:
    if support == "dead":
        return "dead_support"
    if support != "alive":
        return "ambiguous_support"
    if proposal_low:
        return "alive_low_final_q"
    if prefix_high:
        return "alive_deep_prefix_not_low_q"
    if pc_fragile:
        return "alive_pc_fragile_not_previous"
    return "alive_regular"
