from collections import Counter

import numpy as np
import pytest
from scipy.stats import binomtest

from long_range_percolation.enumeration import exact_partition_distribution
from long_range_percolation.geometric import sample_geometric
from long_range_percolation.kernel import edge_probabilities, periodic_kernel
from long_range_percolation.model import ModelSpec, distance_classes
from long_range_percolation.oracle import sample_quadratic

GEOMETRIC_DISTANCE_SAMPLE_COUNT = 20_000
PARTITION_SAMPLE_COUNT = 40_000

GEOMETRIC_DISTANCE_FAMILYWISE_ALPHA = 0.001
PARTITION_FAMILYWISE_ALPHA = 0.001

GEOMETRIC_DISTANCE_SEED_BASE = 100_000
ORACLE_PARTITION_SEED_BASE = 200_000
GEOMETRIC_PARTITION_SEED_BASE = 1_200_000


def _edge_distance(edge: tuple[int, int], length: int) -> int:
    separation = edge[1] - edge[0]
    return min(separation, length - separation)


def _distance_open_counts(samples: list, length: int) -> Counter[int]:
    counts: Counter[int] = Counter()
    for sample in samples:
        counts.update(
            _edge_distance(tuple(edge), length)
            for edge in sample.edges.tolist()
        )
    return counts


def _partition_counts(samples: list) -> Counter[tuple[int, ...]]:
    counts: Counter[tuple[int, ...]] = Counter()
    for sample in samples:
        _, sizes = np.unique(sample.labels, return_counts=True)
        counts[tuple(sorted(sizes.tolist(), reverse=True))] += 1
    return counts


@pytest.mark.parametrize("length", [4, 8, 32])
def test_geometric_distance_frequencies_match_exact_bernoulli_probabilities(length: int):
    spec = ModelSpec(length, 1.0, 0.7)
    samples = [
        sample_geometric(spec, np.random.default_rng(GEOMETRIC_DISTANCE_SEED_BASE + index))
        for index in range(GEOMETRIC_DISTANCE_SAMPLE_COUNT)
    ]
    counts = _distance_open_counts(samples, length)
    probabilities = edge_probabilities(
        spec,
        periodic_kernel(length, spec.sigma),
    )
    classes = distance_classes(length)
    alpha = GEOMETRIC_DISTANCE_FAMILYWISE_ALPHA / len(classes)

    for item in classes:
        trials = GEOMETRIC_DISTANCE_SAMPLE_COUNT * item.multiplicity
        result = binomtest(
            counts[item.distance],
            trials,
            probabilities[item.distance - 1],
        )
        assert result.pvalue > alpha


@pytest.mark.parametrize("length", [4, 6])
def test_oracle_and_geometric_partition_histograms_match_exact_distribution(length: int):
    spec = ModelSpec(length, 0.9, 0.6)
    exact_distribution = exact_partition_distribution(spec)
    alpha = PARTITION_FAMILYWISE_ALPHA / len(exact_distribution)

    for sampler, seed_base in [
        (sample_quadratic, ORACLE_PARTITION_SEED_BASE),
        (sample_geometric, GEOMETRIC_PARTITION_SEED_BASE),
    ]:
        samples = [
            sampler(spec, np.random.default_rng(seed_base + index))
            for index in range(PARTITION_SAMPLE_COUNT)
        ]
        observed = _partition_counts(samples)
        for partition, probability in exact_distribution.items():
            result = binomtest(observed[partition], PARTITION_SAMPLE_COUNT, probability)
            assert result.pvalue > alpha


def test_accelerated_and_quadratic_samples_use_independent_seed_streams():
    spec = ModelSpec(32, 1.0, 0.7)
    quadratic = sample_quadratic(spec, np.random.default_rng(11))
    geometric = sample_geometric(spec, np.random.default_rng(12))
    assert not np.array_equal(quadratic.edges, geometric.edges)
