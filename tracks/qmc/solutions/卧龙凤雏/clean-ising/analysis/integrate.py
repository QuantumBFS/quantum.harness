"""Deterministic quadrature for thermodynamic integration."""

from typing import Tuple

import numpy as np


def simpson_uniform(x: np.ndarray, y: np.ndarray) -> float:
    x_values = np.asarray(x, dtype=float)
    y_values = np.asarray(y, dtype=float)
    if x_values.ndim != 1 or y_values.ndim != 1 or x_values.shape != y_values.shape:
        raise ValueError("x and y must be one-dimensional arrays of equal length")
    if x_values.size < 3 or x_values.size % 2 == 0:
        raise ValueError("Simpson integration requires an odd number of at least three points")
    if not np.all(np.isfinite(x_values)) or not np.all(np.isfinite(y_values)):
        raise ValueError("Simpson integration inputs must be finite")
    spacing = np.diff(x_values)
    if spacing[0] <= 0.0 or not np.allclose(spacing, spacing[0], rtol=1.0e-12, atol=1.0e-15):
        raise ValueError("Simpson integration requires a strictly increasing uniform grid")
    weighted_sum = (
        y_values[0]
        + y_values[-1]
        + 4.0 * np.sum(y_values[1:-1:2])
        + 2.0 * np.sum(y_values[2:-1:2])
    )
    return float(spacing[0] * weighted_sum / 3.0)


def free_energy_from_energy(k: np.ndarray, mean_h: np.ndarray, n_sites: int) -> float:
    k_values = np.asarray(k, dtype=float)
    if n_sites <= 0:
        raise ValueError("n_sites must be positive")
    if k_values.size == 0 or abs(float(k_values[0])) > 1.0e-15:
        raise ValueError("thermodynamic integration grid must start at K=0")
    return -float(n_sites) * np.log(2.0) + simpson_uniform(k_values, mean_h)


def nested_free_energies(
    k: np.ndarray, mean_h: np.ndarray, n_sites: int
) -> Tuple[float, float]:
    k_values = np.asarray(k, dtype=float)
    energy_values = np.asarray(mean_h, dtype=float)
    full = free_energy_from_energy(k_values, energy_values, n_sites)
    coarse = free_energy_from_energy(k_values[::2], energy_values[::2], n_sites)
    return full, coarse
