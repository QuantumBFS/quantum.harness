"""Finite-size Casimir fits for Ising cylinder free energies."""

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass(frozen=True)
class FitResult:
    c: float
    f_infinity: float
    a: float
    l_min: int
    residual_sum: float
    widths: Tuple[int, ...]


def fit_c(widths: np.ndarray, g_per_row: np.ndarray, l_min: int) -> FitResult:
    width_values = np.asarray(widths, dtype=float)
    free_energy_values = np.asarray(g_per_row, dtype=float)
    if (
        width_values.ndim != 1
        or free_energy_values.ndim != 1
        or width_values.shape != free_energy_values.shape
    ):
        raise ValueError("widths and g_per_row must be equal-length one-dimensional arrays")
    if not np.all(np.isfinite(width_values)) or not np.all(np.isfinite(free_energy_values)):
        raise ValueError("fit inputs must be finite")
    if np.any(width_values <= 0.0) or len(np.unique(width_values)) != width_values.size:
        raise ValueError("fit widths must be positive and unique")
    retained = width_values >= float(l_min)
    if np.count_nonzero(retained) < 4:
        raise ValueError("central-charge fit requires at least four widths")
    selected_widths = width_values[retained]
    per_site = free_energy_values[retained] / selected_widths
    matrix = _design_matrix(selected_widths)
    coefficients, residuals, rank, _ = np.linalg.lstsq(matrix, per_site, rcond=None)
    if rank != 3:
        raise ValueError("central-charge design matrix is rank deficient")
    predicted = matrix @ coefficients
    residual_sum = (
        float(residuals[0])
        if residuals.size
        else float(np.sum((per_site - predicted) ** 2))
    )
    return FitResult(
        c=float(-6.0 * coefficients[1] / np.pi),
        f_infinity=float(coefficients[0]),
        a=float(coefficients[2]),
        l_min=int(l_min),
        residual_sum=residual_sum,
        widths=tuple(int(value) for value in selected_widths),
    )


def fit_draws(widths: np.ndarray, g_draws: np.ndarray, l_min: int) -> np.ndarray:
    width_values = np.asarray(widths, dtype=float)
    draws = np.asarray(g_draws, dtype=float)
    if draws.ndim != 2 or draws.shape[1] != width_values.size:
        raise ValueError("g_draws must have shape (draws, widths)")
    retained = width_values >= float(l_min)
    if np.count_nonzero(retained) < 4:
        raise ValueError("central-charge fit requires at least four widths")
    selected_widths = width_values[retained]
    matrix = _design_matrix(selected_widths)
    if np.linalg.matrix_rank(matrix) != 3:
        raise ValueError("central-charge design matrix is rank deficient")
    per_site = draws[:, retained] / selected_widths[np.newaxis, :]
    coefficients = np.linalg.lstsq(matrix, per_site.T, rcond=None)[0]
    return -6.0 * coefficients[1] / np.pi


def _design_matrix(widths: np.ndarray) -> np.ndarray:
    return np.column_stack(
        [
            np.ones_like(widths),
            1.0 / widths**2,
            1.0 / widths**4,
        ]
    )
