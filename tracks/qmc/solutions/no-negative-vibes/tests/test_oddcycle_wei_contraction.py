import sympy as sp

from oracle.oddcycle_wei_contraction import (
    SCHEMA,
    exact_common_metric_certificate,
)


def test_exact_common_metric_contraction_on_full_interval() -> None:
    result = exact_common_metric_certificate()

    assert result["schema"] == SCHEMA
    assert result["interval"] == (sp.Rational(99, 100), sp.Rational(101, 100))
    assert result["metric_signature"] == (1, 4)
    assert result["minimum_varying_bernstein_coefficients"] == (
        sp.Rational(1523807019, 68890000),
        sp.Rational(397103913, 68890000),
        sp.Rational(475092321, 68890000),
        sp.Rational(475092321, 68890000),
    )
    assert all(
        minor > 0
        for group in result["bernstein_coefficients"]
        for coefficients in group
        for minor in coefficients
    )
    assert "positive definite" in result["conclusion"]
