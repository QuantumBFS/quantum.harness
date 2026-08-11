"""Frequency-resolved bath heat current from collective correlations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import trapezoid

from .bath import bose_occupation, ohmic_spectral_density
from .config import BathConfig
from .correlations import CorrelationResult


@dataclass(frozen=True)
class HeatDeltaPeak:
    harmonic: int
    frequency: float
    weight: float


@dataclass(frozen=True)
class HeatCurrentResult:
    frequencies: NDArray[np.float64]
    continuous: NDArray[np.float64]
    delta_peaks: tuple[HeatDeltaPeak, ...]
    method: str
    metadata: dict[str, float | str]


def heat_current_spectrum(
    correlation: CorrelationResult,
    bath: BathConfig,
    frequencies: NDArray[np.float64],
    window: str = "hann",
) -> HeatCurrentResult:
    """Evaluate the half-sided heat-current transform.

    The continuous part uses only the connected correlation. Coherent
    contributions are returned as analytic delta weights.
    """
    if np.any(frequencies < 0):
        raise ValueError("bath frequencies must be nonnegative")
    delays = correlation.delays
    if len(delays) < 2 or not np.allclose(np.diff(delays), np.diff(delays)[0]):
        raise ValueError("correlation delays must form a uniform grid")
    if window == "hann":
        taper = np.hanning(2 * len(delays) - 1)[len(delays) - 1 :]
    elif window == "none":
        taper = np.ones(len(delays))
    else:
        raise ValueError("window must be 'hann' or 'none'")
    connected = correlation.connected * taper
    output = np.zeros_like(frequencies, dtype=np.float64)
    for index, frequency in enumerate(frequencies):
        if frequency == 0:
            continue
        occupation = bose_occupation(float(frequency), bath.temperature)
        kernel = (
            np.cos(frequency * delays) * np.real(connected)
            + (1 + 2 * occupation)
            * np.sin(frequency * delays)
            * np.imag(connected)
        )
        prefactor = 2 * float(ohmic_spectral_density(float(frequency), bath)) * frequency
        output[index] = prefactor * trapezoid(kernel, delays)

    delta_peaks = tuple(
        HeatDeltaPeak(
            peak.harmonic,
            peak.frequency,
            float(
                np.pi
                * ohmic_spectral_density(peak.frequency, bath)
                * peak.frequency
                * peak.correlation_weight
            ),
        )
        for peak in correlation.delta_peaks
        if peak.frequency > 0
    )
    return HeatCurrentResult(
        frequencies,
        output,
        delta_peaks,
        correlation.method,
        {
            "window": window,
            "tau_max": float(delays[-1]),
            "frequency_resolution": float(2 * np.pi / delays[-1]),
        },
    )
