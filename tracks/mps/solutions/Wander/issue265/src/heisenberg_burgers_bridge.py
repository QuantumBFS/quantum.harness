"""Algebraic bridge from Heisenberg spin hydrodynamics to local surrogates.

This module deliberately separates two statements that are often conflated:

1. A scalar Burgers current ``j_m = a m**2 / 2`` for the physical
   magnetization is forbidden by spin-flip symmetry at zero magnetization.
2. A two-mode Markov embedding can diagonalize into opposite-chirality
   Burgers fields under additional equal-coupling assumptions.  This is one
   possible approximation to projected memory, not a forced microscopic
   closure.

The microscopic input for the hierarchy is generalized hydrodynamics of giant
Heisenberg-chain quasiparticles.  The functions here implement theory-only
KPZ projections as well as algebraic diagnostics for optional local closures.
"""

from __future__ import annotations

import numpy as np


Array = np.ndarray
EXACT_D0_INFINITY_T = 5.0 * np.pi / 27.0
SPECTRAL_REGULATOR_D1_INFINITY_T = -2.0 / (3.0 * np.pi)
EXACT_MOMENT_AMPLITUDE_INFINITY_T = 20.0 * np.pi / 81.0
KPZ_SCALING_VARIANCE = 0.5105232641882116
KPZ_SCALING_FOURTH_MOMENT = 0.7329422666735
KPZ_SCALING_FOURTH_CUMULANT = (
    KPZ_SCALING_FOURTH_MOMENT - 3.0 * KPZ_SCALING_VARIANCE**2
)
# For a monotone wall U in [-1/2,1/2] with normalized gradient p=U_x,
# this is the universal stationary-KPZ shape integral
#
#   c_f = integral (1/4-U(y)^2) dy / ((1/4)*sqrt(kappa_2)).
#
# It is evaluated from the published Praehofer--Spohn scaling table, not from
# a Heisenberg trajectory.
KPZ_BURGERS_MOMENT_SHAPE_FACTOR = 2.26610743

# Dimensionless current-projection integrals of the stationary
# Praehofer--Spohn KPZ scaling function.  Their definitions are documented in
# docs/FIRST_PRINCIPLES_WINDOW_DERIVATION.md.
KPZ_CURRENT_PROJECTION_INTEGRALS = (
    0.01796891439985088,
    1.0 / 12.0,
    0.38981359141372784,
    0.04337638795660849,
    0.20239428327375839,
)
KPZ_CURRENT_M2_INTEGRAL = 0.10516244792479386

# Additional universal integrals for the monotone stationary-KPZ wall
# U=F_KPZ-1/2.  They are, respectively,
#
#   integral (1/4-U**2) dy,
#   integral y**2 (1/4-U**2) dy.
#
# Together with the second and fourth moments of f_KPZ they give an
# independent moment-level obstruction to an exact constant-coefficient
# Burgers closure.  As above, these numbers are from the universal KPZ table,
# not from a Heisenberg trajectory.
KPZ_BURGERS_MOMENT_INTEGRALS = (
    0.40478856655038264,
    0.16594389757736522,
)

# Dimensionless strong-form integrals for the stationary KPZ wall
# U(y)=F_KPZ(y)-1/2.  In the order used below they are
#
#   integral U^2 f^2 dy,
#   integral (-U f f') dy,
#   integral (f')^2 dy,
#   integral U y f^2 dy,
#   integral y f f' dy.
#
# They turn the pointwise PDE-discovery loss
# ||U_t + a U U_x - D U_xx||_{L2(dx dt)} into a 2x2 analytic normal
# equation.  The numbers come only from the published universal stationary
# KPZ table; no Heisenberg trajectory is involved.
KPZ_STRONG_PROJECTION_INTEGRALS = (
    0.021535507369069163,
    0.08685200752835978,
    0.3622109781575311,
    0.04719664632988316,
    -0.19490697177313526,
)


def giant_string_diffusion_amplitude_quadrature(
    *,
    quadrature_order: int = 600,
    xi_cutoff: float = 30.0,
) -> float:
    r"""Quadrature of the exact infinite-temperature giant-string ``D0``.

    Equations (22)--(23) of the supplement to arXiv:2003.13708 reduce the
    zero-field XXX diffusion singularity to

    ``D0 = integral_0^inf (2*xi/sinh(xi))**2``
    ``     *(xi*coth(xi)+1)/(9*pi) dxi = 5*pi/27``.

    This function evaluates the first expression without using a spin-chain
    trajectory or the closed-form answer.  It is useful as a normalization
    test before any finite-field or finite-time coefficient is extracted.
    The omitted tail is exponentially small at the default cutoff.
    """

    order = int(quadrature_order)
    cutoff = float(xi_cutoff)
    if order < 64 or not np.isfinite(cutoff) or cutoff < 12.0:
        raise ValueError("Require quadrature_order>=64 and xi_cutoff>=12")
    nodes, weights = np.polynomial.legendre.leggauss(order)
    xi = 0.5 * cutoff * (nodes + 1.0)
    jacobian = 0.5 * cutoff
    integrand = (
        (2.0 * xi / np.sinh(xi)) ** 2
        * (xi / np.tanh(xi) + 1.0)
        / (9.0 * np.pi)
    )
    return float(jacobian * np.dot(weights, integrand))


def _kpz_projection_system(
    t_min: float,
    t_max: float,
    lambda_kpz: float,
    spatial_integrals: tuple[float, float, float, float, float],
) -> tuple[Array, Array]:
    """Return the normal equations for the current-space KPZ projection."""

    A, B, C, r, s = map(float, spatial_integrals)
    ell_scale = float(lambda_kpz) ** (2.0 / 3.0)
    integral_L = (
        ell_scale
        * (3.0 / 5.0)
        * (t_max ** (5.0 / 3.0) - t_min ** (5.0 / 3.0))
    )
    integral_inverse_L = (
        (3.0 / ell_scale)
        * (t_max ** (1.0 / 3.0) - t_min ** (1.0 / 3.0))
    )
    integral_L2_over_t = (
        ell_scale**2
        * (3.0 / 4.0)
        * (t_max ** (4.0 / 3.0) - t_min ** (4.0 / 3.0))
    )
    integral_L_over_t = (
        ell_scale
        * (3.0 / 2.0)
        * (t_max ** (2.0 / 3.0) - t_min ** (2.0 / 3.0))
    )
    gram = np.array(
        [
            [A * integral_L, B * (t_max - t_min)],
            [B * (t_max - t_min), C * integral_inverse_L],
        ],
        dtype=float,
    )
    rhs = (2.0 / 3.0) * np.array(
        [r * integral_L2_over_t, s * integral_L_over_t], dtype=float
    )
    return gram, rhs


def _kpz_strong_projection_system(
    t_min: float,
    t_max: float,
    lambda_kpz: float,
    spatial_integrals: tuple[float, float, float, float, float],
) -> tuple[Array, Array]:
    r"""Return normal equations for the original pointwise strong loss.

    For ``U(x,t)=F_KPZ(x/L)-1/2``, ``f=F_KPZ'`` and
    ``L=(lambda_kpz*t)^(2/3)``, the three fields entering

    ``U_t = a*(-U*U_x) + D*U_xx``

    are ``U_t=-(2/3)*y*f/t``, ``-U*U_x=-U*f/L`` and
    ``U_xx=f'/L^2``.  All time integrals are elementary.
    """

    g11, g12, g22, r1, r2 = map(float, spatial_integrals)
    ell_scale = float(lambda_kpz) ** (2.0 / 3.0)
    integral_inverse_L = (
        3.0
        / ell_scale
        * (t_max ** (1.0 / 3.0) - t_min ** (1.0 / 3.0))
    )
    integral_inverse_L2 = (
        3.0
        / ell_scale**2
        * (t_min ** (-1.0 / 3.0) - t_max ** (-1.0 / 3.0))
    )
    integral_inverse_L3 = (
        (1.0 / ell_scale**3) * (1.0 / t_min - 1.0 / t_max)
    )
    integral_inverse_t = np.log(t_max / t_min)
    integral_inverse_tL = (
        3.0
        / (2.0 * ell_scale)
        * (t_min ** (-2.0 / 3.0) - t_max ** (-2.0 / 3.0))
    )
    gram = np.array(
        [
            [g11 * integral_inverse_L, g12 * integral_inverse_L2],
            [g12 * integral_inverse_L2, g22 * integral_inverse_L3],
        ],
        dtype=float,
    )
    rhs = (2.0 / 3.0) * np.array(
        [r1 * integral_inverse_t, -r2 * integral_inverse_tL], dtype=float
    )
    return gram, rhs


def ghd_moment_amplitude(
    D0: float = EXACT_D0_INFINITY_T,
    chi: float = 0.25,
) -> float:
    """Return the infinite-temperature GHD/KPZ moment-law amplitude.

    The giant-string TBA result is ``D0=lim_{h->0} h D(h)=5*pi/27`` at
    infinite temperature.  Combining the GHD self-consistency relation with
    the KPZ variance gives ``D_moment=A*sqrt(W)`` with
    ``A=(8/3) D0 sqrt(chi)=20*pi/81`` for ``chi=1/4``.
    """

    if D0 <= 0 or chi <= 0:
        raise ValueError("D0 and chi must be positive")
    return float((8.0 / 3.0) * float(D0) * np.sqrt(float(chi)))


def kpz_lambda_from_tba(
    D0: float = EXACT_D0_INFINITY_T,
    chi: float = 0.25,
    scaling_variance: float = KPZ_SCALING_VARIANCE,
) -> float:
    """Return the giant-string self-consistent KPZ scale.

    ``D0`` is the controlled TBA input.  Converting it into ``lambda_kpz``
    additionally uses the thermal-fluctuation self-consistency argument and
    the stationary-KPZ variance; it is not an independent exact TBA identity.
    """

    if D0 <= 0 or chi <= 0 or scaling_variance <= 0:
        raise ValueError("D0, chi and scaling_variance must be positive")
    sigma = np.sqrt(float(scaling_variance))
    return float(4.0 * float(D0) * np.sqrt(float(chi)) / sigma**1.5)


def finite_field_spectral_regulator_diffusion(
    h: float,
    *,
    cutoff_xi: float = 40.0,
) -> float:
    r"""Evaluate the infinite-temperature *spectral regulator* at field ``h``.

    With ``n=s+1``, the closed TBA sum is

    ``4*sinh(h)^2/(9*pi) * sum_{n>=2} n^4/(n^2-1)``
    ``* csch(n*h)^2 * (1+n*tanh(h)*coth(n*h))``.

    Its small-field expansion is

    ``5*pi/(27*h) - 2/(3*pi) + O(h)``.

    This is the analytically tractable spectral expression used to recover
    the giant-string singularity.  It omits the dressed kernel that appears
    in the full finite-field physical spin diffusion constant, so the
    constant term must not be relabelled as the latter's physical ``D1``.
    ``cutoff_xi`` truncates the exponentially convergent variable ``n*h``.
    """

    h = float(h)
    cutoff_xi = float(cutoff_xi)
    if not np.isfinite(h) or not np.isfinite(cutoff_xi):
        raise ValueError("h and cutoff_xi must be finite")
    if h <= 0.0 or h > 0.5:
        raise ValueError("Require 0 < h <= 0.5")
    if cutoff_xi < 15.0 or cutoff_xi > 300.0:
        raise ValueError("Require 15 <= cutoff_xi <= 300")

    n_max = int(np.ceil(cutoff_xi / h))
    n = np.arange(2, n_max + 1, dtype=float)
    nh = n * h
    summand = (
        n**4
        / (n**2 - 1.0)
        / np.sinh(nh) ** 2
        * (1.0 + n * np.tanh(h) / np.tanh(nh))
    )
    return float(4.0 * np.sinh(h) ** 2 / (9.0 * np.pi) * np.sum(summand))


