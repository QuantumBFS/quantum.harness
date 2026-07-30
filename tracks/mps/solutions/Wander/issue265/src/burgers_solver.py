"""
1D viscous Burgers solver:

    u_t + a u u_x = D u_xx
equivalently
    u_t + (a/2 (u^2))_x = D u_xx.

We implement a conservative finite-volume scheme:
- Convective flux: Godunov flux for Burgers (convex flux)
- Diffusion: central difference Laplacian (explicit)
- Time integration: forward Euler with adaptive dt from CFL constraints

This is intended for *verification* tasks and for generating synthetic datasets,
not for production-grade PDE solving.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Union

import numpy as np

FloatArray = np.ndarray
DType = Union[float, Callable[[float], float]]

@dataclass
class BurgersSolveResult:
    x: FloatArray
    t: FloatArray
    u: FloatArray  # shape (Nt, Nx)
    meta: dict

def _flux(u: FloatArray, a: float) -> FloatArray:
    return 0.5 * a * u**2

def _godunov_flux(uL: FloatArray, uR: FloatArray, a: float) -> FloatArray:
    """
    Godunov flux for scalar conservation law with convex flux f(u)=a/2 u^2, a>0.
    Vectorized over arrays uL,uR.

    For Burgers:
      if uL <= uR (rarefaction):
        if uL > 0 => f(uL)
        elif uR < 0 => f(uR)
        else => f(0)=0
      if uL > uR (shock):
        shock speed s = (f(uL)-f(uR))/(uL-uR) = a/2 (uL+uR)
        if s > 0 => f(uL) else f(uR)
    """
    fL = _flux(uL, a)
    fR = _flux(uR, a)

    rare = uL <= uR
    shock = ~rare

    # rarefaction cases
    flux = np.zeros_like(uL, dtype=float)
    # uL > 0
    mask = rare & (uL > 0)
    flux[mask] = fL[mask]
    # uR < 0
    mask = rare & (uR < 0)
    flux[mask] = fR[mask]
    # crossing zero => 0 already

    # shock cases
    # s = a/2 (uL+uR)
    s = 0.5 * a * (uL + uR)
    mask = shock & (s > 0)
    flux[mask] = fL[mask]
    mask = shock & (s <= 0)
    flux[mask] = fR[mask]

    return flux

def solve_viscous_burgers(
    u0: FloatArray,
    x: FloatArray,
    t_eval: FloatArray,
    a: float,
    D: DType,
    *,
    cfl: float = 0.4,
    bc: str = "neumann",
    dt_max: Optional[float] = None,
) -> BurgersSolveResult:
    """
    Solve viscous Burgers on grid `x` with initial condition u0(x) at times t_eval.

    Parameters
    ----------
    u0 : array, shape (Nx,)
    x : array, shape (Nx,), uniform grid assumed
    t_eval : array, shape (Nt,), increasing
    a : nonlinearity coefficient
    D : viscosity coefficient; either constant float or function D(t)
    cfl : CFL safety factor
    bc : 'neumann' (zero-gradient) or 'periodic'
    dt_max : optional cap on dt

    Returns
    -------
    BurgersSolveResult with u[t_i, x_j]
    """
    x = np.asarray(x, dtype=float)
    t_eval = np.asarray(t_eval, dtype=float)
    if np.any(np.diff(t_eval) < 0):
        raise ValueError("t_eval must be non-decreasing")

    u0 = np.asarray(u0, dtype=float)
    if u0.shape != x.shape:
        raise ValueError("u0 and x must have same shape")

    Nx = x.size
    dx = float(x[1] - x[0])
    if Nx < 3:
        raise ValueError("Need at least 3 spatial points")
    if not np.allclose(np.diff(x), dx, atol=1e-12, rtol=1e-9):
        raise ValueError("x grid must be uniform")

    def D_of_t(t: float) -> float:
        return float(D(t) if callable(D) else D)

    Nt = t_eval.size
    u_out = np.zeros((Nt, Nx), dtype=float)
    u = u0.copy()

    t = float(t_eval[0])
    u_out[0] = u.copy()
    out_idx = 1

    def pad(u_in: FloatArray) -> FloatArray:
        if bc == "periodic":
            return np.concatenate([[u_in[-1]], u_in, [u_in[0]]])
        elif bc == "neumann":
            return np.concatenate([[u_in[0]], u_in, [u_in[-1]]])
        else:
            raise ValueError("bc must be 'periodic' or 'neumann'")

    while out_idx < Nt:
        t_target = float(t_eval[out_idx])

        while t < t_target - 1e-15:
            umax = float(np.max(np.abs(u)))
            conv_dt = np.inf if umax == 0 else dx / (abs(a) * umax + 1e-12)
            diff_dt = dx**2 / (2.0 * (D_of_t(t) + 1e-12))
            dt = cfl * min(conv_dt, diff_dt)
            if dt_max is not None:
                dt = min(dt, float(dt_max))
            dt = min(dt, t_target - t)

            up = pad(u)
            uL = up[:-1]
            uR = up[1:]
            F = _godunov_flux(uL, uR, a)
            divF = (F[1:] - F[:-1]) / dx

            Dnow = D_of_t(t)
            u_xx = (up[2:] - 2.0 * up[1:-1] + up[:-2]) / dx**2

            u = u + dt * (-divF + Dnow * u_xx)
            t += dt

        u_out[out_idx] = u.copy()
        out_idx += 1

    meta = dict(a=float(a), bc=bc, cfl=float(cfl), dx=float(dx),
                D=("callable" if callable(D) else float(D)))
    return BurgersSolveResult(x=x, t=t_eval, u=u_out, meta=meta)
