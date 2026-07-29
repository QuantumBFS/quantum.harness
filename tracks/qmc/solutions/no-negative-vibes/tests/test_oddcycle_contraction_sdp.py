import pytest


cvxpy = pytest.importorskip("cvxpy")

from oracle.oddcycle_contraction_sdp import common_metric_sdp


def test_fixed_oddcycle_is_rejected_by_a_strict_common_metric():
    result = common_metric_sdp(1.0, 1.0, 1.0)

    assert result["status"] == "strict-common-metric-found"
    assert result["objective_margin"] > 1.0e-3
    assert result["verified_margin"] > 1.0e-3
    assert result["metric_inertia"]["zero"] == 0
    assert (
        result["interpretation"]
        == "known-common-split-contraction-class"
    )
