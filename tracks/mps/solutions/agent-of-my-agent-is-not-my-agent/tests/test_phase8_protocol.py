from pathlib import Path

import pytest

from lrtfim.phase8_protocol import (
    build_crossing_spec,
    build_gap_spec,
    common_field_sensitivity,
    decide_crossing,
)


def _summary(length: int, gamma: float, r_xi: float) -> dict:
    return {
        "status": "success",
        "settings": {
            "sigma": 1.75,
            "length": length,
            "gamma": gamma,
            "num_exponentials": 24,
            "alpha": 0.5,
            "r_fit": 2048,
            "chi_schedule": [64],
            "sectors": ["even"],
            "direct_only": True,
        },
        "mpo": {
            "pruned": True,
            "approximate_compression": False,
        },
        "raw_observables": {"r_xi": r_xi},
    }


def test_crossing_spec_contains_only_two_sigma175_even_chi64_cells(
    tmp_path: Path,
):
    spec = build_crossing_spec(tmp_path)
    assert [
        (cell["sigma"], cell["L"], cell["Gamma"], cell["sector"], cell["chi"])
        for cell in spec["cells"]
    ] == [
        (1.75, 128, 1.55, "even", 64),
        (1.75, 128, 1.60, "even", 64),
    ]
    assert spec["settings"]["adaptive_gamma"] is False
    assert spec["settings"]["K"] == 24
    assert spec["settings"]["approximate_mpo_compression"] is False


def test_crossing_decision_uses_l64_and_l128_endpoint_values():
    phase7 = {
        "sigma": 1.75,
        "status": "ready",
        "broad_bracket": [1.55, 1.60],
        "broad_Gamma_x": 1.5679,
    }
    summaries = {
        (64, 1.55): _summary(64, 1.55, 0.41),
        (64, 1.60): _summary(64, 1.60, 0.47),
        (128, 1.55): _summary(128, 1.55, 0.44),
        (128, 1.60): _summary(128, 1.60, 0.45),
    }
    result = decide_crossing(phase7, summaries)
    assert result["status"] == "resolved"
    assert result["Gamma_x_32_64"] == pytest.approx(1.5679)
    assert result["Gamma_x_64_128"] == pytest.approx(1.58)
    assert result["common_field"]["primary"] == "power"


def test_common_field_records_power_and_log_without_model_selection():
    result = common_field_sensitivity(1.5679, 1.5620)
    assert result["primary"] == "power"
    assert result["power"]["residual_degrees_of_freedom"] == 0
    assert result["log"]["residual_degrees_of_freedom"] == 0
    assert result["gap_field"] == result["power"]["estimate"]
    assert result["propagated_to_gap_uncertainty"] is False
    assert result["correction_coordinates_are_sensitivity_only"] is True


def test_gap_spec_is_ten_ordered_chi128_states_only_after_resolved_crossing(
    tmp_path: Path,
):
    decision = {
        "status": "resolved",
        "sigma": 1.75,
        "common_field": {"gap_field": 1.5609},
    }
    spec = build_gap_spec(decision, tmp_path)
    assert len(spec["cells"]) == 10
    assert [
        (cell["L"], cell["sector"]) for cell in spec["cells"]
    ] == [
        (16, "even"),
        (16, "odd"),
        (32, "even"),
        (32, "odd"),
        (64, "even"),
        (64, "odd"),
        (96, "even"),
        (96, "odd"),
        (128, "even"),
        (128, "odd"),
    ]
    assert {cell["chi"] for cell in spec["cells"]} == {128}
    assert {cell["Gamma"] for cell in spec["cells"]} == {1.5609}


def test_gap_spec_refuses_unresolved_crossing(tmp_path: Path):
    with pytest.raises(ValueError, match="resolved"):
        build_gap_spec(
            {"status": "unresolved_no_L64_L128_bracket"},
            tmp_path,
        )
