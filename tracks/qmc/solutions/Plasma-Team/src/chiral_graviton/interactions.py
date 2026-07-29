"""Rotationally invariant two-body interactions on the Haldane sphere."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from sympy import Rational
from sympy.physics.wigner import wigner_3j


def _half(value: int):
    return Rational(value, 2)


@lru_cache(maxsize=None)
def _wigner_3j_float(
    two_j1: int,
    two_j2: int,
    two_j3: int,
    two_m1: int,
    two_m2: int,
    two_m3: int,
) -> float:
    return float(
        wigner_3j(
            _half(two_j1),
            _half(two_j2),
            _half(two_j3),
            _half(two_m1),
            _half(two_m2),
            _half(two_m3),
        )
    )


@lru_cache(maxsize=None)
def clebsch_gordan_equal_shell(
    two_q: int, two_m1: int, two_m2: int, pair_j: int, pair_m: int
) -> float:
    """Return <Q,m1;Q,m2|J,M> using the Condon-Shortley convention."""

    if two_m1 + two_m2 != 2 * pair_m:
        return 0.0
    # <j1m1 j2m2|JM> = (-1)^(j1-j2+M) sqrt(2J+1)
    #                       (j1 j2 J; m1 m2 -M).
    phase = -1.0 if pair_m % 2 else 1.0
    return phase * np.sqrt(2 * pair_j + 1) * _wigner_3j_float(
        two_q, two_q, 2 * pair_j, two_m1, two_m2, -2 * pair_m
    )


@lru_cache(maxsize=None)
def _density_harmonic_element(
    two_q: int, bra_two_m: int, ket_two_m: int, rank: int, component: int
) -> float:
    """Matrix element <Q,m'|Y_{kq}|Q,m> for an LLL monopole shell."""

    if bra_two_m - ket_two_m != 2 * component:
        return 0.0
    phase_power = (two_q + bra_two_m) // 2
    phase = -1.0 if phase_power % 2 else 1.0
    prefactor = (two_q + 1) * np.sqrt((2 * rank + 1) / (4.0 * np.pi))
    orbital = _wigner_3j_float(
        two_q, 2 * rank, two_q, -bra_two_m, 2 * component, ket_two_m
    )
    monopole = _wigner_3j_float(two_q, 2 * rank, two_q, -two_q, 0, two_q)
    return phase * prefactor * orbital * monopole


@lru_cache(maxsize=None)
def orbital_coulomb_element(
    two_q: int, bra_a: int, bra_b: int, ket_c: int, ket_d: int
) -> float:
    """Return <a,b|1/r12|c,d> in units e^2/(epsilon*l_B).

    Orbitals are integer indices in increasing m. The interaction uses the
    three-dimensional chord distance on a sphere of radius sqrt(Q)*l_B.
    """

    if two_q <= 0:
        raise ValueError("CG001: Coulomb sphere requires Q>0")
    two_m = tuple(range(-two_q, two_q + 1, 2))
    ma, mb, mc, md = (two_m[i] for i in (bra_a, bra_b, ket_c, ket_d))
    if ma + mb != mc + md:
        return 0.0

    value = 0.0
    for rank in range(two_q + 1):
        for component in range(-rank, rank + 1):
            # Y*_{kq}=(-1)^q Y_{k,-q}.
            first = _density_harmonic_element(two_q, ma, mc, rank, -component)
            if first == 0.0:
                continue
            second = _density_harmonic_element(two_q, mb, md, rank, component)
            if second == 0.0:
                continue
            phase = -1.0 if component % 2 else 1.0
            value += 4.0 * np.pi / (2 * rank + 1) * phase * first * second
    return float(value / np.sqrt(two_q / 2.0))


@lru_cache(maxsize=None)
def coulomb_pseudopotentials(two_q: int) -> dict[int, float]:
    """Chord-Coulomb Haldane pseudopotentials keyed by relative momentum."""

    if two_q <= 0:
        raise ValueError("CG001: Coulomb sphere requires Q>0")
    two_m_values = tuple(range(-two_q, two_q + 1, 2))
    output: dict[int, float] = {}
    for relative_m in range(two_q + 1):
        pair_j = two_q - relative_m
        pair_m = pair_j
        coupled: list[tuple[int, int, float]] = []
        for a, ma in enumerate(two_m_values):
            for b, mb in enumerate(two_m_values):
                coefficient = clebsch_gordan_equal_shell(two_q, ma, mb, pair_j, pair_m)
                if abs(coefficient) > 1e-15:
                    coupled.append((a, b, coefficient))
        value = 0.0
        for a, b, left in coupled:
            for c, d, right in coupled:
                value += left * right * orbital_coulomb_element(two_q, a, b, c, d)
        output[relative_m] = float(value)
    return output


def v1_pseudopotentials(two_q: int) -> dict[int, float]:
    """Return the fermionic Laughlin parent interaction V_1=1."""

    if two_q < 1:
        raise ValueError("CG001: V1 requires at least two orbitals")
    return {relative_m: float(relative_m == 1) for relative_m in range(two_q + 1)}


@dataclass(frozen=True)
class PairTable:
    """Antisymmetrized matrix elements between ordered orbital pairs a<b."""

    two_q: int
    pairs: tuple[tuple[int, int], ...]
    matrix: np.ndarray


def pair_matrix_elements(two_q: int, pseudopotentials: dict[int, float]) -> PairTable:
    """Transform pair-channel pseudopotentials to an antisymmetric pair basis."""

    two_m = tuple(range(-two_q, two_q + 1, 2))
    pairs = tuple((a, b) for a in range(two_q + 1) for b in range(a + 1, two_q + 1))
    matrix = np.zeros((len(pairs), len(pairs)), dtype=np.float64)

    for row, (a, b) in enumerate(pairs):
        total_two_m = two_m[a] + two_m[b]
        for col, (c, d) in enumerate(pairs):
            if total_two_m != two_m[c] + two_m[d]:
                continue
            value = 0.0
            for relative_m, pseudo in pseudopotentials.items():
                if relative_m % 2 == 0 or pseudo == 0.0:
                    continue
                pair_j = two_q - relative_m
                pair_m = total_two_m // 2
                left = clebsch_gordan_equal_shell(
                    two_q, two_m[a], two_m[b], pair_j, pair_m
                )
                right = clebsch_gordan_equal_shell(
                    two_q, two_m[c], two_m[d], pair_j, pair_m
                )
                value += 2.0 * pseudo * left * right
            matrix[row, col] = value

    matrix = 0.5 * (matrix + matrix.T)
    return PairTable(two_q=two_q, pairs=pairs, matrix=matrix)
