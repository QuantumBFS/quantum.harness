import numpy as np
import pytest

from long_range_percolation.model import ModelSpec
from long_range_percolation.oracle import (
    expected_open_edges,
    no_edge_probability,
    sample_quadratic,
    variance_open_edges,
)


def test_quadratic_oracle_exact_limits():
    empty = sample_quadratic(
        ModelSpec(8, 1.0, 0.0),
        np.random.default_rng(1),
    )
    assert empty.edges.shape == (0, 2)
    np.testing.assert_array_equal(empty.labels, np.arange(8))

    full = sample_quadratic(
        ModelSpec(8, 1.0, 1e6),
        np.random.default_rng(1),
    )
    assert full.edges.shape == (28, 2)
    np.testing.assert_array_equal(full.labels, np.zeros(8, dtype=np.int64))


def test_oracle_edge_count_matches_analytic_moments():
    spec = ModelSpec(8, 0.9, 0.7)
    counts = np.array(
        [
            sample_quadratic(spec, np.random.default_rng(seed)).edges.shape[0]
            for seed in range(30_000)
        ]
    )
    assert counts.mean() == pytest.approx(
        expected_open_edges(spec),
        abs=5.0 * np.sqrt(variance_open_edges(spec) / counts.size),
    )
    assert counts.var(ddof=1) == pytest.approx(
        variance_open_edges(spec),
        rel=0.05,
    )


def test_no_edge_probability_uses_total_kernel_weight():
    spec = ModelSpec(6, 1.0, 0.4)
    observed = np.mean(
        [
            sample_quadratic(spec, np.random.default_rng(seed)).edges.size == 0
            for seed in range(40_000)
        ]
    )
    assert observed == pytest.approx(no_edge_probability(spec), abs=0.01)
