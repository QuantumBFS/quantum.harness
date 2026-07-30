from __future__ import annotations

import math
from typing import Iterator

import numpy as np

from .kernel import periodic_kernel
from .model import ModelSpec, canonical_edge, distance_classes
from .sample import GraphSample
from .union_find import UnionFind


def _iter_open_offsets(
    multiplicity: int,
    rate: float,
    rng: np.random.Generator,
) -> Iterator[int]:
    if multiplicity < 1 or rate == 0.0:
        return
    if not math.isfinite(rate) or math.exp(-rate) == 0.0:
        yield from range(multiplicity)
        return

    offset = 0
    while offset < multiplicity:
        remaining = multiplicity - offset
        exponential = -math.log1p(-float(rng.random()))
        if exponential >= rate * remaining:
            break
        skipped = int(exponential / rate)
        offset += skipped
        yield offset
        offset += 1


def sample_geometric(
    spec: ModelSpec,
    rng: np.random.Generator,
) -> GraphSample:
    if not isinstance(rng, np.random.Generator):
        raise ValueError("rng must be numpy.random.Generator")
    if spec.kappa == 0.0:
        return GraphSample(
            spec.length,
            np.empty((0, 2), dtype=np.int64),
            np.arange(spec.length, dtype=np.int64),
        )

    with np.errstate(over="ignore", under="ignore"):
        rates = spec.kappa * periodic_kernel(spec.length, spec.sigma)

    union_find = UnionFind(spec.length)
    edges: list[tuple[int, int]] = []
    for item in distance_classes(spec.length):
        rate = float(rates[item.distance - 1])
        for offset in _iter_open_offsets(item.multiplicity, rate, rng):
            edge = canonical_edge(spec.length, item.distance, offset)
            edges.append(edge)
            union_find.union(*edge)

    edge_array = np.asarray(sorted(edges), dtype=np.int64).reshape(-1, 2)
    return GraphSample(spec.length, edge_array, union_find.labels())
