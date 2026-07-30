from collections import Counter
import inspect

import long_range_percolation.geometric as geometric_module
import long_range_percolation.oracle as oracle_module
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

FAMILYWISE_ALPHA = 0.001

GEOMETRIC_DISTANCE_LENGTHS = (4, 8, 32)
PARTITION_LENGTHS = (4, 6)
GEOMETRIC_DISTANCE_SEED_BASE = 100_000
ORACLE_PARTITION_SEED_BASE = 200_000
GEOMETRIC_PARTITION_SEED_BASE = 1_200_000
PARTITION_SAMPLERS = (
    ("quadratic", sample_quadratic, ORACLE_PARTITION_SEED_BASE),
    ("geometric", sample_geometric, GEOMETRIC_PARTITION_SEED_BASE),
)


def _geometric_distance_family_denominator() -> int:
    return sum(
        len(distance_classes(length))
        for length in GEOMETRIC_DISTANCE_LENGTHS
    )


def _partition_family_denominator() -> int:
    return sum(
        len(exact_partition_distribution(ModelSpec(length, 0.9, 0.6)))
        * len(PARTITION_SAMPLERS)
        for length in PARTITION_LENGTHS
    )


GEOMETRIC_DISTANCE_BONFERRONI_DENOMINATOR = (
    _geometric_distance_family_denominator()
)
PARTITION_BONFERRONI_DENOMINATOR = _partition_family_denominator()
GEOMETRIC_DISTANCE_GLOBAL_ALPHA = (
    FAMILYWISE_ALPHA / GEOMETRIC_DISTANCE_BONFERRONI_DENOMINATOR
)
PARTITION_GLOBAL_ALPHA = FAMILYWISE_ALPHA / PARTITION_BONFERRONI_DENOMINATOR


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


def _acceptance_message(
    *,
    family: str,
    pvalue: float,
    threshold: float,
    length: int,
    sampler: str,
    distance: int | None = None,
    partition: tuple[int, ...] | None = None,
) -> str:
    fields = [
        f"family={family}",
        f"pvalue={pvalue:.6g}",
        f"threshold={threshold:.6g}",
        f"L={length}",
        f"sampler={sampler}",
    ]
    if distance is not None:
        fields.append(f"distance={distance}")
    if partition is not None:
        fields.append(f"partition={partition}")
    return ", ".join(fields)


def _geometric_distance_acceptance_cases(length: int) -> list[dict[str, object]]:
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
    cases: list[dict[str, object]] = []
    for item in distance_classes(length):
        trials = GEOMETRIC_DISTANCE_SAMPLE_COUNT * item.multiplicity
        result = binomtest(
            counts[item.distance],
            trials,
            probabilities[item.distance - 1],
        )
        cases.append(
            {
                "distance": item.distance,
                "length": length,
                "pvalue": float(result.pvalue),
                "sampler": "geometric",
            }
        )
    return cases


def _partition_acceptance_cases(length: int) -> list[dict[str, object]]:
    spec = ModelSpec(length, 0.9, 0.6)
    exact_distribution = exact_partition_distribution(spec)
    cases: list[dict[str, object]] = []

    for sampler_name, sampler, seed_base in PARTITION_SAMPLERS:
        samples = [
            sampler(spec, np.random.default_rng(seed_base + index))
            for index in range(PARTITION_SAMPLE_COUNT)
        ]
        observed = _partition_counts(samples)
        for partition, probability in exact_distribution.items():
            result = binomtest(observed[partition], PARTITION_SAMPLE_COUNT, probability)
            cases.append(
                {
                    "length": length,
                    "partition": partition,
                    "pvalue": float(result.pvalue),
                    "sampler": sampler_name,
                }
            )
    return cases


@pytest.mark.parametrize("length", GEOMETRIC_DISTANCE_LENGTHS)
def test_geometric_distance_frequencies_match_exact_bernoulli_probabilities(length: int):
    for case in _geometric_distance_acceptance_cases(length):
        assert case["pvalue"] > GEOMETRIC_DISTANCE_GLOBAL_ALPHA, _acceptance_message(
            family="geometric-distance",
            pvalue=float(case["pvalue"]),
            threshold=GEOMETRIC_DISTANCE_GLOBAL_ALPHA,
            length=length,
            sampler=str(case["sampler"]),
            distance=int(case["distance"]),
        )


@pytest.mark.parametrize("length", PARTITION_LENGTHS)
def test_oracle_and_geometric_partition_histograms_match_exact_distribution(length: int):
    for case in _partition_acceptance_cases(length):
        assert case["pvalue"] > PARTITION_GLOBAL_ALPHA, _acceptance_message(
            family="partition",
            pvalue=float(case["pvalue"]),
            threshold=PARTITION_GLOBAL_ALPHA,
            length=length,
            sampler=str(case["sampler"]),
            partition=tuple(case["partition"]),
        )


def test_geometric_and_quadratic_samplers_remain_structurally_independent():
    geometric_module_source = inspect.getsource(geometric_module)
    geometric_sampler_source = inspect.getsource(sample_geometric)
    oracle_module_source = inspect.getsource(oracle_module)
    quadratic_sampler_source = inspect.getsource(sample_quadratic)

    assert "distance_classes" in geometric_module_source
    assert "_iter_open_offsets" in geometric_sampler_source
    assert "sample_quadratic" not in geometric_module_source
    assert "iter_unordered_edges" not in geometric_module_source
    assert "for left in range(spec.length)" not in geometric_sampler_source
    assert "for right in range(left + 1, spec.length)" not in geometric_sampler_source

    assert "for left in range(spec.length)" in quadratic_sampler_source
    assert "for right in range(left + 1, spec.length)" in quadratic_sampler_source
    assert "_iter_open_offsets" not in oracle_module_source
    assert "sample_geometric" not in oracle_module_source
