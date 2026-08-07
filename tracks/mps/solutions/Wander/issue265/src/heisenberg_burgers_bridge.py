"""Algebraic bridge from Heisenberg spin hydrodynamics to Burgers modes.

This module deliberately separates two statements that are often conflated:

1. A scalar Burgers current ``j_m = a m**2 / 2`` for the physical
   magnetization is forbidden by spin-flip symmetry at zero magnetization.
2. The symmetry-allowed two-mode fluctuating hydrodynamics for magnetization
   ``m`` and its effective velocity ``phi`` diagonalizes into two Burgers
   fields of opposite chirality when the long-time couplings and diffusion
   constants coincide.

The microscopic input for the two-mode theory is generalized hydrodynamics of
giant Heisenberg-chain quasiparticles.  The functions here implement the
model-independent algebra and the moment-level KPZ predictions used by the
repository's derivation note.
"""

from __future__ import annotations

import numpy as np


Array = np.ndarray


def ghd_moment_amplitude(
    D0: float = 5.0 * np.pi / 27.0,
    chi: float = 0.25,
) -> float:
    """Return the GHD square-root moment-law amplitude.

    The self-consistent GHD moment closure gives
    ``dW/dt=A/sqrt(W)`` with
    ``A=(8/3) D0 sqrt(chi)`` in the convention used by this repository.
    At infinite temperature this is ``20*pi/81``.
    """

    if D0 <= 0 or chi <= 0:
        raise ValueError("D0 and chi must be positive")
    return float((8.0 / 3.0) * float(D0) * np.sqrt(float(chi)))


def tangent_burgers_coefficients(
    A: float,
    W_star: float,
    U0: float,
    c_f: float,
) -> tuple[float, float, float]:
    """Map a microscopic moment-law tangent to local Burgers coefficients.

    Matching ``A/sqrt(W)`` to ``D/W+v`` at ``W_star`` in both value and
    derivative gives ``D=A sqrt(W_star)/2`` and
    ``v=A/(2 sqrt(W_star))``.  The exact Burgers moment identity then gives
    ``a=4v/(U0*c_f)``.
    """

    values = np.asarray([A, W_star, U0, c_f], dtype=float)
    if np.any(~np.isfinite(values)) or np.any(values <= 0):
        raise ValueError("A, W_star, U0 and c_f must be positive and finite")
    diffusion = 0.5 * float(A) * np.sqrt(float(W_star))
    speed = float(A) / (2.0 * np.sqrt(float(W_star)))
    coefficient = 4.0 * speed / (float(U0) * float(c_f))
    return coefficient, diffusion, speed


def fit_chiral_amplitude_law(
    mu: Array,
    orientation: Array,
    coefficient: Array,
) -> dict[str, float | Array]:
    """Fit ``a=a0+sigma*(c1*mu+c3*mu**3)`` without hiding an intercept."""

    mu = np.asarray(mu, dtype=float)
    orientation = np.asarray(orientation, dtype=int)
    coefficient = np.asarray(coefficient, dtype=float)
    if (
        mu.ndim != 1
        or orientation.shape != mu.shape
        or coefficient.shape != mu.shape
        or mu.size < 4
    ):
        raise ValueError("Amplitude-law arrays must be one-dimensional and matched")
    if np.any(mu <= 0) or np.any(~np.isin(orientation, (-1, 1))):
        raise ValueError("mu must be positive and orientation must be +/-1")
    design = np.column_stack(
        [
            np.ones(mu.size),
            orientation * mu,
            orientation * mu**3,
        ]
    )
    beta, *_ = np.linalg.lstsq(design, coefficient, rcond=None)
    residual = coefficient - design @ beta
    dof = max(mu.size - 3, 1)
    covariance = (
        float(residual @ residual / dof)
        * np.linalg.pinv(design.T @ design)
    )
    return {
        "a0": float(beta[0]),
        "c1": float(beta[1]),
        "c3": float(beta[2]),
        "g_linear": float(beta[1] / 2.0),
        "mse": float(np.mean(residual**2)),
        "covariance": covariance,
        "condition_number": float(np.linalg.cond(design)),
    }


def scalar_magnetization_flux(m: Array, coupling: float) -> Array:
    """Return the Euler flux assumed by a one-field Burgers closure."""

    m = np.asarray(m, dtype=float)
    return 0.5 * float(coupling) * m**2


def scalar_spin_flip_defect(m: Array, coupling: float) -> Array:
    """Measure violation of ``j(-m) = -j(m)`` by the scalar Burgers flux.

    A global pi rotation of the isotropic Heisenberg chain sends both the
    longitudinal magnetization and its current to their negatives.  Hence an
    admissible one-field constitutive current must be odd in ``m``.  The
    returned defect is identically ``coupling * m**2``.
    """

    m = np.asarray(m, dtype=float)
    return scalar_magnetization_flux(-m, coupling) + scalar_magnetization_flux(
        m, coupling
    )


def two_mode_euler_fluxes(
    m: Array,
    phi: Array,
    *,
    coupling: float = 1.0,
    phi_self_coupling: float | None = None,
) -> tuple[Array, Array]:
    """Return the symmetry-allowed two-mode Euler currents.

    ``m`` is spin-flip odd and ``phi`` (the effective magnetization velocity)
    is spin-flip even.  The currents therefore transform as

    ``j_m(-m, phi) = -j_m(m, phi)`` and
    ``j_phi(-m, phi) = j_phi(m, phi)``.

    The long-time two-Burgers fixed point has
    ``phi_self_coupling == coupling``.
    """

    m = np.asarray(m, dtype=float)
    phi = np.asarray(phi, dtype=float)
    if m.shape != phi.shape:
        raise ValueError("m and phi must have the same shape")
    g = float(coupling)
    g_phi = g if phi_self_coupling is None else float(phi_self_coupling)
    j_m = g * m * phi
    j_phi = 0.5 * g * m**2 + 0.5 * g_phi * phi**2
    return j_m, j_phi