def finite_field_scale_correction(
    D1: float = SPECTRAL_REGULATOR_D1_INFINITY_T,
    *,
    D0: float = EXACT_D0_INFINITY_T,
    chi: float = 0.25,
) -> float:
    r"""Map a putative ``D(h)=D0/h+D1`` term to the KPZ scale correction.

    The giant-string self-consistency equation

    ``ell^2 = 2*(D0/h(ell)+D1)*t``,
    ``h(ell)=1/sqrt(4*chi*ell)``

    gives ``ell=C*t^(2/3)*(1+b*t^(-1/3)+...)`` with
    ``C=(4*D0*sqrt(chi))^(2/3)`` and ``b=4*D1/(3*C^2)``.

    Passing the spectral-regulator constant as ``D1`` is a diagnostic only;
    it does not promote that constant to the full physical finite-field
    diffusion coefficient.
    """

    D0 = float(D0)
    D1 = float(D1)
    chi = float(chi)
    if not np.all(np.isfinite([D0, D1, chi])) or D0 <= 0.0 or chi <= 0.0:
        raise ValueError("D0 and chi must be positive and inputs finite")
    leading_scale = (4.0 * D0 * np.sqrt(chi)) ** (2.0 / 3.0)
    return float(4.0 * D1 / (3.0 * leading_scale**2))


def kpz_tcl_gradient_coefficients(
    t: Array,
    *,
    lambda_kpz: float | None = None,
    variance: float = KPZ_SCALING_VARIANCE,
    fourth_cumulant: float = KPZ_SCALING_FOURTH_CUMULANT,
) -> dict[str, Array]:
    r"""Return the first two coefficients of the exact KPZ TCL generator.

    If ``p_k(t)=fhat(k*L(t))`` and ``L=(lambda*t)^(2/3)``, then exactly

    ``d_t p_k = -k^2 D_TCL(k,t) p_k``

    with

    ``D_TCL=-(2/3)*(L^2/t)*d_z(log(fhat(z)))/z``.

    Expanding about ``z=0`` gives

    ``p_t = D2(t)*p_xx + H4(t)*p_xxxx + ...``,
    ``D2=(2/3)*variance*L^2/t`` and
    ``H4=fourth_cumulant*L^4/(9*t)``.

    At the front scale ``k*L=O(1)`` this gradient series is not controlled;
    the full nonlocal Fourier multiplier is the appropriate leading mean
    equation.
    """

    t = np.asarray(t, dtype=float)
    lam = kpz_lambda_from_tba() if lambda_kpz is None else float(lambda_kpz)
    variance = float(variance)
    fourth_cumulant = float(fourth_cumulant)
    if (
        np.any(~np.isfinite(t))
        or np.any(t <= 0.0)
        or not np.all(np.isfinite([lam, variance, fourth_cumulant]))
        or lam <= 0.0
        or variance <= 0.0
    ):
        raise ValueError("t, lambda_kpz and variance must be positive and finite")
    length = (lam * t) ** (2.0 / 3.0)
    diffusion = (2.0 / 3.0) * variance * length**2 / t
    hyperdiffusion = fourth_cumulant * length**4 / (9.0 * t)
    return {
        "length": length,
        "diffusion": diffusion,
        "hyperdiffusion": hyperdiffusion,
    }


def theory_only_current_projection(
    t_min: float = 50.0,
    t_max: float = 200.0,
    *,
    lambda_kpz: float | None = None,
    spatial_integrals: tuple[float, float, float, float, float] = (
        KPZ_CURRENT_PROJECTION_INTEGRALS
    ),
) -> tuple[float, float]:
    """Project the asymptotic KPZ current onto constant Burgers operators.

    No Heisenberg trajectory enters this calculation.  The input profile is
    the stationary universal KPZ scaling function, whose five dimensionless
    integrals are ``(A,B,C,r,s)``.  The returned pair depends on the declared
    current-space Galerkin projection and is therefore a finite-window
    effective pair, not a pair of microscopic transport invariants.
    """

    t_min = float(t_min)
    t_max = float(t_max)
    if not (0.0 < t_min < t_max):
        raise ValueError("Require 0 < t_min < t_max")
    lam = kpz_lambda_from_tba() if lambda_kpz is None else float(lambda_kpz)
    if not np.isfinite(lam) or lam <= 0:
        raise ValueError("lambda_kpz must be positive and finite")
    A, B, C, r, s = map(float, spatial_integrals)
    if np.any(~np.isfinite([A, B, C, r, s])) or min(A, C, r, s) <= 0:
        raise ValueError("KPZ spatial integrals must be finite and positive")

    gram, rhs = _kpz_projection_system(
        t_min, t_max, lam, (A, B, C, r, s)
    )
    coefficient, diffusion = np.linalg.solve(gram, rhs)
    return float(coefficient), float(diffusion)


def theory_only_running_current_projection(
    t: Array,
    *,
    lambda_kpz: float | None = None,
    spatial_integrals: tuple[float, float, float, float, float] = (
        KPZ_CURRENT_PROJECTION_INTEGRALS
    ),
    moment_integral: float = KPZ_CURRENT_M2_INTEGRAL,
) -> dict[str, Array | float]:
    r"""Return the scale-running local projection of the KPZ mean current.

    At each time the exact leading scaling current is

    ``j_KPZ=Ldot*M(y)``, ``y=x/L``.

    Projecting it in space onto

    ``j_loc=a(t)*q1(y)+D(t)*q2(y)/L``

    gives ``a(t)=alpha*Ldot`` and ``D(t)=delta*L*Ldot``.  The two
    dimensionless constants ``alpha,delta`` solve a time-independent 2x2
    Galerkin system.  Consequently ``a(t) ~ t**(-1/3)`` and
    ``D(t) ~ t**(1/3)``.  This is the minimal local one-field approximation
    compatible with KPZ scaling; replacing it by constants is an additional
    finite-window compression.
    """

    times = np.asarray(t, dtype=float)
    lam = kpz_lambda_from_tba() if lambda_kpz is None else float(lambda_kpz)
    A, B, C, r, s = map(float, spatial_integrals)
    moment_integral = float(moment_integral)
    if (
        np.any(~np.isfinite(times))
        or np.any(times <= 0.0)
        or not np.isfinite(lam)
        or lam <= 0.0
        or np.any(~np.isfinite([A, B, C, r, s, moment_integral]))
        or min(A, C, r, s, moment_integral) <= 0.0
    ):
        raise ValueError("Times and KPZ projection inputs must be positive and finite")

    gram = np.array([[A, B], [B, C]], dtype=float)
    rhs = np.array([r, s], dtype=float)
    alpha, delta = np.linalg.solve(gram, rhs)
    length = (lam * times) ** (2.0 / 3.0)
    length_rate = (2.0 / 3.0) * lam ** (2.0 / 3.0) * times ** (-1.0 / 3.0)
    coefficient = alpha * length_rate
    diffusion = delta * length * length_rate
    residual_squared = (
        moment_integral
        - 2.0 * float(np.array([alpha, delta]) @ rhs)
        + float(np.array([alpha, delta]) @ gram @ np.array([alpha, delta]))
    )
    return {
        "coefficient": coefficient,
        "diffusion": diffusion,
        "length": length,
        "length_rate": length_rate,
        "alpha": float(alpha),
        "delta": float(delta),
        "relative_current_residual": float(
            np.sqrt(max(residual_squared, 0.0) / moment_integral)
        ),
        "gram_condition_number": float(np.linalg.cond(gram)),
    }


def mori_kernel_from_structure_laplace(
    wavenumber: Array,
    laplace_frequency: Array,
    static_structure: Array,
    structure_laplace: Array,
    *,
    lattice: bool = False,
) -> Array:
    r"""Invert a density correlator to its exact linear Mori memory kernel.

    For a conserved lattice density, the normalized structure factor obeys

    ``d_t S(k,t)=-khat**2 integral_0^t K(k,t-s) S(k,s) ds``.

    Hence

    ``Ktilde=(S(k,0)/Stilde-z)/khat**2``.

    ``khat=2*sin(k/2)`` retains the exact nearest-neighbour lattice
    continuity factor; the continuum convention uses ``khat=k``.  This
    identity contains no Markov or white-noise assumption.
    """

    k = np.asarray(wavenumber, dtype=float)
    z = np.asarray(laplace_frequency, dtype=float)
    s0 = np.asarray(static_structure, dtype=float)
    st = np.asarray(structure_laplace, dtype=float)
    k, z, s0, st = np.broadcast_arrays(k, z, s0, st)
    if (
        np.any(~np.isfinite(k))
        or np.any(~np.isfinite(z))
        or np.any(~np.isfinite(s0))
        or np.any(~np.isfinite(st))
        or np.any(z < 0.0)
        or np.any(s0 <= 0.0)
        or np.any(st <= 0.0)
    ):
        raise ValueError("Mori inputs must be finite with z>=0 and S0,Stilde>0")
    khat = 2.0 * np.sin(0.5 * k) if lattice else k
    if np.any(np.abs(khat) < 1e-15):
        raise ValueError("The conserved k=0 mode has no invertible dissipative kernel")
    return (s0 / st - z) / khat**2


def xxx_mori_short_time_moments(
    wavenumber: Array,
    *,
    exchange: float = 1.0,
) -> dict[str, Array]:
    r"""Return the first two exact microscopic moments of the XXX Mori kernel.

    For ``H=J sum_j S_j.S_{j+1}`` at infinite temperature, project the
    Liouvillian dynamics of the Fourier magnetization onto that magnetization.
    With ``khat=2*sin(k/2)`` and

    ``d_t F=-khat**2 integral_0^t K(k,t-s)F(k,s) ds``, one obtains

    ``K(k,0)=J**2/2``

    and

    ``-d_t**2 K(k,0)=J**4*(1/2-cos(k)/4)``.

    Consequently ``K=K0-second_moment*t**2/2+O(t**4)``.  These are local
    Hilbert--Schmidt commutator identities; no spin-transport trajectory or
    fitted hydrodynamic coefficient enters them.
    """

    k = np.asarray(wavenumber, dtype=float)
    J = float(exchange)
    if np.any(~np.isfinite(k)) or not np.isfinite(J):
        raise ValueError("wavenumber and exchange must be finite")
    second_moment = J**4 * (0.5 - 0.25 * np.cos(k))
    return {
        "khat": 2.0 * np.sin(0.5 * k),
        "kernel_at_zero": np.full_like(k, 0.5 * J**2, dtype=float),
        "second_moment": second_moment,
        "quadratic_coefficient": -0.5 * second_moment,
    }


