"""Finite-sphere covariantization of the planar LHYR Coulomb pair source."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import comb, factorial, pi, sqrt
from types import MappingProxyType
from typing import Literal, Mapping

import numpy as np
from sympy import Rational
from sympy.physics.wigner import clebsch_gordan

from challenge15.spec import SphereSpec


Helicity = Literal["+", "-"]
TensorComponent = Literal[-2, -1, 0, 1, 2]
PairChannel = tuple[int, int]

_NORMALIZATION = "raw-LHYR-planar-Coulomb-E_C-resolution-eq-5.6"


@dataclass(frozen=True, slots=True)
class PairReducedSource:
    spec: SphereSpec
    orientation: Literal[-1, 1]
    helicity: Helicity
    values: Mapping[PairChannel, complex]
    normalization: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@lru_cache(maxsize=None)
def planar_coulomb_reduced_amplitudes(
    two_q: int,
) -> tuple[tuple[int, complex], ...]:
    """Return exact-sum planar LHYR amplitudes in ascending odd relative m."""

    if isinstance(two_q, bool) or not isinstance(two_q, int) or two_q < 3:
        raise ValueError("two_q must be an integer at least 3")

    amplitudes: list[tuple[int, complex]] = []
    for relative_m in range(1, two_q - 1, 2):
        gamma_sum_without_sqrt_pi = Fraction(0)
        for k in range(relative_m + 1):
            gamma_without_sqrt_pi = Fraction(
                factorial(2 * k + 4),
                4 ** (k + 2) * factorial(k + 2),
            )
            gamma_sum_without_sqrt_pi += (
                (-1) ** k
                * comb(relative_m + 2, relative_m - k)
                * gamma_without_sqrt_pi
                / factorial(k)
            )
        amplitude = (
            float(gamma_sum_without_sqrt_pi)
            * sqrt(pi)
            / (2.0 * sqrt((relative_m + 1) * (relative_m + 2)))
        )
        if amplitude <= 0.0:
            raise ArithmeticError(
                f"nonpositive LHYR amplitude for relative m={relative_m}"
            )
        amplitudes.append((relative_m, complex(amplitude, 0.0)))
    return tuple(amplitudes)


def lhyr_pair_reduced_source(
    spec: SphereSpec,
    helicity: Helicity,
    *,
    orientation: Literal[-1, 1] = 1,
) -> PairReducedSource:
    """Build one physical-amplitude family of reduced pair channels."""

    if helicity not in ("+", "-"):
        raise ValueError("helicity must be '+' or '-'")
    if (
        isinstance(orientation, bool)
        or not isinstance(orientation, int)
        or orientation not in (-1, 1)
    ):
        raise ValueError("orientation must be -1 or 1")

    minus_values = {
        (spec.two_q - relative_m, spec.two_q - relative_m - 2): amplitude
        for relative_m, amplitude in planar_coulomb_reduced_amplitudes(spec.two_q)
    }
    values = (
        minus_values
        if helicity == "-"
        else {(ket, bra): value for (bra, ket), value in minus_values.items()}
    )
    return PairReducedSource(
        spec=spec,
        orientation=orientation,
        helicity=helicity,
        values=values,
        normalization=_NORMALIZATION,
    )


def _minus_pair_source_tensor(
    source: PairReducedSource,
    component_m: TensorComponent,
) -> np.ndarray:
    """Reconstruct minus at +Q; define -Q by antiunitary reversal.

    The approved source fixes a direct coupled-pair formula only at positive
    orientation. Negative orientation is therefore a construction definition,
    not a second independently derived microscopic source.
    """

    _validate_component(component_m)
    if source.helicity != "-":
        raise ValueError("_minus_pair_source_tensor requires a minus source")

    tensor = _direct_minus_pair_source_tensor(source, component_m)
    if source.orientation == 1:
        return tensor

    orbital_phases = np.asarray(
        [
            (-1) ** ((source.spec.two_q - two_m) // 2)
            for two_m in source.spec.two_m_values
        ],
        dtype=np.float64,
    )
    reversed_transpose = tensor.transpose(2, 3, 0, 1)[
        ::-1, ::-1, ::-1, ::-1
    ]
    reversed_transpose *= np.einsum(
        "a,b,c,d->abcd",
        orbital_phases[::-1],
        orbital_phases[::-1],
        orbital_phases[::-1],
        orbital_phases[::-1],
    )
    _zero_forbidden_components(reversed_transpose, source.spec, component_m)
    return np.asarray(reversed_transpose, dtype=np.complex128)


def _direct_minus_pair_source_tensor(
    source: PairReducedSource,
    component_m: TensorComponent,
) -> np.ndarray:
    """Apply the repository Wigner-Eckart convention at positive monopole sign."""

    count = source.spec.orbital_count
    tensor = np.zeros((count, count, count, count), dtype=np.complex128)
    for (j_bra, j_ket), reduced in source.values.items():
        for m_ket in range(-j_ket, j_ket + 1):
            m_bra = m_ket + component_m
            if abs(m_bra) > j_bra:
                continue
            rank_coefficient = _clebsch(
                2 * j_ket,
                2 * m_ket,
                4,
                2 * component_m,
                2 * j_bra,
                2 * m_bra,
            )
            if rank_coefficient == 0.0:
                continue
            bra = _pair_coefficients(source.spec.two_q, j_bra, m_bra)
            ket = _pair_coefficients(source.spec.two_q, j_ket, m_ket)
            tensor += reduced * rank_coefficient * np.einsum(
                "ab,cd->abcd", bra, ket
            )

    tensor = 0.5 * (tensor - tensor.swapaxes(2, 3))
    tensor = 0.5 * (tensor - tensor.swapaxes(0, 1))
    _zero_forbidden_components(tensor, source.spec, component_m)
    return np.asarray(tensor, dtype=np.complex128)


def pair_source_tensor(
    source: PairReducedSource,
    component_m: TensorComponent,
) -> np.ndarray:
    """Return a covariant orbital tensor, deriving plus only by adjunction."""

    _validate_component(component_m)
    if source.helicity == "-":
        return _minus_pair_source_tensor(source, component_m)
    if source.helicity != "+":
        raise ValueError("helicity must be '+' or '-'")

    minus = lhyr_pair_reduced_source(
        source.spec, "-", orientation=source.orientation
    )
    expected_plus_values = {
        (ket, bra): value for (bra, ket), value in minus.values.items()
    }
    if (
        source.normalization != _NORMALIZATION
        or dict(source.values) != expected_plus_values
    ):
        raise ValueError("plus source values must equal the physical amplitudes")
    minus_tensor = _minus_pair_source_tensor(minus, -component_m)
    phase = -1.0 if component_m % 2 else 1.0
    return np.asarray(
        phase * minus_tensor.conj().transpose(2, 3, 0, 1),
        dtype=np.complex128,
    )


def _validate_component(component_m: object) -> None:
    if (
        isinstance(component_m, bool)
        or not isinstance(component_m, int)
        or component_m not in (-2, -1, 0, 1, 2)
    ):
        raise ValueError("component_m must be one of -2, -1, 0, 1, 2")


@lru_cache(maxsize=None)
def _pair_coefficients(two_q: int, total_j: int, total_m: int) -> np.ndarray:
    two_m_values = tuple(range(-two_q, two_q + 1, 2))
    coefficients = np.zeros(
        (two_q + 1, two_q + 1), dtype=np.complex128
    )
    for a, two_ma in enumerate(two_m_values):
        for b, two_mb in enumerate(two_m_values):
            if two_ma + two_mb != 2 * total_m:
                continue
            coefficients[a, b] = _clebsch(
                two_q,
                two_ma,
                two_q,
                two_mb,
                2 * total_j,
                2 * total_m,
            )
    coefficients.flags.writeable = False
    return coefficients


def _zero_forbidden_components(
    tensor: np.ndarray,
    spec: SphereSpec,
    component_m: int,
) -> None:
    for a, two_ma in enumerate(spec.two_m_values):
        for b, two_mb in enumerate(spec.two_m_values):
            for c, two_mc in enumerate(spec.two_m_values):
                for d, two_md in enumerate(spec.two_m_values):
                    if (
                        two_ma + two_mb - two_mc - two_md
                        != 2 * component_m
                    ):
                        tensor[a, b, c, d] = 0.0


@lru_cache(maxsize=None)
def _clebsch(
    two_j1: int,
    two_m1: int,
    two_j2: int,
    two_m2: int,
    two_j3: int,
    two_m3: int,
) -> float:
    return float(
        clebsch_gordan(
            Rational(two_j1, 2),
            Rational(two_j2, 2),
            Rational(two_j3, 2),
            Rational(two_m1, 2),
            Rational(two_m2, 2),
            Rational(two_m3, 2),
        )
    )
