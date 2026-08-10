"""Finite-Haldane-sphere Coulomb matrix elements.

Two independent constructions are kept here deliberately:

* ``_raw_density_coulomb_tensor`` uses the spherical-harmonic density
  expansion and Wigner 3-j symbols.
* ``pair_pseudopotentials`` integrates coupled pair wavefunctions directly by
  Gauss--Jacobi quadrature.

The public four-index tensors are the antisymmetric representative

    A[ab,cd] = (V[ab,cd] - V[ab,dc]) / 2.

With this convention the many-body operator is
``(1/2) sum_abcd A[ab,cd] c†_a c†_b c_d c_c``.  This is exactly equivalent to
using the raw distinguishable-particle integral ``V`` and is the unique part
that can be reconstructed from fermionic pair pseudopotentials.
"""

from __future__ import annotations

from functools import lru_cache
from math import comb, pi, sqrt

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy import sparse
from scipy.special import roots_jacobi
from sympy import Rational
from sympy.physics.wigner import clebsch_gordan, wigner_3j

from challenge15.fermions import DeterminantBasis
from challenge15.spec import SphereSpec
from challenge15.two_body import (
    _legal_transition_capacity,
    assemble_two_body,
)


def density_multipole_integrals(spec: SphereSpec) -> dict[tuple[int, int], np.ndarray]:
    """Return ``F[k,q][m,m'] = <m|Y_kq|m'>`` in the north-chart convention.

    The phase is ``(-1)**(Q-m)``, rather than the occasionally quoted
    ``(-1)**(Q+m)``.  The two differ for half-integral Q.  This choice follows
    directly from the polynomial orbitals used in :mod:`challenge15.monopole`
    and, in particular, makes ``F[0,0] = I/sqrt(4*pi)`` for both integer and
    half-integer Q.
    """

    orbital_count = spec.orbital_count
    result: dict[tuple[int, int], np.ndarray] = {}
    for rank in range(spec.two_q + 1):
        reduced = _three_j(spec.two_q, 2 * rank, spec.two_q, -spec.two_q, 0, spec.two_q)
        prefactor = sqrt(
            orbital_count * orbital_count * (2 * rank + 1) / (4.0 * pi)
        ) * reduced
        for q in range(-rank, rank + 1):
            matrix = np.zeros((orbital_count, orbital_count), dtype=np.float64)
            for row, two_m in enumerate(spec.two_m_values):
                two_mp = two_m - 2 * q
                if two_mp < -spec.two_q or two_mp > spec.two_q:
                    continue
                column = (two_mp + spec.two_q) // 2
                phase = _minus_one_pow((spec.two_q - two_m) // 2)
                matrix[row, column] = (
                    phase
                    * prefactor
                    * _three_j(
                        spec.two_q,
                        2 * rank,
                        spec.two_q,
                        -two_m,
                        2 * q,
                        two_mp,
                    )
                )
            result[(rank, q)] = matrix
    return result


@lru_cache(maxsize=None)
def _raw_density_coulomb_tensor(particles: int) -> np.ndarray:
    """Build unsymmetrized ``<ab|r12^-1|cd>`` density-route integrals."""

    spec = SphereSpec(particles)
    multipoles = density_multipole_integrals(spec)
    count = spec.orbital_count
    tensor = np.zeros((count, count, count, count), dtype=np.float64)
    inverse_radius = 1.0 / spec.radius_in_magnetic_lengths
    for rank in range(spec.two_q + 1):
        coefficient = inverse_radius * 4.0 * pi / (2 * rank + 1)
        for q in range(-rank, rank + 1):
            left = multipoles[(rank, -q)]
            right = multipoles[(rank, q)]
            tensor += coefficient * _minus_one_pow(q) * np.einsum(
                "ac,bd->abcd", left, right
            )

    # Selection-rule zeros should remain exact, not merely roundoff-small.
    two_m = spec.two_m_values
    for a, ma in enumerate(two_m):
        for b, mb in enumerate(two_m):
            for c, mc in enumerate(two_m):
                for d, md in enumerate(two_m):
                    if ma + mb != mc + md:
                        tensor[a, b, c, d] = 0.0
    return tensor


def orbital_coulomb_tensor(spec: SphereSpec) -> np.ndarray:
    """Return the density-route antisymmetric Coulomb tensor representative."""

    raw = _raw_density_coulomb_tensor(spec.particles)
    antisymmetric = 0.5 * (raw - raw.swapaxes(2, 3))
    # Antisymmetry in the bra follows analytically; averaging suppresses the
    # final independent Wigner-evaluation roundoff.
    antisymmetric = 0.5 * (antisymmetric - antisymmetric.swapaxes(0, 1))
    return np.asarray(antisymmetric, dtype=np.float64)


def pair_pseudopotentials(spec: SphereSpec) -> dict[int, float]:
    """Directly integrate all fermion-allowed pair-channel Coulomb energies."""

    values: dict[int, float] = {}
    for total_j in range(spec.two_q + 1):
        if (spec.two_q - total_j) % 2 != 1:
            continue
        north_pole_contributions = [
            _north_pole_channel_integral(spec, total_j, total_m)
            for total_m in range(0, total_j + 1)
        ]
        # It is the M-sum, not an individual |J,M| density, that is invariant
        # under simultaneous rotations.  Terms with M<0 vanish when particle
        # one is at the north pole; division by 2J+1 performs the rotational
        # average appearing in the defining integral.
        values[total_j] = float(sum(north_pole_contributions) / (2 * total_j + 1))
    return values


def _north_pole_channel_integral(
    spec: SphereSpec,
    total_j: int,
    total_m: int,
) -> float:
    """Return one 4π-weighted fixed-north-pole contribution.

    This is one term in the M-summed rotational average defining ``V_J``; it
    is not the energy of the individual ``(J,M)`` state.  Individual-state
    energies require the full two-coordinate integral.
    """

    two_m = 2 * total_m - spec.two_q
    if two_m not in spec.two_m_values:
        raise ValueError("M does not give a north-pole-admissible pair component")
    cg = _clebsch(
        spec.two_q,
        two_m,
        spec.two_q,
        spec.two_q,
        2 * total_j,
        2 * total_m,
    )
    power_u = (spec.two_q + two_m) // 2
    power_v = (spec.two_q - two_m) // 2

    def integrate(order: int) -> float:
        nodes, weights = roots_jacobi(order, -0.5, 0.0)
        polynomial = ((1.0 + nodes) / 2.0) ** power_u
        polynomial *= ((1.0 - nodes) / 2.0) ** power_v
        weighted_integral = float(weights @ polynomial)
        return (
            spec.orbital_count**2
            * cg**2
            * comb(spec.two_q, power_u)
            * weighted_integral
            / (2.0 * sqrt(2.0 * spec.q))
        )

    order = max(4, (spec.two_q + 2) // 2)
    previous = integrate(order)
    for _ in range(8):
        order += 4
        current = integrate(order)
        if abs(current - previous) <= 1e-13 * max(abs(current), 1.0):
            return current
        previous = current
    raise RuntimeError(
        f"Gauss-Jacobi quadrature did not converge for J={total_j}, M={total_m}"
    )


def _full_product_pair_integral(
    spec: SphereSpec,
    total_j: int,
    total_m: int,
    *,
    polar_order: int,
    azimuth_order: int,
) -> float:
    """Slow coordinate-space oracle for an individual coupled pair state.

    This uses neither Wigner density multipoles nor the north-pole reduction.
    A common azimuth is integrated analytically (factor ``2*pi``), while both
    polar cosines and the relative azimuth are product-quadrature variables.
    Midpoint azimuth nodes avoid sampling the integrable coincidence
    singularity.  The routine is intended only for low-Q convention checks.
    """

    if not -total_j <= total_m <= total_j:
        raise ValueError("total_m must satisfy |M| <= J")
    if polar_order < 2 or azimuth_order < 2:
        raise ValueError("quadrature orders must be at least two")

    nodes, weights = leggauss(polar_order)
    relative_phi = (
        np.arange(azimuth_order, dtype=np.float64) + 0.5
    ) * (2.0 * pi / azimuth_order)
    phi_weight = 2.0 * pi / azimuth_order
    powers_u = np.arange(spec.orbital_count)
    powers_v = spec.two_q - powers_u
    normalizations = np.array(
        [
            sqrt(
                spec.orbital_count
                * comb(spec.two_q, power_u)
                / (4.0 * pi)
            )
            for power_u in powers_u
        ],
        dtype=np.float64,
    )
    coefficients = np.zeros((spec.orbital_count, spec.orbital_count))
    for a, two_ma in enumerate(spec.two_m_values):
        two_mb = 2 * total_m - two_ma
        if -spec.two_q <= two_mb <= spec.two_q:
            b = (two_mb + spec.two_q) // 2
            coefficients[a, b] = _clebsch(
                spec.two_q,
                two_ma,
                spec.two_q,
                two_mb,
                2 * total_j,
                2 * total_m,
            )

    integral = 0.0
    for x1, weight1 in zip(nodes, weights, strict=True):
        orbitals1 = normalizations
        orbitals1 = orbitals1 * ((1.0 + x1) / 2.0) ** (powers_u / 2.0)
        orbitals1 = orbitals1 * ((1.0 - x1) / 2.0) ** (powers_v / 2.0)
        transverse1 = sqrt(max(0.0, 1.0 - x1 * x1))
        for x2, weight2 in zip(nodes, weights, strict=True):
            radial2 = normalizations
            radial2 = radial2 * ((1.0 + x2) / 2.0) ** (powers_u / 2.0)
            radial2 = radial2 * ((1.0 - x2) / 2.0) ** (powers_v / 2.0)
            orbitals2 = radial2[None, :] * np.exp(
                -1j * relative_phi[:, None] * powers_v[None, :]
            )
            wavefunction = np.einsum(
                "a,ab,pb->p", orbitals1, coefficients, orbitals2
            )
            cosine_gamma = (
                x1 * x2
                + transverse1
                * sqrt(max(0.0, 1.0 - x2 * x2))
                * np.cos(relative_phi)
            )
            inverse_distance = 1.0 / (
                sqrt(2.0 * spec.q) * np.sqrt(1.0 - cosine_gamma)
            )
            integral += (
                weight1
                * weight2
                * phi_weight
                * float(np.sum(np.abs(wavefunction) ** 2 * inverse_distance))
            )
    return 2.0 * pi * integral


def pseudopotential_coulomb_tensor(
    spec: SphereSpec,
    pseudopotentials: dict[int, float],
) -> np.ndarray:
    """Reconstruct the antisymmetric tensor from independently supplied ``V_J``."""

    allowed = {
        total_j
        for total_j in range(spec.two_q + 1)
        if (spec.two_q - total_j) % 2 == 1
    }
    if set(pseudopotentials) != allowed:
        raise ValueError("pseudopotentials must contain exactly the fermion-allowed J channels")

    count = spec.orbital_count
    tensor = np.zeros((count, count, count, count), dtype=np.float64)
    for total_j in sorted(allowed):
        value = float(pseudopotentials[total_j])
        if not np.isfinite(value):
            raise ValueError("pseudopotentials must be finite")
        for total_m in range(-total_j, total_j + 1):
            coefficients = np.zeros((count, count), dtype=np.float64)
            for a, two_ma in enumerate(spec.two_m_values):
                two_mb = 2 * total_m - two_ma
                if two_mb < -spec.two_q or two_mb > spec.two_q:
                    continue
                b = (two_mb + spec.two_q) // 2
                coefficients[a, b] = _clebsch(
                    spec.two_q,
                    two_ma,
                    spec.two_q,
                    two_mb,
                    2 * total_j,
                    2 * total_m,
                )
            tensor += value * np.einsum("ab,cd->abcd", coefficients, coefficients)
    return tensor


def many_body_coulomb(
    basis: DeterminantBasis,
    tensor: np.ndarray,
) -> sparse.csr_matrix:
    """Assemble ``(1/2) A_abcd c†_a c†_b c_d c_c`` by legal substitutions."""

    return assemble_two_body(basis, basis, tensor)


@lru_cache(maxsize=None)
def _three_j(
    two_j1: int,
    two_j2: int,
    two_j3: int,
    two_m1: int,
    two_m2: int,
    two_m3: int,
) -> float:
    return float(
        wigner_3j(
            Rational(two_j1, 2),
            Rational(two_j2, 2),
            Rational(two_j3, 2),
            Rational(two_m1, 2),
            Rational(two_m2, 2),
            Rational(two_m3, 2),
        )
    )


@lru_cache(maxsize=None)
def _clebsch(
    two_j1: int,
    two_m1: int,
    two_j2: int,
    two_m2: int,
    two_j3: int,
    two_m3: int,
) -> float:
    return float(
        clebsch_gordan(
            Rational(two_j1, 2),
            Rational(two_j2, 2),
            Rational(two_j3, 2),
            Rational(two_m1, 2),
            Rational(two_m2, 2),
            Rational(two_m3, 2),
        )
    )


def _minus_one_pow(exponent: int) -> float:
    return -1.0 if exponent % 2 else 1.0
