from decimal import Decimal

import pytest

from xxzcert.bethe import bethe_interval


def test_xx_encloses_known_decimal():
    iv = bethe_interval("0", 40)
    assert iv.contains(Decimal("-0.318309886183790671537767526745028724"))
    assert iv.width < Decimal("1e-14")


def test_xxx_encloses_known_decimal():
    iv = bethe_interval("1", 40)
    assert iv.contains(Decimal("-0.443147180559945309417232121458176568"))
    assert iv.width < Decimal("1e-14")


def test_ferromagnetic_formula_is_exact():
    assert bethe_interval("-2").as_strings() == ("-0.5", "-0.5")
    assert bethe_interval("-1").as_strings() == ("-0.25", "-0.25")


def test_root_of_unity_half_is_exact():
    assert bethe_interval("0.5").as_strings() == ("-0.375", "-0.375")


def test_massive_delta_two_encloses_reference():
    iv = bethe_interval("2", 30)
    assert iv.contains(Decimal("-0.6172220459758656"))
    assert iv.width < Decimal("1e-14")


@pytest.mark.parametrize(
    ("delta", "reference"),
    [
        ("-0.5", Decimal("-0.274519052838329")),
        ("0.9", Decimal("-0.4286")),
    ],
)
def test_general_gapless_interval_encloses_high_precision_reference(
    delta, reference
):
    iv = bethe_interval(delta, 20)
    assert iv.contains(reference)
    assert iv.width < Decimal("3e-4")
