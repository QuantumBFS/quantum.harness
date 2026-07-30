"""Pure analysis helpers for Phase 6 correlation-ratio crossings."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Crossing:
    gamma: float
    left_index: int
    right_index: int
    fraction: float


@dataclass(frozen=True)
class DriftFit:
    form: str
    intercept: float
    slope: float
    residual_rms: float


@dataclass(frozen=True)
class ConvergenceStatus:
    converged: bool
    next_chi: int | None
    threshold: float
    final_shift: float
    reason: str


def linear_crossing(gamma, r_small, r_large) -> Crossing:
    """Interpolate a unique crossing between adjacent sampled Gamma values."""
    x = np.asarray(gamma, dtype=float)
    d = np.asarray(r_small, dtype=float) - np.asarray(r_large, dtype=float)
    if x.ndim != 1 or d.shape != x.shape or len(x) < 2:
        raise ValueError("gamma and ratio arrays must be equal one-dimensional arrays")
    exact = np.flatnonzero(d == 0)
    if len(exact) > 1:
        raise ValueError("multiple_crossings")
    if len(exact) == 1:
        index = int(exact[0])
        if index == 0:
            return Crossing(float(x[index]), 0, 1, 0.0)
        return Crossing(float(x[index]), index - 1, index, 1.0)
    candidates = []
    for i in range(len(x) - 1):
        if d[i] * d[i + 1] < 0:
            fraction = -d[i] / (d[i + 1] - d[i])
            candidates.append((i, i + 1, float(fraction)))
    if len(candidates) != 1:
        reason = "window_extension_required" if not candidates else "multiple_crossings"
        raise ValueError(reason)
    left, right, fraction = candidates[0]
    value = x[left] + fraction * (x[right] - x[left])
    return Crossing(float(value), left, right, fraction)


def fit_crossing_drift(lengths, crossings, form: str = "power") -> DriftFit:
    """Fit the preregistered drift forms without selecting between them."""
    sizes = np.asarray(lengths, dtype=float)
    values = np.asarray(crossings, dtype=float)
    if form == "power":
        coordinate = 1.0 / sizes
    elif form == "log":
        coordinate = 1.0 / np.log(sizes)
    else:
        raise ValueError("form must be 'power' or 'log'")
    slope, intercept = np.polyfit(coordinate, values, 1)
    residual = values - (intercept + slope * coordinate)
    return DriftFit(form, float(intercept), float(slope), float(np.sqrt(np.mean(residual**2))))


def crossing_chi_status(values_by_chi, threshold: float = 2e-4) -> ConvergenceStatus:
    """Apply the preregistered numerical crossing convergence rule."""
    values = {int(k): float(v) for k, v in values_by_chi.items()}
    required = (128, 256, 384)
    if not all(k in values for k in required):
        return ConvergenceStatus(False, next(k for k in required if k not in values), threshold, np.nan, "missing_chi")
    prior = abs(values[256] - values[128])
    final = abs(values[384] - values[256])
    converged = final <= threshold and final <= prior
    return ConvergenceStatus(
        converged,
        None if converged else 512,
        threshold,
        final,
        "converged" if converged else "threshold_or_monotonicity_failed",
    )
