"""Weighted M0/M1 fits for the even-power cylinder Casimir basis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

FitModel = Literal["M0", "M1"]
Quantity = Literal["phi", "shannon"]


@dataclass(frozen=True)
class CasimirFit:
    model: FitModel
    quantity: Quantity
    sizes: NDArray[np.float64]
    coefficients: NDArray[np.float64]
    coefficient_covariance: NDArray[np.float64]
    central_charge: float
    central_charge_error: float
    chi_squared: float
    degrees_of_freedom: int
    reduced_chi_squared: float
    design_condition_number: float
    well_conditioned: bool
    residuals: NDArray[np.float64]


def design_matrix(
    sizes: NDArray[np.floating], model: FitModel
) -> NDArray[np.float64]:
    sizes_array = np.asarray(sizes, dtype=np.float64)
    if sizes_array.ndim != 1 or sizes_array.size == 0:
        raise ValueError("sizes must be a non-empty rank-1 array")
    if not np.all(np.isfinite(sizes_array)) or np.any(sizes_array <= 0.0):
        raise ValueError("sizes must be finite and positive")
    if np.unique(sizes_array).size != sizes_array.size:
        raise ValueError("sizes must be unique")
    inverse_square = sizes_array**-2
    if model == "M0":
        return np.column_stack((np.ones_like(sizes_array), inverse_square))
    if model == "M1":
        return np.column_stack(
            (np.ones_like(sizes_array), inverse_square, inverse_square**2)
        )
    raise ValueError("model must be 'M0' or 'M1'")


def fit_casimir(
    sizes: NDArray[np.floating],
    values: NDArray[np.floating],
    *,
    errors: NDArray[np.floating] | None = None,
    covariance: NDArray[np.floating] | None = None,
    model: FitModel,
    quantity: Quantity,
    alpha: float = 1.0,
    condition_limit: float = 1.0e10,
) -> CasimirFit:
    """Fit one declared Casimir model; never cycles between M0 and M1."""

    sizes_array = np.asarray(sizes, dtype=np.float64)
    values_array = np.asarray(values, dtype=np.float64)
    matrix = design_matrix(sizes_array, model)
    if values_array.shape != sizes_array.shape:
        raise ValueError("values and sizes shapes must match")
    if not np.all(np.isfinite(values_array)):
        raise ValueError("values must be finite")
    if alpha <= 0.0 or not np.isfinite(alpha):
        raise ValueError("alpha must be finite and positive")
    if condition_limit <= 1.0:
        raise ValueError("condition_limit must exceed 1")
    if errors is not None and covariance is not None:
        raise ValueError("provide errors or covariance, not both")

    if covariance is not None:
        covariance_array = np.asarray(covariance, dtype=np.float64)
        if covariance_array.shape != (sizes_array.size, sizes_array.size):
            raise ValueError("covariance shape mismatch")
    elif errors is not None:
        error_array = np.asarray(errors, dtype=np.float64)
        if error_array.shape != sizes_array.shape:
            raise ValueError("errors and sizes shapes must match")
        if not np.all(np.isfinite(error_array)) or np.any(error_array <= 0.0):
            raise ValueError("errors must be finite and positive")
        covariance_array = np.diag(error_array**2)
    else:
        covariance_array = np.eye(sizes_array.size, dtype=np.float64)

    if not np.all(np.isfinite(covariance_array)):
        raise ValueError("covariance must be finite")
    cholesky = np.linalg.cholesky(covariance_array)
    whitened_matrix = np.linalg.solve(cholesky, matrix)
    whitened_values = np.linalg.solve(cholesky, values_array)
    coefficients, _, rank, _ = np.linalg.lstsq(
        whitened_matrix, whitened_values, rcond=None
    )
    if rank != matrix.shape[1]:
        raise np.linalg.LinAlgError("Casimir design matrix is rank deficient")
    degrees_of_freedom = sizes_array.size - matrix.shape[1]
    if degrees_of_freedom < 1:
        raise ValueError("at least one fit degree of freedom is required")

    normal_matrix = whitened_matrix.T @ whitened_matrix
    coefficient_covariance = np.linalg.inv(normal_matrix)
    residuals = values_array - matrix @ coefficients
    whitened_residuals = np.linalg.solve(cholesky, residuals)
    chi_squared = float(whitened_residuals @ whitened_residuals)
    condition = float(np.linalg.cond(whitened_matrix))

    if quantity == "phi":
        conversion = 6.0 / (np.pi * alpha)
    elif quantity == "shannon":
        conversion = -6.0 / (np.pi * alpha)
    else:
        raise ValueError("quantity must be 'phi' or 'shannon'")
    central_charge = float(conversion * coefficients[1])
    central_charge_error = float(
        abs(conversion) * np.sqrt(coefficient_covariance[1, 1])
    )

    return CasimirFit(
        model=model,
        quantity=quantity,
        sizes=sizes_array.copy(),
        coefficients=coefficients,
        coefficient_covariance=coefficient_covariance,
        central_charge=central_charge,
        central_charge_error=central_charge_error,
        chi_squared=chi_squared,
        degrees_of_freedom=degrees_of_freedom,
        reduced_chi_squared=chi_squared / degrees_of_freedom,
        design_condition_number=condition,
        well_conditioned=condition <= condition_limit,
        residuals=residuals,
    )


def fit_bootstrap_samples(
    sizes: NDArray[np.floating],
    bootstrap_values: NDArray[np.floating],
    *,
    errors: NDArray[np.floating],
    model: FitModel,
    quantity: Quantity,
    alpha: float = 1.0,
) -> tuple[NDArray[np.float64], int]:
    """Refit every declared bootstrap sample, retaining failures as NaN."""

    samples = np.asarray(bootstrap_values, dtype=np.float64)
    sizes_array = np.asarray(sizes, dtype=np.float64)
    if samples.ndim != 2 or samples.shape[1] != sizes_array.size:
        raise ValueError("bootstrap_values must have shape (n_bootstrap, n_sizes)")
    charges = np.full(samples.shape[0], np.nan, dtype=np.float64)
    failures = 0
    for index, values in enumerate(samples):
        try:
            charges[index] = fit_casimir(
                sizes_array,
                values,
                errors=errors,
                model=model,
                quantity=quantity,
                alpha=alpha,
            ).central_charge
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            failures += 1
    return charges, failures
