from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from .algebra import PauliSum, QComplex


@dataclass
class OperatorSeries:
    """A truncated power series whose coefficients are exact operators."""

    coefficients: list[PauliSum]

    @classmethod
    def zero(cls, order: int) -> OperatorSeries:
        return cls([PauliSum.zero() for _ in range(order + 1)])

    @classmethod
    def identity(cls, order: int) -> OperatorSeries:
        result = cls.zero(order)
        result.coefficients[0] = PauliSum.identity()
        return result

    @property
    def order(self) -> int:
        return len(self.coefficients) - 1

    def __add__(self, other: OperatorSeries) -> OperatorSeries:
        if self.order != other.order:
            raise ValueError("series truncation orders differ")
        return OperatorSeries(
            [left + right for left, right in zip(self.coefficients, other.coefficients)]
        )

    def __sub__(self, other: OperatorSeries) -> OperatorSeries:
        return self + other.scale(-1)

    def scale(self, scalar: QComplex | int | Fraction) -> OperatorSeries:
        return OperatorSeries([coefficient.scale(scalar) for coefficient in self.coefficients])

    def __mul__(self, other: OperatorSeries) -> OperatorSeries:
        if self.order != other.order:
            raise ValueError("series truncation orders differ")
        result = self.zero(self.order)
        for degree in range(self.order + 1):
            coefficient = PauliSum.zero()
            for left_degree in range(degree + 1):
                coefficient += (
                    self.coefficients[left_degree]
                    * other.coefficients[degree - left_degree]
                )
            result.coefficients[degree] = coefficient
        return result

    def power(self, exponent: int) -> OperatorSeries:
        if exponent < 0:
            raise ValueError("negative series powers are unsupported")
        result = self.identity(self.order)
        base = self
        for _ in range(exponent):
            result = result * base
        return result


def exponential_series(
    generator: PauliSum,
    coefficient: QComplex | int | Fraction,
    order: int,
) -> OperatorSeries:
    """Return exp(t * coefficient * generator) through ``t**order``."""

    result = OperatorSeries.zero(order)
    power = PauliSum.identity()
    scalar = QComplex.coerce(coefficient)
    scalar_power = QComplex(1)
    factorial = 1
    for degree in range(order + 1):
        if degree:
            power = power * generator
            scalar_power *= scalar
            factorial *= degree
        result.coefficients[degree] = power.scale(scalar_power / factorial)
    return result


def product_series(stages: Iterable[OperatorSeries], order: int) -> OperatorSeries:
    result = OperatorSeries.identity(order)
    for stage in stages:
        if stage.order != order:
            raise ValueError("stage truncation order differs")
        result = result * stage
    return result


def logarithm_series(series: OperatorSeries) -> OperatorSeries:
    if series.coefficients[0] != PauliSum.identity():
        raise ValueError("logarithm requires unit constant coefficient")
    delta = series - OperatorSeries.identity(series.order)
    result = OperatorSeries.zero(series.order)
    power = OperatorSeries.identity(series.order)
    for exponent in range(1, series.order + 1):
        power = power * delta
        sign = 1 if exponent % 2 else -1
        result = result + power.scale(Fraction(sign, exponent))
    return result
