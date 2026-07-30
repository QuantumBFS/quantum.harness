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
from decimal import Decimal, localcontext
from functools import lru_cache
from numbers import Integral

import numpy as np


MAX_PROJECTED_DENSITY_TWO_Q = 127
"""Largest flux verified for the fixed-precision projected-density kernel."""


def _require_integer(name: str, value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    return int(value)


def _validate_density_inputs(two_q: object, ell: object, m: object) -> tuple[int, int, int]:
    checked_two_q = _require_integer("two_q", two_q)
    checked_ell = _require_integer("ell", ell)
    checked_m = _require_integer("m", m)
    if checked_two_q <= 0:
        raise ValueError("two_q must be positive")
    if checked_two_q > MAX_PROJECTED_DENSITY_TWO_Q:
        raise ValueError(
            f"two_q must be <= {MAX_PROJECTED_DENSITY_TWO_Q} for verified "
            "projected-density numerics"
        )
    if not 0 <= checked_ell <= checked_two_q:
        raise ValueError("ell must satisfy 0 <= ell <= two_q")
    if abs(checked_m) > checked_ell:
        raise ValueError("m must satisfy -ell <= m <= ell")
    return checked_two_q, checked_ell, checked_m


_CG_DECIMAL_PRECISION = 80


def _factorial_argument(value: float) -> int:
    integer = round(value)
    if not math.isclose(value, integer, rel_tol=0.0, abs_tol=1.0e-12) or integer < 0:
        raise ValueError("invalid angular-momentum factorial")
    return integer


@lru_cache(maxsize=None)
def _log_factorial(integer: int) -> Decimal:
    with localcontext() as context:
        context.prec = _CG_DECIMAL_PRECISION
        return Decimal(math.factorial(integer)).ln()


@lru_cache(maxsize=None)
def _clebsch_gordan(
    j1: float,
    m1: float,
    j2: float,
    m2: float,
    total_j: float,
    total_m: float,
) -> float:
    """Return a log-scaled Condon--Shortley CG coefficient."""

    if not math.isclose(m1 + m2, total_m, rel_tol=0.0, abs_tol=1.0e-12):
        return 0.0
    if total_j < abs(j1 - j2) or total_j > j1 + j2:
        return 0.0
    if abs(m1) > j1 or abs(m2) > j2 or abs(total_m) > total_j:
        return 0.0

    with localcontext() as context:
        context.prec = _CG_DECIMAL_PRECISION
        log_prefactor = (
            Decimal(_factorial_argument(2.0 * total_j + 1.0)).ln()
            + _log_factorial(_factorial_argument(total_j + j1 - j2))
            + _log_factorial(_factorial_argument(total_j - j1 + j2))
            + _log_factorial(_factorial_argument(j1 + j2 - total_j))
            - _log_factorial(_factorial_argument(j1 + j2 + total_j + 1.0))
            + _log_factorial(_factorial_argument(total_j + total_m))
            + _log_factorial(_factorial_argument(total_j - total_m))
            + _log_factorial(_factorial_argument(j1 - m1))
            + _log_factorial(_factorial_argument(j1 + m1))
            + _log_factorial(_factorial_argument(j2 - m2))
            + _log_factorial(_factorial_argument(j2 + m2))
        ) / 2

        k_min = max(0, round(j2 - total_j - m1), round(j1 + m2 - total_j))
        k_max = min(
            round(j1 + j2 - total_j),
            round(j1 - m1),
            round(j2 + m2),
        )
        signed_logs: list[tuple[int, Decimal]] = []
        for k in range(k_min, k_max + 1):
            log_denominator = sum(
                (
                    _log_factorial(_factorial_argument(argument))
                    for argument in (
                        float(k),
                        j1 + j2 - total_j - k,
                        j1 - m1 - k,
                        j2 + m2 - k,
                        total_j - j2 + m1 + k,
                        total_j - j1 - m2 + k,
                    )
                ),
                Decimal(0),
            )
            signed_logs.append(((-1) ** k, -log_denominator))
        if not signed_logs:
            return 0.0
        common_scale = max(log_term for _, log_term in signed_logs)
        scaled_sum = sum(
            (
                Decimal(sign) * (log_term - common_scale).exp()
                for sign, log_term in signed_logs
            ),
            Decimal(0),
        )
        if scaled_sum == 0:
            return 0.0
        magnitude = (
            log_prefactor + common_scale + abs(scaled_sum).ln()
        ).exp()
        return math.copysign(float(magnitude), float(scaled_sum))


@lru_cache(maxsize=None)
def _projected_density_tensor(two_q: int, ell: int, m: int) -> np.ndarray:
    j = 0.5 * two_q
    matrix = np.zeros((two_q + 1, two_q + 1), dtype=np.complex128)
    normalization = math.sqrt(2 * ell + 1)
    for source in range(two_q + 1):
        target = source + m
        if 0 <= target <= two_q:
            matrix[target, source] = normalization * _clebsch_gordan(
                j,
                source - j,
                float(ell),
                float(m),
                j,
                target - j,
            )
    matrix.setflags(write=False)
    return matrix


def projected_density_tensor(*, two_q: int, ell: int, m: int) -> np.ndarray:
    """Return the rank-``ell`` projected-density component ``m``.

    The matrix acts only among the ``two_q+1`` electronic LLL orbitals.  It
    therefore cannot change flux or create a higher-Landau-level component.
    This tensor-only interface supports ``two_q`` through
    :data:`MAX_PROJECTED_DENSITY_TWO_Q`; that verified numerical cap is
    independent of the signed-``int64`` occupation backend's lower limit.
    Returned arrays are immutable because they are shared cached tensors.
    """

    checked = _validate_density_inputs(two_q, ell, m)
    return _projected_density_tensor(*checked)


__all__ = ["MAX_PROJECTED_DENSITY_TWO_Q", "projected_density_tensor"]
