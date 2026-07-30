"""Autocorrelation, effective sample size, and timing summaries."""

from __future__ import annotations

import numpy as np


WINDOW_RULE = "sokal_c5_with_initial_positive_fallback"


def normalized_autocorrelation(series: np.ndarray) -> np.ndarray:
    values = np.asarray(series, dtype=np.float64)
    if values.ndim != 1 or values.size < 4:
        raise ValueError("series must be one-dimensional with at least four samples")
    centered = values - values.mean()
    fft_length = 1 << (2 * values.size - 1).bit_length()
    spectrum = np.fft.rfft(centered, n=fft_length)
    covariance = np.fft.irfft(spectrum * np.conjugate(spectrum), n=fft_length)[
        : values.size
    ]
    covariance /= np.arange(values.size, 0, -1)
    if covariance[0] <= 0.0:
        raise ValueError("series has zero variance")
    return covariance / covariance[0]


def sokal_integrated_time(acf: np.ndarray, c: float = 5.0) -> tuple[float, int]:
    values = np.asarray(acf, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.isclose(values[0], 1.0):
        raise ValueError("acf must be normalized and one-dimensional")
    tau = 0.5
    last_positive_window = 0
    for lag in range(1, values.size):
        if values[lag] <= 0.0:
            break
        tau += float(values[lag])
        last_positive_window = lag
        if lag >= c * tau:
            return max(0.5, tau), lag
    return max(0.5, tau), last_positive_window


def autocorrelation_summary(
    series: np.ndarray,
    elapsed_seconds: float,
) -> dict[str, float | int | str]:
    if elapsed_seconds <= 0.0:
        raise ValueError("elapsed_seconds must be positive")
    values = np.asarray(series, dtype=np.float64)
    acf = normalized_autocorrelation(values)
    tau, window = sokal_integrated_time(acf)
    ess = float(values.size / (2.0 * tau))
    return {
        "samples": int(values.size),
        "tau_int": float(tau),
        "window": int(window),
        "window_rule": WINDOW_RULE,
        "ess": ess,
        "elapsed_seconds": float(elapsed_seconds),
        "ess_per_second": ess / float(elapsed_seconds),
    }
