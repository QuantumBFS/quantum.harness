from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterator

import numpy as np

from .kernel import periodic_kernel
from .model import ModelSpec, iter_unordered_edges
from .union_find import UnionFind


@dataclass(frozen=True)
class GraphOutcome:
    mask: int
    probability: float
    open_edges: int
    component_sizes: tuple[int, ...]


def _log_open_edge_weight(log_rate: float) -> float:
    rate = math.exp(log_rate)
    if rate == 0.0:
        return log_rate
    if math.exp(-rate) == 1.0:
        complement = -math.expm1(-rate)
        if complement == 0.0:
            return log_rate
        return math.log(complement)
    return math.log1p(-math.exp(-rate))


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
                log_probability += -math.exp(log_rate)
        yield GraphOutcome(
            mask=mask,
            probability=math.exp(log_probability),
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
