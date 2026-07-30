"""Spatial scaling dimensions and temporal anisotropy calibration."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class SpatialFit:
    delta: float
    standard_error: float
    intercept: float
    window: tuple[float, float]
    points: int


@dataclass(frozen=True)
class AlphaFit:
    alpha: float
    standard_error: float
    estimates: tuple[float, ...]
    block_window: tuple[int | None, int | None]
    stable: bool


def fit_spatial_dimension(
    correlation_blocks: dict[int, list[np.ndarray]],
    widths: tuple[int, ...] | list[int],
    window: tuple[float, float],
) -> SpatialFit:
    lower, upper = window
    if not 0.0 < lower < upper <= 0.5:
        raise ValueError("spatial window must lie inside (0, 1/2]")
    log_chord: list[float] = []
    log_correlation: list[float] = []
    for width in widths:
        for block in correlation_blocks.get(width, []):
            values = np.asarray(block, dtype=float)
            if values.ndim != 2 or values.shape[1] != 2:
                raise ValueError("correlation blocks require distance and value columns")
            distance, correlation = values[:, 0], values[:, 1]
            selected = (
                (distance >= lower * width)
                & (distance <= upper * width)
                & np.isfinite(correlation)
                & (np.abs(correlation) > 0)
            )
            chord = width / np.pi * np.sin(np.pi * distance[selected] / width)
            log_chord.extend(np.log(chord))
            log_correlation.extend(np.log(np.abs(correlation[selected])))
    x = np.asarray(log_chord)
    y = np.asarray(log_correlation)
    if len(x) < 4:
        raise ValueError("spatial fit has too few correlation points")
    design = np.column_stack([np.ones(len(x)), x])
    coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
    residuals = y - design @ coefficients
    variance = float(residuals @ residuals) / max(len(x) - 2, 1)
    covariance = np.linalg.inv(design.T @ design) * variance
    delta = -0.5 * float(coefficients[1])
    standard_error = 0.5 * math.sqrt(max(float(covariance[1, 1]), 0.0))
    if not math.isfinite(delta) or delta <= 0:
        raise ValueError("spatial scaling dimension is not positive")
    return SpatialFit(
        delta=delta,
        standard_error=standard_error,
        intercept=float(coefficients[0]),
        window=window,
        points=len(x),
    )


def calibrate_alpha(
    spatial_fit: SpatialFit,
    lyapunov_blocks: dict[int, list[np.ndarray]],
    window: tuple[int | None, int | None],
) -> AlphaFit:
    estimates = []
    start, stop = window
    for width, blocks in sorted(lyapunov_blocks.items()):
        for spectrum in blocks[slice(start, stop)]:
            values = np.asarray(spectrum, dtype=float)
            if values.ndim != 1 or len(values) < 2 or not np.all(np.isfinite(values)):
                raise ValueError("Lyapunov block must contain two finite exponents")
            ordered = np.sort(values)[::-1]
            gap = float(ordered[0] - ordered[1])
            if gap <= 0:
                raise ValueError("temporal Lyapunov gap is not positive")
            estimates.append(
                gap * width / (2.0 * np.pi * spatial_fit.delta)
            )
    if len(estimates) < 3:
        raise ValueError("anisotropy calibration requires at least three blocks")
    array = np.asarray(estimates)
    alpha = float(array.mean())
    standard_error = float(array.std(ddof=1) / np.sqrt(len(array)))
    stable = bool(
        alpha > 0
        and np.all(array > 0)
        and (standard_error == 0.0 or np.max(np.abs(array - alpha)) <= 4 * standard_error)
    )
    return AlphaFit(
        alpha=alpha,
        standard_error=standard_error,
        estimates=tuple(float(value) for value in array),
        block_window=window,
        stable=stable,
    )
