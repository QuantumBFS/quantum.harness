import pytest

from lrtfim.phase7_reporting import (
    convergence_flags,
    endpoint_chi_validation,
    interpolate_endpoint_value,
    two_size_power_exponent,
    z_eff_from_gaps,
)


def test_endpoint_chi_validation_checks_shift_signs_and_bracket() -> None:
    result = endpoint_chi_validation(
        r_small=[0.40, 0.50],
        r_large_chi64=[0.45, 0.45],
        r_large_chi128=[0.450003, 0.450002],
        threshold=1.0e-4,
    )

    assert result["accepted"]
    assert result["signs_unchanged"]
    assert result["bracket_unchanged"]
    assert result["max_abs_r_xi_shift"] == pytest.approx(3.0e-6)


def test_gap_interpolation_and_effective_z() -> None:
    delta32 = interpolate_endpoint_value(
        1.55,
        1.60,
        0.14,
        0.22,
        1.575,
    )
    delta64 = interpolate_endpoint_value(
        1.55,
        1.60,
        0.07,
        0.15,
        1.575,
    )

    assert delta32 == pytest.approx(0.18)
    assert delta64 == pytest.approx(0.11)
    assert z_eff_from_gaps(delta32, delta64) == pytest.approx(
        0.7104933828050151
    )


def test_two_size_power_exponent_uses_declared_size_ratio() -> None:
    assert two_size_power_exponent(4.0, 8.0, size_ratio=2.0) == pytest.approx(
        1.0
    )
    with pytest.raises(ValueError, match="positive"):
        two_size_power_exponent(0.0, 8.0, size_ratio=2.0)


def test_convergence_flags_keep_sector_diagnostics_separate() -> None:
    state = {
        "energy": -100.0,
        "variance": 2.0e-7,
        "discarded_weight": 5.0e-9,
        "sweeps": 18,
        "reached_chi": 128,
    }
    assert convergence_flags(state, max_sweeps=30) == []

    unstable = dict(state, variance=2.0e-6, discarded_weight=2.0e-8)
    assert convergence_flags(unstable, max_sweeps=30) == [
        "relative_variance",
        "discarded_weight",
    ]
