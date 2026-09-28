"""
Synthetic datasets for validating parameter inference and drift tests.

We provide two datasets (both generated on a large periodic domain and later cropped for fitting):

1) Constant-D viscous Burgers with ground-truth (a,D) close to Kharkov values.
   Generated using the *Cole–Hopf transformation* (spectral heat-equation solver), which
   yields a solution that satisfies Burgers with extremely small numerical error.

2) Drifting-D(t) dataset with D(t) ~ t^{gamma} (gamma=1/3 as KPZ-inspired effective viscosity).
   Generated using a pseudo-spectral method + RK4 time-stepping. This is still numerical,
   but avoids the strong artificial viscosity of 1st-order finite-volume schemes.

The purpose is methodological:
- ensure regression does NOT produce spurious D drift when ground truth is constant
- ensure regression CAN detect drift when it is present

Once you have real tDMRG data, you can use the same analysis code by loading your npz file.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Union

import numpy as np

@dataclass
class Dataset:
    x: np.ndarray
    t: np.ndarray
    u: np.ndarray  # shape (Nt,Nx)
    meta: dict

def smooth_domain_wall(x: np.ndarray, uL: float, uR: float, width: float) -> np.ndarray:
    """
    Smooth domain wall using tanh profile:
        u(x) = (uL+uR)/2 + (uL-uR)/2 * tanh(-x/width)
    so that x -> -inf gives uL, x -> +inf gives uR.
    """
    x = np.asarray(x, dtype=float)
    return 0.5*(uL+uR) + 0.5*(uL-uR)*np.tanh(-x/width)

def _fft_k(x: np.ndarray) -> np.ndarray:
    """
    Wavenumbers for periodic grid x (uniform).
    """
    dx = float(x[1]-x[0])
    L = dx * x.size
    k = 2*np.pi * np.fft.fftfreq(x.size, d=dx)
    return k

def cole_hopf_solution(
    *,
    x: np.ndarray,
    t: np.ndarray,
    a: float,
    D: float,
    u0: np.ndarray,
) -> np.ndarray:
    """
    Exact (up to spectral discretization) solution of constant-coefficient Burgers via Cole–Hopf.

    Our PDE: u_t + a u u_x = D u_xx.

    Define v = a u. Then:
        v_t + v v_x = D v_xx,
    which is standard Burgers with viscosity D.

    Cole–Hopf: v = -2D (∂_x ln ψ), with ψ_t = D ψ_xx.

    Steps:
    - Given v0(x), construct ψ0(x) s.t. v0 = -2D ψ_x/ψ
      => ψ0 ∝ exp( - ∫ v0/(2D) dx ).
    - Evolve ψ in Fourier space: ψ_k(t) = ψ_k(0) exp(-D k^2 t).
    - Recover v and then u = v/a.

    NOTE: requires periodic domain and that the integral of v0 over the period is ~0 to make ψ periodic.
    For antisymmetric domain walls v0 is odd => integral ~0.
    """
    x = np.asarray(x, float)
    t = np.asarray(t, float)
    u0 = np.asarray(u0, float)
    if u0.shape != x.shape:
        raise ValueError("u0 shape mismatch")

    dx = float(x[1]-x[0])
    k = _fft_k(x)

    v0 = a * u0

    # enforce zero-mean for periodic consistency (safe even if already ~0)
    v0 = v0 - np.mean(v0)

    # compute integral of v0: cumulative trapezoid
    # choose psi0 = exp( - (1/(2D)) * ∫^x v0(s) ds )
    # approximate integral with cumulative sum (midpoint-ish)
    integ = np.cumsum(v0) * dx
    psi0 = np.exp(-integ/(2.0*D))
    psi0 = psi0 / np.mean(psi0)  # normalize to avoid overflow

    psi0_k = np.fft.fft(psi0)

    u_out = np.zeros((t.size, x.size), dtype=float)
    for it, tt in enumerate(t):
        psi_k = psi0_k * np.exp(-D * (k**2) * tt)
        psi = np.fft.ifft(psi_k)
        # derivative
        psi_x = np.fft.ifft(1j*k * psi_k)
        v = -2.0*D * (psi_x/psi)
        u = (v.real) / a
        u_out[it] = u
    return u_out

def solve_burgers_spectral_rk4(
    *,
    x: np.ndarray,
    t: np.ndarray,
    a: float,
    D_of_t: Callable[[float], float],
    u0: np.ndarray,
    dt_internal: float = 0.02,
    dealias: bool = True,
) -> np.ndarray:
    """
    Pseudo-spectral solver for:
        u_t = -a u u_x + D(t) u_xx
    on a periodic domain x.

    Implementation: Strang splitting
      - diffusion step solved *exactly* in Fourier space
      - nonlinearity step integrated with RK4 (dealiased)

    This avoids the severe stability limits / overflows that can occur
    when treating the Laplacian explicitly.
    """
    x = np.asarray(x, float)
    t = np.asarray(t, float)
    u = np.asarray(u0, float).copy()
    k = _fft_k(x)
    k2 = k**2

    def rhs_nl(u_real: np.ndarray) -> np.ndarray:
        uk = np.fft.fft(u_real)
        ux = np.fft.ifft(1j*k*uk).real
        nl = -a * u_real * ux
        if dealias:
            nk = np.fft.fft(nl)
            N = nk.size
            cutoff = N//3
            nk[cutoff:-cutoff] = 0
            nl = np.fft.ifft(nk).real
        return nl

    def diffuse(u_real: np.ndarray, tt: float, dt: float) -> np.ndarray:
        Dnow = float(D_of_t(tt))
        uk = np.fft.fft(u_real)
        uk = uk * np.exp(-Dnow * k2 * dt)
        return np.fft.ifft(uk).real

    u_out = np.zeros((t.size, x.size), dtype=float)
    u_out[0] = u.copy()

    t_cur = float(t[0])
    for it in range(1, t.size):
        t_target = float(t[it])
        while t_cur < t_target - 1e-12:
            dt = min(dt_internal, t_target - t_cur)

            # Strang: half diffusion at t_cur
            u = diffuse(u, t_cur, 0.5*dt)

            # RK4 for nonlinearity only
            k1 = rhs_nl(u)
            k2v = rhs_nl(u + 0.5*dt*k1)
            k3 = rhs_nl(u + 0.5*dt*k2v)
            k4 = rhs_nl(u + dt*k3)
            u = u + (dt/6.0)*(k1 + 2*k2v + 2*k3 + k4)

            # half diffusion at t_cur+dt (use updated time)
            u = diffuse(u, t_cur + dt, 0.5*dt)

            t_cur += dt

        u_out[it] = u.copy()

    return u_out

def make_constantD_dataset(
    *,
    a: float = 0.24,
    D: float = 1.90,
    uL: float = 0.5,
    uR: float = -0.5,
    width: float = 2.0,
    x_min: float = -256.0,
    x_max: float = 256.0,
    dx: float = 0.5,
    t_max: float = 200.0,
    dt_out: float = 1.0,
) -> Dataset:
    # periodic grid
    x = np.arange(x_min, x_max, dx, dtype=float)  # periodic endpoint excluded
    t = np.arange(0.0, t_max + 1e-12, dt_out, dtype=float)
    u0 = smooth_domain_wall(x, uL=uL, uR=uR, width=width)

    u = cole_hopf_solution(x=x, t=t, a=a, D=D, u0=u0)

    meta = dict(kind="constantD_colehopf", a=a, D=D, uL=uL, uR=uR, width=width,
                x_min=x_min, x_max=x_max, dx=dx, t_max=t_max, dt_out=dt_out, bc="periodic")
    return Dataset(x=x, t=t, u=u, meta=meta)

def make_driftingD_dataset(
    *,
    a: float = 0.24,
    D0: float = 1.90,
    gamma: float = 1/3,
    t_ref: float = 50.0,
    uL: float = 0.5,
    uR: float = -0.5,
    width: float = 2.0,
    x_min: float = -256.0,
    x_max: float = 256.0,
    dx: float = 0.5,
    t_max: float = 200.0,
    dt_out: float = 1.0,
    dt_internal: float = 0.01,
) -> Dataset:
    """
    D(t) = D0 * (max(t,t_ref)/t_ref)^gamma  (avoid singularity at t=0).
    """
    x = np.arange(x_min, x_max, dx, dtype=float)
    t = np.arange(0.0, t_max + 1e-12, dt_out, dtype=float)
    u0 = smooth_domain_wall(x, uL=uL, uR=uR, width=width)

    def D_of_t(tt: float) -> float:
        tt2 = max(tt, t_ref)
        return float(D0 * (tt2 / t_ref) ** gamma)

    u = solve_burgers_spectral_rk4(x=x, t=t, a=a, D_of_t=D_of_t, u0=u0, dt_internal=dt_internal, dealias=True)

    meta = dict(kind="driftingD_spectralRK4", a=a, D0=D0, gamma=gamma, t_ref=t_ref,
                uL=uL, uR=uR, width=width, x_min=x_min, x_max=x_max, dx=dx,
                t_max=t_max, dt_out=dt_out, dt_internal=dt_internal, bc="periodic")
    return Dataset(x=x, t=t, u=u, meta=meta)

def save_npz(ds: Dataset, path: str) -> None:
    np.savez_compressed(path, x=ds.x, t=ds.t, u=ds.u, meta=np.array([ds.meta], dtype=object))

def load_npz(path: str) -> Dataset:
    d = np.load(path, allow_pickle=True)
    meta_arr = d["meta"]
    if meta_arr.shape == ():
        meta = meta_arr.item()
    else:
        meta0 = meta_arr.reshape(-1)[0]
        meta = meta0.item() if hasattr(meta0, "item") else meta0
    return Dataset(x=d["x"], t=d["t"], u=d["u"], meta=meta)