def xxx_mori_even_moments(
    wavenumber: Array,
    *,
    exchange: float = 1.0,
) -> dict[int, Array]:
    r"""Return exact XXX Mori spectral moments through order sixteen.

    The convention is ``K(k,t)=sum_n (-1)^n mu[2*n]*t**(2*n)/(2*n)!``.
    Sparse Pauli-string commutators on rings larger than the operator support
    give the following thermodynamic local identities.  They contain no
    trajectory information.
    """

    k = np.asarray(wavenumber, dtype=float)
    J = float(exchange)
    if np.any(~np.isfinite(k)) or not np.isfinite(J):
        raise ValueError("wavenumber and exchange must be finite")
    return {
        0: np.full_like(k, 0.5 * J**2, dtype=float),
        2: J**4 * (0.5 - 0.25 * np.cos(k)),
        4: J**6 * (
            11.0 / 8.0 - 15.0 / 16.0 * np.cos(k) + 1.0 / 8.0 * np.cos(2.0 * k)
        ),
        6: J**8 * (
            95.0 / 16.0
            - 259.0 / 64.0 * np.cos(k)
            + 27.0 / 32.0 * np.cos(2.0 * k)
            - 5.0 / 64.0 * np.cos(3.0 * k)
        ),
        8: J**10 * (
            4457.0 / 128.0
            - 1263.0 / 64.0 * np.cos(k)
            + 317.0 / 64.0 * np.cos(2.0 * k)
            - 49.0 / 64.0 * np.cos(3.0 * k)
            + 7.0 / 128.0 * np.cos(4.0 * k)
        ),
        10: J**12 * (
            66119.0 / 256.0
            - 25573.0 / 256.0 * np.cos(k)
            + 7345.0 / 256.0 * np.cos(2.0 * k)
            - 5811.0 / 1024.0 * np.cos(3.0 * k)
            + 45.0 / 64.0 * np.cos(4.0 * k)
            - 21.0 / 512.0 * np.cos(5.0 * k)
        ),
        12: J**14 * (
            296391.0 / 128.0
            - 1686043.0 / 4096.0 * np.cos(k)
            + 84431.0 / 512.0 * np.cos(2.0 * k)
            - 39303.0 / 1024.0 * np.cos(3.0 * k)
            + 12881.0 / 2048.0 * np.cos(4.0 * k)
            - 2673.0 / 4096.0 * np.cos(5.0 * k)
            + 33.0 / 1024.0 * np.cos(6.0 * k)
        ),
        14: J**16 * (
            99561985.0 / 4096.0
            + 13520761.0 / 16384.0 * np.cos(k)
            + 7514507.0 / 8192.0 * np.cos(2.0 * k)
            - 4079257.0 / 16384.0 * np.cos(3.0 * k)
            + 49933.0 / 1024.0 * np.cos(4.0 * k)
            - 111969.0 / 16384.0 * np.cos(5.0 * k)
            + 5005.0 / 8192.0 * np.cos(6.0 * k)
            - 429.0 / 16384.0 * np.cos(7.0 * k)
        ),
        16: J**18 * (
            9567505701.0 / 32768.0
            + 34306115.0 / 512.0 * np.cos(k)
            + 84399355.0 / 16384.0 * np.cos(2.0 * k)
            - 26404215.0 / 16384.0 * np.cos(3.0 * k)
            + 2877591.0 / 8192.0 * np.cos(4.0 * k)
            - 1959425.0 / 32768.0 * np.cos(5.0 * k)
            + 30017.0 / 4096.0 * np.cos(6.0 * k)
            - 4719.0 / 8192.0 * np.cos(7.0 * k)
            + 715.0 / 32768.0 * np.cos(8.0 * k)
        ),
    }


def xxx_mori_long_wave_lanczos(*, exchange: float = 1.0) -> dict[str, Array]:
    r"""Return thirteen exact long-wave Mori--Lanczos recurrents.

    For the symmetric kernel spectral measure,

    ``Ktilde=mu0/(z+b1**2/(z+b2**2/(z+...)))``.

    The values below follow algebraically from the exact moments through
    ``mu26``.  The last five moments are obtained directly from the uniform-current
    commutator chain, which is the ``k -> 0`` density force.  A terminator
    beyond ``b13`` is still required to represent the
    continuum and its KPZ low-frequency singularity.
    """

    J = float(exchange)
    if not np.isfinite(J):
        raise ValueError("exchange must be finite")
    squared = J**2 * np.asarray(
        [
            1.0 / 2.0,
            7.0 / 4.0,
            89.0 / 28.0,
            5199.0 / 1246.0,
            16362745.0 / 3701688.0,
            533174919181.0 / 97222755720.0,
            155669008835604501.0 / 28007079431635030.0,
            4880178544612122657668885.0 / 717500221130768922597084.0,
            1661338264320398559685770311237065.0
            / 250046006650855968625336278366756.0,
            8947223295590546232590956669440969508183131.0
            / 1157939709161061360332266823095747081714670.0,
            4998855168101323939519657338176816790733704038061133749.0
            / 662940090391383920022207046600208806645584336263399720.0,
            50132156701168705499901888783939441335625086510164717309097902703635.0
            / 5723858454419032516985810177548916159600312473930368972463971550968.0,
            3830599597503707351550130770645203489092745851543132140176839142618275372045569703.0
            / 432843590440934458009633813168074175889453230158717769172869909448364119630832969.0,
        ]
    )
    return {
        "mu0": np.asarray(0.5 * J**2),
        "mu18": np.asarray(726837552981.0 / 131072.0 * J**20),
        "mu20": np.asarray(23930343808959.0 / 262144.0 * J**22),
        "mu22": np.asarray(6735689494485335.0 / 4194304.0 * J**24),
        "mu24": np.asarray(503357997961442429.0 / 16777216.0 * J**26),
        "mu26": np.asarray(9934914094146058465.0 / 16777216.0 * J**28),
        "squared_recurrents": squared,
        "recurrents": np.sqrt(squared),
    }


def xxx_mori_lanczos_recurrents(
    wavenumber: Array,
    *,
    exchange: float = 1.0,
) -> Array:
    """Return eight momentum-dependent recurrents fixed by ``mu0..mu16``.

    A Stieltjes/Gram--Schmidt construction is used instead of explicit moment
    formulas.  For the symmetric spectral measure the monic polynomials obey
    ``p[n+1]=omega*p[n]-b[n]**2*p[n-1]`` and
    ``b[n+1]**2=<p[n+1],p[n+1]>/<p[n],p[n]>``.
    """

    k = np.asarray(wavenumber, dtype=float)
    moments = xxx_mori_even_moments(k, exchange=exchange)
    flattened = {order: np.ravel(value) for order, value in moments.items()}
    recurrent_count = max(moments) // 2
    output = np.empty((k.size, recurrent_count), dtype=float)
    for position in range(k.size):
        spectral = {
            order: float(value[position]) for order, value in flattened.items()
        }

        def inner(left: Array, right: Array) -> float:
            total = 0.0
            for left_order, left_value in enumerate(left):
                for right_order, right_value in enumerate(right):
                    total += (
                        left_value
                        * right_value
                        * spectral.get(left_order + right_order, 0.0)
                    )
            return total

        previous = np.zeros(1, dtype=float)
        polynomial = np.ones(1, dtype=float)
        previous_norm = np.nan
        norm = inner(polynomial, polynomial)
        for level in range(recurrent_count):
            beta = 0.0 if level == 0 else norm / previous_norm
            shifted = np.pad(polynomial, (1, 0))
            projected = np.pad(previous, (0, shifted.size - previous.size))
            following = shifted - beta * projected
            following_norm = inner(following, following)
            output[position, level] = following_norm / norm
            previous, polynomial = polynomial, following
            previous_norm, norm = norm, following_norm
    squared = output.reshape(k.shape + (recurrent_count,))
    if np.any(~np.isfinite(squared)) or np.any(squared <= 0.0):
        raise ValueError("moments do not define positive recurrents")
    return squared


def mori_lanczos_terminator_from_kernel(
    laplace_frequency: Array,
    kernel_laplace: Array,
    mu0: float,
    squared_recurrents: Array,
) -> Array:
    r"""Peel a finite Mori--Lanczos continued fraction from a kernel.

    If ``C0=Ktilde/mu0`` and ``Cn=1/(z+b[n+1]**2*C[n+1])``, repeated inversion
    returns the exact remaining Stieltjes terminator.  This operation makes no
    pole-count or Markov assumption.
    """

    z = np.asarray(laplace_frequency, dtype=float)
    kernel = np.asarray(kernel_laplace, dtype=float)
    b2 = np.asarray(squared_recurrents, dtype=float)
    z, kernel = np.broadcast_arrays(z, kernel)
    mu0 = float(mu0)
    if (
        np.any(~np.isfinite(z))
        or np.any(~np.isfinite(kernel))
        or np.any(z < 0.0)
        or np.any(kernel <= 0.0)
        or not np.isfinite(mu0)
        or mu0 <= 0.0
        or b2.ndim != 1
        or b2.size == 0
        or np.any(~np.isfinite(b2))
        or np.any(b2 <= 0.0)
    ):
        raise ValueError("Require z>=0 and positive finite Stieltjes data")
    tail = kernel / mu0
    for recurrent in b2:
        tail = (1.0 / tail - z) / recurrent
    return tail


def mori_kernel_from_lanczos_terminator(
    laplace_frequency: Array,
    terminator: Array,
    mu0: float,
    squared_recurrents: Array,
) -> Array:
    """Reconstruct ``Ktilde`` from a Mori--Lanczos terminator."""

    z = np.asarray(laplace_frequency, dtype=float)
    tail = np.asarray(terminator, dtype=float)
    b2 = np.asarray(squared_recurrents, dtype=float)
    z, tail = np.broadcast_arrays(z, tail)
    mu0 = float(mu0)
    if (
        np.any(~np.isfinite(z))
        or np.any(~np.isfinite(tail))
        or np.any(z < 0.0)
        or np.any(tail <= 0.0)
        or not np.isfinite(mu0)
        or mu0 <= 0.0
        or b2.ndim != 1
        or b2.size == 0
        or np.any(~np.isfinite(b2))
        or np.any(b2 <= 0.0)
    ):
        raise ValueError("Require z>=0 and positive finite Stieltjes data")
    for recurrent in b2[::-1]:
        tail = 1.0 / (z + recurrent * tail)
    return mu0 * tail


def mori_lanczos_stieltjes_bounds(
    laplace_frequency: Array,
    mu0: float,
    squared_recurrents: Array,
) -> dict[str, Array]:
    r"""Return endpoint bounds allowed by finitely many Mori moments.

    The normalized unresolved terminator is a Stieltjes transform.  For real
    ``z>0`` it obeys ``0 <= T(z) <= 1/z``.  The positive finite continued
    fraction is fractional-linear in ``T``; evaluating these two endpoints
    and sorting gives the complete pointwise interval allowed by the supplied
    recurrents alone.  No pole or Markov closure is introduced.
    """

    z = np.asarray(laplace_frequency, dtype=float)
    b2 = np.asarray(squared_recurrents, dtype=float)
    scale = float(mu0)
    if (
        np.any(~np.isfinite(z))
        or np.any(z <= 0.0)
        or b2.ndim != 1
        or b2.size == 0
        or np.any(~np.isfinite(b2))
        or np.any(b2 <= 0.0)
        or not np.isfinite(scale)
        or scale <= 0.0
    ):
        raise ValueError("Require z>0, mu0>0, and positive finite recurrents")

    def evaluate(terminator: Array) -> Array:
        tail = np.asarray(terminator, dtype=float)
        for recurrent in b2[::-1]:
            tail = 1.0 / (z + recurrent * tail)
        return scale * tail

    endpoint_zero = evaluate(np.zeros_like(z))
    endpoint_atom_at_zero = evaluate(1.0 / z)
    return {
        "lower": np.minimum(endpoint_zero, endpoint_atom_at_zero),
        "upper": np.maximum(endpoint_zero, endpoint_atom_at_zero),
        "terminator_zero_endpoint": endpoint_zero,
        "terminator_one_over_z_endpoint": endpoint_atom_at_zero,
    }


