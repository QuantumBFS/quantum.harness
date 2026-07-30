"""Trotter extrapolation and thermodynamic reconstruction for QMC bins."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import cumulative_simpson

@dataclass(frozen=True, slots=True)
class Extrapolated:
    value: float
    stderr: float
    slope: float
    reduced_chi2: float


@dataclass(frozen=True, slots=True)
class TrotterPoint:
    value: float
    stderr: float
    slope: float
    reduced_chi2: float
    fit_spread: float
    status: str


@dataclass(frozen=True, slots=True)
class BootstrapThermodynamics:
    beta: np.ndarray
    u: np.ndarray
    u_error: np.ndarray
    f: np.ndarray
    f_error: np.ndarray
    c: np.ndarray
    c_error: np.ndarray
    fit_spread: np.ndarray
    reduced_chi2: np.ndarray
    status: tuple[str, ...]


def trotter_extrapolate(beta, m, values, errors) -> Extrapolated:
    m = np.asarray(m, dtype=float)
    y = np.asarray(values, dtype=float)
    sigma = np.asarray(errors, dtype=float)
    if m.ndim != 1 or y.shape != m.shape or sigma.shape != m.shape:
        raise ValueError("m, values, and errors must be equal one-dimensional arrays")
    if len(m) < 3:
        raise ValueError("at least three Trotter slice counts are required")
    if not all(np.isfinite(array).all() for array in (m, y, sigma)):
        raise ValueError("Trotter fit inputs must be finite")
    if float(beta) <= 0 or np.any(m <= 0) or np.any(sigma <= 0):
        raise ValueError("beta, M, and fit errors must be positive")
    if len(np.unique(m)) != len(m):
        raise ValueError("Trotter slice counts must be distinct")

    x = (float(beta) / m) ** 2
    design = np.column_stack((np.ones_like(x), x))
    weights = 1.0 / sigma**2
    normal = design.T @ (weights[:, None] * design)
    try:
        covariance = np.linalg.inv(normal)
    except np.linalg.LinAlgError as error:
        raise ValueError("Trotter fit is singular") from error
    coefficients = covariance @ design.T @ (weights * y)
    residual = (y - design @ coefficients) / sigma
    degrees_of_freedom = len(y) - design.shape[1]
    reduced_chi2 = float((residual @ residual) / degrees_of_freedom)
    return Extrapolated(
        value=float(coefficients[0]),
        stderr=float(np.sqrt(covariance[0, 0])),
        slope=float(coefficients[1]),
        reduced_chi2=reduced_chi2,
    )


def integrate_free_energy(beta, u):
    beta = np.asarray(beta, dtype=float)
    u = np.asarray(u, dtype=float)
    if beta.ndim != 1 or u.shape != beta.shape or len(beta) < 2:
        raise ValueError("beta and u must be equal one-dimensional grids")
    if not np.isfinite(beta).all() or not np.isfinite(u).all():
        raise ValueError("integration inputs must be finite")
    if beta[0] != 0.0 or u[0] != 0.0 or np.any(np.diff(beta) <= 0):
        raise ValueError("integration grid must begin at beta=0 with u=0")
    beta_f = -np.log(2.0) + cumulative_simpson(u, x=beta, initial=0.0)
    result = np.full_like(beta, np.nan)
    result[1:] = beta_f[1:] / beta[1:]
    return result


def specific_heat_from_u(beta, u):
    from .measure import local_polynomial_derivative

    beta = np.asarray(beta, dtype=float)
    u = np.asarray(u, dtype=float)
    derivative = local_polynomial_derivative(beta, u)
    return -(beta**2) * derivative


def _point_inputs(chain_bins: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    bins = np.asarray(chain_bins, dtype=float)
    if bins.ndim != 3:
        raise ValueError("chain bins must have shape (M, chain, bin)")
    if bins.shape[1] != 4:
        raise ValueError("every M value must contain exactly four chains")
    if bins.shape[2] < 32:
        raise ValueError("every chain must contain at least 32 bins")
    if not np.isfinite(bins).all():
        raise ValueError("QMC bins must be finite")
    flattened = bins.reshape(bins.shape[0], -1)
    values = np.mean(flattened, axis=1)
    errors = np.std(flattened, axis=1, ddof=1) / np.sqrt(flattened.shape[1])
    if np.any(errors <= 0):
        raise ValueError("every M value must have a positive statistical error")
    return values, errors


def analyze_trotter_point(beta, m, chain_bins) -> TrotterPoint:
    m = np.asarray(m, dtype=float)
    bins = np.asarray(chain_bins, dtype=float)
    if bins.shape[0] != len(m):
        raise ValueError("chain bins must provide one block per M value")
    values, errors = _point_inputs(bins)
    fit = trotter_extrapolate(beta, m, values, errors)
    return TrotterPoint(
        value=fit.value,
        stderr=fit.stderr,
        slope=fit.slope,
        reduced_chi2=fit.reduced_chi2,
        fit_spread=float(np.max(np.abs(values - fit.value))),
        status="success" if fit.reduced_chi2 < 4.0 else "unconverged",
    )


def bootstrap_thermodynamics(
    beta,
    m,
    chain_bins,
    *,
    bootstrap_samples: int = 2000,
    seed: int = 147,
) -> BootstrapThermodynamics:
    beta = np.asarray(beta, dtype=float)
    m = np.asarray(m, dtype=float)
    bins = np.asarray(chain_bins, dtype=float)
    if beta.ndim != 1 or len(beta) < 4 or np.any(beta <= 0):
        raise ValueError("beta must be a positive one-dimensional grid")
    if np.any(np.diff(beta) <= 0):
        raise ValueError("beta grid must be strictly increasing")
    if bins.ndim != 4 or bins.shape[:2] != (len(beta), len(m)):
        raise ValueError("chain bins must have shape (beta, M, chain, bin)")
    if bootstrap_samples < 2:
        raise ValueError("at least two bootstrap samples are required")

    points = [analyze_trotter_point(point, m, block) for point, block in zip(beta, bins, strict=True)]
    errors = np.stack([_point_inputs(block)[1] for block in bins])
    rng = np.random.default_rng(seed)
    u_samples = np.empty((bootstrap_samples, len(beta)), dtype=float)
    f_samples = np.empty_like(u_samples)
    c_samples = np.empty_like(u_samples)
    bin_count = bins.shape[3]
    for sample in range(bootstrap_samples):
        for beta_index, point in enumerate(beta):
            m_values = np.empty(len(m), dtype=float)
            for m_index in range(len(m)):
                block = bins[beta_index, m_index]
                indices = rng.integers(0, bin_count, size=block.shape)
                resampled = np.take_along_axis(block, indices, axis=1)
                m_values[m_index] = float(np.mean(np.mean(resampled, axis=1)))
            u_samples[sample, beta_index] = trotter_extrapolate(
                point, m, m_values, errors[beta_index]
            ).value
        anchored_beta = np.concatenate(([0.0], beta))
        anchored_u = np.concatenate(([0.0], u_samples[sample]))
        f_samples[sample] = integrate_free_energy(anchored_beta, anchored_u)[1:]
        c_samples[sample] = specific_heat_from_u(anchored_beta, anchored_u)[1:]

    return BootstrapThermodynamics(
        beta=beta.copy(),
        u=np.median(u_samples, axis=0),
        u_error=np.std(u_samples, axis=0, ddof=1),
        f=np.median(f_samples, axis=0),
        f_error=np.std(f_samples, axis=0, ddof=1),
        c=np.median(c_samples, axis=0),
        c_error=np.std(c_samples, axis=0, ddof=1),
        fit_spread=np.asarray([point.fit_spread for point in points]),
        reduced_chi2=np.asarray([point.reduced_chi2 for point in points]),
        status=tuple(point.status for point in points),
    )
