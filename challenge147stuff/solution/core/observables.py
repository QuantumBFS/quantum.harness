"""Unified thermodynamic-result container and aggregators shared by every
engine (ED, QMC, METTS). Engines return ``ThermoResult``; the observable
contract is engine-agnostic.
"""
from dataclasses import dataclass


@dataclass
class ThermoResult:
    beta: float
    f: float
    u: float
    C: float
    chi: float | None = None
    u_err: float = 0.0
    C_err: float = 0.0
    chi_err: float = 0.0
    n_samples: int | None = None
    bond_dim: int | None = None


def rel_err(a, b):
    """Relative error |a-b|/|b|, or |a-b| when b == 0."""
    if b == 0:
        return abs(a - b)
    return abs(a - b) / abs(b)


def within_tol(a, b, tol):
    return rel_err(a, b) <= tol


def thermodynamics_from_logZ(beta, N, logZ, E_mean, E2_mean):
    """f = -ln Z / (beta N), u = <H>/N, C = beta^2 (<H^2> - <H>^2) / N."""
    f = -logZ / (beta * N)
    u = E_mean / N
    C = beta * beta * (E2_mean - E_mean * E_mean) / N
    return ThermoResult(beta=beta, f=f, u=u, C=C)


def free_energy_from_u(betas, us, local_dim=2):
    """Reconstruct the free-energy density f(beta) from a u(beta) curve.

    Uses d(beta f)/d beta = u  =>  beta f(beta) = (beta f)|_{0} + integral_0^beta u d beta'.
    The integration constant is the infinite-temperature free energy: as beta->0,
    Z -> d^N (d = local Hilbert dim, =2 for spin-1/2), so f(0) = -(1/beta) ln d,
    i.e. (beta f)|_0 -> -N ln d, and per site (beta f)|_0 -> -ln d. Thus

        f(beta) = -(1/beta) ln d + (1/beta) integral_0^beta u(beta') d beta'

    with u(0)=0 (TFIM H is traceless). Trapezoidal. Returns one f per input beta
    (nan for beta=0).
    """
    import math
    betas = list(betas)
    us = list(us)
    bb = [0.0] + betas            # prepend the beta=0, u=0 anchor
    uu = [0.0] + us
    integ = [0.0]
    for i in range(1, len(bb)):
        integ.append(integ[-1] + 0.5 * (uu[i] + uu[i - 1]) * (bb[i] - bb[i - 1]))
    anchor = -math.log(local_dim)
    fs = []
    for i in range(1, len(bb)):
        b = bb[i]
        fs.append((anchor + integ[i]) / b if b > 0 else float("nan"))
    return fs
