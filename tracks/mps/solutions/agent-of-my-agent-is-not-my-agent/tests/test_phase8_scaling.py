import math

import pytest

from lrtfim.phase8_scaling import (
    adjacent_effective_exponents,
    direct_gap_power_law,
    gap_scaling_summary,
    sensitivity_regression,
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


def _gaps_from_adjacent_z(lengths, z_values, first_gap=0.4):
    gaps = [first_gap]
    for left, right, z_eff in zip(lengths, lengths[1:], z_values):
        gaps.append(gaps[-1] * (right / left) ** (-z_eff))
    return gaps


def test_adjacent_effective_exponents_support_five_nondoubling_sizes():
    lengths = [16, 32, 64, 96, 128]
    effective_lengths = [
        math.sqrt(left * right) for left, right in zip(lengths, lengths[1:])
    ]
    expected = [0.94 + 1.7 / length for length in effective_lengths]
    gaps = _gaps_from_adjacent_z(lengths, expected)

    result = adjacent_effective_exponents(lengths, gaps)

    assert result["pairs"] == ["16_32", "32_64", "64_96", "96_128"]
    assert result["effective_lengths"] == pytest.approx(effective_lengths)
    assert result["values"] == pytest.approx(expected)


def test_direct_gap_power_law_recovers_exact_amplitude_and_exponent():
    lengths = [16, 32, 64, 96, 128]
    amplitude = 2.75
    exponent = 0.93
    gaps = [amplitude * length ** (-exponent) for length in lengths]

    result = direct_gap_power_law(lengths, gaps)

    assert result["amplitude"] == pytest.approx(amplitude)
    assert result["exponent"] == pytest.approx(exponent)
    assert result["residual_rms"] == pytest.approx(0.0, abs=1.0e-14)
    assert result["residual_degrees_of_freedom"] == 3


def test_direct_gap_power_law_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="at least three"):
        direct_gap_power_law([16, 32], [0.3, 0.2])
    with pytest.raises(ValueError, match="positive"):
        direct_gap_power_law([16, 32, 64], [0.3, 0.0, 0.1])
    with pytest.raises(ValueError, match="finite"):
        direct_gap_power_law([16, 32, 64], [0.3, float("nan"), 0.1])


def test_five_size_gap_summary_reports_regressions_and_leave_l16_out():
    lengths = [16, 32, 64, 96, 128]
    effective_lengths = [
        math.sqrt(left * right) for left, right in zip(lengths, lengths[1:])
    ]
    expected = [0.94 + 1.7 / length for length in effective_lengths]
    gaps = _gaps_from_adjacent_z(lengths, expected)

    result = gap_scaling_summary(lengths, gaps)

    assert result["z_eff"]["values"] == pytest.approx(expected)
    assert result["regression"]["power"]["estimate"] == pytest.approx(0.94)
    assert result["regression"]["power"]["residual_degrees_of_freedom"] == 2
    assert result["regression"]["log"]["residual_degrees_of_freedom"] == 2
    assert (
        result["regression"]["leave_L16_out"]["power"][
            "residual_degrees_of_freedom"
        ]
        == 1
    )
    assert result["regression"]["shared_gap_correlations_ignored"] is True
    assert result["regression"]["interpretation"] == (
        "deterministic_finite_size_sensitivity_regression"
    )


def test_sensitivity_regression_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="at least three"):
        sensitivity_regression([0.9, 0.8], [20.0, 40.0], "power")
    with pytest.raises(ValueError, match="strictly increasing"):
        sensitivity_regression([0.9, 0.8, 0.7], [20.0, 20.0, 40.0], "power")
    with pytest.raises(ValueError, match="form"):
        sensitivity_regression([0.9, 0.8, 0.7], [20.0, 30.0, 40.0], "other")


def test_gap_summary_rejects_nonpositive_or_nonincreasing_inputs():
    with pytest.raises(ValueError, match="positive"):
        gap_scaling_summary(
            [16, 32, 64, 96, 128], [0.30, 0.20, 0.0, 0.09, 0.07]
        )
    with pytest.raises(ValueError, match="strictly increasing"):
        gap_scaling_summary(
            [16, 32, 64, 64, 128], [0.30, 0.20, 0.13, 0.09, 0.07]
        )


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
        gap_scaling_summary(
            [16, 32, 64, 96, 128],
            [0.30, 0.20, float("nan"), 0.09, 0.07],
        )
