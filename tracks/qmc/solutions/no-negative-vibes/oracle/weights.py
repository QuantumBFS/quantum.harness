"""Stable determinant-weight evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.linalg import expm


@dataclass(frozen=True)
class WeightResult:
    classification: str
    value: complex
    phase: complex
    log_abs: float
    sigma_min: float
    condition_number: float


def product_exponentials(generators: list[np.ndarray]) -> np.ndarray:
    if not generators:
        raise ValueError("at least one generator is required")
    shape = np.asarray(generators[0]).shape
    if len(shape) != 2 or shape[0] != shape[1]:
        raise ValueError("generators must be square matrices")

    dtype = np.result_type(*[np.asarray(generator).dtype for generator in generators])
    product = np.eye(shape[0], dtype=dtype)
    for generator in generators:
        matrix = np.asarray(generator)
        if matrix.shape != shape:
            raise ValueError("all generators must have the same shape")
        product = product @ expm(matrix)
    return product


def classify_product(
    product: np.ndarray,
    *,
    phase_tolerance: float = 1e-10,
    uncertainty_rtol: float = 1e-12,
) -> WeightResult:
    product = np.asarray(product)
    if product.ndim != 2 or product.shape[0] != product.shape[1]:
        raise ValueError("product must be a square matrix")

    shifted = np.eye(product.shape[0], dtype=product.dtype) + product
    phase, log_abs = np.linalg.slogdet(shifted)
    singular_values = np.linalg.svd(shifted, compute_uv=False)
    sigma_max = float(singular_values[0])
    sigma_min = float(singular_values[-1])
    condition_number = math.inf if sigma_min == 0.0 else sigma_max / sigma_min
    effective_phase_tolerance = max(
        phase_tolerance,
        32.0 * np.finfo(float).eps * condition_number,
    )

    if phase == 0:
        classification = "zero"
        value = 0.0
    else:
        complex_phase = complex(phase)
        if log_abs > math.log(np.finfo(float).max):
            value = complex(
                math.copysign(math.inf, complex_phase.real)
                if complex_phase.real
                else 0.0,
                math.copysign(math.inf, complex_phase.imag)
                if complex_phase.imag
                else 0.0,
            )
        else:
            value = complex_phase * math.exp(float(log_abs))
        if sigma_min <= uncertainty_rtol * max(1.0, sigma_max):
            classification = "uncertain"
        elif abs(complex_phase.imag) > effective_phase_tolerance:
            classification = "complex"
        elif complex_phase.real > 0.0:
            classification = "positive"
        else:
            classification = "negative"

    return WeightResult(
        classification=classification,
        value=value,
        phase=complex(phase),
        log_abs=float(log_abs),
        sigma_min=sigma_min,
        condition_number=condition_number,
    )
