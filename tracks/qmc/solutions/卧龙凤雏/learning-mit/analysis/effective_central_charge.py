"""Chord-length and finite-size effective-central-charge estimators."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class EntanglementCentralChargeFit:
    phi_pi: float
    widths: np.ndarray
    per_width: np.ndarray
    extrapolated: float
    interval: tuple[float, float]
    fitted: np.ndarray
    residuals: np.ndarray
    chi2_per_dof: float
    covariance_condition: float
    model_weights: dict[str, float]
    stable_without_smallest: bool


def chord_log(interval: np.ndarray, width: float) -> np.ndarray:
    interval = np.asarray(interval, dtype=float)
    if (
        not math.isfinite(width)
        or width <= 0
        or not np.all(np.isfinite(interval))
        or np.any(interval <= 0)
        or np.any(interval >= width)
    ):
        raise ValueError("chord inputs must be finite and lie inside the ring")
    return np.log((width / np.pi) * np.sin(np.pi * interval / width))


def fit_width_c_eff(rows: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    values = np.asarray(rows, dtype=float)
    if values.ndim != 2 or values.shape[1] != 4 or len(values) < 4:
        raise ValueError("entropy rows require at least four four-column observations")
    if not np.all(np.isfinite(values)):
        raise ValueError("entropy rows must be finite")
    widths = np.unique(values[:, 1])
    if len(widths) != 1:
        raise ValueError("entropy rows must describe one width")
    width = float(widths[0])
    if np.any(values[:, 3] <= 0):
        raise ValueError("entropy uncertainties must be positive")
    fraction = values[:, 0] / width
    selected = values[(fraction >= 0.25) & (fraction <= 0.75)]
    if len(selected) < 4:
        raise ValueError("central entropy window requires at least four points")
    interval, entropy, uncertainty = selected[:, 0], selected[:, 2], selected[:, 3]
    design = np.column_stack(
        [
            np.ones(len(selected)),
            chord_log(interval, width) / 3.0,
            np.cos(2.0 * np.pi * interval / width) / width**2,
        ]
    )
    precision = np.diag(uncertainty**-2)
    normal = design.T @ precision @ design
    condition = float(np.linalg.cond(normal))
    if not math.isfinite(condition) or condition > 1.0e12:
        raise ValueError("width fit condition number is too large")
    covariance = np.linalg.inv(normal)
    coefficients = covariance @ design.T @ precision @ entropy
    residuals = entropy - design @ coefficients
    return (
        float(coefficients[1]),
        _readonly(covariance),
        _readonly(residuals),
    )


def extrapolate_c_eff(
    phi_pi: float,
    fits_by_width: dict[int, tuple[float, float]],
    model_weights: dict[str, float],
) -> EntanglementCentralChargeFit:
    if len(fits_by_width) < 4:
        raise ValueError("effective-central-charge extrapolation requires at least four widths")
    ordered = sorted(fits_by_width.items())
    widths = np.asarray([width for width, _ in ordered], dtype=float)
    estimates = np.asarray([fit[0] for _, fit in ordered], dtype=float)
    errors = np.asarray([fit[1] for _, fit in ordered], dtype=float)
    weights = np.asarray(list(model_weights.values()), dtype=float)
    if not (
        math.isfinite(phi_pi)
        and np.all(np.isfinite(widths))
        and np.all(np.isfinite(estimates))
        and np.all(np.isfinite(errors))
        and np.all(np.isfinite(weights))
    ):
        raise ValueError("effective-central-charge inputs must be finite")
    if np.any(widths <= 0) or len(np.unique(widths)) != len(widths):
        raise ValueError("effective-central-charge widths must be positive and distinct")
    if np.any(errors <= 0):
        raise ValueError("effective-central-charge errors must be positive")
    if np.any(weights < 0):
        raise ValueError("model weights must be nonnegative")

    coefficients, covariance, fitted, residuals, condition, chi2_per_dof = _fit_size_window(
        widths, estimates, errors
    )
    trimmed, trimmed_covariance, _, _, _, _ = _fit_size_window(
        widths[1:], estimates[1:], errors[1:]
    )
    combined_error = math.sqrt(
        max(float(covariance[0, 0]), 0.0)
        + max(float(trimmed_covariance[0, 0]), 0.0)
    )
    stable = abs(float(coefficients[0] - trimmed[0])) <= 1.96 * combined_error
    standard_error = math.sqrt(max(float(covariance[0, 0]), 0.0))
    per_width = np.column_stack([widths, estimates, errors])
    return EntanglementCentralChargeFit(
        phi_pi=float(phi_pi),
        widths=_readonly(widths),
        per_width=_readonly(per_width),
        extrapolated=float(coefficients[0]),
        interval=(
            float(coefficients[0] - 1.96 * standard_error),
            float(coefficients[0] + 1.96 * standard_error),
        ),
        fitted=_readonly(fitted),
        residuals=_readonly(residuals),
        chi2_per_dof=chi2_per_dof,
        covariance_condition=condition,
        model_weights=dict(model_weights),
        stable_without_smallest=bool(stable),
    )


def _fit_size_window(
    widths: np.ndarray, estimates: np.ndarray, errors: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, float]:
    design = np.column_stack([np.ones(len(widths)), widths**-2])
    precision = np.diag(errors**-2)
    normal = design.T @ precision @ design
    condition = float(np.linalg.cond(normal))
    if not math.isfinite(condition) or condition > 1.0e10:
        raise ValueError("effective-central-charge fit condition number exceeds 1e10")
    covariance = np.linalg.inv(normal)
    coefficients = covariance @ design.T @ precision @ estimates
    fitted = design @ coefficients
    residuals = estimates - fitted
    dof = len(widths) - design.shape[1]
    chi2 = float(residuals @ precision @ residuals)
    return coefficients, covariance, fitted, residuals, condition, chi2 / max(dof, 1)


def _readonly(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    result.setflags(write=False)
    return result
