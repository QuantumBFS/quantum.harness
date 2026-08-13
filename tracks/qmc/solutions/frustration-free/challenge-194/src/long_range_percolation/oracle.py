from __future__ import annotations

import math

import numpy as np

from .kernel import edge_probabilities, kernel_weight_sum, periodic_kernel
from .model import ModelSpec
from .sample import GraphSample
from .union_find import UnionFind


def _distance(left: int, right: int, length: int) -> int:
    separation = right - left
    return min(separation, length - separation)


def sample_quadratic(
    spec: ModelSpec,
    rng: np.random.Generator,
) -> GraphSample:
    if not isinstance(rng, np.random.Generator):
        raise ValueError("rng must be numpy.random.Generator")
    probabilities = edge_probabilities(
        spec,
        periodic_kernel(spec.length, spec.sigma),
    )
    union_find = UnionFind(spec.length)
    edges = []
    for left in range(spec.length):
        for right in range(left + 1, spec.length):
            probability = probabilities[_distance(left, right, spec.length) - 1]
            if rng.random() < probability:
                edges.append((left, right))
                union_find.union(left, right)
    edge_array = np.asarray(edges, dtype=np.int64).reshape(-1, 2)
    return GraphSample(spec.length, edge_array, union_find.labels())


def _class_probabilities(spec: ModelSpec) -> tuple[np.ndarray, np.ndarray]:
    from .model import distance_classes

    multiplicity = np.array(
        [item.multiplicity for item in distance_classes(spec.length)],
        dtype=np.float64,
    )
    probability = edge_probabilities(
        spec,
        periodic_kernel(spec.length, spec.sigma),
    )
    return multiplicity, probability


def expected_open_edges(spec: ModelSpec) -> float:
    multiplicity, probability = _class_probabilities(spec)
    return float(multiplicity @ probability)


def variance_open_edges(spec: ModelSpec) -> float:
    multiplicity, probability = _class_probabilities(spec)
    return float(multiplicity @ (probability * (1.0 - probability)))


def no_edge_probability(spec: ModelSpec) -> float:
    return math.exp(-spec.kappa * kernel_weight_sum(spec.length, spec.sigma))