def xxx_structure_factor_short_time(
    wavenumber: Array,
    time: Array,
    *,
    exchange: float = 1.0,
) -> Array:
    r"""Return the normalized XXX structure factor through order ``t**4``.

    Combining the exact moments from :func:`xxx_mori_short_time_moments` with
    the Mori equation gives

    ``S(k,t)/S(k,0) = 1-q*K0*t**2/2``

    ``+ (q*mu2+q**2*K0**2)*t**4/24 + O(t**6)``,

    where ``q=(2*sin(k/2))**2``.  This is a microscopic/high-frequency
    expansion, not a controlled extrapolation to hydrodynamic times.
    """

    k = np.asarray(wavenumber, dtype=float)
    t = np.asarray(time, dtype=float)
    k, t = np.broadcast_arrays(k, t)
    if np.any(~np.isfinite(t)):
        raise ValueError("time must be finite")
    moments = xxx_mori_short_time_moments(k, exchange=exchange)
    q = moments["khat"] ** 2
    k0 = moments["kernel_at_zero"]
    mu2 = moments["second_moment"]
    return 1.0 - 0.5 * q * k0 * t**2 + (q * mu2 + q**2 * k0**2) * t**4 / 24.0


def kpz_mori_laplace_scaling(
    wavenumber: Array,
    laplace_frequency: Array,
    scaled_structure_laplace: Array,
    *,
    lambda_kpz: float | None = None,
) -> Array:
    r"""Return the leading KPZ Mori kernel from its scaling transform.

    Write ``Lambda=lambda_kpz*abs(k)**(3/2)``, ``s=z/Lambda`` and

    ``Phi(s)=integral_0^inf exp(-s*tau) fhat(tau**(2/3)) dtau``.

    The KPZ structure factor has ``Stilde/S0=Phi(s)/Lambda``.  Exact Mori
    inversion therefore gives

    ``Ktilde=lambda_kpz*abs(k)**(-1/2)*(1/Phi-s)``.

    This nonanalytic ``|k|**(-1/2)`` scaling is the precise reason a constant
    Markov diffusion coefficient cannot be the asymptotic one-field law.
    ``scaled_structure_laplace`` is ``Phi(s)`` and may be obtained from the
    universal stationary-KPZ table, independently of a spin trajectory.
    """

    k = np.asarray(wavenumber, dtype=float)
    z = np.asarray(laplace_frequency, dtype=float)
    phi = np.asarray(scaled_structure_laplace, dtype=float)
    k, z, phi = np.broadcast_arrays(k, z, phi)
    lam = kpz_lambda_from_tba() if lambda_kpz is None else float(lambda_kpz)
    if (
        np.any(~np.isfinite(k))
        or np.any(~np.isfinite(z))
        or np.any(~np.isfinite(phi))
        or np.any(np.abs(k) < 1e-15)
        or np.any(z < 0.0)
        or np.any(phi <= 0.0)
        or not np.isfinite(lam)
        or lam <= 0.0
    ):
        raise ValueError("Require k!=0, z>=0, Phi>0 and a positive KPZ scale")
    rate = lam * np.abs(k) ** 1.5
    scaled_frequency = z / rate
    return lam * np.abs(k) ** (-0.5) * (1.0 / phi - scaled_frequency)


def kpz_mori_laplace_first_correction(
    wavenumber: Array,
    leading_scaled_structure_laplace: Array,
    correction_scaled_structure_laplace: Array,
    *,
    lambda_kpz: float | None = None,
) -> Array:
    r"""Map the first finite-time structure correction to the Mori kernel.

    Let ``Lambda=lambda*abs(k)**(3/2)`` and suppose the normalized structure
    factor has the low-``k`` Laplace expansion

    ``Ftilde=(Phi0(s)+Lambda**(1/3)*Phi1(s)+...)/Lambda``.

    Exact Mori inversion gives the first subleading kernel

    ``delta Ktilde=-lambda**(4/3)*Phi1/Phi0**2``.

    It is order ``k**0`` whereas the leading KPZ kernel is proportional to
    ``abs(k)**(-1/2)``.  The function does not model or fit ``Phi1``; it makes
    explicit the finite-time quantity that a microscopic GHD/Mori calculation
    still has to determine.
    """

    k = np.asarray(wavenumber, dtype=float)
    phi0 = np.asarray(leading_scaled_structure_laplace, dtype=float)
    phi1 = np.asarray(correction_scaled_structure_laplace, dtype=float)
    k, phi0, phi1 = np.broadcast_arrays(k, phi0, phi1)
    lam = kpz_lambda_from_tba() if lambda_kpz is None else float(lambda_kpz)
    if (
        np.any(~np.isfinite(k))
        or np.any(~np.isfinite(phi0))
        or np.any(~np.isfinite(phi1))
        or np.any(np.abs(k) < 1e-15)
        or np.any(phi0 <= 0.0)
        or not np.isfinite(lam)
        or lam <= 0.0
    ):
        raise ValueError("Require k!=0, Phi0>0 and finite correction inputs")
    return -(lam ** (4.0 / 3.0)) * phi1 / phi0**2


def theory_only_strong_projection(
    t_min: float = 50.0,
    t_max: float = 200.0,
    *,
    lambda_kpz: float | None = None,
    spatial_integrals: tuple[float, float, float, float, float] = (
        KPZ_STRONG_PROJECTION_INTEGRALS
    ),
) -> tuple[float, float]:
    r"""Project the leading KPZ wall using the article's strong PDE loss.

    This minimizes

    ``integral |U_t + a*U*U_x - D*U_xx|^2 dx dt``

    over the declared time window.  It is the continuum counterpart of the
    two active columns in the original PDE-discovery regression.  No spin
    trajectory or fitted wall width enters.  As with the current-space
    projection, the result is a projection-dependent finite-window pair,
    not a microscopic transport invariant.
    """

    t_min = float(t_min)
    t_max = float(t_max)
    if not (0.0 < t_min < t_max):
        raise ValueError("Require 0 < t_min < t_max")
    lam = kpz_lambda_from_tba() if lambda_kpz is None else float(lambda_kpz)
    if not np.isfinite(lam) or lam <= 0.0:
        raise ValueError("lambda_kpz must be positive and finite")
    g11, g12, g22, r1, r2 = map(float, spatial_integrals)
    if (
        np.any(~np.isfinite([g11, g12, g22, r1, r2]))
        or g11 <= 0.0
        or g22 <= 0.0
        or r1 <= 0.0
        or r2 >= 0.0
    ):
        raise ValueError("KPZ strong-form integrals have invalid signs")

    gram, rhs = _kpz_strong_projection_system(
        t_min, t_max, lam, (g11, g12, g22, r1, r2)
    )
    coefficient, diffusion = np.linalg.solve(gram, rhs)
    return float(coefficient), float(diffusion)


def _validate_scale_history(
    time: Array,
    length: Array,
    length_rate: Array,
) -> tuple[Array, Array, Array]:
    """Validate a differentiable one-parameter wall scale history."""

    time = np.asarray(time, dtype=float)
    length = np.asarray(length, dtype=float)
    length_rate = np.asarray(length_rate, dtype=float)
    if (
        time.ndim != 1
        or length.shape != time.shape
        or length_rate.shape != time.shape
        or time.size < 3
        or np.any(~np.isfinite(time))
        or np.any(~np.isfinite(length))
        or np.any(~np.isfinite(length_rate))
        or np.any(np.diff(time) <= 0.0)
        or np.any(length <= 0.0)
        or np.any(length_rate <= 0.0)
    ):
        raise ValueError(
            "time, length and length_rate must be finite one-dimensional "
            "histories with increasing time and positive scale/rate"
        )
    return time, length, length_rate


def _trapz_history(value: Array, time: Array) -> float:
    """Integrate a sampled history without a SciPy dependency."""

    return float(
        np.sum(0.5 * (value[1:] + value[:-1]) * np.diff(time))
    )


def theory_only_strong_projection_from_scale(
    time: Array,
    length: Array,
    length_rate: Array,
    *,
    spatial_integrals: tuple[float, float, float, float, float] = (
        KPZ_STRONG_PROJECTION_INTEGRALS
    ),
) -> tuple[float, float]:
    r"""Project a prescribed KPZ-shaped wall with an arbitrary scale history.

    The profile is ``U(x,t)=F_KPZ(x/L(t))-1/2``.  This function performs the
    same pointwise strong-form projection as
    :func:`theory_only_strong_projection`, but it does not assume
    ``L(t) proportional to t**(2/3)``.  It is therefore suitable for auditing
    a proposed finite-scale correction or a running memory kernel.  The scale
    history itself remains an input; this routine does not promote any
    particular finite-field regulator into a microscopic finite-time law.
    """

    time, length, length_rate = _validate_scale_history(
        time, length, length_rate
    )
    g11, g12, g22, r1, r2 = map(float, spatial_integrals)
    if (
        np.any(~np.isfinite([g11, g12, g22, r1, r2]))
        or g11 <= 0.0
        or g22 <= 0.0
        or r1 <= 0.0
        or r2 >= 0.0
    ):
        raise ValueError("KPZ strong-form integrals have invalid signs")
    inverse_length = 1.0 / length
    gram = np.array(
        [
            [g11 * _trapz_history(inverse_length, time),
             g12 * _trapz_history(inverse_length**2, time)],
            [g12 * _trapz_history(inverse_length**2, time),
             g22 * _trapz_history(inverse_length**3, time)],
        ],
        dtype=float,
    )
    rhs = np.array(
        [
            r1 * _trapz_history(length_rate * inverse_length, time),
            -r2
            * _trapz_history(length_rate * inverse_length**2, time),
        ],
        dtype=float,
    )
    coefficient, diffusion = np.linalg.solve(gram, rhs)
    return float(coefficient), float(diffusion)


def theory_only_current_projection_from_scale(
    time: Array,
    length: Array,
    length_rate: Array,
    *,
    spatial_integrals: tuple[float, float, float, float, float] = (
        KPZ_CURRENT_PROJECTION_INTEGRALS
    ),
) -> tuple[float, float]:
    r"""Project the exact continuity current for an arbitrary scale history.

    For ``U=F_KPZ(x/L)-1/2`` the exact mean current is
    ``j=Ldot*M(x/L)``.  Its conservative two-column projection has normal
    equations

    ``G11=A*int L dt, G12=B*int dt, G22=C*int dt/L`` and
    ``b1=r*int L*Ldot dt, b2=s*int Ldot dt``.

    This identity makes it possible to test running-scale hypotheses without
    reading a spin-chain trajectory.
    """

    time, length, length_rate = _validate_scale_history(
        time, length, length_rate
    )
    A, B, C, r, s = map(float, spatial_integrals)
    if np.any(~np.isfinite([A, B, C, r, s])) or min(A, C, r, s) <= 0.0:
        raise ValueError("KPZ current-projection integrals are invalid")
    duration = float(time[-1] - time[0])
    gram = np.array(
        [
            [A * _trapz_history(length, time), B * duration],
            [B * duration, C * _trapz_history(1.0 / length, time)],
        ],
        dtype=float,
    )
    rhs = np.array(
        [
            r * _trapz_history(length * length_rate, time),
            s * _trapz_history(length_rate, time),
        ],
        dtype=float,
    )
    coefficient, diffusion = np.linalg.solve(gram, rhs)
    return float(coefficient), float(diffusion)


