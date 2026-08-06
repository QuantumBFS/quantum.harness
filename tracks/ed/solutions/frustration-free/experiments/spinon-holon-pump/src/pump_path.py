"""Pump path factory functions for the Rice-Mele-Hubbard model.

Provides callable δ(τ) and Δ(τ) for CW, CCW, and frozen protocols.

Pump path:
  δ(φ) = R_δ cos(φ)
  Δ(φ) = 5 + 2.1 sin(φ)

Protocols:
  CW:    φ(τ) = -2πτ/T  (clockwise)
  CCW:   φ(τ) = +2πτ/T  (counter-clockwise)
  frozen: φ(τ) = 0       (static at pump start)
"""

from __future__ import annotations

import numpy as np


def make_pump_functions(R_delta: float, T: float, direction: str = "cw"):
    """Return (delta_of_tau, Delta_of_tau) callables for a pump protocol.

    Parameters
    ----------
    R_delta : float
        Dimerisation amplitude R_δ.
    T : float
        Total pump period.
    direction : str
        "cw" (clockwise, θ = -2πτ/T),
        "ccw" (counter-clockwise, θ = +2πτ/T),
        "frozen" (static at φ=0: δ = R_δ, Δ = 5.0).

    Returns
    -------
    delta_of_tau : callable
        Function δ(τ).
    Delta_of_tau : callable
        Function Δ(τ).
    """
    direction = direction.lower().strip()
    if direction not in ("cw", "ccw", "frozen"):
        raise ValueError(f"Unknown direction: {direction!r}, "
                         f"expected 'cw', 'ccw', or 'frozen'")

    if direction == "frozen":
        delta_fixed = R_delta  # cos(0) = 1
        Delta_fixed = 5.0       # sin(0) = 0

        def delta_of_tau(tau: float) -> float:
            return delta_fixed

        def Delta_of_tau(tau: float) -> float:
            return Delta_fixed

        return delta_of_tau, Delta_of_tau

    sign = -1.0 if direction == "cw" else 1.0

    def delta_of_tau(tau: float) -> float:
        phi = sign * 2.0 * np.pi * tau / T
        return R_delta * np.cos(phi)

    def Delta_of_tau(tau: float) -> float:
        phi = sign * 2.0 * np.pi * tau / T
        return 5.0 + 2.1 * np.sin(phi)

    return delta_of_tau, Delta_of_tau
