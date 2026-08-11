"""Pump path functions for the one-hole Chern experiment.

Pump path (centered on Mott-insulating region):
    δ(φ) = R_δ cos φ
    Δ(φ) = 5.0 + 2.1 sin φ

Default R_δ values: 0.2, 0.4.
"""

from __future__ import annotations

import numpy as np

# Default pump parameters
DEFAULT_R_DELTA = 0.4
DEFAULT_DELTA_OFFSET = 5.0
DEFAULT_DELTA_AMP = 2.1


def pump_delta(phi: float, R_delta: float = DEFAULT_R_DELTA) -> float:
    """Dimerisation parameter: δ(φ) = R_δ cos φ."""
    return R_delta * np.cos(phi)


def pump_Delta(phi: float, offset: float = DEFAULT_DELTA_OFFSET,
               amp: float = DEFAULT_DELTA_AMP) -> float:
    """Staggered potential: Δ(φ) = Δ_offset + Δ_amp sin φ."""
    return offset + amp * np.sin(phi)


def pump_path(phi: float, R_delta: float = DEFAULT_R_DELTA,
              Delta_offset: float = DEFAULT_DELTA_OFFSET,
              Delta_amp: float = DEFAULT_DELTA_AMP) -> tuple[float, float]:
    """Return (δ, Δ) at pump phase φ."""
    return pump_delta(phi, R_delta), pump_Delta(phi, Delta_offset, Delta_amp)
