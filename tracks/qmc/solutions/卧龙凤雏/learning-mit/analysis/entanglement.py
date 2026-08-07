"""Weighted linear fits for finite-size entanglement arcs."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class EntropyModelFit:
    model: str
    coefficients: np.ndarray
    covariance: np.ndarray
    residuals: np.ndarray
    aicc: float
    weight: float


@dataclass(frozen=True)
class EntropyFitSet:
    fits: tuple[EntropyModelFit, ...]
    best_model: str

    def by_name(self, model: str) -> EntropyModelFit:
        return next(fit for fit in self.fits if fit.model == model)


def fit_entropy_arc(
    points: np.ndarray, models: tuple[str, ...]
) -> EntropyFitSet:
    values = np.asarray(points, dtype=float)
    if values.ndim != 2 or values.shape[1] not in (3, 4) or len(values) < 3:
        raise ValueError("entropy points must have columns l, L, S[, sigma]")
    if not np.all(np.isfinite(values)):
        raise ValueError("entropy points must be finite")
    interval, length, entropy = values[:, 0], values[:, 1], values[:, 2]
    if np.any(interval <= 0) or np.any(interval >= length):
        raise ValueError("entropy intervals must lie strictly inside the chain")
    sigma = values[:, 3] if values.shape[1] == 4 else np.ones(len(values))
    if np.any(sigma <= 0):
        raise ValueError("entropy uncertainties must be positive")

    radius = length / np.pi * np.sin(np.pi * interval / length)
    log_radius = np.log(radius)
    page = np.minimum(interval, length - interval) * math.log(2.0)
    raw_fits: list[tuple[str, np.ndarray, np.ndarray, np.ndarray, float]] = []
    for model in models:
        design = _design(model, log_radius, page)
        if len(values) <= design.shape[1] + 1:
            aicc = math.inf
            coefficients = np.linalg.lstsq(design, entropy, rcond=None)[0]
            residuals = entropy - design @ coefficients
            covariance = np.full((design.shape[1], design.shape[1]), np.nan)
        else:
            weighted_design = design / sigma[:, None]
            weighted_entropy = entropy / sigma
            coefficients = np.linalg.lstsq(
                weighted_design, weighted_entropy, rcond=None
            )[0]
            residuals = entropy - design @ coefficients
            chi2 = float(np.sum((residuals / sigma) ** 2))
            rss = max(chi2, np.finfo(float).tiny)
            count, parameters = design.shape
            aic = count * math.log(rss / count) + 2 * parameters
            aicc = aic + 2 * parameters * (parameters + 1) / (
                count - parameters - 1
            )
            normal = weighted_design.T @ weighted_design
            covariance = (
                np.linalg.pinv(normal) * chi2 / max(count - parameters, 1)
            )
        raw_fits.append((model, coefficients, covariance, residuals, aicc))

    finite_aicc = [fit[4] for fit in raw_fits if math.isfinite(fit[4])]
    if not finite_aicc:
        raise ValueError("no entropy model has enough points for AICc")
    minimum = min(finite_aicc)
    relative = np.array(
        [
            math.exp(-0.5 * (fit[4] - minimum)) if math.isfinite(fit[4]) else 0.0
            for fit in raw_fits
        ]
    )
    relative /= relative.sum()
    fits = tuple(
        EntropyModelFit(
            model=model,
            coefficients=_readonly(coefficients),
            covariance=_readonly(covariance),
            residuals=_readonly(residuals),
            aicc=aicc,
            weight=float(weight),
        )
        for (model, coefficients, covariance, residuals, aicc), weight in zip(
            raw_fits, relative, strict=True
        )
    )
    best = max(fits, key=lambda fit: fit.weight).model
    return EntropyFitSet(fits=fits, best_model=best)


def _design(model: str, log_radius: np.ndarray, page: np.ndarray) -> np.ndarray:
    constant = np.ones_like(log_radius)
    columns = {
        "constant": (constant,),
        "log": (constant, log_radius),
        "log2": (constant, log_radius**2),
        "log_log2": (constant, log_radius, log_radius**2),
        "page_log_log2": (constant, page, log_radius, log_radius**2),
    }
    if model not in columns:
        raise ValueError(f"unknown entropy model: {model}")
    return np.column_stack(columns[model])


def _readonly(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    result.setflags(write=False)
    return result