def to_chiral_modes(m: Array, phi: Array) -> tuple[Array, Array]:
    """Map physical fields to right/left Burgers normal modes.

    The convention is ``u_plus = m + phi`` and ``u_minus = m - phi``.
    """

    m = np.asarray(m, dtype=float)
    phi = np.asarray(phi, dtype=float)
    if m.shape != phi.shape:
        raise ValueError("m and phi must have the same shape")
    return m + phi, m - phi


def from_chiral_modes(u_plus: Array, u_minus: Array) -> tuple[Array, Array]:
    """Recover ``m`` and ``phi`` from the two chiral modes."""

    u_plus = np.asarray(u_plus, dtype=float)
    u_minus = np.asarray(u_minus, dtype=float)
    if u_plus.shape != u_minus.shape:
        raise ValueError("u_plus and u_minus must have the same shape")
    return 0.5 * (u_plus + u_minus), 0.5 * (u_plus - u_minus)


def chiral_euler_fluxes(
    u_plus: Array,
    u_minus: Array,
    *,
    coupling: float = 1.0,
) -> tuple[Array, Array]:
    """Return opposite-chirality Burgers fluxes for ``u_plus`` and ``u_minus``."""

    u_plus = np.asarray(u_plus, dtype=float)
    u_minus = np.asarray(u_minus, dtype=float)
    if u_plus.shape != u_minus.shape:
        raise ValueError("u_plus and u_minus must have the same shape")
    g = float(coupling)
    return 0.5 * g * u_plus**2, -0.5 * g * u_minus**2


def normalized_chiral_burgers_coefficient(
    coupling: float,
    amplitude: float,
    *,
    chirality: int,
) -> float:
    """Map a physical chiral Burgers field to a normalized data field.

    If ``q`` satisfies

    ``q_t + chirality * coupling * q * q_x = D * q_xx``

    and the stored field is ``V = q / amplitude``, then ``V`` has nonlinear
    coefficient ``chirality * coupling * amplitude``.  This makes explicit
    that a learned Burgers coefficient depends on the field normalization.
    """

    if chirality not in (-1, 1):
        raise ValueError("chirality must be -1 or +1")
    return float(chirality) * float(coupling) * float(amplitude)


def article_single_chiral_coefficient(
    coupling: float,
    mu: float,
    *,
    chirality: int,
) -> float:
    """Return the article-field coefficient under a single-chiral projection.

    A one-chirality state has ``u_chiral = 2 m``.  Kharkov et al. store
    ``U = m / mu``, hence ``u_chiral = 2 mu U`` and the conditional scalar
    equation has ``a = 2 * chirality * coupling * mu``.

    The actual weak Gibbs wall has zero initial effective velocity and excites
    both chiralities, so this identity is a conditional projection rather
    than a microscopic derivation of the fitted value ``a ~= 0.24``.
    """

    return normalized_chiral_burgers_coefficient(
        coupling,
        2.0 * float(mu),
        chirality=chirality,
    )


def sector_conditioned_scalar_flux(
    m: Array,
    *,
    sector: int,
    coupling: float,
) -> Array:
    """Return a quadratic flux conditioned on a spin-flip-odd sector label.

    A bare scalar flux proportional to ``m**2`` violates
    ``j(-m) = -j(m)``.  If a wall-orientation label also transforms as
    ``sector -> -sector``, the conditional flux
    ``j(m, sector) = sector * coupling * m**2 / 2`` obeys the combined
    symmetry.  Fixing one sector can therefore mimic the article's scalar
    equation on one trajectory, but it is not a local constitutive law of
    ``m`` alone.
    """

    if sector not in (-1, 1):
        raise ValueError("sector must be -1 or +1")
    m = np.asarray(m, dtype=float)
    return 0.5 * float(sector) * float(coupling) * m**2


def linear_response_front_gradient(correlation: Array, chi: float = 0.25) -> Array:
    """Convert ``C^{zz}(x,t)`` to the normalized weak-wall gradient.

    At infinite temperature for spin 1/2, ``chi = 1/4`` and the exact linear
    response identity is ``partial_x U = C^{zz}/chi = 4 C^{zz}``.
    """

    if chi <= 0:
        raise ValueError("chi must be positive")
    return np.asarray(correlation, dtype=float) / float(chi)


def kpz_width(
    t: Array,
    *,
    lambda_kpz: float = 1.9265248888988316,
    scaling_variance: float = 0.510523,
) -> Array:
    """Return the asymptotic standard deviation of the normalized spin peak."""

    t = np.asarray(t, dtype=float)
    if np.any(t <= 0) or lambda_kpz <= 0 or scaling_variance <= 0:
        raise ValueError("t, lambda_kpz and scaling_variance must be positive")
    return np.sqrt(scaling_variance) * (float(lambda_kpz) * t) ** (2.0 / 3.0)


def kpz_moment_diffusivity(
    t: Array,
    *,
    lambda_kpz: float = 1.9265248888988316,
    scaling_variance: float = 0.510523,
) -> Array:
    """Return ``0.5 d Var/dt`` for the asymptotic KPZ spin propagator."""

    t = np.asarray(t, dtype=float)
    if np.any(t <= 0) or lambda_kpz <= 0 or scaling_variance <= 0:
        raise ValueError("t, lambda_kpz and scaling_variance must be positive")
    return (
        (2.0 / 3.0)
        * float(scaling_variance)
        * float(lambda_kpz) ** (4.0 / 3.0)
        * t ** (1.0 / 3.0)
    )
