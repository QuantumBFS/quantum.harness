from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.special import sph_harm_y


@dataclass(frozen=True)
class SphereGrid:
    """Product quadrature and normalized LLL monopole orbitals."""

    theta: np.ndarray
    phi: np.ndarray
    weights: np.ndarray
    orbitals: np.ndarray


def monopole_orbital_grid(
    two_q: int,
    *,
    n_theta: int | None = None,
    n_phi: int | None = None,
) -> SphereGrid:
    """Evaluate the ``2Q+1`` LLL orbitals on a sphere quadrature grid."""

    if two_q <= 0:
        raise ValueError("two_q must be positive")
    n_theta = n_theta or max(48, 4 * two_q + 4)
    n_phi = n_phi or max(64, 4 * two_q + 4)

    x_nodes, x_weights = leggauss(n_theta)
    phi_nodes = 2.0 * math.pi * np.arange(n_phi) / n_phi
    x = np.repeat(x_nodes, n_phi)
    phi = np.tile(phi_nodes, n_theta)
    theta = np.arccos(x)
    weights = np.repeat(x_weights, n_phi) * (2.0 * math.pi / n_phi)

    u = np.sqrt((1.0 + x) / 2.0) * np.exp(0.5j * phi)
    v = np.sqrt((1.0 - x) / 2.0) * np.exp(-0.5j * phi)
    orbitals = np.empty((x.size, two_q + 1), dtype=np.complex128)
    for orbital in range(two_q + 1):
        u_power = orbital
        v_power = two_q - orbital
        normalization = math.sqrt(
            (two_q + 1) * math.comb(two_q, orbital) / (4.0 * math.pi)
        )
        gauge_sign = -1.0 if v_power % 2 else 1.0
        orbitals[:, orbital] = (
            gauge_sign * normalization * u**u_power * v**v_power
        )

    return SphereGrid(theta=theta, phi=phi, weights=weights, orbitals=orbitals)


def coulomb_integrals(
    two_q: int,
    *,
    n_theta: int | None = None,
    n_phi: int | None = None,
) -> np.ndarray:
    """Return ``<ab|1/(sqrt(Q)|Omega-Omega'|)|cd>`` in LLL units."""

    grid = monopole_orbital_grid(
        two_q,
        n_theta=n_theta,
        n_phi=n_phi,
    )
    harmonic_labels = [
        (degree, order)
        for degree in range(two_q + 1)
        for order in range(-degree, degree + 1)
    ]
    harmonics = np.column_stack(
        [
            sph_harm_y(degree, order, grid.theta, grid.phi)
            for degree, order in harmonic_labels
        ]
    )

    n_orbitals = two_q + 1
    transition_density = (
        grid.orbitals.conj()[:, :, None] * grid.orbitals[:, None, :]
    ).reshape(grid.weights.size, n_orbitals * n_orbitals)
    transitions = (
        harmonics.T @ (grid.weights[:, None] * transition_density)
    ).reshape(len(harmonic_labels), n_orbitals, n_orbitals)

    orbital_indices = np.arange(n_orbitals)
    delta_m = orbital_indices[:, None] - orbital_indices[None, :]
    for harmonic, (_, order) in enumerate(harmonic_labels):
        transitions[harmonic, delta_m != order] = 0.0

    q = two_q / 2.0
    kernel_coefficients = np.array(
        [
            4.0 * math.pi / ((2 * degree + 1) * math.sqrt(q))
            for degree, _ in harmonic_labels
        ]
    )
    integrals = np.einsum(
        "hac,hdb,h->abcd",
        transitions,
        transitions.conj(),
        kernel_coefficients,
        optimize=True,
    )
    return integrals


def antisymmetrized_pair_matrix(
    integrals: np.ndarray,
) -> tuple[tuple[tuple[int, int], ...], np.ndarray]:
    """Convert unsymmetrized integrals to the ordered fermion-pair basis."""

    n_orbitals = integrals.shape[0]
    pairs = tuple(
        (a, b) for a in range(n_orbitals) for b in range(a + 1, n_orbitals)
    )
    matrix = np.empty((len(pairs), len(pairs)), dtype=np.complex128)
    for row, (a, b) in enumerate(pairs):
        for column, (c, d) in enumerate(pairs):
            matrix[row, column] = (
                integrals[a, b, c, d] - integrals[a, b, d, c]
            )
    return pairs, matrix
