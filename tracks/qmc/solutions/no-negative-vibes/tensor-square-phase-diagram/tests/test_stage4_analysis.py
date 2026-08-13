import math

import pytest

from tensor_square.stage4_analysis import (
    aggregate_production_cell,
    aggregate_replica_estimate,
    classify_numerical_sentinel,
    classify_stage4_candidate,
    metric_trend,
    PRODUCTION_METRICS,
)
from tensor_square.scan import run_fingerprint


def _cell(
    *,
    m: int,
    beta: float,
    q: float,
    q_error: float = 0.04,
    xi: float = 0.1,
    xi_error: float = 0.01,
) -> dict[str, object]:
    return {
        "audit_status": "PASS",
        "m": m,
        "beta": beta,
        "q_combined_mean": q,
        "q_combined_stderr": q_error,
        "staggered_structure_mean": xi,
        "staggered_structure_stderr": xi_error,
        "q_a_susceptibility_mean": xi,
        "q_a_susceptibility_stderr": xi_error,
        "q_b_susceptibility_mean": xi,
        "q_b_susceptibility_stderr": xi_error,
        "q_a_binder_mean": xi,
        "q_a_binder_stderr": xi_error,
        "q_b_binder_mean": xi,
        "q_b_binder_stderr": xi_error,
        "correlation_length_over_m_mean": xi,
        "correlation_length_over_m_stderr": xi_error,
    }


def _production_replica(replica: int) -> dict[str, object]:
    run_spec = {
        "cell_id": "cell",
        "config": {"m": 8, "beta": 8.0},
        "source_revision": "a" * 40,
        "budget_plan_digest": "b" * 64,
        "replica": replica,
    }
    row: dict[str, object] = {
        "status": "COMPLETE",
        "cell_id": "cell",
        "cohort": "half_filled_core",
        "pair_id": None,
        "replica": replica,
        "run_spec": run_spec,
        "run_fingerprint": run_fingerprint(run_spec),
        "final_audit": {"status": "PASS", "achieved_ess": 40.0 + replica},
        "acceptance": 0.5,
        "direct_sign_min": 1.0,
        "weight_log_error_max": 1.0e-12,
        "realized_measurement_sweeps": 640,
    }
    for value_key, stderr_key in PRODUCTION_METRICS.values():
        row[value_key] = 1.0 + 0.01 * replica
        if stderr_key is not None:
            row[stderr_key] = 0.02
    return row


def test_replica_aggregation_includes_between_replica_scatter() -> None:
    estimate = aggregate_replica_estimate(
        [
            {"value": 1.0, "error": 0.1},
            {"value": 3.0, "error": 0.1},
        ],
        value_key="value",
        stderr_key="error",
    )

    assert estimate["mean"] == pytest.approx(2.0)
    assert estimate["within_replica_stderr"] == pytest.approx(
        math.sqrt(0.02) / 2.0
    )
    assert estimate["between_replica_stderr"] == pytest.approx(1.0)
    assert estimate["stderr"] == pytest.approx(1.0)


def test_production_cell_requires_four_fingerprinted_ess_passing_replicas() -> None:
    result = aggregate_production_cell(
        [_production_replica(replica) for replica in range(4)]
    )

    assert result["audit_status"] == "PASS"
    assert result["minimum_ess"] == pytest.approx(40.0)
    assert result["q_combined_mean"] == pytest.approx(1.015)


def test_production_cell_marks_failed_replica_as_statistical_stop() -> None:
    rows = [_production_replica(replica) for replica in range(4)]
    rows[2]["status"] = "EARLY_STOP"

    result = aggregate_production_cell(rows)

    assert result["audit_status"] == "STOP"
    assert "ESS" in result["audit_reason"]


def test_metric_trend_applies_frozen_two_sigma_and_five_percent_gate() -> None:
    low = {"x_mean": 1.0, "x_stderr": 0.02}
    high = {"x_mean": 1.1, "x_stderr": 0.02}

    result = metric_trend(low, high, metric="x")

    assert result["delta"] == pytest.approx(0.1)
    assert result["relative_delta"] == pytest.approx(0.1)
    assert result["z"] > 3.0
    assert result["strict_positive"] is True


def test_core_candidate_survives_only_with_independent_diagnostic() -> None:
    rows = []
    for beta, values in ((4.0, (1.0, 1.2, 1.5)), (8.0, (1.2, 1.6, 2.0))):
        for m, q in zip((4, 6, 8), values):
            rows.append(_cell(m=m, beta=beta, q=q, xi=0.1 + 0.02 * m))

    result = classify_stage4_candidate(rows, cohort="half_filled_core")

    assert result["classification"] == "SURVIVE"
    assert result["primary_size_strict"] is True
    assert result["primary_thermal_strict"] is True
    assert result["independent_diagnostic_support"] is True


def test_core_candidate_without_collective_support_is_extend() -> None:
    rows = []
    for beta, values in ((4.0, (1.0, 1.2, 1.5)), (8.0, (1.2, 1.6, 2.0))):
        for m, q in zip((4, 6, 8), values):
            rows.append(_cell(m=m, beta=beta, q=q, xi=0.1))

    result = classify_stage4_candidate(rows, cohort="half_filled_core")

    assert result["classification"] == "EXTEND"
    assert result["independent_diagnostic_support"] is False


def test_audited_flat_core_candidate_stops() -> None:
    rows = [
        _cell(m=m, beta=beta, q=1.0, xi=0.1)
        for beta in (4.0, 8.0)
        for m in (4, 6, 8)
    ]

    result = classify_stage4_candidate(rows, cohort="half_filled_core")

    assert result["classification"] == "STOP"
    assert result["inference_scope"] == "physics"


def test_incomplete_candidate_is_statistical_stop_not_no_go() -> None:
    rows = [
        _cell(m=m, beta=8.0, q=1.0 + 0.1 * m)
        for m in (4, 6)
    ]

    result = classify_stage4_candidate(rows, cohort="paired_competition")

    assert result["classification"] == "STOP"
    assert result["inference_scope"] == "statistical_only"
    assert "no physics inference" in result["reason"]


def test_competing_candidate_requires_size_trend_and_diagnostic() -> None:
    rows = [
        _cell(m=4, beta=8.0, q=1.0, xi=0.1),
        _cell(m=6, beta=8.0, q=1.3, xi=0.15),
        _cell(m=8, beta=8.0, q=1.7, xi=0.2),
    ]

    result = classify_stage4_candidate(rows, cohort="paired_competition")

    assert result["classification"] == "SURVIVE"
    assert result["primary_size_strict"] is True
    assert result["independent_diagnostic_support"] is True


def test_beta4_numerical_sentinel_uses_same_size_and_diagnostic_gates() -> None:
    rows = [
        _cell(m=4, beta=4.0, q=1.0, xi=0.1),
        _cell(m=6, beta=4.0, q=1.3, xi=0.15),
        _cell(m=8, beta=4.0, q=1.7, xi=0.2),
    ]

    result = classify_numerical_sentinel(rows, beta=4.0)

    assert result["sentinel_classification"] == "ELIGIBLE"
    assert result["inference_scope"] == "numerical_only"


def test_numerical_sentinel_does_not_release_incomplete_endpoint_set() -> None:
    rows = [
        _cell(m=4, beta=4.0, q=1.0, xi=0.1),
        _cell(m=8, beta=4.0, q=1.7, xi=0.2),
    ]

    result = classify_numerical_sentinel(rows, beta=4.0)

    assert result["sentinel_classification"] == "STOP"
    assert result["inference_scope"] == "statistical_only"
