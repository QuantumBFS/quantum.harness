from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import floor


@dataclass(frozen=True, slots=True)
class RationalInterval:
    lower: Fraction
    upper: Fraction

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise ValueError("interval lower endpoint exceeds upper endpoint")

    @classmethod
    def point(cls, value: int | Fraction) -> RationalInterval:
        exact = value if isinstance(value, Fraction) else Fraction(value)
        return cls(exact, exact)

    def __add__(
        self,
        other: RationalInterval | int | Fraction,
    ) -> RationalInterval:
        rhs = other if isinstance(other, RationalInterval) else self.point(other)
        return RationalInterval(self.lower + rhs.lower, self.upper + rhs.upper)

    __radd__ = __add__

    def __neg__(self) -> RationalInterval:
        return RationalInterval(-self.upper, -self.lower)

    def __sub__(
        self,
        other: RationalInterval | int | Fraction,
    ) -> RationalInterval:
        rhs = other if isinstance(other, RationalInterval) else self.point(other)
        return self + (-rhs)

    def __rsub__(
        self,
        other: RationalInterval | int | Fraction,
    ) -> RationalInterval:
        return self.point(other) - self

    def __mul__(
        self,
        other: RationalInterval | int | Fraction,
    ) -> RationalInterval:
        rhs = other if isinstance(other, RationalInterval) else self.point(other)
        values = (
            self.lower * rhs.lower,
            self.lower * rhs.upper,
            self.upper * rhs.lower,
            self.upper * rhs.upper,
        )
        return RationalInterval(min(values), max(values))

    __rmul__ = __mul__

    def reciprocal(self) -> RationalInterval:
        if self.lower <= 0 <= self.upper:
            raise ZeroDivisionError("interval contains zero")
        return RationalInterval(1 / self.upper, 1 / self.lower)

    def __truediv__(
        self,
        other: RationalInterval | int | Fraction,
    ) -> RationalInterval:
        rhs = other if isinstance(other, RationalInterval) else self.point(other)
        return self * rhs.reciprocal()

    def __pow__(self, exponent: int) -> RationalInterval:
        if exponent < 0:
            return (self.reciprocal()) ** (-exponent)
        result = self.point(1)
        base = self
        power = exponent
        while power:
            if power & 1:
                result = result * base
            base = base * base
            power >>= 1
        return result

    def abs_upper(self) -> Fraction:
        return max(abs(self.lower), abs(self.upper))

    def abs_lower(self) -> Fraction:
        if self.lower <= 0 <= self.upper:
            return Fraction()
        return min(abs(self.lower), abs(self.upper))

    def midpoint(self) -> Fraction:
        return (self.lower + self.upper) / 2


def cube_root_four_interval(decimal_digits: int = 24) -> RationalInterval:
    """Return a rational enclosure of the real cube root of four."""

    return nth_root_four_interval(3, decimal_digits)


def nth_root_four_interval(
    root_degree: int,
    decimal_digits: int = 24,
) -> RationalInterval:
    """Return a rational enclosure of the positive ``root_degree`` root of four."""

    if root_degree < 1:
        raise ValueError("root degree must be positive")
    if decimal_digits < 1:
        raise ValueError("decimal_digits must be positive")
    denominator = 10**decimal_digits
    low = denominator
    high = 4 * denominator
    target = 4 * denominator**root_degree
    while low + 1 < high:
        middle = (low + high) // 2
        if middle**root_degree <= target:
            low = middle
        else:
            high = middle
    return RationalInterval(
        Fraction(low, denominator),
        Fraction(high, denominator),
    )


def outward_quantize(
    interval: RationalInterval,
    denominator: int,
) -> RationalInterval:
    """Round an interval outward onto a fixed rational grid."""

    if denominator <= 0:
        raise ValueError("denominator must be positive")
    lower_scaled = interval.lower * denominator
    upper_scaled = interval.upper * denominator
    lower_integer = lower_scaled.numerator // lower_scaled.denominator
    upper_integer = -((-upper_scaled.numerator) // upper_scaled.denominator)
    return RationalInterval(
        Fraction(lower_integer, denominator),
        Fraction(upper_integer, denominator),
    )
