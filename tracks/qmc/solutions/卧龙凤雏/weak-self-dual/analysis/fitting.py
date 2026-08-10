from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class GammaFit:
    minimum_width: int
    widths: list[int]
    correction: str
    bulk_free_energy: float
    central_charge: float
    correction_l3: float | None
    correction_l5: float | None
    covariance: list[list[float]]
    chi_square: float
    degrees_of_freedom: int
    residual_rms: float

    def to_dict(self) -> dict:
        return asdict(self)


def design_matrix(widths: np.ndarray, correction: str) -> np.ndarray:
    widths = np.asarray(widths, dtype=float)
    columns = [widths, -np.pi / (6.0 * widths)]
    if correction == "none":
        return np.column_stack(columns)
    if correction == "l3":
        return np.column_stack([*columns, 1.0 / widths**3])
    if correction == "l3_l5":
        return np.column_stack([*columns, 1.0 / widths**3, 1.0 / widths**5])
    raise ValueError(f"unknown correction model: {correction}")


def fit_gamma(
    widths: np.ndarray,
    gamma: np.ndarray,
    sigma: np.ndarray,
    minimum_width: int,
    correction: str,
) -> GammaFit:
    widths = np.asarray(widths, dtype=float)
    gamma = np.asarray(gamma, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    if widths.ndim != 1 or widths.shape != gamma.shape or widths.shape != sigma.shape:
        raise ValueError("widths, gamma, and sigma must be same-length vectors")
    if not np.all(np.isfinite(widths)) or not np.all(np.isfinite(gamma)):
        raise ValueError("fit inputs must be finite")
    if not np.all(np.isfinite(sigma)) or np.any(sigma <= 0):
        raise ValueError("fit uncertainties must be finite and positive")
    selected = widths >= minimum_width
    selected_widths = widths[selected]
    selected_gamma = gamma[selected]
    selected_sigma = sigma[selected]
    matrix = design_matrix(selected_widths, correction)
    required = max(3, matrix.shape[1])
    if len(selected_widths) < required:
        count = {3: "three", 4: "four"}.get(required, str(required))
        raise ValueError(f"finite-size fit requires at least {count} widths")
    weighted_matrix = matrix / selected_sigma[:, None]
    weighted_gamma = selected_gamma / selected_sigma
    coefficients, _, rank, _ = np.linalg.lstsq(weighted_matrix, weighted_gamma, rcond=None)
    if rank != matrix.shape[1]:
        raise ValueError("finite-size fit design matrix is rank deficient")
    covariance = np.linalg.inv(weighted_matrix.T @ weighted_matrix)
    residual = selected_gamma - matrix @ coefficients
    chi_square = float(np.sum((residual / selected_sigma) ** 2))
    dof = len(selected_widths) - matrix.shape[1]
    return GammaFit(
        minimum_width=int(minimum_width),
        widths=[int(value) for value in selected_widths],
        correction=correction,
        bulk_free_energy=float(coefficients[0]),
        central_charge=float(coefficients[1]),
        correction_l3=float(coefficients[2]) if matrix.shape[1] >= 3 else None,
        correction_l5=float(coefficients[3]) if matrix.shape[1] >= 4 else None,
        covariance=[[float(value) for value in row] for row in covariance],
        chi_square=chi_square,
        degrees_of_freedom=dof,
        residual_rms=float(np.sqrt(np.mean(residual**2))),
    )


def evaluate_fit(fit: GammaFit, widths: np.ndarray) -> np.ndarray:
    widths = np.asarray(widths, dtype=float)
    values = fit.bulk_free_energy * widths - np.pi * fit.central_charge / (6.0 * widths)
    if fit.correction_l3 is not None:
        values = values + fit.correction_l3 / widths**3
    if fit.correction_l5 is not None:
        values = values + fit.correction_l5 / widths**5
    return values
