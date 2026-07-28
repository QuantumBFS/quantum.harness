import inspect

import numpy as np
import pytest

import long_range_percolation as lrp
import long_range_percolation.geometric as geometric_module
from long_range_percolation.geometric import sample_geometric
from long_range_percolation.model import ModelSpec, canonical_edge, distance_classes


def _distance(edge: tuple[int, int], length: int) -> int:
    left, right = edge
    return min((right - left) % length, (left - right) % length)


def _all_canonical_edges(length: int) -> list[tuple[int, int]]:
    return sorted(
        canonical_edge(length, item.distance, offset)
        for item in distance_classes(length)
        for offset in range(item.multiplicity)
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
