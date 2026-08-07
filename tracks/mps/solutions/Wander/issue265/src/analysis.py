"""
Analysis utilities:
- convert FitResult list -> table
- drift tests for D(t): constant vs power-law
- KPZ scaling collapse check u(x,t) ~ u(x / t^{2/3})
- produce plots

These routines aim at the key question: is D a true constant or drifting effective viscosity?
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .fit_burgers import FitResult

def fits_to_dataframe(fits: List[FitResult]) -> pd.DataFrame:
    rows = []
    for fr in fits:
        t1, t2 = fr.meta["t_window"]
        rows.append(dict(
            t1=t1, t2=t2, t_center=0.5*(t1+t2),
            a=fr.a, D=fr.D, stderr_a=fr.stderr_a, stderr_D=fr.stderr_D,
            rmse=fr.rmse, r2=fr.r2, n_obs=fr.n_obs, method=fr.method
        ))
    return pd.DataFrame(rows)

def fit_D_constant(df: pd.DataFrame) -> Dict[str, float]:
    """
    Weighted mean estimate of constant D using stderr as weights.
    """
    w = 1.0 / np.maximum(df["stderr_D"].to_numpy()**2, 1e-18)
    D_hat = float(np.sum(w * df["D"].to_numpy()) / np.sum(w))
    # naive SE of weighted mean
    se = float(np.sqrt(1.0 / np.sum(w)))
    return dict(D_const=D_hat, stderr=se)

def fit_D_powerlaw(df: pd.DataFrame, *, t_ref: float = 50.0) -> Dict[str, float]:
    """
    Fit D(t) = D0 * (t/t_ref)^gamma via weighted linear regression in log space.

    Note: caller should pre-filter df if it wants to exclude early-time transients.
    """
    t = df["t_center"].to_numpy()
    D = df["D"].to_numpy()
    sigma = df["stderr_D"].to_numpy()
    mask = (t > 0) & (D > 0) & np.isfinite(sigma) & (sigma > 0)
    t = t[mask]
    D = D[mask]
    sigma = sigma[mask]
    if len(t) < 3:
        return dict(D0=float("nan"), gamma=float("nan"), stderr_logD0=float("nan"), stderr_gamma=float("nan"), t_ref=t_ref)
    # weights in log space: delta log D ~ sigma/D
    w = 1.0 / np.maximum((sigma / D)**2, 1e-18)
    X = np.column_stack([np.ones_like(t), np.log(t / t_ref)])
    y = np.log(D)
    XtW = X.T * w
    beta = np.linalg.solve(XtW @ X, XtW @ y)
    logD0, gamma = beta
    D0 = float(np.exp(logD0))
    resid = y - X @ beta
    dof = max(len(y) - 2, 1)
    sigma2 = float(np.sum(w * resid**2) / dof)
    cov = sigma2 * np.linalg.inv(XtW @ X)
    se_logD0, se_gamma = np.sqrt(np.diag(cov))
    return dict(D0=D0, gamma=float(gamma), stderr_logD0=float(se_logD0), stderr_gamma=float(se_gamma), t_ref=t_ref)
def model_aic(y: np.ndarray, yhat: np.ndarray, k: int) -> float:
    """
    AIC for Gaussian residuals: n*log(RSS/n) + 2k
    """
    resid = y - yhat
    n = len(y)
    rss = float(np.sum(resid**2))
    rss = max(rss, 1e-30)
    return float(n * np.log(rss / n) + 2*k)

def compare_D_models(df: pd.DataFrame, *, t_ref: float = 50.0, t_min: float = 0.0) -> Dict[str, float]:
    """
    Compare constant-D vs power-law D(t) using AIC on the window estimates.
    This is NOT a fully rigorous time-series model, but a useful diagnostic.
    """
    df2 = df[df["t_center"] >= t_min].copy()
    if len(df2) < 3:
        df2 = df.copy()
    t = df2["t_center"].to_numpy()
    D = df2["D"].to_numpy()

    const = fit_D_constant(df2)
    D_const = const["D_const"]
    yhat_const = np.full_like(D, D_const)
    aic_const = model_aic(D, yhat_const, k=1)

    plaw = fit_D_powerlaw(df2, t_ref=t_ref)
    D0, gamma = plaw["D0"], plaw["gamma"]
    yhat_plaw = D0 * (t / t_ref) ** gamma
    aic_plaw = model_aic(D, yhat_plaw, k=2)

    return dict(
        t_min=t_min,
        D_const=D_const, stderr_D_const=const["stderr"], aic_const=aic_const,
        D0=D0, gamma=gamma, stderr_gamma=plaw["stderr_gamma"], aic_plaw=aic_plaw,
        delta_aic=aic_const - aic_plaw
    )

def kpz_collapse_score(x: np.ndarray, t: np.ndarray, u: np.ndarray, *, times: List[float], zeta: float = 2/3) -> Dict[str, float]:
    """
    Rough collapse score for u(x,t) vs xi=x/t^zeta:
    - interpolate each profile onto a common xi grid
    - compute variance across times
    Smaller score => better collapse
    """
    x = np.asarray(x, float)
    t = np.asarray(t, float)
    u = np.asarray(u, float)

    # choose profiles
    idx = []
    for tt in times:
        j = int(np.argmin(np.abs(t - tt)))
        idx.append(j)
    idx = sorted(set(idx))

    # common xi grid
    xi_min = -20
    xi_max = 20
    n_xi = 801
    xi_grid = np.linspace(xi_min, xi_max, n_xi)

    U = []
    for j in idx:
        tj = float(t[j])
        xi = x / (tj ** zeta)
        uj = u[j]
        # interpolate
        uj_i = np.interp(xi_grid, xi, uj)
        U.append(uj_i)
    U = np.stack(U, axis=0)  # (n_times,n_xi)

    # variance across times
    var = np.var(U, axis=0)
    score = float(np.mean(var))
    return dict(score=score, n_times=U.shape[0], zeta=zeta, xi_min=xi_min, xi_max=xi_max)

def estimate_instantaneous_series(
    x: np.ndarray,
    t: np.ndarray,
    u: np.ndarray,
    *,
    x_crop: Tuple[float, float] = (-120.0, 120.0),
    smooth_x_window: int = 9,
    smooth_t_window: int = 5,
    smooth_poly: int = 3,
    ridge_alpha: float = 1e-10,
    deriv_x: str = "finite",
) -> pd.DataFrame:
    """
    Instantaneous (per-time) strong-form regression:
        u_t(t_i,x) = -a(t_i) u u_x + D(t_i) u_xx

    This is the most direct diagnostic for your key question "D constant or drifting".
    Window-averaging can bias the estimate when D(t) varies inside the window.

    Returns DataFrame with columns:
        t, a, D, stderr_a, stderr_D, rmse, r2, n_obs
    """
    x = np.asarray(x, float)
    t = np.asarray(t, float)
    u = np.asarray(u, float)

    # crop indices
    x1, x2 = x_crop
    xidx = np.where((x >= x1) & (x <= x2))[0]
    if xidx.size < 10:
        raise ValueError("x_crop too small")

    # smoothing via Savitzky-Golay if available (imported in fit_burgers, but we keep local fallback)
    try:
        from scipy.signal import savgol_filter
    except Exception:
        savgol_filter = None

    def maybe_smooth(arr: np.ndarray, axis: int, window: int, poly: int) -> np.ndarray:
        if savgol_filter is None or window <= 2:
            return arr
        if window % 2 == 0:
            window += 1
        window = min(window, arr.shape[axis] - (1 - arr.shape[axis] % 2))
        if window < poly + 2:
            return arr
        return savgol_filter(arr, window_length=window, polyorder=poly, axis=axis, mode="interp")

    u_s = u.copy()
    u_s = maybe_smooth(u_s, axis=1, window=smooth_x_window, poly=smooth_poly)
    u_s = maybe_smooth(u_s, axis=0, window=smooth_t_window, poly=min(smooth_poly, 2))

    dt = float(t[1] - t[0])
    dx = float(x[1] - x[0])

    # time derivative
    ut = np.zeros_like(u_s)
    ut[1:-1, :] = (u_s[2:, :] - u_s[:-2, :]) / (2*dt)
    ut[0, :] = (u_s[1, :] - u_s[0, :]) / dt
    ut[-1, :] = (u_s[-1, :] - u_s[-2, :]) / dt

    # spatial derivatives
    if deriv_x == "finite":
        ux = np.zeros_like(u_s)
        uxx = np.zeros_like(u_s)
        ux[:, 1:-1] = (u_s[:, 2:] - u_s[:, :-2]) / (2*dx)
        uxx[:, 1:-1] = (u_s[:, 2:] - 2*u_s[:, 1:-1] + u_s[:, :-2]) / (dx**2)
        ux[:, 0] = (u_s[:, 1] - u_s[:, 0]) / dx
        ux[:, -1] = (u_s[:, -1] - u_s[:, -2]) / dx
        uxx[:, 0] = (u_s[:, 2] - 2*u_s[:, 1] + u_s[:, 0]) / (dx**2)
        uxx[:, -1] = (u_s[:, -1] - 2*u_s[:, -2] + u_s[:, -3]) / (dx**2)
    elif deriv_x == "spectral":
        # spectral on full domain (assumes periodic)
        k = 2*np.pi * np.fft.fftfreq(x.size, d=dx)
        uk = np.fft.fft(u_s, axis=1)
        ux = np.fft.ifft(1j*k[None, :]*uk, axis=1).real
        uxx = np.fft.ifft(-(k[None, :]**2)*uk, axis=1).real
    else:
        raise ValueError("deriv_x must be 'finite' or 'spectral'")

    rows = []
    for it in range(1, len(t)-1):  # avoid ends for ut accuracy
        f1 = -(u_s[it, xidx] * ux[it, xidx])
        f2 = uxx[it, xidx]
        Y = ut[it, xidx]
        X = np.stack([f1, f2], axis=1)

        XtX = X.T @ X
        XtY = X.T @ Y
        beta = np.linalg.solve(XtX + ridge_alpha*np.eye(2), XtY)
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
        cov = sigma2 * np.linalg.inv(XtX + ridge_alpha*np.eye(2))
        se = np.sqrt(np.diag(cov))
        rows.append(dict(
            t=float(t[it]),
            a=a_hat, D=D_hat,
            stderr_a=float(se[0]), stderr_D=float(se[1]),
            rmse=rmse, r2=float(r2), n_obs=int(n),
            deriv_x=deriv_x
        ))

    return pd.DataFrame(rows)

def drift_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """
    Practical drift metrics for D(t):
      - relative_range = (max-min)/median
      - relative_std = std/mean
    """
    D = df["D"].to_numpy()
    D = D[np.isfinite(D)]
    if len(D) == 0:
        return dict(relative_range=float("nan"), relative_std=float("nan"))
    med = float(np.median(D))
    return dict(
        relative_range=float((np.max(D)-np.min(D)) / (med + 1e-12)),
        relative_std=float(np.std(D) / (np.mean(D) + 1e-12)),
    )

def plot_D_inst(df: pd.DataFrame, out_png: str, *, title: str) -> None:
    plt.figure()
    plt.errorbar(df["t"], df["D"], yerr=df["stderr_D"], fmt="o", capsize=2)
    plt.xlabel("t")
    plt.ylabel("D(t) instantaneous")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    plt.close()

def plot_D_inst_models(df: pd.DataFrame, out_png: str, *, t_ref: float = 50.0, t_min: float = 80.0, title: str="") -> Dict[str, float]:
    """
    Use the same compare_D_models by renaming columns.
    """
    df2 = df.rename(columns={"t":"t_center"}).copy()
    df2["stderr_D"] = df2["stderr_D"].replace(0, np.nan)
    cmp = compare_D_models(df2, t_ref=t_ref, t_min=t_min)
    tvals = df2[df2["t_center"] >= t_min]["t_center"].to_numpy()
    Dvals = df2[df2["t_center"] >= t_min]["D"].to_numpy()

    plt.figure()
    plt.errorbar(tvals, Dvals, yerr=df2[df2["t_center"] >= t_min]["stderr_D"], fmt="o", capsize=2, label="instant fits")
    plt.plot(tvals, np.full_like(tvals, cmp["D_const"]), "--", label=f"const D={cmp['D_const']:.3g}")
    plt.plot(tvals, cmp["D0"]*(tvals/t_ref)**cmp["gamma"], "-", label=f"power γ={cmp['gamma']:.3g}")
    plt.xlabel("t")
    plt.ylabel("D(t)")
    plt.title(title + f" (t_min={t_min}, ΔAIC={cmp['delta_aic']:.2f})")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    plt.close()
    return cmp

def plot_D_time(df: pd.DataFrame, out_png: str, *, title: str) -> None:
    plt.figure()
    plt.errorbar(df["t_center"], df["D"], yerr=df["stderr_D"], fmt="o", capsize=3)
    plt.xlabel("t (window center)")
    plt.ylabel("D fitted")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    plt.close()

def plot_a_time(df: pd.DataFrame, out_png: str, *, title: str) -> None:
    plt.figure()
    plt.errorbar(df["t_center"], df["a"], yerr=df["stderr_a"], fmt="o", capsize=3)
    plt.xlabel("t (window center)")
    plt.ylabel("a fitted")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    plt.close()

def plot_D_models(df: pd.DataFrame, out_png: str, *, t_ref: float = 50.0, title: str = "") -> Dict[str, float]:
    cmp = compare_D_models(df, t_ref=t_ref, t_min=80.0)
    t = df["t_center"].to_numpy()
    plt.figure()
    plt.errorbar(t, df["D"], yerr=df["stderr_D"], fmt="o", capsize=3, label="window fits")
    plt.plot(t, np.full_like(t, cmp["D_const"]), "--", label=f"const D={cmp['D_const']:.3g}")
    plt.plot(t, cmp["D0"]*(t/t_ref)**cmp["gamma"], "-", label=f"power law γ={cmp['gamma']:.3g}")
    plt.xlabel("t (window center)")
    plt.ylabel("D fitted")
    plt.title(title + f"  (ΔAIC = {cmp['delta_aic']:.2f})")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    plt.close()
    return cmp