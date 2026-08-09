from fractions import Fraction

from trottercert.intervals import (
    RationalInterval,
    cube_root_four_interval,
    outward_quantize,
)


def test_rational_interval_arithmetic_and_root_enclosure() -> None:
    left = RationalInterval(Fraction(1, 3), Fraction(1, 2))
    right = RationalInterval(Fraction(-2), Fraction(-1))
    assert left + right == RationalInterval(Fraction(-5, 3), Fraction(-1, 2))
    assert left * right == RationalInterval(Fraction(-1), Fraction(-1, 3))
    root = cube_root_four_interval(12)
    assert root.lower**3 <= 4 <= root.upper**3
    assert root.upper - root.lower == Fraction(1, 10**12)


def test_outward_quantize_contains_original_interval() -> None:
    interval = RationalInterval(Fraction(1, 3), Fraction(5, 7))
    rounded = outward_quantize(interval, 10)
    assert rounded.lower <= interval.lower
    assert rounded.upper >= interval.upper
    assert rounded == RationalInterval(Fraction(3, 10), Fraction(4, 5))
