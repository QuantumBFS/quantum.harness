import math

import pytest


pytest.importorskip("cvxpy")

from oracle.oddcycle_exterior_contraction import (
    common_quadratic_exterior_contraction,
)


def test_repeated_fixed_point_returns_verified_grade_metrics():
    result = common_quadratic_exterior_contraction(
        [(1.0, 1.0, 1.0), (1.0, 1.0, 1.0)],
        gamma_tolerance=5.0e-3,
        epsilon=1.0e-7,
    )

    assert result["status"] == "numerical-common-quadratic-discovery"
    assert result["claim_scope"] == "numerical-discovery-only"
    assert result["points"] == [
        [1.0, 1.0, 1.0],
        [1.0, 1.0, 1.0],
    ]
    assert result["alphabet_size"] == 4
    assert result["determinant_growth_normalization"] == 8.0
    assert set(result["grades"]) == {"1", "2", "3"}

    for grade, dimension in (("1", 5), ("2", 10), ("3", 10)):
        record = result["grades"][grade]
        assert record["status"] == "numerical-feasible-common-metric"
        assert record["solver_status"] in {"optimal", "optimal_inaccurate"}
        assert record["dimension"] == dimension
        assert record["atom_count"] == 4
        assert 0.0 < record["gamma_upper"]
        assert record["metric_eigenvalues"][0] > 0.0
        assert math.isfinite(record["metric_condition_number"])
        assert record["metric_condition_number"] >= 1.0
        assert record["minimum_verified_gap_eigenvalue"] >= -1.0e-6
        assert record["prefactor"] == pytest.approx(
            dimension * math.sqrt(record["metric_condition_number"])
        )

    tail = result["tail_bound"]
    assert tail["criterion"] == (
        "sum_k prefactor_k * gamma_k**N < 2"
    )
    if tail["minimum_integer_N"] is not None:
        assert tail["bound_at_N"] < 2.0
        if tail["minimum_integer_N"] > 1:
            assert tail["bound_at_previous_N"] >= 2.0
