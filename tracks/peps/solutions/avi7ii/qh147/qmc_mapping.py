"""Positive Suzuki-Trotter mapping for the transverse-field Ising model."""

from dataclasses import dataclass
from math import cosh, log, sinh, tanh


@dataclass(frozen=True, slots=True)
class ClassicalCouplings:
    """Couplings and beta derivatives for the classical space-time model."""

    beta: float
    h: float
    j: float
    m: int
    ks: float
    kt: float
    log_a: float
    dks: float
    dkt: float
    dlog_a: float


def couplings(beta: float, h: float, m: int, *, j: float) -> ClassicalCouplings:
    """Return the positive classical couplings for ``H = -J ZZ - h X``."""
    if beta <= 0:
        raise ValueError("beta must be positive")
    if h <= 0:
        raise ValueError("h must be positive")
    if j <= 0:
        raise ValueError("j must be positive")
    if m < 2:
        raise ValueError("m must be at least 2")

    a = beta * h / m
    return ClassicalCouplings(
        beta=beta,
        h=h,
        j=j,
        m=m,
        ks=beta * j / m,
        kt=0.5 * log(1.0 / tanh(a)),
        log_a=0.5 * (log(sinh(a)) + log(cosh(a))),
        dks=j / m,
        dkt=-h / (m * sinh(2.0 * a)),
        dlog_a=h / (m * tanh(2.0 * a)),
    )


def energy_from_bond_sums(
    c: ClassicalCouplings,
    *,
    spatial_sum: float,
    temporal_sum: float,
    nsites: int,
) -> float:
    """Return the unbiased internal-energy estimator per physical site."""
    if nsites <= 0:
        raise ValueError("nsites must be positive")
    return -(
        nsites * c.m * c.dlog_a + c.dks * spatial_sum + c.dkt * temporal_sum
    ) / nsites
