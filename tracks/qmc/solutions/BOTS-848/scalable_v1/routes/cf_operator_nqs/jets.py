"""Bounded Taylor jets for exact one-layer pair-coordinate action."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Number
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np


MultiIndex = tuple[int, int, int, int]
_ZERO_INDEX: MultiIndex = (0, 0, 0, 0)
_PARTICLE_DEGREE = 4


def _checked_axis(axis: object) -> int:
    if isinstance(axis, bool) or not isinstance(axis, int) or axis not in range(4):
        raise ValueError("pair-jet axis must be 0, 1, 2, or 3")
    return axis


@dataclass(frozen=True)
class PairJet:
    """Normalized four-variable Taylor coefficients through pair degree 4."""

    coefficients: Mapping[MultiIndex, complex]

    def __post_init__(self) -> None:
        checked: dict[MultiIndex, complex] = {}
        for index, value in self.coefficients.items():
            if not isinstance(index, tuple) or len(index) != 4 or any(
                isinstance(item, bool) or not isinstance(item, int) or item < 0
                for item in index
            ):
                raise ValueError("invalid pair-jet multi-index")
            if (
                sum(index[:2]) > _PARTICLE_DEGREE
                or sum(index[2:]) > _PARTICLE_DEGREE
            ):
                continue
            scalar = complex(value)
            if not np.isfinite(scalar.real) or not np.isfinite(scalar.imag):
                raise ValueError("pair-jet coefficients must be finite")
            if scalar != 0.0:
                checked[index] = scalar
        object.__setattr__(self, "coefficients", MappingProxyType(checked))

    @classmethod
    def constant(cls, value: complex) -> "PairJet":
        return cls({_ZERO_INDEX: complex(value)})

    @classmethod
    def variable(cls, value: complex, *, axis: int) -> "PairJet":
        checked_axis = _checked_axis(axis)
        unit = [0, 0, 0, 0]
        unit[checked_axis] = 1
        return cls({_ZERO_INDEX: complex(value), tuple(unit): 1.0})

    @property
    def constant_term(self) -> complex:
        return self.coefficients.get(_ZERO_INDEX, 0.0j)

    @staticmethod
    def _coerce(other: object) -> "PairJet" | None:
        if isinstance(other, PairJet):
            return other
        if isinstance(other, Number) and not isinstance(other, (bool, np.bool_)):
            return PairJet.constant(complex(other))
        return None

    def derivative(self, axis: int) -> "PairJet":
        checked_axis = _checked_axis(axis)
        result: dict[MultiIndex, complex] = {}
        for index, value in self.coefficients.items():
            if index[checked_axis] == 0:
                continue
            target = list(index)
            target[checked_axis] -= 1
            target_index = tuple(target)
            result[target_index] = (
                result.get(target_index, 0.0j) + index[checked_axis] * value
            )
        return PairJet(result)

    def __add__(self, other: object) -> "PairJet":
        checked = self._coerce(other)
        if checked is None:
            return NotImplemented
        result = dict(self.coefficients)
        for index, value in checked.coefficients.items():
            result[index] = result.get(index, 0.0j) + value
        return PairJet(result)

    __radd__ = __add__

    def __neg__(self) -> "PairJet":
        return PairJet(
            {index: -value for index, value in self.coefficients.items()}
        )

    def __sub__(self, other: object) -> "PairJet":
        checked = self._coerce(other)
        if checked is None:
            return NotImplemented
        return self + (-checked)

    def __rsub__(self, other: object) -> "PairJet":
        checked = self._coerce(other)
        if checked is None:
            return NotImplemented
        return checked - self

    def __mul__(self, other: object) -> "PairJet":
        checked = self._coerce(other)
        if checked is None:
            return NotImplemented
        result: dict[MultiIndex, complex] = {}
        for left_index, left_value in self.coefficients.items():
            for right_index, right_value in checked.coefficients.items():
                target = tuple(
                    left + right
                    for left, right in zip(left_index, right_index, strict=True)
                )
                if (
                    sum(target[:2]) <= _PARTICLE_DEGREE
                    and sum(target[2:]) <= _PARTICLE_DEGREE
                ):
                    result[target] = (
                        result.get(target, 0.0j) + left_value * right_value
                    )
        return PairJet(result)

    __rmul__ = __mul__

    def __pow__(self, exponent: int) -> "PairJet":
        if (
            isinstance(exponent, bool)
            or not isinstance(exponent, int)
            or exponent < 0
        ):
            raise ValueError("pair-jet exponent must be a nonnegative integer")
        result = PairJet.constant(1.0)
        factor = self
        power = exponent
        while power:
            if power & 1:
                result = result * factor
            factor = factor * factor
            power >>= 1
        return result


def jet_determinant(matrix: Sequence[Sequence[PairJet]]) -> PairJet:
    """Return a determinant over the jet ring without division or pivots."""

    n = len(matrix)
    if any(len(row) != n for row in matrix):
        raise ValueError("jet determinant matrix must be square")
    states = {0: PairJet.constant(1.0)}
    for row in range(n):
        next_states: dict[int, PairJet] = {}
        for mask, partial in states.items():
            for column in range(n):
                if mask & (1 << column):
                    continue
                occupied_after = (mask >> (column + 1)).bit_count()
                sign = -1.0 if occupied_after % 2 else 1.0
                new_mask = mask | (1 << column)
                term = sign * partial * matrix[row][column]
                next_states[new_mask] = next_states.get(
                    new_mask, PairJet.constant(0.0)
                ) + term
        states = next_states
    return states[(1 << n) - 1]


__all__ = ["MultiIndex", "PairJet", "jet_determinant"]
