import math
import inspect

import numpy as np
import pytest
from scipy.stats import binomtest

import long_range_percolation as lrp
import long_range_percolation.geometric as geometric_module
from long_range_percolation.geometric import _iter_open_offsets, sample_geometric
from long_range_percolation.model import ModelSpec, canonical_edge, distance_classes


class _FakeRandomStream:
    def __init__(self, values: list[float]):
        self._values = iter(values)

    def random(self) -> float:
        return next(self._values)


def _distance(edge: tuple[int, int], length: int) -> int:
    left, right = edge
    return min((right - left) % length, (left - right) % length)


def _all_canonical_edges(length: int) -> list[tuple[int, int]]:
    return sorted(
        canonical_edge(length, item.distance, offset)
        for item in distance_classes(length)
        for offset in range(item.multiplicity)
    )


def _open_offset_matrix(
    multiplicity: int,
    rate: float,
    stream_count: int,
) -> np.ndarray:
    seeds = np.random.SeedSequence(20260729).spawn(stream_count)
    result = np.zeros((stream_count, multiplicity), dtype=np.int64)
    for row, seed in enumerate(seeds):
        rng = np.random.default_rng(seed)
        result[row, list(_iter_open_offsets(multiplicity, rate, rng))] = 1
    return result


def _binomial_fourth_central_moment(trials: int, probability: float) -> float:
    variance = trials * probability * (1.0 - probability)
    return variance * (1.0 - 6.0 * probability * (1.0 - probability)) + 3.0 * variance**2


def test_iter_open_offsets_controlled_stream_hits_expected_offsets():
    rate = math.log(2.0)
    offsets = list(_iter_open_offsets(6, rate, _FakeRandomStream([0.0, 0.75, 0.75])))
    assert offsets == [0, 3]
    assert offsets == sorted(offsets)
    assert len(offsets) == len(set(offsets))
    assert all(0 <= offset < 6 for offset in offsets)


def test_iter_open_offsets_boundary_branch_uses_ge_remaining_stop():
    rate = math.log(2.0)
    boundary = 1.0 - math.exp(-2.0 * rate)
    assert boundary == 0.75
    below = math.nextafter(boundary, 0.0)
    above = math.nextafter(boundary, 1.0)
    assert list(_iter_open_offsets(2, rate, _FakeRandomStream([below]))) == [1]
    assert list(_iter_open_offsets(2, rate, _FakeRandomStream([boundary]))) == []
    assert list(_iter_open_offsets(2, rate, _FakeRandomStream([above]))) == []


@pytest.mark.parametrize("rate", [math.log(2.0), 1.7])
def test_iter_open_offsets_matches_binomial_marginals(rate: float):
    multiplicity = 10
    stream_count = 20_000
    openings = _open_offset_matrix(multiplicity, rate, stream_count)
    probability = -math.expm1(-rate)
    per_offset_alpha = 0.001 / (2 * multiplicity)
    for column in range(multiplicity):
        observed = int(openings[:, column].sum())
        p_value = binomtest(observed, stream_count, probability).pvalue
        assert p_value >= per_offset_alpha
    counts = openings.sum(axis=1).astype(np.float64)
    expected_mean = multiplicity * probability
    expected_variance = multiplicity * probability * (1.0 - probability)
    mean_standard_error = math.sqrt(expected_variance / stream_count)
    assert counts.mean() == pytest.approx(expected_mean, abs=6.0 * mean_standard_error)
    fourth_moment = _binomial_fourth_central_moment(multiplicity, probability)
    variance_standard_error = math.sqrt(
        (
            fourth_moment
            - ((stream_count - 3.0) / (stream_count - 1.0)) * expected_variance**2
        )
        / stream_count
    )
    assert counts.var(ddof=1) == pytest.approx(
        expected_variance,
        abs=6.0 * variance_standard_error,
    )


def test_geometric_sampler_does_not_call_quadratic_or_enumerate_pairs():
    source = inspect.getsource(geometric_module)
    assert "sample_quadratic" not in source
    assert "iter_unordered_edges" not in source


def test_geometric_sampler_exact_limits_and_antipodal_uniqueness():
    empty = sample_geometric(
        ModelSpec(8, 1.0, 0.0),
        np.random.default_rng(4),
    )
    assert empty.edges.shape == (0, 2)
    np.testing.assert_array_equal(empty.labels, np.arange(8, dtype=np.int64))

    full = sample_geometric(
        ModelSpec(8, 1.0, 1e6),
        np.random.default_rng(4),
    )
    expected_edges = _all_canonical_edges(8)
    assert [tuple(edge) for edge in full.edges.tolist()] == expected_edges
    antipodal = [edge for edge in expected_edges if _distance(edge, 8) == 4]
    assert len(antipodal) == 4
    assert len([tuple(edge) for edge in full.edges.tolist() if _distance(tuple(edge), 8) == 4]) == 4
    np.testing.assert_array_equal(full.labels, np.zeros(8, dtype=np.int64))


def test_geometric_sampler_is_seed_reproducible():
    spec = ModelSpec(32, 0.8, 0.7)
    first = sample_geometric(spec, np.random.default_rng(20260729))
    second = sample_geometric(spec, np.random.default_rng(20260729))
    np.testing.assert_array_equal(first.edges, second.edges)
    np.testing.assert_array_equal(first.labels, second.labels)


def test_geometric_sampler_rejects_unregistered_rng_objects():
    with pytest.raises(ValueError, match="numpy.random.Generator"):
        sample_geometric(ModelSpec(8, 1.0, 0.7), object())


def test_geometric_sampler_handles_rate_underflow_without_duplicate_edges():
    sample = sample_geometric(
        ModelSpec(8, 128.0, np.nextafter(0.0, 1.0)),
        np.random.default_rng(9),
    )
    edge_tuples = [tuple(edge) for edge in sample.edges.tolist()]
    assert edge_tuples == sorted(edge_tuples)
    assert len(edge_tuples) == len(set(edge_tuples))
    assert all(_distance(edge, 8) == 1 for edge in edge_tuples)


def test_geometric_sampler_handles_rate_overflow_without_duplicate_edges():
    sample = sample_geometric(
        ModelSpec(8, 1.0, 1.7e308),
        np.random.default_rng(11),
    )
    expected_edges = _all_canonical_edges(8)
    assert [tuple(edge) for edge in sample.edges.tolist()] == expected_edges
    np.testing.assert_array_equal(sample.labels, np.zeros(8, dtype=np.int64))


def test_package_root_exports_geometric_sampler():
    assert lrp.sample_geometric is sample_geometric
    assert "sample_geometric" in lrp.__all__
