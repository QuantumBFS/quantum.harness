"""Robust diagnostics for the Burgers/KPZ interpretation tension.

The public Delta=1 domain-wall data support an accurate deterministic Burgers
closure, while local strong-form fits can appear to support a drifting
viscosity.  This module separates four quantities that should not be conflated:

1. the constant coefficient ``D_closure`` in a deterministic mean-profile PDE;
2. a per-time regression coefficient ``D_fit(t)`` from an ill-conditioned
   inverse problem;
3. the front-width exponent of the domain-wall profile; and
4. the effective diffusivity used in asymptotic KPZ transport theory.

All routines are deterministic and operate on the repository's standard
``npz`` interface with arrays ``x``, ``t`` and ``u``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import numpy as np

from .fit_burgers import _central_diff_x, _make_test_functions, _maybe_smooth
from .synthetic_data import solve_burgers_spectral_rk4


Array = np.ndarray


@dataclass(frozen=True)
class WeakFit:
    """Profiled weak-form fit for a prescribed or optimized power exponent."""

    a: float
    D0: float
    gamma: float
    mse: float
    n_obs: int
    t_window: tuple[float, float]
    t_ref: float


def validate_grid_data(x: Array, t: Array, u: Array) -> dict:
    """Run high-value validity and conservation checks on a profile dataset."""

    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    u = np.asarray(u, dtype=float)
    if x.ndim != 1 or t.ndim != 1 or u.ndim != 2:
        raise ValueError("Expected x:(Nx,), t:(Nt,), u:(Nt,Nx)")
    if u.shape != (t.size, x.size):
        raise ValueError(f"Shape mismatch: u={u.shape}, expected {(t.size, x.size)}")
    if x.size < 5 or t.size < 5:
        raise ValueError("Need at least five points on both axes")

    dx = np.diff(x)
    dt = np.diff(t)
    if np.any(dx <= 0) or np.any(dt <= 0):
        raise ValueError("x and t must be strictly increasing")

    finite_fraction = float(np.mean(np.isfinite(u)))
    if finite_fraction < 1.0:
        raise ValueError("u contains NaN or infinite values")

    edge_n = min(10, max(2, x.size // 20))
    left = np.mean(u[:, :edge_n], axis=1)
    right = np.mean(u[:, -edge_n:], axis=1)
    magnetization = np.trapezoid(u, x=x, axis=1)

    ux = np.gradient(u, x, axis=1, edge_order=2)
    positive_mass = np.trapezoid(np.maximum(ux, 0.0), x=x, axis=1)
    negative_mass = np.trapezoid(np.maximum(-ux, 0.0), x=x, axis=1)
    nonmonotone_fraction = negative_mass / np.maximum(positive_mass + negative_mass, 1e-30)

    return {
        "shape": {"Nt": int(t.size), "Nx": int(x.size)},
        "ranges": {
            "x_min": float(x[0]),
            "x_max": float(x[-1]),
            "t_min": float(t[0]),
            "t_max": float(t[-1]),
            "u_min": float(np.min(u)),
            "u_max": float(np.max(u)),
        },
        "finite_fraction": finite_fraction,
        "dx": float(np.median(dx)),
        "dt": float(np.median(dt)),
        "max_dx_deviation": float(np.max(np.abs(dx - np.median(dx)))),
        "max_dt_deviation": float(np.max(np.abs(dt - np.median(dt)))),
        "left_plateau_range": [float(np.min(left)), float(np.max(left))],
        "right_plateau_range": [float(np.min(right)), float(np.max(right))],
        "magnetization_integral_range": [
            float(np.min(magnetization)),
            float(np.max(magnetization)),
        ],
        "magnetization_integral_drift": float(np.ptp(magnetization)),
        "max_nonmonotone_gradient_fraction": float(np.max(nonmonotone_fraction)),
    }


def front_width_series(
    x: Array,
    t: Array,
    u: Array,
    *,
    x_crop: tuple[float, float] | None = None,
    clip_negative_gradient: bool = False,
) -> dict[str, Array]:
    """Measure the domain-wall front as moments of its normalized gradient.

    For the public data the profile rises from approximately -1/2 to +1/2, so
    ``p(x,t) = u_x / integral(u_x dx)`` behaves like a probability density.
    Its standard deviation is a derivative-light, integral front-width metric.
    """

    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    u = np.asarray(u, dtype=float)
    if x_crop is not None:
        mask = (x >= x_crop[0]) & (x <= x_crop[1])
        if np.count_nonzero(mask) < 10:
            raise ValueError("x_crop leaves too few points")
        xw = x[mask]
        uw = u[:, mask]
    else:
        xw = x
        uw = u

    ux = np.gradient(uw, xw, axis=1, edge_order=2)
    if clip_negative_gradient:
        ux = np.maximum(ux, 0.0)
    norm = np.trapezoid(ux, x=xw, axis=1)
    if np.any(norm <= 0):
        raise ValueError("Front gradient has non-positive total mass")
    center = np.trapezoid(ux * xw[None, :], x=xw, axis=1) / norm
    centered = xw[None, :] - center[:, None]
    variance = np.trapezoid(ux * centered**2, x=xw, axis=1) / norm
    variance = np.maximum(variance, 0.0)
    width = np.sqrt(variance)
    return {
        "t": t.copy(),
        "width": width,
        "variance": variance,
        "center": center,
        "gradient_mass": norm,
    }


def fit_power_exponent(
    t: Array,
    y: Array,
    *,
    t_min: float,
    t_max: float | None = None,
) -> dict[str, float]:
    """Fit ``y = amplitude * t**exponent`` in log space."""

    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    if t_max is None:
        t_max = float(t[-1])
    mask = (t >= t_min) & (t <= t_max) & (t > 0) & (y > 0)
    if np.count_nonzero(mask) < 5:
        raise ValueError("Power fit needs at least five positive observations")
    logt = np.log(t[mask])
    logy = np.log(y[mask])
    X = np.column_stack([np.ones_like(logt), logt])
    beta, *_ = np.linalg.lstsq(X, logy, rcond=None)
    pred = X @ beta
    resid = logy - pred
    n = logy.size
    sigma2 = float(np.sum(resid**2) / max(n - 2, 1))
    cov = sigma2 * np.linalg.inv(X.T @ X)
    return {
        "t_min": float(t_min),
        "t_max": float(t_max),
        "amplitude": float(np.exp(beta[0])),
        "exponent": float(beta[1]),
        "stderr_exponent_naive": float(np.sqrt(cov[1, 1])),
        "rmse_log": float(np.sqrt(np.mean(resid**2))),
        "n_obs": int(n),
    }


def local_log_slope(t: Array, y: Array, *, half_window: int = 25) -> Array:
    """Local log-log slope using centered linear fits."""

    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    if t.shape != y.shape or np.any(t <= 0) or np.any(y <= 0):
        raise ValueError("t and y must be positive arrays with the same shape")
    n = t.size
    slopes = np.empty(n, dtype=float)
    for i in range(n):
        lo = max(0, i - half_window)
        hi = min(n, i + half_window + 1)
        if hi - lo < 5:
            lo = max(0, hi - 5)
            hi = min(n, lo + 5)
        slopes[i] = np.polyfit(np.log(t[lo:hi]), np.log(y[lo:hi]), 1)[0]
    return slopes


def _smoothed_derivatives(
    x: Array,
    t: Array,
    u: Array,
    *,
    smooth_x_window: int = 9,
    smooth_t_window: int = 5,
    smooth_poly: int = 3,
) -> tuple[Array, Array, Array, Array]:
    """Return smoothed u and its t, x and xx derivatives."""

    us = _maybe_smooth(np.asarray(u, float), axis=1, window=smooth_x_window, poly=smooth_poly)
    us = _maybe_smooth(us, axis=0, window=smooth_t_window, poly=min(smooth_poly, 2))
    ut = np.gradient(us, np.asarray(t, float), axis=0, edge_order=2)
    ux = np.gradient(us, np.asarray(x, float), axis=1, edge_order=2)
    uxx = np.gradient(ux, np.asarray(x, float), axis=1, edge_order=2)
    return us, ut, ux, uxx


def instantaneous_joint_fit(
    x: Array,
    t: Array,
    u: Array,
    *,
    x_crop: tuple[float, float] = (-120.0, 120.0),
) -> dict[str, Array]:
    """Jointly fit a(t), D(t) at each interior time point."""

    x = np.asarray(x, float)
    t = np.asarray(t, float)
    us, ut, ux, uxx = _smoothed_derivatives(x, t, u)
    mask = (x >= x_crop[0]) & (x <= x_crop[1])
    rows: list[tuple[float, float, float, float]] = []
    for i in range(1, t.size - 1):
        f1 = -(us[i, mask] * ux[i, mask])
        f2 = uxx[i, mask]
        X = np.column_stack([f1, f2])
        beta, *_ = np.linalg.lstsq(X, ut[i, mask], rcond=None)
        corr = float(np.corrcoef(f1, f2)[0, 1])
        rows.append((float(t[i]), float(beta[0]), float(beta[1]), corr))
    arr = np.asarray(rows)
    return {"t": arr[:, 0], "a": arr[:, 1], "D": arr[:, 2], "feature_corr": arr[:, 3]}


def fixed_a_D_series(
    x: Array,
    t: Array,
    u: Array,
    *,
    a_fixed: float,
    x_crop: tuple[float, float] = (-120.0, 120.0),
) -> dict[str, Array]:
    """Fit only D(t) while holding the nonlinear coefficient fixed."""

    x = np.asarray(x, float)
    t = np.asarray(t, float)
    us, ut, ux, uxx = _smoothed_derivatives(x, t, u)
    mask = (x >= x_crop[0]) & (x <= x_crop[1])
    values = []
    for i in range(1, t.size - 1):
        response = ut[i, mask] + float(a_fixed) * us[i, mask] * ux[i, mask]
        feature = uxx[i, mask]
        denom = float(feature @ feature)
        values.append(float((feature @ response) / denom))
    return {"t": t[1:-1].copy(), "D": np.asarray(values), "a_fixed": float(a_fixed)}


def feature_conditioning(
    x: Array,
    t: Array,
    u: Array,
    *,
    t_mins: Sequence[float],
    t_max: float,
    x_crop: tuple[float, float] = (-120.0, 120.0),
) -> list[dict[str, float]]:
    """Quantify collinearity of ``-u*u_x`` and ``u_xx`` by time window."""

    x = np.asarray(x, float)
    t = np.asarray(t, float)
    us, _, ux, uxx = _smoothed_derivatives(x, t, u)
    xmask = (x >= x_crop[0]) & (x <= x_crop[1])
    results = []
    for t_min in t_mins:
        tmask = (t >= t_min) & (t <= t_max)
        f1 = (-(us[tmask][:, xmask] * ux[tmask][:, xmask])).ravel()
        f2 = uxx[tmask][:, xmask].ravel()
        X = np.column_stack([f1, f2])
        Xs = (X - np.mean(X, axis=0)) / np.std(X, axis=0)
        results.append(
            {
                "t_min": float(t_min),
                "t_max": float(t_max),
                "feature_correlation": float(np.corrcoef(f1, f2)[0, 1]),
                "condition_number_raw": float(np.linalg.cond(X)),
                "condition_number_standardized": float(np.linalg.cond(Xs)),
            }
        )
    return results


def _weak_design(
    x: Array,
    t: Array,
    u: Array,
    *,
    t_window: tuple[float, float],
    x_crop: tuple[float, float],
    n_phi: int = 11,
) -> tuple[Array, Array, Array, Array]:
    """Build weak-form response and the a/D feature columns."""

    x = np.asarray(x, float)
    t = np.asarray(t, float)
    u = np.asarray(u, float)
    tmask = (t >= t_window[0]) & (t <= t_window[1])
    xmask = (x >= x_crop[0]) & (x <= x_crop[1])
    tw = t[tmask]
    xw = x[xmask]
    uw = u[tmask][:, xmask]
    if tw.size < 5 or xw.size < 20:
        raise ValueError("Weak design window is too small")

    us = _maybe_smooth(uw, axis=1, window=9, poly=3)
    us = _maybe_smooth(us, axis=0, window=5, poly=2)
    ut = np.gradient(us, tw, axis=0, edge_order=2)
    phi = np.stack(_make_test_functions(xw, n_phi=n_phi), axis=0)
    phi_x, phi_xx = _central_diff_x(phi, float(xw[1] - xw[0]))

    response: list[float] = []
    nonlinear: list[float] = []
    diffusion: list[float] = []
    row_time: list[float] = []
    for i, ti in enumerate(tw):
        for k in range(n_phi):
            response.append(float(np.trapezoid(phi[k] * ut[i], x=xw)))
            nonlinear.append(float(0.5 * np.trapezoid(phi_x[k] * us[i] ** 2, x=xw)))
            diffusion.append(float(np.trapezoid(phi_xx[k] * us[i], x=xw)))
            row_time.append(float(ti))
    return (
        np.asarray(response),
        np.asarray(nonlinear),
        np.asarray(diffusion),
        np.asarray(row_time),
    )


def fit_profiled_weak(
    x: Array,
    t: Array,
    u: Array,
    *,
    t_window: tuple[float, float],
    x_crop: tuple[float, float] = (-120.0, 120.0),
    t_ref: float = 50.0,
    gamma: float | None = None,
    gamma_grid: Iterable[float] | None = None,
) -> WeakFit:
    """Fit a and D0, optionally profiling over ``D(t)=D0*(t/t_ref)^gamma``."""

    response, nonlinear, diffusion, row_time = _weak_design(
        x, t, u, t_window=t_window, x_crop=x_crop
    )
    if gamma is not None:
        candidates = [float(gamma)]
    elif gamma_grid is not None:
        candidates = [float(value) for value in gamma_grid]
    else:
        candidates = [float(value) for value in np.linspace(-0.5, 0.7, 241)]

    best: WeakFit | None = None
    for candidate in candidates:
        scale = (row_time / float(t_ref)) ** candidate
        X = np.column_stack([nonlinear, diffusion * scale])
        beta, *_ = np.linalg.lstsq(X, response, rcond=None)
        residual = response - X @ beta
        fit = WeakFit(
            a=float(beta[0]),
            D0=float(beta[1]),
            gamma=float(candidate),
            mse=float(np.mean(residual**2)),
            n_obs=int(response.size),
            t_window=(float(t_window[0]), float(t_window[1])),
            t_ref=float(t_ref),
        )
        if best is None or fit.mse < best.mse:
            best = fit
    assert best is not None
    return best


def forecast_profile(
    x: Array,
    t: Array,
    u0: Array,
    *,
    fit: WeakFit,
    absolute_start_time: float,
    dt_internal: float = 0.02,
) -> Array:
    """Integrate a fitted closure over a relative output-time grid."""

    def D_of_relative_time(relative_time: float) -> float:
        absolute_time = absolute_start_time + relative_time
        return float(fit.D0 * (absolute_time / fit.t_ref) ** fit.gamma)

    return solve_burgers_spectral_rk4(
        x=np.asarray(x, float),
        t=np.asarray(t, float),
        a=fit.a,
        D_of_t=D_of_relative_time,
        u0=np.asarray(u0, float),
        dt_internal=dt_internal,
        dealias=True,
    )


def forecast_error(
    prediction: Array,
    truth: Array,
    x: Array,
    *,
    x_crop: tuple[float, float],
) -> dict[str, float]:
    """Return integrated and endpoint relative L2 errors."""

    x = np.asarray(x, float)
    mask = (x >= x_crop[0]) & (x <= x_crop[1])
    pred = np.asarray(prediction, float)[:, mask]
    obs = np.asarray(truth, float)[:, mask]
    integrated = float(np.linalg.norm(pred - obs) / np.maximum(np.linalg.norm(obs), 1e-30))
    endpoint = float(
        np.linalg.norm(pred[-1] - obs[-1]) / np.maximum(np.linalg.norm(obs[-1]), 1e-30)
    )
    return {"integrated_relative_l2": integrated, "endpoint_relative_l2": endpoint}


def split_forecast_comparison(
    x: Array,
    t: Array,
    u: Array,
    *,
    cutoffs: Sequence[float] = (80.0, 100.0, 120.0, 140.0),
    x_crop: tuple[float, float] = (-120.0, 120.0),
    train_start: float = 52.0,
    t_ref: float = 50.0,
    dt_internal: float = 0.02,
) -> list[dict]:
    """Compare constant, free-power and KPZ-power D models out of sample."""

    x = np.asarray(x, float)
    t = np.asarray(t, float)
    u = np.asarray(u, float)
    results: list[dict] = []
    for cutoff in cutoffs:
        start_idx = int(np.argmin(np.abs(t - cutoff)))
        start_time = float(t[start_idx])
        relative_times = t[start_idx:] - start_time
        truth = u[start_idx:]

        fits = {
            "constant_D": fit_profiled_weak(
                x, t, u, t_window=(train_start, start_time), x_crop=x_crop, t_ref=t_ref, gamma=0.0
            ),
            "free_power_D": fit_profiled_weak(
                x, t, u, t_window=(train_start, start_time), x_crop=x_crop, t_ref=t_ref
            ),
            "kpz_gamma_1_3": fit_profiled_weak(
                x,
                t,
                u,
                t_window=(train_start, start_time),
                x_crop=x_crop,
                t_ref=t_ref,
                gamma=1.0 / 3.0,
            ),
        }
        model_results = {}
        for label, fit in fits.items():
            prediction = forecast_profile(
                x,
                relative_times,
                truth[0],
                fit=fit,
                absolute_start_time=start_time,
                dt_internal=dt_internal,
            )
            metrics = forecast_error(prediction, truth, x, x_crop=x_crop)
            model_results[label] = {
                "fit": {
                    "a": fit.a,
                    "D0": fit.D0,
                    "gamma": fit.gamma,
                    "train_mse": fit.mse,
                    "n_train_obs": fit.n_obs,
                },
                "test": metrics,
            }
        results.append(
            {
                "cutoff_requested": float(cutoff),
                "cutoff_actual": start_time,
                "test_t_max": float(t[-1]),
                "models": model_results,
            }
        )
    return results


def constant_closure_observed_window(
    x: Array,
    t: Array,
    u: Array,
    *,
    x_crop: tuple[float, float] = (-120.0, 120.0),
    fit_window: tuple[float, float] = (52.0, 198.0),
    dt_internal: float = 0.02,
) -> tuple[WeakFit, Array, dict[str, Array]]:
    """Fit constant D globally and predict the whole observed window from t[0]."""

    fit = fit_profiled_weak(x, t, u, t_window=fit_window, x_crop=x_crop, gamma=0.0)
    relative_t = np.asarray(t, float) - float(t[0])
    prediction = forecast_profile(
        x,
        relative_t,
        np.asarray(u, float)[0],
        fit=fit,
        absolute_start_time=float(t[0]),
        dt_internal=dt_internal,
    )
    width = front_width_series(x, t, prediction, x_crop=x_crop)
    return fit, prediction, width


def extended_constant_closure_width(
    x: Array,
    t: Array,
    u: Array,
    *,
    fit: WeakFit,
    t_max: float = 5000.0,
    domain_half_width: int = 2048,
    width_crop: tuple[float, float] = (-1000.0, 1000.0),
    dt_internal: float = 0.2,
    n_outputs: int = 80,
) -> dict[str, Array]:
    """Continue the constant closure to expose its crossover toward rarefaction.

    This is a property of the inferred deterministic PDE, not a prediction that
    the quantum data must follow beyond the observed time range.
    """

    x = np.asarray(x, float)
    t = np.asarray(t, float)
    u = np.asarray(u, float)
    x_ext = np.arange(-domain_half_width, domain_half_width, 1.0)
    initial = np.interp(x_ext, x, u[0], left=u[0, 0], right=u[0, -1])
    physical_times = np.geomspace(float(t[0]), float(t_max), int(n_outputs))
    relative_times = physical_times - float(t[0])
    prediction = forecast_profile(
        x_ext,
        relative_times,
        initial,
        fit=fit,
        absolute_start_time=float(t[0]),
        dt_internal=dt_internal,
    )
    width = front_width_series(x_ext, physical_times, prediction, x_crop=width_crop)
    width["local_exponent"] = local_log_slope(
        width["t"], width["width"], half_window=max(2, n_outputs // 25)
    )
    width["x"] = x_ext
    return width
