from __future__ import annotations

from dataclasses import dataclass
import math
import sys
from typing import Iterator

import numpy as np

from .kernel import periodic_kernel
from .model import ModelSpec, iter_unordered_edges
from .union_find import UnionFind

# log_rate = log(kappa) + log(J) branch thresholds (float64).
#
# exp(log_rate) overflows when log_rate exceeds LOG_RATE_EXP_OVERFLOW.
LOG_RATE_EXP_OVERFLOW = math.log(sys.float_info.max)


def _compute_open_saturation_log_rate() -> float:
    lo = math.log(-math.log(sys.float_info.min))
    hi = 7.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if math.exp(-math.exp(mid)) == 0.0:
            hi = mid
        else:
            lo = mid
    return hi


def _compute_exp_underflow_log_rate() -> float:
    lo = -750.0
    hi = -700.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if math.exp(mid) == 0.0:
            lo = mid
        else:
            hi = mid
    return lo


# exp(-exp(log_rate)) underflows to 0.0 once log_rate reaches this value.
LOG_RATE_OPEN_SATURATION = _compute_open_saturation_log_rate()

# exp(log_rate) underflows to 0.0 at or below this value.
LOG_RATE_EXP_UNDERFLOW = _compute_exp_underflow_log_rate()


@dataclass(frozen=True)
class GraphOutcome:
    mask: int
    probability: float
    open_edges: int
    component_sizes: tuple[int, ...]


def _log_open_edge_weight(log_rate: float) -> float:
    if log_rate <= LOG_RATE_EXP_UNDERFLOW:
        return log_rate
    if log_rate >= LOG_RATE_OPEN_SATURATION:
        return 0.0
    rate = math.exp(log_rate)
    if rate == 0.0:
        return log_rate
    neg_rate_exp = math.exp(-rate)
    if neg_rate_exp == 0.0:
        return 0.0
    if neg_rate_exp == 1.0:
        complement = -math.expm1(-rate)
        if complement == 0.0:
            return log_rate
        return math.log(complement)
    return math.log1p(-neg_rate_exp)


def _log_closed_edge_weight(log_rate: float) -> float:
    if log_rate > LOG_RATE_EXP_OVERFLOW:
        return -math.inf
    rate = math.exp(log_rate)
    if rate == 0.0:
        return -0.0
    return -rate


def _probability_from_log(log_probability: float) -> float:
    if log_probability == -math.inf:
        return 0.0
    return math.exp(log_probability)


def _component_sizes_for_mask(
    length: int,
    edges: list[tuple[int, int]],
    mask: int,
) -> tuple[int, ...]:
    union_find = UnionFind(length)
    for index, (left, right) in enumerate(edges):
        if mask & (1 << index):
            union_find.union(left, right)
    return tuple(union_find.component_sizes().tolist())


def enumerate_graphs(spec: ModelSpec) -> Iterator[GraphOutcome]:
    if spec.length > 6:
        raise ValueError("exact enumeration supports length at most six")
    edges = list(iter_unordered_edges(spec.length))
    if spec.kappa == 0.0:
        for mask in range(1 << len(edges)):
            yield GraphOutcome(
                mask=mask,
                probability=1.0 if mask == 0 else 0.0,
                open_edges=0 if mask == 0 else mask.bit_count(),
                component_sizes=(
                    tuple([1] * spec.length)
                    if mask == 0
                    else _component_sizes_for_mask(spec.length, edges, mask)
                ),
            )
        return
    kernel = periodic_kernel(spec.length, spec.sigma)
    log_rates = math.log(spec.kappa) + np.log(kernel)
    for mask in range(1 << len(edges)):
        union_find = UnionFind(spec.length)
        log_probability = 0.0
        open_count = 0
        for index, (left, right) in enumerate(edges):
            separation = right - left
            distance = min(separation, spec.length - separation)
            log_rate = float(log_rates[distance - 1])
            if mask & (1 << index):
                log_probability += _log_open_edge_weight(log_rate)
                open_count += 1
                union_find.union(left, right)
            else:
                log_probability += _log_closed_edge_weight(log_rate)
        yield GraphOutcome(
            mask=mask,
            probability=_probability_from_log(log_probability),
            open_edges=open_count,
            component_sizes=tuple(union_find.component_sizes().tolist()),
        )


def exact_partition_distribution(
    spec: ModelSpec,
) -> dict[tuple[int, ...], float]:
    result: dict[tuple[int, ...], float] = {}
    for outcome in enumerate_graphs(spec):
        result[outcome.component_sizes] = (
            result.get(outcome.component_sizes, 0.0) + outcome.probability
        )
    return result
