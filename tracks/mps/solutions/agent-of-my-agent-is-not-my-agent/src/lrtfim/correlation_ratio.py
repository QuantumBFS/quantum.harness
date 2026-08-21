"""Physical correlations and second-moment correlation ratio."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from .parity_dmrg import physical_correlations_rotated


@dataclass(frozen=True)
class CorrelationRatio:
    s_zero: float
    s_k_min: float
    xi: float
    r_xi: float
    k_min: float


def second_moment_ratio(correlations: ArrayLike) -> CorrelationRatio:
    """Return auditable ``S(0)``, ``S(k_min)``, ``xi``, and ``xi/L``."""
    values = np.asarray(correlations)
    if values.ndim != 1 or len(values) < 4:
        raise ValueError("correlations must be a one-dimensional length >= 4")
    if np.max(np.abs(np.imag(values))) > 1.0e-12:
        raise ValueError("correlations must be real")
    values = np.real(values).astype(float)
    if np.any(~np.isfinite(values)):
        raise ValueError("correlations must be finite")
    length = len(values)
    distances = np.arange(length)
    k_min = 2.0 * np.pi / length
    s_zero = float(np.sum(values))
    s_k_min = float(np.sum(np.cos(k_min * distances) * values))
    if s_k_min <= 0.0:
        raise ValueError("S(k_min) must be positive")
    if s_zero < s_k_min:
        raise ValueError("S(0) must be at least S(k_min)")
    xi = float(
        np.sqrt(s_zero / s_k_min - 1.0)
        / (2.0 * np.sin(k_min / 2.0))
    )
    return CorrelationRatio(
        s_zero=s_zero,
        s_k_min=s_k_min,
        xi=xi,
        r_xi=xi / length,
        k_min=k_min,
    )
