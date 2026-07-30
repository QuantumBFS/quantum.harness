from __future__ import annotations

import math

import numpy as np
from scipy.special import zeta

from .model import ModelSpec


def _negative_power(values: np.ndarray, exponent: float) -> np.ndarray:
    logarithms = -exponent * np.log(values)
    representable = logarithms >= math.log(
        np.nextafter(0.0, 1.0)
    )
    result = np.zeros_like(values)
    with np.errstate(under="ignore"):
        result[representable] = np.power(
            values[representable], -exponent
        )
    return result


def _negative_power_scalar(value: float, exponent: float) -> float:
    logarithm = -exponent * math.log(value)
    if logarithm < math.log(np.nextafter(0.0, 1.0)):
        return 0.0
    return math.pow(value, -exponent)


def periodic_kernel(length: int, sigma: float) -> np.ndarray:
    ModelSpec(length=length, sigma=sigma, kappa=0.0)
    distances = np.arange(1, length // 2 + 1, dtype=np.float64)
    if float(sigma) == 1.0:
        angles = np.pi * distances / length
        values = (np.pi / length) ** 2 / np.sin(angles) ** 2
    else:
        exponent = 1.0 + float(sigma)
        fraction = distances / length
        nearest = _negative_power(distances, exponent)
        mirrored = _negative_power(length - distances, exponent)
        scale = _negative_power_scalar(float(length), exponent)
        tail = scale * (
            zeta(exponent, 1.0 + fraction)
            + zeta(exponent, 2.0 - fraction)
        )
        values = nearest + mirrored + tail
    if not np.all(np.isfinite(values)):
        raise ValueError("periodic kernel produced a nonfinite entry")
    if np.any(values <= 0.0):
        raise ValueError(
            "periodic kernel has a positive entry below float64 "
            "representability"
        )
    return values


def periodic_kernel_reference(
    length: int,
    sigma: float,
    images: int,
) -> tuple[np.ndarray, np.ndarray]:
    ModelSpec(length=length, sigma=sigma, kappa=0.0)
    if isinstance(images, bool) or not isinstance(images, int) or images < 1:
        raise ValueError("images must be a positive integer")
    exponent = 1.0 + float(sigma)
    distances = np.arange(1, length // 2 + 1, dtype=np.float64)
    partial = np.zeros_like(distances)
    for image in range(-images, images + 1):
        displacement = np.abs(distances + image * length)
        partial += displacement ** (-exponent)
    half_index = images + 0.5
    tail = np.full_like(
        distances,
        2.0 * length ** (-exponent) * (
            half_index ** (-exponent)
            + half_index ** (1.0 - exponent) / (exponent - 1.0)
        ),
    )
    return partial, tail


def kernel_weight_sum(length: int, sigma: float) -> float:
    ModelSpec(length=length, sigma=sigma, kappa=0.0)
    exponent = 1.0 + float(sigma)
    finite_size_correction = _negative_power_scalar(
        float(length), exponent
    )
    total = float(
        length
        * zeta(exponent, 1.0)
        * (1.0 - finite_size_correction)
    )
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("kernel weight sum must be finite and positive")
    return total


def edge_probabilities(spec: ModelSpec, kernel: np.ndarray) -> np.ndarray:
    values = np.asarray(kernel, dtype=np.float64)
    if values.shape != (spec.length // 2,):
        raise ValueError("kernel shape does not match model length")
    if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("kernel must contain finite positive values")
    return -np.expm1(-spec.kappa * values)
