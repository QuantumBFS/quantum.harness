from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mixed_kernel_step_certificate_is_fail_closed_and_reproducible() -> None:
    payload = json.loads(
        (ROOT / "docs/adaptive_mixed_kernel_step_zero_field_audit.json").read_text()
    )
    calibration = payload["matched_kernel_step_calibration"]
    corrected = payload["corrected_small_field_point"]
    envelope = payload["intercept_envelope"]

    assert payload["uses_target_trajectory"] is False
    assert payload["uses_target_a_or_D"] is False
    assert 0.284 < calibration["c_center"] < 0.288
    assert abs(corrected["corrected_value"] - 0.5531500753445342) < 1e-13
    assert corrected["scheme_uncertainty"] < 2e-6
    assert envelope["maximum"] < payload["exact_D0"]
    assert payload["gates"]["leading_D0_gate_pass"] is False
    assert payload["eq16_order_of_limits_eligible"] is False
    assert payload["gates"]["eq16_order_of_limits_pass"] is False
    assert payload["gates"]["eligible_for_physical_D1"] is False
    control = payload["closed_spectral_regulator_positive_control"]
    assert control["physical_finite_field_D1"] is False
    assert control["minimum_relative_intercept_error"] < 1.0e-5
    assert payload["gates"]["eligible_for_physical_D1"] is False
    assert all(
        fit["physical_D1_certified"] is False
        for fit in payload["forced_exact_leading_diagnostics"]
    )
