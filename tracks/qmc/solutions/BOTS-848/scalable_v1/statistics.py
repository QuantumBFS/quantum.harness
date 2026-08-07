from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class ScalarEstimate:
    mean: float
    variance: float
    standard_error: float
    effective_sample_size: float
    maximum_imaginary_part: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def blocking_estimate(values: np.ndarray, *, block_size: int) -> ScalarEstimate:
    array = np.asarray(values)
    if block_size <= 0 or array.ndim != 2 or array.shape[1] % block_size:
        raise ValueError("values must be [chains, samples] with divisible blocks")
    if array.shape[0] == 0 or array.shape[1] == 0:
        raise ValueError("values must contain nonempty chains and samples")
    if not np.all(np.isfinite(array)):
        raise ValueError("estimator values must be finite")
    maximum_imaginary = float(np.max(np.abs(np.imag(array))))
    real = np.real(array).astype(float, copy=False)
    chains, samples = real.shape
    blocks = real.reshape(chains, samples // block_size, block_size).mean(axis=2).ravel()
    mean = float(np.mean(real))
    variance = float(np.var(real, ddof=1)) if real.size > 1 else 0.0
    standard_error = float(np.std(blocks, ddof=1) / math.sqrt(blocks.size)) if blocks.size > 1 else 0.0
    ess = float(real.size) if variance == 0.0 or standard_error == 0.0 else min(float(real.size), variance / standard_error**2)
    return ScalarEstimate(mean, variance, standard_error, ess, maximum_imaginary)


def combine_independent(left_mean: float, left_error: float, right_mean: float, right_error: float) -> tuple[float, float]:
    if not all(math.isfinite(value) for value in (left_mean, left_error, right_mean, right_error)):
        raise ValueError("means and errors must be finite")
    if left_error < 0.0 or right_error < 0.0:
        raise ValueError("errors must be nonnegative")
    return left_mean - right_mean, math.hypot(left_error, right_error)


def normalized_residual(actual: np.ndarray, expected: np.ndarray) -> float:
    actual = np.asarray(actual, dtype=complex)
    expected = np.asarray(expected, dtype=complex)
    if actual.shape != expected.shape:
        raise ValueError("actual and expected must have the same shape")
    if actual.size == 0:
        raise ValueError("actual and expected must be nonempty")
    if not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected)):
        raise ValueError("actual and expected must be finite")
    denominator = max(float(np.linalg.norm(expected)), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected) / denominator)