def theory_only_current_projection_diagnostics(
    t_min: float = 50.0,
    t_max: float = 200.0,
    *,
    lambda_kpz: float | None = None,
    spatial_integrals: tuple[float, float, float, float, float] = (
        KPZ_CURRENT_PROJECTION_INTEGRALS
    ),
    moment_integral: float = KPZ_CURRENT_M2_INTEGRAL,
) -> dict[str, float | Array]:
    """Diagnose residual size and identifiability without trajectory data.

    ``moment_integral`` is ``integral M(y)**2 dy`` for the exact stationary
    KPZ scaling function.  The raw Gram condition number is unit-dependent;
    ``normalized_condition_number`` is the condition number after giving the
    two basis functions unit norm and is therefore the more interpretable
    collinearity diagnostic.
    """

    t_min = float(t_min)
    t_max = float(t_max)
    if not (0.0 < t_min < t_max):
        raise ValueError("Require 0 < t_min < t_max")
    lam = kpz_lambda_from_tba() if lambda_kpz is None else float(lambda_kpz)
    if not np.isfinite(lam) or lam <= 0:
        raise ValueError("lambda_kpz must be positive and finite")
    A, B, C, r, s = map(float, spatial_integrals)
    if np.any(~np.isfinite([A, B, C, r, s])) or min(A, C, r, s) <= 0:
        raise ValueError("KPZ spatial integrals must be finite and positive")
    moment_integral = float(moment_integral)
    if not np.isfinite(moment_integral) or moment_integral <= 0:
        raise ValueError("moment_integral must be positive and finite")

    gram, rhs = _kpz_projection_system(
        t_min, t_max, lam, (A, B, C, r, s)
    )
    coefficients = np.linalg.solve(gram, rhs)
    # j_KPZ=(2/3)(L/t)M and L^3=lambda_kpz^2 t^2.
    exact_norm_squared = (
        (4.0 / 9.0)
        * moment_integral
        * lam**2
        * (t_max - t_min)
    )
    residual_squared = (
        exact_norm_squared
        - 2.0 * float(coefficients @ rhs)
        + float(coefficients @ gram @ coefficients)
    )
    residual_squared = max(residual_squared, 0.0)
    spatial_correlation = B / np.sqrt(A * C)
    window_correlation = gram[0, 1] / np.sqrt(gram[0, 0] * gram[1, 1])
    normalized_condition = (1.0 + abs(window_correlation)) / (
        1.0 - abs(window_correlation)
    )
    return {
        "coefficient": float(coefficients[0]),
        "diffusion": float(coefficients[1]),
        "relative_current_residual": float(
            np.sqrt(residual_squared / exact_norm_squared)
        ),
        "spatial_basis_correlation": float(spatial_correlation),
        "window_basis_correlation": float(window_correlation),
        "gram_condition_number": float(np.linalg.cond(gram)),
        "normalized_condition_number": float(normalized_condition),
        "gram": gram,
        "rhs": rhs,
    }


def theory_only_scale_corrected_projection(
    correction: float,
    t_min: float = 50.0,
    t_max: float = 200.0,
    *,
    lambda_kpz: float | None = None,
    spatial_integrals: tuple[float, float, float, float, float] = (
        KPZ_CURRENT_PROJECTION_INTEGRALS
    ),
) -> tuple[float, float]:
    r"""Project a scale-only ``t^{-1/3}`` correction to the KPZ front.

    The ansatz is

    ``L(t)=lambda_kpz**(2/3)*(t**(2/3)+b*t**(1/3))``.

    It changes the scale but deliberately keeps the universal shape fixed.
    This function tests whether such a one-parameter correction can account
    for simultaneous shifts in both Burgers coefficients; it is not a fit to
    a Heisenberg trajectory.
    """

    b = float(correction)
    t_min = float(t_min)
    t_max = float(t_max)
    if not (0.0 < t_min < t_max):
        raise ValueError("Require 0 < t_min < t_max")
    lam = kpz_lambda_from_tba() if lambda_kpz is None else float(lambda_kpz)
    if not np.isfinite(lam) or lam <= 0 or not np.isfinite(b):
        raise ValueError("lambda_kpz must be positive and inputs finite")
    A, B, C, r, s = map(float, spatial_integrals)
    if np.any(~np.isfinite([A, B, C, r, s])) or min(A, C, r, s) <= 0:
        raise ValueError("KPZ spatial integrals must be finite and positive")

    scale = lam ** (2.0 / 3.0)
    u_min = t_min ** (1.0 / 3.0)
    u_max = t_max ** (1.0 / 3.0)
    if u_min + b <= 0.0:
        raise ValueError("The corrected KPZ scale must stay positive")

    def length(t: float) -> float:
        return scale * (t ** (2.0 / 3.0) + b * t ** (1.0 / 3.0))

    integral_L = scale * (
        (3.0 / 5.0) * (t_max ** (5.0 / 3.0) - t_min ** (5.0 / 3.0))
        + b
        * (3.0 / 4.0)
        * (t_max ** (4.0 / 3.0) - t_min ** (4.0 / 3.0))
    )
    if abs(b) < 1e-14:
        integral_inverse_L = (
            3.0 / scale * (u_max - u_min)
        )
    else:
        integral_inverse_L = (3.0 / scale) * (
            (u_max - u_min)
            - b * np.log((u_max + b) / (u_min + b))
        )
    length_min = length(t_min)
    length_max = length(t_max)
    gram = np.array(
        [
            [A * integral_L, B * (t_max - t_min)],
            [B * (t_max - t_min), C * integral_inverse_L],
        ],
        dtype=float,
    )
    # For a self-similar profile j=dot(L) M.  Hence the two right-hand
    # sides are r*integral L dot(L) dt and s*integral dot(L) dt.
    rhs = np.array(
        [
            0.5 * r * (length_max**2 - length_min**2),
            s * (length_max - length_min),
        ],
        dtype=float,
    )
    coefficient, diffusion = np.linalg.solve(gram, rhs)
    return float(coefficient), float(diffusion)


def theory_only_strong_scale_corrected_projection(
    correction: float,
    t_min: float = 50.0,
    t_max: float = 200.0,
    *,
    lambda_kpz: float | None = None,
    spatial_integrals: tuple[float, float, float, float, float] = (
        KPZ_STRONG_PROJECTION_INTEGRALS
    ),
) -> tuple[float, float]:
    r"""Strong-loss projection with a scale-only ``t^(-1/3)`` correction.

    The wall keeps the stationary KPZ shape but uses

    ``L=c*(t^(2/3)+b*t^(1/3))``.

    This is the strong-form analogue of
    :func:`theory_only_scale_corrected_projection`.  In particular, passing
    :func:`finite_field_scale_correction` is only a spectral-regulator
    diagnostic, not a derivation of the full physical finite-field term.
    """

    b = float(correction)
    t_min = float(t_min)
    t_max = float(t_max)
    if not (0.0 < t_min < t_max):
        raise ValueError("Require 0 < t_min < t_max")
    lam = kpz_lambda_from_tba() if lambda_kpz is None else float(lambda_kpz)
    if not np.isfinite(lam) or lam <= 0.0 or not np.isfinite(b):
        raise ValueError("lambda_kpz must be positive and inputs finite")
    g11, g12, g22, r1, r2 = map(float, spatial_integrals)
    if (
        np.any(~np.isfinite([g11, g12, g22, r1, r2]))
        or g11 <= 0.0
        or g22 <= 0.0
        or r1 <= 0.0
        or r2 >= 0.0
    ):
        raise ValueError("KPZ strong-form integrals have invalid signs")

    c = lam ** (2.0 / 3.0)
    u_min = t_min ** (1.0 / 3.0)
    u_max = t_max ** (1.0 / 3.0)
    if u_min + b <= 0.0:
        raise ValueError("The corrected KPZ scale must stay positive")

    def primitive_inverse_cubic(u: float) -> float:
        return (
            np.log(u / (u + b)) / b**3
            + 1.0 / (b**2 * (u + b))
            + 1.0 / (2.0 * b * (u + b) ** 2)
        )

    integral_inverse_L = (3.0 / c) * (
        (u_max - u_min)
        - b * np.log((u_max + b) / (u_min + b))
    )
    integral_inverse_L2 = (3.0 / c**2) * (
        1.0 / (u_min + b) - 1.0 / (u_max + b)
    )
    if abs(b) < 1e-8:
        integral_inverse_L3 = (1.0 / c**3) * (
            1.0 / t_min - 1.0 / t_max
        )
    else:
        integral_inverse_L3 = (3.0 / c**3) * (
            primitive_inverse_cubic(u_max)
            - primitive_inverse_cubic(u_min)
        )
    integral_log_derivative = np.log(
        u_max * (u_max + b) / (u_min * (u_min + b))
    )
    length_min = c * u_min * (u_min + b)
    length_max = c * u_max * (u_max + b)
    integral_Lprime_over_L2 = 1.0 / length_min - 1.0 / length_max

    gram = np.array(
        [
            [g11 * integral_inverse_L, g12 * integral_inverse_L2],
            [g12 * integral_inverse_L2, g22 * integral_inverse_L3],
        ],
        dtype=float,
    )
    rhs = np.array(
        [
            r1 * integral_log_derivative,
            -r2 * integral_Lprime_over_L2,
        ],
        dtype=float,
    )
    coefficient, diffusion = np.linalg.solve(gram, rhs)
    return float(coefficient), float(diffusion)


def theory_only_width_rate_projection(
    t_min: float = 50.0,
    t_max: float = 200.0,
    *,
    lambda_kpz: float | None = None,
    variance: float = KPZ_SCALING_VARIANCE,
    wall_height: float = 0.5,
    shape_factor: float = KPZ_BURGERS_MOMENT_SHAPE_FACTOR,
) -> dict[str, float | Array]:
    r"""Project the theory-only KPZ width rate onto a Burgers moment law.

    The exact leading scaling form fixes the standard deviation of the
    normalized wall gradient to

    ``W(t)=C*t**(2/3)``, ``C=sqrt(variance)*lambda_kpz**(2/3)``.

    A constant Burgers proxy obeys the moment identity

    ``dW/dt = D/W + v``, ``v=a*wall_height*shape_factor/4``.

    This routine minimizes the *declared continuum rate-space loss*

    ``integral_(t_min)^(t_max) (dW/dt-D/W-v)**2 dt``.

    Its normal equations are elementary and use no sampling grid, measured
    width, fitted amplitude, or Heisenberg trajectory.  The result is one
    projection-dependent pair, not a microscopic definition of ``a,D``.
    """

    t_min = float(t_min)
    t_max = float(t_max)
    lam = kpz_lambda_from_tba() if lambda_kpz is None else float(lambda_kpz)
    variance = float(variance)
    wall_height = float(wall_height)
    shape_factor = float(shape_factor)
    values = np.asarray(
        [t_min, t_max, lam, variance, wall_height, shape_factor], dtype=float
    )
    if np.any(~np.isfinite(values)) or not (0.0 < t_min < t_max):
        raise ValueError("Require finite inputs and 0 < t_min < t_max")
    if min(lam, variance, wall_height, shape_factor) <= 0.0:
        raise ValueError("Scale, variance, wall height and shape factor must be positive")

    width_scale = np.sqrt(variance) * lam ** (2.0 / 3.0)
    gram = np.array(
        [
            [
                3.0
                / width_scale**2
                * (t_min ** (-1.0 / 3.0) - t_max ** (-1.0 / 3.0)),
                3.0
                / width_scale
                * (t_max ** (1.0 / 3.0) - t_min ** (1.0 / 3.0)),
            ],
            [
                3.0
                / width_scale
                * (t_max ** (1.0 / 3.0) - t_min ** (1.0 / 3.0)),
                t_max - t_min,
            ],
        ],
        dtype=float,
    )
    rhs = np.array(
        [
            (2.0 / 3.0) * np.log(t_max / t_min),
            width_scale * (t_max ** (2.0 / 3.0) - t_min ** (2.0 / 3.0)),
        ],
        dtype=float,
    )
    diffusion, speed = np.linalg.solve(gram, rhs)
    coefficient = 4.0 * speed / (wall_height * shape_factor)
    target_norm_squared = (
        (4.0 / 3.0)
        * width_scale**2
        * (t_max ** (1.0 / 3.0) - t_min ** (1.0 / 3.0))
    )
    parameters = np.array([diffusion, speed], dtype=float)
    residual_squared = (
        target_norm_squared
        - 2.0 * float(parameters @ rhs)
        + float(parameters @ gram @ parameters)
    )
    return {
        "coefficient": float(coefficient),
        "diffusion": float(diffusion),
        "speed": float(speed),
        "width_scale": float(width_scale),
        "relative_rate_residual": float(
            np.sqrt(max(residual_squared, 0.0) / target_norm_squared)
        ),
        "gram_condition_number": float(np.linalg.cond(gram)),
        "gram": gram,
        "rhs": rhs,
    }


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


