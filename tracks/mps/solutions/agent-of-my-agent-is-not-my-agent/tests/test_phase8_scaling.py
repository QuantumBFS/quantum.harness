import pytest

from lrtfim.phase8_scaling import (
    gap_scaling_summary,
    strict_endpoint_crossing,
    two_point_sensitivity,
)


def test_strict_crossing_interpolates_only_a_sign_change():
    result = strict_endpoint_crossing(
        [1.55, 1.60],
        [0.41, 0.47],
        [0.44, 0.45],
    )
    assert result["status"] == "resolved"
    assert result["differences"] == pytest.approx([-0.03, 0.02])
    assert result["Gamma_x"] == pytest.approx(1.58)
    assert result["crossing_resolution"] == pytest.approx(0.025)


@pytest.mark.parametrize(
    ("r_small", "r_large"),
    [
        ([0.41, 0.43], [0.44, 0.45]),
        ([0.41, 0.45], [0.41, 0.43]),
    ],
)
def test_strict_crossing_rejects_missing_or_endpoint_only_sign_change(
    r_small,
    r_large,
):
    result = strict_endpoint_crossing(
        [1.55, 1.60],
        r_small,
        r_large,
    )
    assert result["status"] == "unresolved_no_L64_L128_bracket"
    assert "Gamma_x" not in result


def test_power_and_log_sensitivities_are_explicit_two_point_evaluations():
    power = two_point_sensitivity([1.56, 1.558], [32, 64], "power")
    log = two_point_sensitivity([1.56, 1.558], [32, 64], "log")
    assert power["estimate"] == pytest.approx(1.556)
    assert power["residual_degrees_of_freedom"] == 0
    assert log["residual_degrees_of_freedom"] == 0
    assert power["interpretation"] == "two_point_sensitivity_extrapolation"
    assert power["coordinate_role"] == "sensitivity_only"
    assert power["known_correction_exponent_assumed"] is False
    assert log["coordinate_role"] == "sensitivity_only"
    assert log["known_correction_exponent_assumed"] is False


def test_gap_summary_keeps_effective_and_sensitivity_values_separate():
    result = gap_scaling_summary([32, 64, 128], [0.20, 0.12, 0.073])
    assert set(result["z_eff"]) == {"32_64", "64_128"}
    assert set(result["sensitivity"]) == {"power", "log", "spread"}
    assert result["sensitivity"]["power"]["residual_degrees_of_freedom"] == 0


def test_gap_summary_rejects_nonpositive_or_nondoubling_inputs():
    with pytest.raises(ValueError, match="positive"):
        gap_scaling_summary([32, 64, 128], [0.20, 0.0, 0.073])
    with pytest.raises(ValueError, match="doubling"):
        gap_scaling_summary([32, 60, 128], [0.20, 0.12, 0.073])


def test_phase8_scaling_rejects_nonfinite_inputs():
    with pytest.raises(ValueError, match="finite"):
        strict_endpoint_crossing(
            [1.55, float("nan")],
            [0.41, 0.47],
            [0.44, 0.45],
        )
    with pytest.raises(ValueError, match="finite"):
        two_point_sensitivity([1.56, float("inf")], [32, 64], "power")
    with pytest.raises(ValueError, match="finite"):
        gap_scaling_summary([32, 64, 128], [0.20, float("nan"), 0.073])
