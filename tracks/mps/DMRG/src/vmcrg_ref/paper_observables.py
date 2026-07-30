from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RGJacobianEstimate:
    a: np.ndarray
    b: np.ndarray
    transformation: np.ndarray
    leading_eigenvalue: float
    b_condition_number: float
    equation_relative_residual: float


def covariance_matrices_from_sums(
    sample_count: int,
    micro_sum: np.ndarray,
    block_sum: np.ndarray,
    micro_block_sum: np.ndarray,
    block_outer_sum: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Construct A and B in paper Eqs. 16-17 from sufficient statistics."""
    if sample_count <= 1:
        raise ValueError("at least two samples are required")
    micro_sum = np.asarray(micro_sum, dtype=np.float64)
    block_sum = np.asarray(block_sum, dtype=np.float64)
    micro_block_sum = np.asarray(micro_block_sum, dtype=np.float64)
    block_outer_sum = np.asarray(block_outer_sum, dtype=np.float64)
    if micro_sum.ndim != 1 or block_sum.shape != micro_sum.shape:
        raise ValueError("operator sums have incompatible shapes")
    expected_matrix = (micro_sum.size, micro_sum.size)
    if micro_block_sum.shape != expected_matrix or block_outer_sum.shape != expected_matrix:
        raise ValueError("second-moment sums have incompatible shapes")

    micro_mean = micro_sum / sample_count
    block_mean = block_sum / sample_count
    a = micro_block_sum / sample_count - np.outer(micro_mean, block_mean)
    b = block_outer_sum / sample_count - np.outer(block_mean, block_mean)
    b = 0.5 * (b + b.T)
    return a, b


def leading_real_eigenvalue(matrix: np.ndarray, imaginary_tolerance: float = 1e-7) -> float:
    eigenvalues = np.linalg.eigvals(np.asarray(matrix, dtype=np.float64))
    leading = eigenvalues[int(np.argmax(np.abs(eigenvalues)))]
    scale = max(1.0, abs(float(leading.real)))
    if abs(float(leading.imag)) > imaginary_tolerance * scale:
        raise ValueError(f"leading eigenvalue is not real within tolerance: {leading}")
    value = float(leading.real)
    if value <= 0.0:
        raise ValueError(f"leading eigenvalue must be positive, got {value}")
    return value


def estimate_rg_jacobian(a: np.ndarray, b: np.ndarray) -> RGJacobianEstimate:
    """Solve A=T^T B as T=solve(B, A^T), without explicitly inverting B."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or b.shape != a.shape:
        raise ValueError("A and B must be square matrices of the same shape")
    transformation = np.linalg.solve(b, a.T)
    denominator = np.linalg.norm(a)
    residual = np.linalg.norm(a - transformation.T @ b)
    relative_residual = float(residual / denominator) if denominator else float(residual)
    return RGJacobianEstimate(
        a=a,
        b=b,
        transformation=transformation,
        leading_eigenvalue=leading_real_eigenvalue(transformation),
        b_condition_number=float(np.linalg.cond(b)),
        equation_relative_residual=relative_residual,
    )


def scaling_dimensions(lambda_even: float, lambda_odd: float, block_scale: float = 3.0) -> dict[str, float]:
    if lambda_even <= 0.0 or lambda_odd <= 0.0 or block_scale <= 1.0:
        raise ValueError("eigenvalues must be positive and block_scale must exceed one")
    y_t = float(np.log(lambda_even) / np.log(block_scale))
    y_h = float(np.log(lambda_odd) / np.log(block_scale))
    dimension = 2.0
    return {
        "y_t": y_t,
        "y_h": y_h,
        "nu": 1.0 / y_t,
        "eta": dimension + 2.0 - 2.0 * y_h,
        "beta": (dimension - y_h) / y_t,
        "gamma": (2.0 * y_h - dimension) / y_t,
        "alpha": 2.0 - dimension / y_t,
    }


def normalized_connected_autocorrelation(series: np.ndarray, max_lag: int) -> np.ndarray:
    values = np.asarray(series, dtype=np.float64)
    if values.ndim != 1 or values.size < 2:
        raise ValueError("series must be one-dimensional with at least two values")
    if max_lag < 0 or max_lag >= values.size:
        raise ValueError("max_lag must lie between zero and len(series)-1")
    centered = values - values.mean()
    fft_length = 1 << (2 * values.size - 1).bit_length()
    spectrum = np.fft.rfft(centered, fft_length)
    covariance = np.fft.irfft(spectrum * np.conjugate(spectrum), fft_length)[: values.size]
    covariance /= np.arange(values.size, 0, -1)
    if covariance[0] <= 0.0:
        raise ValueError("observable has zero variance")
    return covariance[: max_lag + 1] / covariance[0]


def integrated_autocorrelation_time(acf: np.ndarray) -> float:
    """Initial-positive-sequence estimate using the same rule for all chains."""
    values = np.asarray(acf, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isclose(values[0], 1.0):
        raise ValueError("acf must be one-dimensional and normalized at lag zero")
    positive_sum = 0.0
    for value in values[1:]:
        if value <= 0.0:
            break
        positive_sum += float(value)
    return 0.5 + positive_sum