def physical_quadratic_current_kubo_vertex() -> float:
    r"""Return the exact zero-field quadratic Kubo vertex of physical current.

    A global pi spin rotation maps the longitudinal source ``h`` and the
    physical current ``j_m`` to their negatives.  Thus the microscopic current
    functional obeys ``<j_m>[h] = -<j_m>[-h]`` and every even functional
    derivative at ``h=0`` vanishes.  A nonzero quadratic Burgers coefficient
    can only be an orientation-conditioned, non-analytic hydrodynamic
    projection after non-commuting long-time and weak-field limits; it is not
    a local-equilibrium Taylor coefficient.
    """

    return 0.0


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


def general_chiral_euler_fluxes(
    u_plus: Array,
    u_minus: Array,
    *,
    lambda_m: float,
    lambda_phi: float,
) -> tuple[Array, Array]:
    """Return the chiral fluxes away from the two-Burgers manifold.

    Starting from

    ``j_m=lambda_m*m*phi`` and
    ``j_phi=(lambda_m*m**2+lambda_phi*phi**2)/2``,

    this returns ``j_plus=j_m+j_phi`` and ``j_minus=j_m-j_phi`` in
    ``u_plus=m+phi`` and ``u_minus=m-phi`` variables.  Mixed-mode terms are
    retained.  They vanish only when ``lambda_m == lambda_phi``.
    """

    u_plus = np.asarray(u_plus, dtype=float)
    u_minus = np.asarray(u_minus, dtype=float)
    if u_plus.shape != u_minus.shape:
        raise ValueError("u_plus and u_minus must have the same shape")
    lm = float(lambda_m)
    lp = float(lambda_phi)
    j_plus = (
        (3.0 * lm + lp) * u_plus**2
        + (lp - lm) * u_minus**2
        + 2.0 * (lm - lp) * u_plus * u_minus
    ) / 8.0
    j_minus = (
        (lm - lp) * u_plus**2
        - (3.0 * lm + lp) * u_minus**2
        - 2.0 * (lm - lp) * u_plus * u_minus
    ) / 8.0
    return j_plus, j_minus


def chiral_diffusive_fluxes(
    grad_u_plus: Array,
    grad_u_minus: Array,
    *,
    Dm: float,
    Dphi: float,
) -> tuple[Array, Array]:
    """Transform diagonal ``m,phi`` diffusion to the chiral basis.

    The returned dissipative currents are

    ``j_plus^d=-Dbar*grad(u_plus)-deltaD*grad(u_minus)`` and
    ``j_minus^d=-deltaD*grad(u_plus)-Dbar*grad(u_minus)``.

    Thus unequal physical diffusivities couple the two nominal Burgers
    modes even if their Euler currents have already diagonalized.
    """

    grad_u_plus = np.asarray(grad_u_plus, dtype=float)
    grad_u_minus = np.asarray(grad_u_minus, dtype=float)
    if grad_u_plus.shape != grad_u_minus.shape:
        raise ValueError("Chiral gradients must have the same shape")
    if Dm <= 0 or Dphi <= 0:
        raise ValueError("Dm and Dphi must be positive")
    Dbar = 0.5 * (float(Dm) + float(Dphi))
    delta_D = 0.5 * (float(Dm) - float(Dphi))
    return (
        -Dbar * grad_u_plus - delta_D * grad_u_minus,
        -delta_D * grad_u_plus - Dbar * grad_u_minus,
    )


def tangent_constitutive_error(A: float, W: Array, W_star: float) -> Array:
    """Return ``A*sqrt(W)`` minus its value-and-slope tangent at ``W_star``."""

    W = np.asarray(W, dtype=float)
    if A <= 0 or W_star <= 0 or np.any(W <= 0):
        raise ValueError("A, W and W_star must be positive")
    diffusion = 0.5 * float(A) * np.sqrt(float(W_star))
    speed = float(A) / (2.0 * np.sqrt(float(W_star)))
    return float(A) * np.sqrt(W) - (diffusion + speed * W)


def weak_projection_coefficients(gram: Array, rhs: Array) -> tuple[float, float]:
    """Solve the two-feature normal equations for profile-level ``a,D``.

    This is an analytic projection of a supplied profile dataset, not a
    first-principles microscopic prediction.  The columns are the weak-form
    nonlinear and diffusion features, in that order.
    """

    gram = np.asarray(gram, dtype=float)
    rhs = np.asarray(rhs, dtype=float)
    if gram.shape != (2, 2) or rhs.shape != (2,):
        raise ValueError("Expected a 2x2 Gram matrix and a two-vector")
    if not np.allclose(gram, gram.T, rtol=1e-12, atol=1e-14):
        raise ValueError("Gram matrix must be symmetric")
    if np.any(~np.isfinite(gram)) or np.any(~np.isfinite(rhs)):
        raise ValueError("Normal-equation inputs must be finite")
    if np.linalg.matrix_rank(gram) < 2:
        raise ValueError("Gram matrix must have full rank")
    coefficient, diffusion = np.linalg.solve(gram, rhs)
    return float(coefficient), float(diffusion)


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
def giant_bare_scattering_kernel(
    xi: float | np.ndarray,
    zeta: float | np.ndarray,
    rapidity_difference: float | np.ndarray,
) -> np.ndarray:
    r"""Leading giant-string bare scattering kernel.

    This is the ``s=xi/h``, ``s'=zeta/h``, ``theta=u/h`` limit of the
    isotropic XXX bare kernel,

    ``T0=pi^-1 log[(4u^2+(xi+zeta)^2)/(4u^2+(xi-zeta)^2)]``.
    """

    xi = np.asarray(xi, dtype=float)
    zeta = np.asarray(zeta, dtype=float)
    u = np.asarray(rapidity_difference, dtype=float)
    numerator = 4.0 * u**2 + (xi + zeta) ** 2
    denominator = 4.0 * u**2 + (xi - zeta) ** 2
    return np.log(numerator / denominator) / np.pi


def zero_field_edge_dressed_momentum_green(
    left_string: int | np.ndarray,
    source_string: int | np.ndarray,
    rapidity_wave_number: float,
) -> np.ndarray:
    r"""Exact zero-field discrete-string dressing Green function.

    At infinite temperature and strictly zero magnetic field,
    ``n_s=1/(s+1)^2``.  If ``Y_s=(1-n_s)F_s``, the local XXX dressing
    recurrence becomes the symmetric Jacobi problem

    ``-Y_(s-1) + 2*cosh(q)/(1-(s+1)^-2)*Y_s - Y_(s+1) = source_s``,

    with ``q=abs(k)/2`` and the boundary ``Y_0=0``.  Its decaying solution is

    ``psi_n=exp(-q*n)*(sinh(q)+cosh(q)/n)``, ``n=s+1``.

    Combining it with the solution regular at ``n=1`` gives the exact
    half-line Green function.  The returned quantity is ``F_s`` for a unit
    source at ``source_string``; it therefore includes the final division by
    ``1-n_s``.  At ``k=0`` the removable limit is evaluated algebraically.
    """

    left = np.asarray(left_string, dtype=int)
    source = np.asarray(source_string, dtype=int)
    left, source = np.broadcast_arrays(left, source)
    if np.any(left < 1) or np.any(source < 1):
        raise ValueError("string indices must be positive")
    n_left = left.astype(float) + 1.0
    n_source = source.astype(float) + 1.0
    n_min = np.minimum(n_left, n_source)
    n_max = np.maximum(n_left, n_source)
    q = 0.5 * abs(float(rapidity_wave_number))
    if q == 0.0:
        green_y = (n_min**2 - 1.0) / (3.0 * n_max)
    else:
        # Factor exp(q*n_min) from the regular solution before multiplying by
        # the decaying solution.  This avoids separately overflowing the two
        # homogeneous solutions when q*n is large.  Long-double arithmetic
        # protects the q^3 cancellation in the boundary Wronskian.
        ql = np.longdouble(q)
        lo = n_min.astype(np.longdouble)
        hi = n_max.astype(np.longdouble)
        sinh_q = np.sinh(ql)
        cosh_q = np.cosh(ql)
        regular_factor = (
            sinh_q
            - cosh_q / lo
            + np.exp(-2.0 * ql * lo) * (sinh_q + cosh_q / lo)
        )
        decaying_factor = sinh_q + cosh_q / hi
        phi_two = (
            np.exp(2.0 * ql) * (sinh_q - cosh_q / 2.0)
            + np.exp(-2.0 * ql) * (sinh_q + cosh_q / 2.0)
        )
        green_y = np.asarray(
            np.exp(-ql * (hi - lo))
            * regular_factor
            * decaying_factor
            / phi_two,
            dtype=float,
        )
    hole_left = 1.0 - 1.0 / n_left**2
    return green_y / hole_left


def zero_field_edge_dressed_scattering_fourier(
    left_string: int | np.ndarray,
    right_string: int | np.ndarray,
    rapidity_wave_number: float,
) -> np.ndarray:
    r"""Exact dressed XXX scattering kernel in the zero-field edge region.

    In the local string recurrence the bare scattering source for right
    string ``s'`` is ``e_(s'-1)+e_(s'+1)``; the lower source is absent for
    ``s'=1``.  This function performs that source sum using
    :func:`zero_field_edge_dressed_momentum_green`.
    """

    left = np.asarray(left_string, dtype=int)
    right = np.asarray(right_string, dtype=int)
    left, right = np.broadcast_arrays(left, right)
    if np.any(right < 1):
        raise ValueError("string indices must be positive")
    result = zero_field_edge_dressed_momentum_green(
        left, right + 1, rapidity_wave_number
    )
    mask = right > 1
    if np.any(mask):
        lower_source = np.where(mask, right - 1, 1)
        lower = zero_field_edge_dressed_momentum_green(
            left, lower_source, rapidity_wave_number
        )
        result = result + np.where(mask, lower, 0.0)
    return result


def zero_field_edge_thermodynamic_fields(
    string: int | np.ndarray,
    rapidity: float | np.ndarray,
) -> dict[str, np.ndarray]:
    r"""Strict-zero-field thermodynamics for discrete XXX strings.

    The magnetic source is retained to first order only.  In particular,
    ``m_s^dr = h*(s+1)^2/3 + O(h^3)``; the returned
    ``dressed_magnetization_per_field`` is its coefficient.  All other fields
    are their finite ``h->0`` limits at fixed string and rapidity.
    """

    s = np.asarray(string, dtype=float)
    theta = np.asarray(rapidity, dtype=float)
    s, theta = np.broadcast_arrays(s, theta)
    if np.any(s < 1.0) or np.any(s != np.floor(s)):
        raise ValueError("string indices must be positive integers")
    n = s + 1.0
    a = 4.0 * theta**2 + s**2
    a2 = 4.0 * theta**2 + (s + 2.0) ** 2
    filling = 1.0 / n**2
    rho_total = 4.0 * n**2 / (np.pi * a * a2)
    velocity = 4.0 * theta * (a + a2) / (a * a2)
    return {
        "filling": filling,
        "holes": 1.0 - filling,
        "rho_total": rho_total,
        "velocity": velocity,
        "dressed_magnetization_per_field": n**2 / 3.0,
    }


