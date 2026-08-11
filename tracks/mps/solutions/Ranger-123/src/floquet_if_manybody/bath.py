"""Ohmic bosonic-bath conventions used throughout the project."""

from __future__ import annotations

import numpy as np
from scipy.integrate import quad

from .config import BathConfig


def ohmic_spectral_density(frequency: float | np.ndarray, bath: BathConfig) -> float | np.ndarray:
    frequency_array = np.asarray(frequency)
    result = bath.alpha * frequency_array * np.exp(-frequency_array / bath.cutoff)
    result = np.where(frequency_array >= 0, result, 0.0)
    return float(result) if result.ndim == 0 else result


def bose_occupation(frequency: float, temperature: float) -> float:
    if frequency <= 0:
        raise ValueError("frequency must be positive")
    if temperature == 0:
        return 0.0
    argument = frequency / temperature
    if argument > 700:
        return 0.0
    return float(1.0 / float(np.expm1(argument)))


def bath_correlation(time: float, bath: BathConfig) -> complex:
    """Return <B(t)B(0)> for J(w)=alpha*w*exp(-w/wc), hbar=kB=1."""
    zero_temperature = bath.alpha * bath.cutoff**2 / (1 + 1j * bath.cutoff * time) ** 2
    if bath.temperature == 0 or bath.alpha == 0:
        return complex(zero_temperature)

    def thermal_real(frequency: float) -> float:
        density = float(ohmic_spectral_density(frequency, bath))
        return float(
            2
            * density
            * bose_occupation(frequency, bath.temperature)
            * np.cos(frequency * time)
        )

    thermal, _ = quad(thermal_real, 0, np.inf, epsabs=1e-10, epsrel=1e-9, limit=300)
    return complex(zero_temperature + thermal)
