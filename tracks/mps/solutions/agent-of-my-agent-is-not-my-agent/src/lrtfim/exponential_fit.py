"""Bounded exponential approximation of an infinite power-law kernel."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import least_squares, nnls


@dataclass(frozen=True)
class ExponentialFit:
    """A fitted sum ``sum_k coefficients[k] * lambdas[k]**r``."""

    sigma: float
    r_fit: int
    lambdas: NDArray[np.float64]
    coefficients: NDArray[np.float64]
    max_relative_error: float
    rms_relative_error: float

    def evaluate(self, distances: ArrayLike) -> NDArray[np.float64]:
        """Evaluate the infinite-chain exponential approximation."""
        r = np.asarray(distances, dtype=float)
        return np.asarray(
            np.power(self.lambdas[:, None], r.ravel()[None, :]).T
            @ self.coefficients,
            dtype=float,
        ).reshape(r.shape)


def power_law_values(distances: ArrayLike, *, sigma: float) -> NDArray[np.float64]:
    """Return ``r**(-1-sigma)`` at strictly positive distances."""
    r = np.asarray(distances, dtype=float)
    if not np.isfinite(sigma) or sigma <= 0.0:
        raise ValueError("sigma must be finite and positive")
    if np.any(~np.isfinite(r)) or np.any(r <= 0.0):
        raise ValueError("distances must be finite and positive")
    return np.asarray(r ** (-1.0 - float(sigma)), dtype=float)


def fit_power_law(
    *,
    sigma: float,
    num_exponentials: int,
    r_fit: int,
    min_rate_scale: float | None = None,
) -> ExponentialFit:
    """Fit the infinite kernel by deterministic bounded variable projection.

    The nonlinear variables are logarithms of positive decay rates
    ``a_k = -log(lambda_k)``. For every nonlinear trial, coefficients are
    solved by linear least squares against the relative residual.
    """
    if not np.isfinite(sigma) or sigma <= 0.0:
        raise ValueError("sigma must be finite and positive")
    if not isinstance(num_exponentials, (int, np.integer)) or num_exponentials < 1:
        raise ValueError("num_exponentials must be a positive integer")
    if not isinstance(r_fit, (int, np.integer)) or r_fit < 1:
        raise ValueError("r_fit must be a positive integer")
    if min_rate_scale is not None and (
        not np.isfinite(min_rate_scale) or min_rate_scale <= 0.0
    ):
        raise ValueError("min_rate_scale must be finite and positive")

    r = np.arange(1, r_fit + 1, dtype=float)
    exact = power_law_values(r, sigma=sigma)
    p = 1.0 + float(sigma)
    minimum_rate = (
        1.0e-8 / r_fit
        if min_rate_scale is None
        else float(min_rate_scale) / r_fit
    )
    if minimum_rate >= 4.0 * p:
        raise ValueError("min_rate_scale is too large for the fitting interval")

    initial_minimum = max(0.25 / r_fit, 1.01 * minimum_rate)
    initial_rates = np.geomspace(initial_minimum, 4.0 * p, num_exponentials)
    initial = np.log(initial_rates)
    if num_exponentials == 1:
        lower = np.array([np.log(minimum_rate)])
        upper = np.array([np.log(20.0 * p)])
    else:
        midpoints = 0.5 * (initial[:-1] + initial[1:])
        lower = np.concatenate(([np.log(minimum_rate)], midpoints))
        upper = np.concatenate((midpoints, [np.log(20.0 * p)]))

    def projected(log_rates: NDArray[np.float64]):
        lambdas = np.exp(-np.exp(log_rates))
        weighted_basis = np.power(lambdas[None, :], r[:, None]) / exact[:, None]
        coefficients, _ = nnls(
            weighted_basis,
            np.ones(r_fit, dtype=float),
            maxiter=10000,
        )
        residual = weighted_basis @ coefficients - 1.0
        return residual, lambdas, coefficients

    result = least_squares(
        lambda x: projected(x)[0],
        initial,
        bounds=(lower, upper),
        method="trf",
        ftol=1.0e-13,
        xtol=1.0e-13,
        gtol=1.0e-13,
        max_nfev=5000,
    )
    residual, lambdas, coefficients = projected(result.x)
    absolute_relative = np.abs(residual)
    return ExponentialFit(
        sigma=float(sigma),
        r_fit=int(r_fit),
        lambdas=np.asarray(lambdas, dtype=float),
        coefficients=np.asarray(coefficients, dtype=float),
        max_relative_error=float(np.max(absolute_relative)),
        rms_relative_error=float(np.sqrt(np.mean(residual**2))),
    )


def periodized_exponential_couplings(
    length: int,
    fit: ExponentialFit,
) -> NDArray[np.float64]:
    """Analytically periodize an exponential fit for distances ``1..L-1``."""
    if not isinstance(length, (int, np.integer)) or length < 2:
        raise ValueError("length must be an integer >= 2")
    if np.any(fit.lambdas <= 0.0) or np.any(fit.lambdas >= 1.0):
        raise ValueError("all exponential lambdas must satisfy 0 < lambda < 1")

    r = np.arange(1, length, dtype=float)[:, None]
    lambdas = fit.lambdas[None, :]
    terms = (
        np.power(lambdas, r) + np.power(lambdas, float(length) - r)
    ) / (1.0 - np.power(lambdas, length))
    return np.asarray(terms @ fit.coefficients, dtype=float)
