"""Physical observables and distribution distances for MPS VMCRG runs."""

from __future__ import annotations

import numpy as np


def _relative_entropy(left: np.ndarray, right: np.ndarray) -> float:
    mask = left > 0.0
    return float(np.sum(left[mask] * np.log(left[mask] / right[mask])))


def patch_distribution_distances(
    counts: np.ndarray,
    pseudocount: float = 0.5,
) -> dict[str, float]:
    values = np.asarray(counts, dtype=np.float64)
    if values.shape != (512,) or np.any(values < 0.0) or values.sum() <= 0.0:
        raise ValueError("counts must be 512 nonnegative values with positive total")
    if pseudocount <= 0.0:
        raise ValueError("pseudocount must be positive")
    target = np.full(512, 1.0 / 512.0, dtype=np.float64)
    empirical = values / values.sum()
    total_variation = 0.5 * float(np.abs(empirical - target).sum())
    midpoint = 0.5 * (empirical + target)
    jensen_shannon = 0.5 * (
        _relative_entropy(empirical, midpoint) + _relative_entropy(target, midpoint)
    )
    smoothed = (values + pseudocount) / (values.sum() + 512.0 * pseudocount)
    kl_smoothed = _relative_entropy(smoothed, target)
    return {
        "total_variation": total_variation,
        "jensen_shannon": float(jensen_shannon),
        "kl_smoothed": float(kl_smoothed),
        "pseudocount": float(pseudocount),
    }


def displacement_correlation(spins: np.ndarray, dx: int, dy: int) -> float:
    values = np.asarray(spins, dtype=np.int8)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError("spins must be a square array")
    shifted = np.roll(values, shift=(-dx, -dy), axis=(0, 1))
    return float(np.mean(values * shifted))


def multisite_product(spins: np.ndarray, offsets: tuple[tuple[int, int], ...]) -> float:
    values = np.asarray(spins, dtype=np.int8)
    if not offsets:
        raise ValueError("at least one offset is required")
    product = np.ones_like(values, dtype=np.int8)
    for dx, dy in offsets:
        product *= np.roll(values, shift=(-dx, -dy), axis=(0, 1))
    return float(np.mean(product))
