"""Discrete Feynman-Vernon coefficients for piecewise-constant paths."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import quad

from .bath import bath_correlation
from .config import BathConfig


@dataclass(frozen=True)
class InfluenceCoefficients:
    values: NDArray[np.complex128]
    dt: float
    quadrature_error: float
    tail_bound: float


def _integrate_complex(
    function: Callable[[float], complex], low: float, high: float
) -> tuple[complex, float]:
    real, real_error = quad(lambda x: np.real(function(x)), low, high, epsabs=2e-11)
    imag, imag_error = quad(lambda x: np.imag(function(x)), low, high, epsabs=2e-11)
    return complex(real, imag), float(real_error + imag_error)


def discretize_influence(
    bath: BathConfig,
    dt: float,
    memory_steps: int,
) -> InfluenceCoefficients:
    """Cell-integrate the bath correlation.

    ``eta[0]`` uses the causal triangle in a single time cell. ``eta[k>0]``
    uses two full cells separated by ``k`` timesteps.
    """
    if dt <= 0 or memory_steps < 1:
        raise ValueError("dt and memory_steps must be positive")
    values = np.empty(memory_steps + 1, dtype=np.complex128)
    error = 0.0

    # eta_0 = integral_0^dt du integral_0^u dv C(u-v)
    value0, error0 = _integrate_complex(
        lambda tau: (dt - tau) * bath_correlation(tau, bath), 0, dt
    )
    values[0] = value0
    error += error0

    for lag in range(1, memory_steps + 1):
        # Difference of two points from equal-width cells has triangular weight.
        center = lag * dt

        def integrand(offset: float, center: float = center) -> complex:
            return (dt - abs(offset)) * bath_correlation(center + offset, bath)

        value, item_error = _integrate_complex(
            integrand,
            -dt,
            dt,
        )
        values[lag] = value
        error += item_error

    memory_time = memory_steps * dt
    tail_bound = bath.alpha / max(1 / bath.cutoff, memory_time)
    return InfluenceCoefficients(values, dt, error, float(tail_bound))
