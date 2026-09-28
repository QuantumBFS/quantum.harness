from __future__ import annotations

from src.joint_zero_field_audit import (
    audit_joint_zero_field_limit,
    giant_string_leading_tail_bound,
)


def test_giant_string_leading_tail_bound_is_positive_and_decreases() -> None:
    values = [giant_string_leading_tail_bound(cutoff) for cutoff in (4.0, 8.0, 12.0)]
    assert values[0] > values[1] > values[2] > 0.0


def _row(h, cutoff, terms, value, rapidity=None):
    row = {
        "field": h,
        "string_xi_cutoff": cutoff,
        "velocity_series_terms": terms,
        "h_times_full_diffusion": value,
    }
    if rapidity is not None:
        row["rho_total_relative_l2_error"] = rapidity
    return row


def test_joint_limit_refuses_missing_string_and_rapidity_controls() -> None:
    payload = {
        "full_cross_runs": [
            _row(0.2, 8, 100, 0.46),
            _row(0.2, 8, 200, 0.465),
            _row(0.1, 8, 100, 0.52),
            _row(0.1, 8, 200, 0.525),
            _row(0.05, 8, 100, 0.55),
            _row(0.05, 8, 200, 0.555),
        ]
    }
    result = audit_joint_zero_field_limit(
        payload, exact_leading=0.58, physical_d1_candidate=True
    )
    audit = result["joint_limit_audit"]
    assert audit["all_regulator_directions_bounded"] is False
    assert audit["zero_field_joint_limit_controlled"] is False
    assert audit["physical_D1_certified"] is False


def test_joint_limit_can_pass_only_with_all_regulator_directions() -> None:
    rows = []
    exact = 0.58
    for h in (0.04, 0.03, 0.02):
        target = exact - 0.7 * h + 0.1 * h**2
        for cutoff, tail in ((8.0, -2e-5), (12.0, 0.0)):
            rows.append(_row(h, cutoff, 100, target + tail + 1e-5, 1e-4))
            rows.append(_row(h, cutoff, 200, target + tail + 5e-6, 1e-4))
    result = audit_joint_zero_field_limit(
        {"full_cross_runs": rows},
        exact_leading=exact,
        physical_d1_candidate=True,
        maximum_d1_scheme_spread=0.1,
    )
    audit = result["joint_limit_audit"]
    assert audit["all_regulator_directions_bounded"] is True
    assert audit["approaches_exact_leading_monotonically"] is True
    assert audit["zero_field_joint_limit_controlled"] is True
    assert audit["physical_D1_certified"] is True

    diagnostic = audit_joint_zero_field_limit(
        {"full_cross_runs": rows},
        exact_leading=exact,
        physical_d1_candidate=False,
        maximum_d1_scheme_spread=0.1,
    )
    assert diagnostic["joint_limit_audit"]["zero_field_joint_limit_controlled"] is True
    assert diagnostic["joint_limit_audit"]["physical_D1_certified"] is False
