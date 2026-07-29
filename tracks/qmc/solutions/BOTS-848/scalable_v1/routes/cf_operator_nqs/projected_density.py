"""Electronic-LLL projected density multipoles on the Haldane sphere.

Orbitals are ordered by ``m_z=-Q,-Q+1,...,Q`` at fixed ``Q=two_q/2``.
The returned matrices use the Condon--Shortley Clebsch--Gordan convention

``<Q,m'|rho_bar[ell,m]|Q,m0> = sqrt(2*ell+1) <Q,m0;ell,m|Q,m'>``.

This operator normalization makes ``rho_bar[0,0]`` the identity.  A physical
spherical-harmonic form factor is a real, rank-dependent scalar and can be
absorbed into a variational scalar coefficient without changing the tensor
algebra, LLL closure, or the scalar contractions used by this route.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np


def _require_integer(name: str, value: object) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    return value


def _factorial(value: float) -> int:
    integer = round(value)
    if not math.isclose(value, integer, rel_tol=0.0, abs_tol=1.0e-12) or integer < 0:
        raise ValueError("invalid angular-momentum factorial")
    return math.factorial(integer)


@lru_cache(maxsize=None)
def _clebsch_gordan(
    j1: float,
    m1: float,
    j2: float,
    m2: float,
    total_j: float,
    total_m: float,
) -> float:
    """Return a Condon--Shortley Clebsch--Gordan coefficient.

    The finite Racah sum is sufficient here because all supported angular
    momenta are integer or half-integer and Route C uses modest electronic
    fluxes.  Factorial arguments are integral by the selection rules.
    """

    if not math.isclose(m1 + m2, total_m, rel_tol=0.0, abs_tol=1.0e-12):
        return 0.0
    if total_j < abs(j1 - j2) or total_j > j1 + j2:
        return 0.0
    if abs(m1) > j1 or abs(m2) > j2 or abs(total_m) > total_j:
        return 0.0

    prefactor_triangle = math.sqrt(
        (2.0 * total_j + 1.0)
        * _factorial(total_j + j1 - j2)
        * _factorial(total_j - j1 + j2)
        * _factorial(j1 + j2 - total_j)
        / _factorial(j1 + j2 + total_j + 1.0)
    )
    prefactor_m = math.sqrt(
        _factorial(total_j + total_m)
        * _factorial(total_j - total_m)
        * _factorial(j1 - m1)
        * _factorial(j1 + m1)
        * _factorial(j2 - m2)
        * _factorial(j2 + m2)
    )

    k_min = max(0, round(j2 - total_j - m1), round(j1 + m2 - total_j))
    k_max = min(
        round(j1 + j2 - total_j),
        round(j1 - m1),
        round(j2 + m2),
    )
    total = 0.0
    for k in range(k_min, k_max + 1):
        denominator = (
            _factorial(float(k))
            * _factorial(j1 + j2 - total_j - k)
            * _factorial(j1 - m1 - k)
            * _factorial(j2 + m2 - k)
            * _factorial(total_j - j2 + m1 + k)
            * _factorial(total_j - j1 - m2 + k)
        )
        total += (-1) ** k / denominator
    return prefactor_triangle * prefactor_m * total


def _validate_density_inputs(two_q: object, ell: object, m: object) -> tuple[int, int, int]:
    checked_two_q = _require_integer("two_q", two_q)
    checked_ell = _require_integer("ell", ell)
    checked_m = _require_integer("m", m)
    if checked_two_q <= 0:
        raise ValueError("two_q must be positive")
    if not 0 <= checked_ell <= checked_two_q:
        raise ValueError("ell must satisfy 0 <= ell <= two_q")
    if abs(checked_m) > checked_ell:
        raise ValueError("m must satisfy -ell <= m <= ell")
    return checked_two_q, checked_ell, checked_m


@lru_cache(maxsize=None)
def _projected_density_tensor(two_q: int, ell: int, m: int) -> np.ndarray:
    j = 0.5 * two_q
    matrix = np.zeros((two_q + 1, two_q + 1), dtype=np.complex128)
    normalization = math.sqrt(2 * ell + 1)
    for source in range(two_q + 1):
        source_m = source - j
        target = source + m
        if 0 <= target <= two_q:
            target_m = target - j
            matrix[target, source] = normalization * _clebsch_gordan(
                j, source_m, float(ell), float(m), j, target_m
            )
    matrix.setflags(write=False)
    return matrix


def projected_density_tensor(*, two_q: int, ell: int, m: int) -> np.ndarray:
    """Return the rank-``ell`` projected-density component ``m``.

    The matrix acts only among the ``two_q+1`` electronic LLL orbitals.  It
    therefore cannot change flux or create a higher-Landau-level component.
    Returned arrays are immutable because they are shared cached tensors.
    """

    checked = _validate_density_inputs(two_q, ell, m)
    return _projected_density_tensor(*checked)


__all__ = ["projected_density_tensor"]
