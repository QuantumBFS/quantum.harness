import math

import pytest

import long_range_percolation as lrp
from long_range_percolation.enumeration import (
    GraphOutcome,
    enumerate_graphs,
    exact_partition_distribution,
)
from long_range_percolation.model import ModelSpec, iter_unordered_edges
from long_range_percolation.oracle import (
    expected_open_edges,
    no_edge_probability,
)
from long_range_percolation.union_find import UnionFind


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


def test_all_graph_probabilities_normalize_and_reproduce_analytic_moments():
    for length in (2, 4, 6):
        spec = ModelSpec(length, 0.9, 0.6)
        outcomes = list(enumerate_graphs(spec))
        assert len(outcomes) == 2 ** (length * (length - 1) // 2)
        assert math.fsum(item.probability for item in outcomes) == pytest.approx(1.0)
        assert math.fsum(
            item.probability * item.open_edges for item in outcomes
        ) == pytest.approx(expected_open_edges(spec))
        assert outcomes[0].probability == pytest.approx(no_edge_probability(spec))


def test_two_site_partition_probabilities_are_exact():
    spec = ModelSpec(2, 1.0, 0.3)
    distribution = exact_partition_distribution(spec)
    closed = no_edge_probability(spec)
    assert distribution[(1, 1)] == pytest.approx(closed)
    assert distribution[(2,)] == pytest.approx(1.0 - closed)


def test_enumeration_rejects_lengths_above_six():
    with pytest.raises(ValueError, match="at most six"):
        list(enumerate_graphs(ModelSpec(8, 1.0, 1.0)))


def test_zero_coupling_assigns_unit_mass_to_empty_graph():
    spec = ModelSpec(4, 1.0, 0.0)
    edges = list(iter_unordered_edges(spec.length))
    outcomes = list(enumerate_graphs(spec))
    assert outcomes[0].probability == 1.0
    assert all(item.probability == 0.0 for item in outcomes[1:])
    for outcome in outcomes:
        assert outcome.open_edges == outcome.mask.bit_count()
        expected_sizes = _component_sizes_for_mask(
            spec.length,
            edges,
            outcome.mask,
        )
        assert outcome.component_sizes == expected_sizes


def test_large_kappa_with_saturated_edge_probabilities():
    spec = ModelSpec(2, 1.0, 100.0)
    edge_count = spec.length * (spec.length - 1) // 2
    outcomes = list(enumerate_graphs(spec))
    assert len(outcomes) == 2 ** edge_count
    for outcome in outcomes:
        assert math.isfinite(outcome.probability)
        assert outcome.probability >= 0.0
    assert math.fsum(item.probability for item in outcomes) == pytest.approx(1.0)
    fully_open_mask = (1 << edge_count) - 1
    open_outcome = next(item for item in outcomes if item.mask == fully_open_mask)
    total_mass = math.fsum(item.probability for item in outcomes)
    assert open_outcome.probability / total_mass == pytest.approx(1.0, rel=1e-12)
    for item in outcomes:
        if item.mask != fully_open_mask:
            assert item.probability < 1e-50


def test_package_root_exports_enumeration_symbols():
    assert lrp.GraphOutcome is GraphOutcome
    assert lrp.enumerate_graphs is enumerate_graphs
    assert lrp.exact_partition_distribution is exact_partition_distribution
    assert "GraphOutcome" in lrp.__all__
    assert "enumerate_graphs" in lrp.__all__
    assert "exact_partition_distribution" in lrp.__all__