def giant_bare_scattering_first_field_correction(
    xi: float | np.ndarray,
    zeta: float | np.ndarray,
    rapidity_difference: float | np.ndarray,
) -> np.ndarray:
    r"""Coefficient of the first field correction to giant scattering.

    The exact discrete XXX sum has string step two.  Euler--Maclaurin at its
    shifted endpoints gives ``T_h=T0+h*T1+O(h^2)``, with

    ``T1=-2/pi*(a/(a^2+4u^2)+b/(b^2+4u^2))``,
    ``a=abs(xi-zeta)``, ``b=xi+zeta``.

    The published leading giant-string calculation discards precisely this
    term.  Dressing ``T1`` and matching it to fixed strings are required for
    the physical constant ``D1``.
    """

    xi = np.asarray(xi, dtype=float)
    zeta = np.asarray(zeta, dtype=float)
    u = np.asarray(rapidity_difference, dtype=float)
    lower = np.abs(xi - zeta)
    upper = xi + zeta
    return -2.0 / np.pi * (
        lower / (lower**2 + 4.0 * u**2)
        + upper / (upper**2 + 4.0 * u**2)
    )


def giant_bare_scattering_fourier_kernel(
    xi: float | np.ndarray,
    zeta: float | np.ndarray,
    scaled_wave_number: float | np.ndarray,
) -> np.ndarray:
    r"""Fourier transform in scaled rapidity of the leading bare kernel.

    With ``a=abs(k)/2`` and the convention

    ``T_hat(k)=integral du exp(i*k*u) T(u)``, one has

    ``T0_hat=(exp(-a*abs(xi-zeta))-exp(-a*(xi+zeta)))/a``.

    The value at ``a=0`` is its continuous limit ``2*min(xi,zeta)``.
    Thus ``T0_hat`` is twice the Dirichlet Green function of
    ``-d_xi^2+a^2`` on the positive half-line.
    """

    x = np.asarray(xi, dtype=float)
    y = np.asarray(zeta, dtype=float)
    a = 0.5 * np.abs(np.asarray(scaled_wave_number, dtype=float))
    x, y, a = np.broadcast_arrays(x, y, a)
    result = np.empty_like(x)
    zero = a < 1.0e-10
    result[zero] = 2.0 * np.minimum(x[zero], y[zero])
    az = a[~zero]
    result[~zero] = (
        np.exp(-az * np.abs(x[~zero] - y[~zero]))
        - np.exp(-az * (x[~zero] + y[~zero]))
    ) / az
    return result


def giant_bare_scattering_first_field_fourier_kernel(
    xi: float | np.ndarray,
    zeta: float | np.ndarray,
    scaled_wave_number: float | np.ndarray,
) -> np.ndarray:
    r"""Fourier transform of the first bare giant-kernel correction."""

    x = np.asarray(xi, dtype=float)
    y = np.asarray(zeta, dtype=float)
    a = 0.5 * np.abs(np.asarray(scaled_wave_number, dtype=float))
    return -(
        np.exp(-a * np.abs(x - y)) + np.exp(-a * (x + y))
    )


def giant_dressed_scattering_fourier_kernel(
    xi: float | np.ndarray,
    zeta: float | np.ndarray,
    scaled_wave_number: float | np.ndarray,
) -> np.ndarray:
    r"""Exact leading giant-string dressed kernel in rapidity Fourier space.

    The XXX dressing sign in the symmetric positive-kernel convention is

    ``X0=T0-T0*N0*X0``, ``N0(xi)=csch(xi)^2``.

    Since ``T0`` is twice a free half-line Green function, this is equivalent
    to

    ``[-d_xi^2+a^2+2*csch(xi)^2] X0(xi,zeta)=2 delta(xi-zeta)``,

    where ``a=abs(k)/2``.  The Pöschl--Teller operator is elementary.  The
    formula below uses its solution regular as ``xi^2`` at the origin and its
    decaying Jost solution at infinity.  Continuous limits are used at the
    removable singularities ``a=0`` and ``a=1``.
    """

    x = np.asarray(xi, dtype=float)
    y = np.asarray(zeta, dtype=float)
    a = 0.5 * np.abs(np.asarray(scaled_wave_number, dtype=float))
    x, y, a = np.broadcast_arrays(x, y, a)
    if np.any(x <= 0.0) or np.any(y <= 0.0):
        raise ValueError("xi and zeta must be positive")
    lo = np.minimum(x, y)
    hi = np.maximum(x, y)
    coth_lo = 1.0 / np.tanh(lo)
    coth_hi = 1.0 / np.tanh(hi)
    right = (a + coth_hi) * np.exp(-a * hi)

    result = np.empty_like(lo)
    near_zero = a < 1.0e-7
    near_one = np.abs(a - 1.0) < 1.0e-6
    regular = ~(near_zero | near_one)

    ar = a[regular]
    lr = lo[regular]
    cr = coth_lo[regular]
    left = (cr - ar) * np.exp(ar * lr) - (ar + cr) * np.exp(-ar * lr)
    result[regular] = left * right[regular] / (ar * (1.0 - ar**2))

    # a -> 0: left/[a*(1-a^2)] -> 2*(xi*coth(xi)-1).
    lz = lo[near_zero]
    result[near_zero] = (
        2.0 * (lz * coth_lo[near_zero] - 1.0) * coth_hi[near_zero]
    )

    # a -> 1: apply l'Hopital to left/(1-a^2).
    l1 = lo[near_one]
    c1 = coth_lo[near_one]
    left_derivative = (
        (-1.0 + l1 * (c1 - 1.0)) * np.exp(l1)
        + (-1.0 + l1 * (1.0 + c1)) * np.exp(-l1)
    )
    result[near_one] = (
        -0.5
        * left_derivative
        * (1.0 + coth_hi[near_one])
        * np.exp(-hi[near_one])
    )
    return result


def giant_dressed_scattering_common_shift_derivative_fourier_kernel(
    xi: float | np.ndarray,
    zeta: float | np.ndarray,
    scaled_wave_number: float | np.ndarray,
) -> np.ndarray:
    r"""Directional derivative of the leading giant dressed kernel.

    The exact discrete string coordinate is ``x=h*(s+1)``, rather than
    ``xi=h*s``.  At fixed natural coordinates the symmetric local dressing
    recurrence has no odd power of ``h`` and therefore

    ``h*Tdr_h(x,y;h*K)=X0(x,y;K)+O(h**2)``.

    Expressing the same result at fixed old coordinates ``xi=h*s`` gives

    ``X_old=X0(xi,zeta)+h*(d_xi+d_zeta)X0+O(h**2)``.

    This routine evaluates that common-shift derivative analytically.  It is
    well defined on the diagonal because both Green-function arguments are
    shifted together, so their ordering never changes.
    """

    x = np.asarray(xi, dtype=float)
    y = np.asarray(zeta, dtype=float)
    a = 0.5 * np.abs(np.asarray(scaled_wave_number, dtype=float))
    x, y, a = np.broadcast_arrays(x, y, a)
    if np.any(x <= 0.0) or np.any(y <= 0.0):
        raise ValueError("xi and zeta must be positive")
    lo = np.minimum(x, y)
    hi = np.maximum(x, y)
    coth_lo = 1.0 / np.tanh(lo)
    coth_hi = 1.0 / np.tanh(hi)
    csch2_lo = 1.0 / np.sinh(lo) ** 2
    csch2_hi = 1.0 / np.sinh(hi) ** 2

    result = np.empty_like(lo)
    near_zero = a < 1.0e-7
    near_one = np.abs(a - 1.0) < 1.0e-6
    regular = ~(near_zero | near_one)

    ar = a[regular]
    lr = lo[regular]
    hr = hi[regular]
    clr = coth_lo[regular]
    chr_ = coth_hi[regular]
    slr = csch2_lo[regular]
    shr = csch2_hi[regular]
    exp_plus = np.exp(ar * lr)
    exp_minus = np.exp(-ar * lr)
    left = (clr - ar) * exp_plus - (ar + clr) * exp_minus
    dleft = (
        (-slr + ar * (clr - ar)) * exp_plus
        + (slr + ar * (ar + clr)) * exp_minus
    )
    right = (ar + chr_) * np.exp(-ar * hr)
    dright = (-shr - ar * (ar + chr_)) * np.exp(-ar * hr)
    result[regular] = (
        dleft * right + left * dright
    ) / (ar * (1.0 - ar**2))

    lz = lo[near_zero]
    clz = coth_lo[near_zero]
    chz = coth_hi[near_zero]
    slz = csch2_lo[near_zero]
    shz = csch2_hi[near_zero]
    result[near_zero] = 2.0 * (
        (clz - lz * slz) * chz
        - (lz * clz - 1.0) * shz
    )

    l1 = lo[near_one]
    h1 = hi[near_one]
    c1 = coth_lo[near_one]
    ch1 = coth_hi[near_one]
    s1 = csch2_lo[near_one]
    sh1 = csch2_hi[near_one]
    first_factor = -1.0 + l1 * (c1 - 1.0)
    second_factor = -1.0 + l1 * (1.0 + c1)
    left_derivative = (
        first_factor * np.exp(l1) + second_factor * np.exp(-l1)
    )
    dleft_derivative = (
        (c1 - 1.0 - l1 * s1 + first_factor) * np.exp(l1)
        + (1.0 + c1 - l1 * s1 - second_factor) * np.exp(-l1)
    )
    right_one = (1.0 + ch1) * np.exp(-h1)
    dright_one = (-sh1 - 1.0 - ch1) * np.exp(-h1)
    result[near_one] = -0.5 * (
        dleft_derivative * right_one + left_derivative * dright_one
    )
    return result


def giant_dressed_scattering_first_field_fourier_quadrature(
    xi: float,
    zeta: float,
    scaled_wave_number: float,
    *,
    xi_cutoff: float = 14.0,
    order: int = 240,
) -> float:
    r"""Return the old-coordinate outer ``O(h)`` dressed-kernel coefficient.

    This compatibility wrapper used to solve a Nyström equation obtained by
    expanding ``xi=h*s`` term by term.  That expansion misses the discrete
    string shift and its half-line boundary contribution.  The exact local
    recurrence instead shows that the natural coordinate is ``h*(s+1)`` and
    has no physical ``O(h)`` bulk correction.  Consequently the coefficient
    at fixed ``xi=h*s`` is exactly ``(d_xi+d_zeta)X0``.  ``xi_cutoff`` and
    ``order`` are retained only for API compatibility and input validation.
    """

    x = float(xi)
    y = float(zeta)
    k = float(scaled_wave_number)
    cutoff = float(xi_cutoff)
    n_order = int(order)
    if x <= 0.0 or y <= 0.0:
        raise ValueError("xi and zeta must be positive")
    if cutoff <= max(x, y) or n_order < 24:
        raise ValueError("xi_cutoff must exceed xi,zeta and order must be >=24")

    return float(
        giant_dressed_scattering_common_shift_derivative_fourier_kernel(
            x, y, k
        )
    )


