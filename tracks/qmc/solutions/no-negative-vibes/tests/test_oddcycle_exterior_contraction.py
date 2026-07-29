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
        assert record["block_length"] == 1
        assert record["block_atom_count"] == 4
        assert record["gamma_block_upper"] == pytest.approx(
            record["gamma_upper"]
        )
        assert record["effective_per_letter_gamma"] == pytest.approx(
            record["gamma_upper"]
        )
        assert record["residue_bounds"] == [
            {
                "residue": 0,
                "word_count": 1,
                "maximum_p_induced_norm": pytest.approx(1.0),
                "trace_prefactor": pytest.approx(record["prefactor"]),
            }
        ]
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


def test_grade_three_block_metric_reports_all_residue_bounds():
    result = common_quadratic_exterior_contraction(
        [(1.0, 1.0, 1.0)],
        grades=(3,),
        block_lengths={3: 2},
        gamma_tolerance=1.0e-2,
        epsilon=1.0e-7,
    )

    record = result["grades"]["3"]
    assert record["status"] == "numerical-feasible-common-metric"
    assert record["atom_count"] == 2
    assert record["block_length"] == 2
    assert record["block_atom_count"] == 4
    assert record["effective_per_letter_gamma"] == pytest.approx(
        math.sqrt(record["gamma_block_upper"])
    )
    assert [entry["residue"] for entry in record["residue_bounds"]] == [0, 1]
    assert [entry["word_count"] for entry in record["residue_bounds"]] == [1, 2]
    assert record["residue_bounds"][0]["maximum_p_induced_norm"] == (
        pytest.approx(1.0)
    )
    for entry in record["residue_bounds"]:
        assert entry["trace_prefactor"] == pytest.approx(
            record["prefactor"] * entry["maximum_p_induced_norm"]
        )
    assert result["tail_bound"]["period"] == 2
