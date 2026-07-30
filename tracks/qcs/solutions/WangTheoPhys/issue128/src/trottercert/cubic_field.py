from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

from .intervals import RationalInterval


Rational = int | Fraction


@dataclass(frozen=True, slots=True)
class Cubic:
    """An exact element of ``Q[alpha] / (alpha**3 - 4)``."""

    a0: Fraction
    a1: Fraction
    a2: Fraction

    def __init__(self, a0: Rational, a1: Rational, a2: Rational) -> None:
        object.__setattr__(self, "a0", Fraction(a0))
        object.__setattr__(self, "a1", Fraction(a1))
        object.__setattr__(self, "a2", Fraction(a2))

    @classmethod
    def zero(cls) -> Cubic:
        return cls(0, 0, 0)

    @classmethod
    def one(cls) -> Cubic:
        return cls(1, 0, 0)

    @classmethod
    def coerce(cls, value: Cubic | Rational) -> Cubic:
        if isinstance(value, cls):
            return value
        if isinstance(value, (int, Fraction)):
            return cls(value, 0, 0)
        raise TypeError(f"cannot coerce {type(value).__name__} to Cubic")

    def __add__(self, other: Cubic | Rational) -> Cubic:
        rhs = self.coerce(other)
        return Cubic(
            self.a0 + rhs.a0,
            self.a1 + rhs.a1,
            self.a2 + rhs.a2,
        )

    __radd__ = __add__

    def __neg__(self) -> Cubic:
        return Cubic(-self.a0, -self.a1, -self.a2)

    def __sub__(self, other: Cubic | Rational) -> Cubic:
        return self + (-self.coerce(other))

    def __rsub__(self, other: Cubic | Rational) -> Cubic:
        return self.coerce(other) - self

    def __mul__(self, other: Cubic | Rational) -> Cubic:
        rhs = self.coerce(other)
        return Cubic(
            self.a0 * rhs.a0
            + 4 * (self.a1 * rhs.a2 + self.a2 * rhs.a1),
            self.a0 * rhs.a1
            + self.a1 * rhs.a0
            + 4 * self.a2 * rhs.a2,
            self.a0 * rhs.a2 + self.a1 * rhs.a1 + self.a2 * rhs.a0,
        )

    __rmul__ = __mul__

    def __truediv__(self, other: Rational) -> Cubic:
        denominator = Fraction(other)
        if denominator == 0:
            raise ZeroDivisionError("division by zero")
        return Cubic(
            self.a0 / denominator,
            self.a1 / denominator,
            self.a2 / denominator,
        )

    def __pow__(self, exponent: int) -> Cubic:
        if not isinstance(exponent, int):
            raise TypeError("Cubic exponent must be an integer")
        if exponent < 0:
            raise ValueError("negative Cubic powers are not implemented")
        result = self.one()
        base = self
        power = exponent
        while power:
            if power & 1:
                result = result * base
            base = base * base
            power >>= 1
        return result

    def enclose(self, root: RationalInterval) -> RationalInterval:
        """Enclose this element when ``alpha`` lies in ``root``."""

        return (
            RationalInterval.point(self.a0)
            + self.a1 * root
            + self.a2 * root**2
        )


@dataclass(frozen=True, slots=True)
class CubicStage:
    fragment_index: int
    coefficient: Cubic


def _second_order_cubic_stages(
    n_fragments: int,
    scale: Cubic,
) -> list[CubicStage]:
    half = scale / 2
    stages = [
        CubicStage(fragment_index, half)
        for fragment_index in range(n_fragments - 1)
    ]
    stages.append(CubicStage(n_fragments - 1, scale))
    stages.extend(
        CubicStage(fragment_index, half)
        for fragment_index in reversed(range(n_fragments - 1))
    )
    return stages


def _merge_cubic_stages(
    stages: Sequence[CubicStage],
) -> tuple[CubicStage, ...]:
    merged: list[CubicStage] = []
    for stage in stages:
        if merged and merged[-1].fragment_index == stage.fragment_index:
            previous = merged.pop()
            merged.append(
                CubicStage(
                    stage.fragment_index,
                    previous.coefficient + stage.coefficient,
                )
            )
        else:
            merged.append(stage)
    return tuple(merged)


def fourth_order_suzuki_cubic_stages(
    n_fragments: int = 4,
) -> tuple[CubicStage, ...]:
    """Return the fourth-order Suzuki stages with exact algebraic weights."""

    if n_fragments < 1:
        raise ValueError("number of fragments must be positive")
    # alpha**3 = 4 and 1 / (4 - alpha) = (16 + 4 alpha + alpha**2) / 60.
    u = Cubic(Fraction(4, 15), Fraction(1, 15), Fraction(1, 60))
    scales = (u, u, Cubic.one() - 4 * u, u, u)
    stages: list[CubicStage] = []
    for scale in scales:
        stages.extend(_second_order_cubic_stages(n_fragments, scale))
    return _merge_cubic_stages(stages)