def giant_dressed_scattering_real_kernel(
    xi: float,
    zeta: float,
    scaled_rapidity_difference: float,
    *,
    wave_number_cutoff: float = 48.0,
    wave_number_order: int = 320,
) -> float:
    r"""Inverse Fourier transform of the leading dressed giant kernel.

    The kernel is even in wave number, hence
    ``X0(u)=pi^-1 integral_0^K cos(k*u) X0_hat(k) dk``.  This routine is
    intended for pointwise convergence audits away from the coincident
    logarithmic singularity.  Bulk four-dimensional integration should use a
    shared FFT grid rather than repeatedly calling this scalar quadrature.
    """

    cutoff = float(wave_number_cutoff)
    order = int(wave_number_order)
    if cutoff <= 0.0 or order < 32:
        raise ValueError("wave-number cutoff/order is too small")
    nodes, weights = np.polynomial.legendre.leggauss(order)
    wave_numbers = 0.5 * cutoff * (nodes + 1.0)
    wave_weights = 0.5 * cutoff * weights
    transformed = giant_dressed_scattering_fourier_kernel(
        float(xi), float(zeta), wave_numbers
    )
    return float(
        np.dot(
            wave_weights,
            np.cos(wave_numbers * float(scaled_rapidity_difference))
            * transformed,
        )
        / np.pi
    )


def giant_dressed_scattering_first_field_real_kernel(
    xi: float,
    zeta: float,
    scaled_rapidity_difference: float,
    *,
    wave_number_cutoff: float = 48.0,
    wave_number_order: int = 160,
    xi_cutoff: float = 14.0,
    xi_order: int = 240,
) -> float:
    r"""Inverse Fourier transform of the outer first dressed kernel.

    This composes the independently controlled one-dimensional ``xi``
    Nyström solve with an even Fourier quadrature.  As for the leading helper,
    it is a pointwise certificate routine; production outer integration
    should reuse all wave-number solves on a common FFT grid.
    """

    cutoff = float(wave_number_cutoff)
    order = int(wave_number_order)
    if cutoff <= 0.0 or order < 24:
        raise ValueError("wave-number cutoff/order is too small")
    nodes, weights = np.polynomial.legendre.leggauss(order)
    wave_numbers = 0.5 * cutoff * (nodes + 1.0)
    wave_weights = 0.5 * cutoff * weights
    transformed = np.asarray(
        [
            giant_dressed_scattering_first_field_fourier_quadrature(
                float(xi),
                float(zeta),
                float(wave_number),
                xi_cutoff=xi_cutoff,
                order=xi_order,
            )
            for wave_number in wave_numbers
        ]
    )
    return float(
        np.dot(
            wave_weights,
            np.cos(wave_numbers * float(scaled_rapidity_difference))
            * transformed,
        )
        / np.pi
    )


def giant_infinite_temperature_first_field_data(
    xi: float | np.ndarray,
) -> dict[str, np.ndarray]:
    r"""Leading and first field coefficients of two giant-string TBA data.

    At infinite temperature and ``s=xi/h`` the exact filling and dressed
    magnetization obey

    ``n_s/h^2 = csch(xi)^2 - 2h*coth(xi)csch(xi)^2 + O(h^2)``,
    ``h*m_s^dr = xi*coth(xi)-1``
    ``             +h*(coth(xi)-xi*csch(xi)^2)+O(h^2)``.

    These coefficients, together with the first bare-kernel correction, are
    inputs to the linearized giant-string dressing equation for ``D1``.
    """

    xi = np.asarray(xi, dtype=float)
    if np.any(xi <= 0.0):
        raise ValueError("xi must be positive")
    sinh = np.sinh(xi)
    coth = 1.0 / np.tanh(xi)
    csch_squared = 1.0 / sinh**2
    return {
        "scaled_filling_leading": csch_squared,
        "scaled_filling_first": -2.0 * coth * csch_squared,
        "scaled_dressed_magnetization_leading": xi * coth - 1.0,
        "scaled_dressed_magnetization_first": coth - xi * csch_squared,
    }


def giant_density_velocity_first_field_data(
    xi: float | np.ndarray,
    scaled_rapidity: float | np.ndarray,
) -> dict[str, np.ndarray]:
    r"""First two giant-string coefficients of ``rho_tot`` and ``v_eff``.

    For ``s=xi/h`` and ``theta=u/h`` write

    ``rho_tot=h^2*(rho0+h*rho1+O(h^2))`` and
    ``v_eff=h*(v0+h*v1+O(h^2))``.

    The result follows by Taylor expanding the exact infinite-temperature TBA
    differences between strings ``s`` and ``s+2``.  It supplies the remaining
    explicit thermodynamic source terms in the outer linearized dressing
    problem for the physical ``D1``.
    """

    x = np.asarray(xi, dtype=float)
    u = np.asarray(scaled_rapidity, dtype=float)
    if np.any(x <= 0.0):
        raise ValueError("xi must be positive")
    a = 4.0 * u**2 + x**2
    sinh = np.sinh(x)
    cosh = np.cosh(x)
    coth = cosh / sinh
    csch_squared = 1.0 / sinh**2

    f = x / (a * sinh)
    log_f_prime = 1.0 / x - 2.0 * x / a - coth
    log_f_second = (
        -1.0 / x**2 - 2.0 / a + 4.0 * x**2 / a**2 + csch_squared
    )
    f_prime = f * log_f_prime
    f_second = f * (log_f_prime**2 + log_f_second)
    rho0 = -2.0 * sinh * f_prime / np.pi
    rho1 = -2.0 * (cosh * f_prime + sinh * f_second) / np.pi

    g = x / (a**2 * sinh)
    log_g_prime = 1.0 / x - 4.0 * x / a - coth
    log_g_second = (
        -1.0 / x**2 - 4.0 / a + 8.0 * x**2 / a**2 + csch_squared
    )
    g_prime = g * log_g_prime
    g_second = g * (log_g_prime**2 + log_g_second)
    energy0 = -16.0 * u * sinh * g_prime
    energy1 = -16.0 * u * (cosh * g_prime + sinh * g_second)
    velocity0 = energy0 / (2.0 * np.pi * rho0)
    velocity1 = (
        energy1 * rho0 - energy0 * rho1
    ) / (2.0 * np.pi * rho0**2)
    return {
        "scaled_total_density_leading": rho0,
        "scaled_total_density_first": rho1,
        "scaled_effective_velocity_leading": velocity0,
        "scaled_effective_velocity_first": velocity1,
    }


def giant_diagonal_diffusion_outer_factors(
    xi: float | np.ndarray,
    scaled_rapidity: float | np.ndarray,
) -> dict[str, np.ndarray]:
    r"""Leading/first factors of the diagonal diffusion integrand.

    Equation (16) of the supplement contains, for a left quasiparticle,

    ``A=n*(1-n)*m_dr^2/rho_tot``

    and, for the collision partner, ``B=n*(1-n)*rho_tot``.  In giant
    variables

    ``A=h^-2*(A0+h*A1+...)`` and ``B=h^4*(B0+h*B1+...)``.

    Since ``n=O(h^2)``, the hole factor has no relative ``O(h)`` term.  This
    routine combines all already-known thermodynamic first coefficients and
    makes the remaining dressed-kernel/absolute-velocity contractions
    explicit.
    """

    thermo = giant_infinite_temperature_first_field_data(xi)
    kinetic = giant_density_velocity_first_field_data(xi, scaled_rapidity)
    n0 = thermo["scaled_filling_leading"]
    n1 = thermo["scaled_filling_first"]
    m0 = thermo["scaled_dressed_magnetization_leading"]
    m1 = thermo["scaled_dressed_magnetization_first"]
    rho0 = kinetic["scaled_total_density_leading"]
    rho1 = kinetic["scaled_total_density_first"]
    a0 = n0 * m0**2 / rho0
    a1 = (
        n1 * m0**2 / rho0
        + 2.0 * n0 * m0 * m1 / rho0
        - n0 * m0**2 * rho1 / rho0**2
    )
    b0 = n0 * rho0
    b1 = n1 * rho0 + n0 * rho1
    cross0 = n0 * m0
    cross1 = n1 * m0 + n0 * m1
    return {
        "left_weight_leading": a0,
        "left_weight_first": a1,
        "partner_weight_leading": b0,
        "partner_weight_first": b1,
        "cross_weight_leading": cross0,
        "cross_weight_first": cross1,
        "velocity_leading": kinetic["scaled_effective_velocity_leading"],
        "velocity_first": kinetic["scaled_effective_velocity_first"],
    }


def giant_diagonal_diffusion_outer_integrand_coefficients(
    left_xi: float | np.ndarray,
    left_scaled_rapidity: float | np.ndarray,
    right_xi: float | np.ndarray,
    right_scaled_rapidity: float | np.ndarray,
    dressed_kernel_leading: float | np.ndarray,
    dressed_kernel_first: float | np.ndarray,
    *,
    susceptibility: float = 0.25,
) -> dict[str, np.ndarray]:
    r"""Return the complete pointwise outer coefficients ``I0`` and ``I1``.

    After the two string sums and two rapidity measures are rescaled, the
    diagonal diffusion is ``D=h^-1*integral(I0)+integral(I1)+...`` before the
    Euler--Maclaurin and fixed-string matching terms.  The first coefficient
    includes the left weight, partner weight, velocity cusp and both dressed
    kernels.  At a zero leading relative velocity, the directional first
    coefficient is ``abs(dv1)``; this set has zero measure in the final
    integral but makes the pointwise expansion continuous as a directional
    statement.
    """

    if susceptibility <= 0.0:
        raise ValueError("susceptibility must be positive")
    left = giant_diagonal_diffusion_outer_factors(
        left_xi, left_scaled_rapidity
    )
    right = giant_diagonal_diffusion_outer_factors(
        right_xi, right_scaled_rapidity
    )
    x0 = np.asarray(dressed_kernel_leading, dtype=float)
    x1 = np.asarray(dressed_kernel_first, dtype=float)
    dv0 = left["velocity_leading"] - right["velocity_leading"]
    dv1 = left["velocity_first"] - right["velocity_first"]
    abs_dv0 = np.abs(dv0)
    abs_dv1 = np.where(abs_dv0 > 1.0e-14, np.sign(dv0) * dv1, np.abs(dv1))
    a0 = left["left_weight_leading"]
    a1 = left["left_weight_first"]
    b0 = right["partner_weight_leading"]
    b1 = right["partner_weight_first"]
    inverse_chi = 1.0 / float(susceptibility)
    leading = inverse_chi * a0 * b0 * abs_dv0 * x0**2
    first = inverse_chi * (
        (a1 * b0 + a0 * b1) * abs_dv0 * x0**2
        + a0 * b0 * abs_dv1 * x0**2
        + 2.0 * a0 * b0 * abs_dv0 * x0 * x1
    )
    return {
        "integrand_leading": leading,
        "integrand_first": first,
        "absolute_velocity_leading": abs_dv0,
        "absolute_velocity_first": abs_dv1,
    }


def finite_rescaled_bare_scattering_kernel(
    field: float,
    left_string: int,
    right_string: int,
    rapidity_difference: float,
) -> float:
    r"""Exact rescaled finite-field sum used to certify the expansion.

    Here ``xi=h*s``, ``zeta=h*s'`` and the physical rapidity difference is
    ``u/h``.  The returned quantity is the finite sum whose limit is
    :func:`giant_bare_scattering_kernel`.
    """

    h = float(field)
    s = int(left_string)
    sp = int(right_string)
    u = float(rapidity_difference)
    if h <= 0.0 or s < 1 or sp < 1:
        raise ValueError("field and string indices must be positive")
    indices = np.arange(abs(s - sp) + 2, s + sp - 1, 2, dtype=float)
    return float(
        np.sum(
            4.0
            * indices
            * h**2
            / (np.pi * ((indices * h) ** 2 + 4.0 * u**2))
        )
    )
