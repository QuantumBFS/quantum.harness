"""Frozen coupling and normalization conventions.

Internal random-bond Ising convention:

    Z(tau) = sum_sigma exp(K * sum_b tau_b sigma_i sigma_j)
    Pr(tau_b = -1) = p
    exp(-2 K_N) = p / (1 - p)

Honecker, Picco, and Pujol use a local delta-energy convention whose beta is
twice this module's ``K``.  Keeping that conversion in one module prevents the
factor-of-two error from leaking into transfer-matrix code.
"""

from __future__ import annotations

import math

CLEAN_ISING_C = 0.5
NISHIMORI_C_TARGET = 0.464
NISHIMORI_C_TARGET_ERROR = 0.004
SELFDUAL_C_TARGET = 0.447
SELFDUAL_C_TARGET_ERROR = 0.001

NISHIMORI_PC = 0.1092212
NISHIMORI_PC_ERROR = 0.0000004

SELFDUAL_THETA = math.pi / 4.0
ISING_K_CRITICAL = 0.5 * math.log1p(math.sqrt(2.0))


def nishimori_coupling(p: float) -> float:
    """Return the standard Ising coupling K on the ferromagnetic branch."""

    if not 0.0 < p < 0.5:
        raise ValueError(f"expected 0 < p < 0.5, received p={p!r}")
    return 0.5 * math.log((1.0 - p) / p)


def honecker_beta(p: float) -> float:
    """Return beta in the delta-energy convention of cond-mat/0010143."""

    return 2.0 * nishimori_coupling(p)


def selfdual_couplings(theta: float) -> tuple[float, float]:
    """Return beta, beta' with tanh(beta)=sin(theta), tanh(beta')=cos(theta)."""

    if not 0.0 < theta < math.pi / 2.0:
        raise ValueError(
            f"expected 0 < theta < pi/2, received theta={theta!r}"
        )
    return math.atanh(math.sin(theta)), math.atanh(math.cos(theta))
