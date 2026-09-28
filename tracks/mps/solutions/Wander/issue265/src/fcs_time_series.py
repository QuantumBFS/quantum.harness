"""Validation and cumulant extraction for transfer-FCS time series."""

from __future__ import annotations

from dataclasses import dataclass
from math import factorial

import numpy as np


Array = np.ndarray


@dataclass(frozen=True)
class ValidatedFCS:
    t: Array
    gamma: Array
    logz: Array
    cumulants: Array
    diagnostics: dict[str, float]


def _cumulant_design(gamma: Array, order: int) -> Array:
    return np.column_stack(
        [(1j * gamma) ** n / factorial(n) for n in range(1, order + 1)]
    )


def fit_cumulants(
    gamma: Array,
    logz: Array,
    *,
    order: int,
) -> Array:
    """Fit real cumulants in ``log Z=sum (i gamma)^n kappa_n/n!``."""

    gamma = np.asarray(gamma, dtype=float)
    values = np.asarray(logz, dtype=complex)
    if gamma.ndim != 1 or values.ndim != 2 or values.shape[1] != gamma.size:
        raise ValueError("expected logz with shape (Nt, Ngamma)")
    if order < 1 or order >= gamma.size:
        raise ValueError("cumulant order must be positive and below gamma count")
    design = _cumulant_design(gamma, order)
    real_design = np.vstack([design.real, design.imag])
    result = np.empty((values.shape[0], order), dtype=float)
    for index, row in enumerate(values):
        target = np.concatenate([row.real, row.imag])
        result[index], *_ = np.linalg.lstsq(real_design, target, rcond=None)
    return result


def validate_fcs_time_series(
    t: Array,
    gamma: Array,
    logz: Array,
    *,
    normalization_tol: float = 1e-10,
    conjugacy_tol: float = 1e-10,
    cumulant_stability_tol: float = 0.10,
) -> ValidatedFCS:
    """Normalize, unwrap, validate, and extract cumulants through fourth order."""

    t = np.asarray(t, dtype=float)
    gamma = np.asarray(gamma, dtype=float)
    raw = np.asarray(logz, dtype=complex)
    if t.ndim != 1 or gamma.ndim != 1 or raw.shape != (t.size, gamma.size):
        raise ValueError("expected t:(Nt,), gamma:(Ng,), logz:(Nt,Ng)")
    if t.size < 2 or np.any(np.diff(t) <= 0):
        raise ValueError("time grid must be strictly increasing")
    if gamma.size != 7 or np.any(np.diff(gamma) <= 0):
        raise ValueError("FCS gamma grid must contain seven increasing values")
    zero_matches = np.flatnonzero(np.isclose(gamma, 0.0, rtol=0.0, atol=1e-13))
    if zero_matches.size != 1:
        raise ValueError("FCS gamma grid must contain exactly one zero")
    if not np.allclose(gamma, -gamma[::-1], rtol=0.0, atol=1e-13):
        raise ValueError("FCS gamma grid must be symmetric")
    if np.any(~np.isfinite(raw.real)) or np.any(~np.isfinite(raw.imag)):
        raise ValueError("FCS logZ contains non-finite values")
    if normalization_tol <= 0 or conjugacy_tol <= 0 or cumulant_stability_tol <= 0:
        raise ValueError("FCS validation tolerances must be positive")

    zero = int(zero_matches[0])
    normalization_defect = float(np.max(np.abs(raw[:, zero])))
    if normalization_defect > normalization_tol:
        raise ValueError("FCS zero-field normalization failed")
    normalized = raw - raw[:, zero, None]
    characteristic = np.exp(normalized)
    conjugacy_defect = float(
        np.max(np.abs(characteristic - np.conj(characteristic[:, ::-1])))
    )
    if conjugacy_defect > conjugacy_tol:
        raise ValueError("FCS conjugacy validation failed")

    phase = np.unwrap(normalized.imag, axis=0)
    phase = np.unwrap(phase, axis=1)
    phase -= phase[:, zero, None]
    unwrapped = normalized.real + 1j * phase
    post_unwrap_defect = float(
        np.max(np.abs(unwrapped - np.conj(unwrapped[:, ::-1])))
    )
    if post_unwrap_defect > max(conjugacy_tol, 1e-12):
        raise ValueError("FCS branch could not be unwrapped conjugately")

    order4 = fit_cumulants(gamma, unwrapped, order=4)
    order6 = fit_cumulants(gamma, unwrapped, order=6)
    denominator = np.maximum(1.0, np.abs(order6[:, :4]))
    stability_by_row = np.max(
        np.abs(order6[:, :4] - order4) / denominator,
        axis=1,
    )
    stability = float(np.max(stability_by_row))
    if stability > cumulant_stability_tol:
        raise ValueError("FCS cumulants are unstable between order-4 and order-6 fits")
    variance_floor = cumulant_stability_tol
    minimum_variance = float(np.min(order4[:, 1]))
    if minimum_variance < -variance_floor:
        raise ValueError("FCS second cumulant is negative beyond the numerical floor")
    order4[:, 1] = np.maximum(order4[:, 1], 0.0)

    reconstruction = _cumulant_design(gamma, 4) @ order4.T
    reconstruction_error = float(
        np.sqrt(np.mean(np.abs(reconstruction.T - unwrapped) ** 2))
    )
    return ValidatedFCS(
        t=t.copy(),
        gamma=gamma.copy(),
        logz=unwrapped,
        cumulants=order4,
        diagnostics={
            "normalization_max_abs": normalization_defect,
            "conjugacy_max_abs": conjugacy_defect,
            "post_unwrap_conjugacy_max_abs": post_unwrap_defect,
            "cumulant_order4_order6_max_relative": stability,
            "minimum_second_cumulant": minimum_variance,
            "order4_reconstruction_rmse": reconstruction_error,
        },
    )
