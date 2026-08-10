"""Correlated finite-size fits of the record-free-energy Casimir amplitude."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CasimirFit:
    widths: np.ndarray
    correction: str
    bulk_density: float
    casimir_amplitude: float
    correction_coefficients: tuple[float, ...]
    parameter_covariance: np.ndarray
    residuals: np.ndarray
    chi2: float
    degrees_of_freedom: int
    covariance_floor: float
    covariance_condition: float
    stable_without_smallest: bool


def fit_casimir(
    widths: np.ndarray,
    gamma: np.ndarray,
    covariance: np.ndarray,
    minimum_width: float,
    correction: str,
) -> CasimirFit:
    widths = np.asarray(widths, dtype=float)
    gamma = np.asarray(gamma, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    if correction not in {"none", "l3", "l3_l5"}:
        raise ValueError(f"unknown Casimir correction: {correction}")
    if widths.ndim != 1 or gamma.shape != widths.shape:
        raise ValueError("width and gamma arrays must be one-dimensional and aligned")
    if covariance.shape != (len(widths), len(widths)):
        raise ValueError("Casimir covariance has the wrong shape")
    if not (
        np.all(np.isfinite(widths))
        and np.all(np.isfinite(gamma))
        and np.all(np.isfinite(covariance))
    ):
        raise ValueError("Casimir inputs must be finite")
    selected = widths >= minimum_width
    widths = widths[selected]
    gamma = gamma[selected]
    covariance = covariance[np.ix_(selected, selected)]
    if len(widths) < 5:
        raise ValueError("Casimir fit requires at least five widths")
    if np.any(widths <= 0) or len(np.unique(widths)) != len(widths):
        raise ValueError("Casimir widths must be positive and distinct")

    design_columns = [widths, -np.pi / (6.0 * widths)]
    if correction in {"l3", "l3_l5"}:
        design_columns.append(widths**-3)
    if correction == "l3_l5":
        design_columns.append(widths**-5)
    design = np.column_stack(design_columns)
    if np.linalg.matrix_rank(design) != design.shape[1]:
        raise ValueError("Casimir design matrix is rank deficient")

    symmetric = 0.5 * (covariance + covariance.T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    scale = max(float(np.max(np.abs(eigenvalues))), 1.0)
    floor = max(scale * 1e-12, np.finfo(float).eps)
    regularized = eigenvectors @ np.diag(np.maximum(eigenvalues, floor)) @ eigenvectors.T
    precision = np.linalg.inv(regularized)
    coefficients, parameter_covariance, covariance_condition = _solve(
        design, precision, gamma
    )
    residuals = gamma - design @ coefficients
    chi2 = float(residuals @ precision @ residuals)
    trimmed_design = design[1:]
    trimmed_precision = np.linalg.inv(regularized[1:, 1:])
    trimmed_coefficients, trimmed_covariance, _ = _solve(
        trimmed_design, trimmed_precision, gamma[1:]
    )
    combined_error = np.sqrt(
        max(float(parameter_covariance[1, 1]), 0.0)
        + max(float(trimmed_covariance[1, 1]), 0.0)
    )
    stable_without_smallest = bool(
        abs(float(coefficients[1] - trimmed_coefficients[1]))
        <= 1.96 * combined_error
    )
    return CasimirFit(
        widths=_readonly(widths),
        correction=correction,
        bulk_density=float(coefficients[0]),
        casimir_amplitude=float(coefficients[1]),
        correction_coefficients=tuple(float(value) for value in coefficients[2:]),
        parameter_covariance=_readonly(parameter_covariance),
        residuals=_readonly(residuals),
        chi2=chi2,
        degrees_of_freedom=len(widths) - design.shape[1],
        covariance_floor=floor,
        covariance_condition=covariance_condition,
        stable_without_smallest=stable_without_smallest,
    )


def _solve(
    design: np.ndarray, precision: np.ndarray, values: np.ndarray
) -> tuple[np.ndarray, np.ndarray, float]:
    normal = design.T @ precision @ design
    norms = np.linalg.norm(design, axis=0)
    if np.any(norms == 0):
        raise ValueError("Casimir design matrix has a zero column")
    normalized = design / norms
    normalized_normal = normalized.T @ precision @ normalized
    condition = float(np.linalg.cond(normalized_normal))
    if not np.isfinite(condition) or condition > 1.0e10:
        raise ValueError("Casimir covariance condition number exceeds 1e10")
    covariance = np.linalg.inv(normal)
    coefficients = covariance @ design.T @ precision @ values
    return coefficients, covariance, condition


def _readonly(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    result.setflags(write=False)
    return result
