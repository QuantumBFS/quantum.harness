from __future__ import annotations

from fractions import Fraction

import pytest

from trottercert.cubic_field import (
    Cubic,
    fourth_order_suzuki_cubic_stages,
)
from trottercert.intervals import cube_root_four_interval
from trottercert.rigorous_fourth import fourth_order_suzuki_interval_stages


def test_cubic_multiplication_reduces_alpha_cubed() -> None:
    alpha = Cubic(0, 1, 0)
    assert alpha * alpha * alpha == Cubic(4, 0, 0)
    assert alpha**4 == Cubic(0, 4, 0)


def test_exact_suzuki_scale_is_inverse_of_four_minus_alpha() -> None:
    alpha = Cubic(0, 1, 0)
    u = Cubic(Fraction(4, 15), Fraction(1, 15), Fraction(1, 60))
    assert u * (Cubic(4, 0, 0) - alpha) == Cubic.one()


def test_cubic_ring_arithmetic_and_rational_division() -> None:
    left = Cubic(Fraction(1, 3), Fraction(2, 5), Fraction(-7, 11))
    right = Cubic(Fraction(-2, 7), Fraction(3, 13), Fraction(5, 17))
    assert left + right - right == left
    assert 2 * left == left * 2
    assert left / 3 == Cubic(
        Fraction(1, 9), Fraction(2, 15), Fraction(-7, 33)
    )
    assert left**0 == Cubic.one()
    with pytest.raises(ValueError, match="negative"):
        _ = left**-1
    with pytest.raises(ZeroDivisionError):
        _ = left / 0


def test_exact_stages_enclose_inside_existing_interval_stages() -> None:
    exact = fourth_order_suzuki_cubic_stages(4)
    interval, root = fourth_order_suzuki_interval_stages(
        4, decimal_digits=24
    )
    assert len(exact) == len(interval) == 31
    for left, right in zip(exact, interval):
        assert left.fragment_index == right.fragment_index
        enclosed = left.coefficient.enclose(root)
        assert right.coefficient.lower <= enclosed.lower
        assert enclosed.upper <= right.coefficient.upper


def test_exact_stage_sum_is_one_for_every_fragment() -> None:
    stages = fourth_order_suzuki_cubic_stages(4)
    for fragment in range(4):
        assert sum(
            (
                stage.coefficient
                for stage in stages
                if stage.fragment_index == fragment
            ),
            Cubic.zero(),
        ) == Cubic.one()


def test_cubic_interval_enclosure_contains_high_precision_root_value() -> None:
    value = Cubic(Fraction(3, 7), Fraction(-5, 11), Fraction(13, 17))
    root = cube_root_four_interval(30)
    interval = value.enclose(root)
    midpoint = (root.lower + root.upper) / 2
    evaluated = value.a0 + value.a1 * midpoint + value.a2 * midpoint**2
    assert interval.lower <= evaluated <= interval.upper
