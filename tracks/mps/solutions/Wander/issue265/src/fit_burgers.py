"""
Parameter estimation for viscous Burgers:

    u_t + a u u_x = D u_xx

Two estimators:

(A) Strong form regression:
    u_t = -a u u_x + D u_xx
    Solve least squares in (a,D).

Requires numerical derivatives u_x, u_xx.

(B) Weak form regression (noise-robust):
Write in conservative form:

    u_t + (a/2 u^2)_x = D u_xx

Multiply by test function φ(x), integrate over x and integrate by parts:

    ∫ φ u_t dx = (a/2) ∫ φ_x u^2 dx + D ∫ φ_xx u dx
assuming φ vanishes at boundary or we use compact-support windows.

This avoids computing u_xx from noisy data.

The weak-form idea is standard in equation discovery literature; it is
especially useful for your key task: deciding whether D is constant or drifts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

try:
    from scipy.signal import savgol_filter
except Exception:  # pragma: no cover
    savgol_filter = None  # type: ignore

FloatArray = np.ndarray

@dataclass
class FitResult:
    a: float
    D: float
    stderr_a: float
    stderr_D: float
    rmse: float
    r2: float
    n_obs: int
    method: str
    meta: dict

def _central_diff_x(u: FloatArray, dx: float) -> Tuple[FloatArray, FloatArray]:
    """
    Return (u_x, u_xx) with central differences, same shape as u.
    Boundary points are computed with one-sided differences.
    """
    ux = np.zeros_like(u)
    uxx = np.zeros_like(u)
    ux[..., 1:-1] = (u[..., 2:] - u[..., :-2]) / (2*dx)
    uxx[..., 1:-1] = (u[..., 2:] - 2*u[..., 1:-1] + u[..., :-2]) / (dx**2)

    ux[..., 0] = (u[..., 1] - u[..., 0]) / dx
    ux[..., -1] = (u[..., -1] - u[..., -2]) / dx
    uxx[..., 0] = (u[..., 2] - 2*u[..., 1] + u[..., 0]) / (dx**2)
    uxx[..., -1] = (u[..., -1] - 2*u[..., -2] + u[..., -3]) / (dx**2)
    return ux, uxx

def _spectral_diff_x(u: FloatArray, x: FloatArray) -> Tuple[FloatArray, FloatArray]:
    """
    Spectral derivatives (periodic):
      u_x  = ifft(i k fft(u))
      u_xx = ifft(-k^2 fft(u))
    Works for u with shape (..., Nx). Returns same shape.
    """
    x = np.asarray(x, dtype=float)
    dx = float(x[1] - x[0])
    N = x.size
    k = 2*np.pi * np.fft.fftfreq(N, d=dx)
    uk = np.fft.fft(u, axis=-1)
    ux = np.fft.ifft(1j*k * uk, axis=-1).real
    uxx = np.fft.ifft(-(k**2) * uk, axis=-1).real
    return ux, uxx

def _central_diff_t(u: FloatArray, dt: float) -> FloatArray:
    ut = np.zeros_like(u)
    ut[1:-1, :] = (u[2:, :] - u[:-2, :]) / (2*dt)
    ut[0, :] = (u[1, :] - u[0, :]) / dt
    ut[-1, :] = (u[-1, :] - u[-2, :]) / dt
    return ut

def _maybe_smooth(u: FloatArray, *, axis: int, window: int, poly: int) -> FloatArray:
    if savgol_filter is None or window <= 2:
        return u
    if window % 2 == 0:
        window += 1
    window = min(window, u.shape[axis] - (1 - u.shape[axis] % 2))
    if window < poly + 2:
        return u
    return savgol_filter(u, window_length=window, polyorder=poly, axis=axis, mode="interp")

def fit_strong_form(
    x: FloatArray,
    t: FloatArray,
    u: FloatArray,
    *,
    t_window: Tuple[float, float],
    x_crop: Optional[Tuple[float, float]] = None,
    smooth_x_window: int = 9,
    smooth_t_window: int = 5,
    smooth_poly: int = 3,
    ridge_alpha: float = 1e-10,
    deriv_x: str = "finite",
) -> FitResult:
    """
    Strong-form least squares regression over a chosen time window (and optional x crop).
    """
    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    u = np.asarray(u, dtype=float)

    dx = float(x[1] - x[0])
    dt = float(t[1] - t[0])

    # indices
    t1, t2 = t_window
    tidx = np.where((t >= t1) & (t <= t2))[0]
    if tidx.size < 3:
        raise ValueError("Need at least 3 time points in window")
    u_w = u[tidx, :].copy()
    x_w = x.copy()

    if x_crop is not None:
        x1, x2 = x_crop
        xidx = np.where((x >= x1) & (x <= x2))[0]
        if xidx.size < 5:
            raise ValueError("Need more x points after crop")
        u_w = u_w[:, xidx]
        x_w = x[xidx]
        dx = float(x_w[1] - x_w[0])

    # smoothing
    u_s = _maybe_smooth(u_w, axis=1, window=smooth_x_window, poly=smooth_poly)
    u_s = _maybe_smooth(u_s, axis=0, window=smooth_t_window, poly=min(smooth_poly, 2))

    ut = _central_diff_t(u_s, dt)
    if deriv_x == "finite":
        ux, uxx = _central_diff_x(u_s, dx)
    elif deriv_x == "spectral":
        ux, uxx = _spectral_diff_x(u_s, x_w)
    else:
        raise ValueError("deriv_x must be 'finite' or 'spectral'")

    # Build regression: ut = a*(-u*ux) + D*(uxx)
    f1 = -u_s * ux
    f2 = uxx
    y = ut

    # flatten and remove boundaries in x to reduce one-sided noise
    X = np.stack([f1[:, 2:-2].ravel(), f2[:, 2:-2].ravel()], axis=1)
    Y = y[:, 2:-2].ravel()

    # ridge: (X^T X + αI) β = X^T Y
    XtX = X.T @ X
    XtY = X.T @ Y
    reg = ridge_alpha * np.eye(2)
    beta = np.linalg.solve(XtX + reg, XtY)
    a_hat, D_hat = float(beta[0]), float(beta[1])

    # residuals
    Yhat = X @ beta
    resid = Y - Yhat
    rmse = float(np.sqrt(np.mean(resid**2)))
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((Y - np.mean(Y))**2))
    r2 = 1.0 - ss_res/ss_tot if ss_tot > 0 else float("nan")

    # standard errors (homoskedastic)
    n = X.shape[0]
    p = 2
    sigma2 = ss_res / max(n - p, 1)
    cov = sigma2 * np.linalg.inv(XtX + reg)
    stderr = np.sqrt(np.diag(cov))
    stderr_a, stderr_D = float(stderr[0]), float(stderr[1])

    return FitResult(
        a=a_hat, D=D_hat, stderr_a=stderr_a, stderr_D=stderr_D,
        rmse=rmse, r2=float(r2), n_obs=int(n),
        method="strong_form",
        meta=dict(t_window=t_window, x_crop=x_crop, smooth_x_window=smooth_x_window,
                  smooth_t_window=smooth_t_window, smooth_poly=smooth_poly, ridge_alpha=ridge_alpha, deriv_x=deriv_x)
    )

def _make_test_functions(x: FloatArray, n_phi: int = 9) -> List[FloatArray]:
    """
    Compact-support (actually compact-on-grid) test functions that vanish at boundaries
    together with (approximately) vanishing first derivative at boundaries.

    Construction on the interval [x0, x1]:
      s = (x-x0)/(x1-x0) in [0,1]
      w(s) = s^2 (1-s)^2  (so w(0)=w(1)=w'(0)=w'(1)=0)
      phi_n(s) = w(s) * sin(n pi s),  n=1..n_phi

    This choice suppresses boundary terms in the integrations-by-parts used by weak form.
    """
    x = np.asarray(x, dtype=float)
    x0, x1 = float(x[0]), float(x[-1])
    L = x1 - x0
    if L <= 0:
        raise ValueError("x grid must be increasing")
    s = (x - x0) / L
    w = (s**2) * ((1.0 - s)**2)
    phi_list: List[FloatArray] = []
    for n in range(1, n_phi + 1):
        phi = w * np.sin(n * np.pi * s)
        phi_list.append(phi)
    return phi_list

def fit_weak_form(
    x: FloatArray,
    t: FloatArray,
    u: FloatArray,
    *,
    t_window: Tuple[float, float],
    x_crop: Optional[Tuple[float, float]] = None,
    n_phi: int = 11,
    sigma: float = 25.0,
    smooth_x_window: int = 9,
    smooth_t_window: int = 5,
    smooth_poly: int = 3,
    ridge_alpha: float = 1e-10,
) -> FitResult:
    """
    Weak-form regression:
      ∫ φ u_t dx = (a/2) ∫ φ_x u^2 dx + D ∫ φ_xx u dx
    """
    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    u = np.asarray(u, dtype=float)

    dx = float(x[1] - x[0])
    dt = float(t[1] - t[0])

    t1, t2 = t_window
    tidx = np.where((t >= t1) & (t <= t2))[0]
    if tidx.size < 3:
        raise ValueError("Need at least 3 time points in window")
    u_w = u[tidx, :].copy()
    x_w = x.copy()

    if x_crop is not None:
        x1, x2 = x_crop
        xidx = np.where((x >= x1) & (x <= x2))[0]
        if xidx.size < 11:
            raise ValueError("Need more x points after crop")
        u_w = u_w[:, xidx]
        x_w = x[xidx]
        dx = float(x_w[1] - x_w[0])

    # smoothing
    u_s = _maybe_smooth(u_w, axis=1, window=smooth_x_window, poly=smooth_poly)
    u_s = _maybe_smooth(u_s, axis=0, window=smooth_t_window, poly=min(smooth_poly, 2))

    ut = _central_diff_t(u_s, dt)

    # test functions
    phis = _make_test_functions(x_w, n_phi=n_phi)

    # numerical derivatives of phi
    Phi = np.stack(phis, axis=0)  # (n_phi, Nx)
    Phi_x, Phi_xx = _central_diff_x(Phi, dx)

    # build linear system b = (a/2)A + D B
    rows = []
    rhs = []

    for it in range(u_s.shape[0]):
        u_it = u_s[it]
        ut_it = ut[it]
        for k in range(n_phi):
            phi = Phi[k]
            phix = Phi_x[k]
            phixx = Phi_xx[k]

            b = np.trapz(phi * ut_it, x_w)
            A = np.trapz(phix * (u_it**2), x_w)
            B = np.trapz(phixx * u_it, x_w)
            rows.append([0.5 * A, B])
            rhs.append(b)

    X = np.asarray(rows, dtype=float)
    Y = np.asarray(rhs, dtype=float)

    XtX = X.T @ X
    XtY = X.T @ Y
    reg = ridge_alpha * np.eye(2)
    beta = np.linalg.solve(XtX + reg, XtY)
    a_hat, D_hat = float(beta[0]), float(beta[1])

    Yhat = X @ beta
    resid = Y - Yhat
    rmse = float(np.sqrt(np.mean(resid**2)))
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((Y - np.mean(Y))**2))
    r2 = 1.0 - ss_res/ss_tot if ss_tot > 0 else float("nan")

    n = X.shape[0]
    p = 2
    sigma2 = ss_res / max(n - p, 1)
    cov = sigma2 * np.linalg.inv(XtX + reg)
    stderr = np.sqrt(np.diag(cov))
    stderr_a, stderr_D = float(stderr[0]), float(stderr[1])

    return FitResult(
        a=a_hat, D=D_hat, stderr_a=stderr_a, stderr_D=stderr_D,
        rmse=rmse, r2=float(r2), n_obs=int(n),
        method="weak_form",
        meta=dict(t_window=t_window, x_crop=x_crop, n_phi=n_phi,
                  smooth_x_window=smooth_x_window, smooth_t_window=smooth_t_window,
                  smooth_poly=smooth_poly, ridge_alpha=ridge_alpha)
    )

def scan_time_windows(
    x: FloatArray,
    t: FloatArray,
    u: FloatArray,
    *,
    window: float,
    step: float,
    method: str = "weak_form",
    x_crop: Optional[Tuple[float, float]] = (-120.0, 120.0),
    deriv_x: str = "finite",
) -> List[FitResult]:
    """
    Sliding window scan:
      windows: [t_i, t_i+window] with step
    """
    t0 = float(t[0])
    t_end = float(t[-1])
    results: List[FitResult] = []
    ti = t0
    while ti + window <= t_end + 1e-12:
        tw = (ti, ti + window)
        if method == "weak_form":
            fr = fit_weak_form(x, t, u, t_window=tw, x_crop=x_crop)
        elif method == "strong_form":
            fr = fit_strong_form(x, t, u, t_window=tw, x_crop=x_crop, deriv_x=deriv_x)
        else:
            raise ValueError("method must be 'weak_form' or 'strong_form'")
        results.append(fr)
        ti += step
    return results