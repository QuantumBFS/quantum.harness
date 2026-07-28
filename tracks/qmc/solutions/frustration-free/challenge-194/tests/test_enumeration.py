import math

import pytest

from long_range_percolation.enumeration import (
    enumerate_graphs,
    exact_partition_distribution,
)
from long_range_percolation.model import ModelSpec
from long_range_percolation.oracle import (
    expected_open_edges,
    no_edge_probability,
)


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
    outcomes = list(enumerate_graphs(ModelSpec(4, 1.0, 0.0)))
    assert outcomes[0].probability == 1.0
    assert all(item.probability == 0.0 for item in outcomes[1:])
