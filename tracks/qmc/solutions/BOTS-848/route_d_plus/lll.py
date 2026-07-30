"""One-particle lowest-Landau-level primitives on the Haldane sphere."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.special import roots_legendre


@dataclass(frozen=True)
class SphereQuadrature:
    """Flattened Gauss-Legendre × uniform-Fourier sphere quadrature."""

    x: np.ndarray
    theta: np.ndarray
    phi: np.ndarray
    u: np.ndarray
    v: np.ndarray
    weights: np.ndarray
    n_theta: int
    n_phi: int

    @property
    def size(self) -> int:
        return int(self.weights.size)


def _validate_two_q(two_q: int) -> int:
    if isinstance(two_q, bool) or not isinstance(two_q, (int, np.integer)):
        raise TypeError("two_q must be an integer")
    value = int(two_q)
    if value < 0:
        raise ValueError("two_q must be non-negative")
    return value


def _validate_two_m(two_q: int, two_m: int) -> int:
    if isinstance(two_m, bool) or not isinstance(two_m, (int, np.integer)):
        raise TypeError("two_m must be an integer")
    value = int(two_m)
    if abs(value) > two_q or (two_q - value) % 2:
        raise ValueError(
            "two_m must have the parity of two_q and satisfy |m| <= Q"
        )
    return value


def spinor(
    theta: np.ndarray | float,
    phi: np.ndarray | float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the fixed-gauge Haldane-sphere spinor ``(u, v)``.

    The convention is
    ``u = cos(theta/2) exp(+i phi/2)`` and
    ``v = sin(theta/2) exp(-i phi/2)``.
    """

    theta_array, phi_array = np.broadcast_arrays(
        np.asarray(theta, dtype=np.float64),
        np.asarray(phi, dtype=np.float64),
    )
    if not np.all(np.isfinite(theta_array)) or not np.all(
        np.isfinite(phi_array)
    ):
        raise ValueError("theta and phi must be finite")
    if np.any(theta_array < 0.0) or np.any(theta_array > math.pi):
        raise ValueError("theta must lie in [0, pi]")

    half_phi_phase = np.exp(0.5j * phi_array)
    u = np.asarray(
        np.cos(0.5 * theta_array) * half_phi_phase,
        dtype=np.complex128,
    )
    v = np.asarray(
        np.sin(0.5 * theta_array) / half_phi_phase,
        dtype=np.complex128,
    )
    return u, v


def monopole_orbital(
    two_q: int,
    two_m: int,
    u: np.ndarray | complex,
    v: np.ndarray | complex,
) -> np.ndarray:
    """Evaluate the normalized LLL monopole orbital ``phi_m(u, v)``."""

    two_q = _validate_two_q(two_q)
    two_m = _validate_two_m(two_q, two_m)
    u_array, v_array = np.broadcast_arrays(
        np.asarray(u, dtype=np.complex128),
        np.asarray(v, dtype=np.complex128),
    )
    u_power = (two_q + two_m) // 2
    v_power = (two_q - two_m) // 2
    log_normalization = 0.5 * (
        math.lgamma(two_q + 2)
        - math.log(4.0 * math.pi)
        - math.lgamma(u_power + 1)
        - math.lgamma(v_power + 1)
    )
    return np.asarray(
        math.exp(log_normalization)
        * np.power(u_array, u_power)
        * np.power(v_array, v_power),
        dtype=np.complex128,
    )


def monopole_orbitals(
    two_q: int,
    u: np.ndarray | complex,
    v: np.ndarray | complex,
) -> np.ndarray:
    """Evaluate all ``2Q+1`` LLL orbitals ordered from ``m=-Q`` to ``m=Q``."""

    two_q = _validate_two_q(two_q)
    return np.stack(
        [
            monopole_orbital(two_q, -two_q + 2 * index, u, v)
            for index in range(two_q + 1)
        ],
        axis=-1,
    )


def reproducing_kernel(
    two_q: int,
    u: np.ndarray | complex,
    v: np.ndarray | complex,
    u_prime: np.ndarray | complex,
    v_prime: np.ndarray | complex,
) -> np.ndarray:
    """Evaluate ``K_Q(x, x')`` in its closed spinor-overlap form."""

    two_q = _validate_two_q(two_q)
    overlap = np.asarray(u, dtype=np.complex128) * np.conjugate(
        np.asarray(u_prime, dtype=np.complex128)
    ) + np.asarray(v, dtype=np.complex128) * np.conjugate(
        np.asarray(v_prime, dtype=np.complex128)
    )
    return np.asarray(
        ((two_q + 1) / (4.0 * math.pi)) * np.power(overlap, two_q),
        dtype=np.complex128,
    )


def sphere_quadrature(
    two_q: int,
    *,
    n_theta: int | None = None,
    n_phi: int | None = None,
) -> SphereQuadrature:
    """Construct the Phase 2 product quadrature for monopole charge ``Q``."""

    two_q = _validate_two_q(two_q)
    minimum_theta = 2 * two_q + 4
    minimum_phi = 4 * two_q + 4
    n_theta = minimum_theta if n_theta is None else int(n_theta)
    n_phi = minimum_phi if n_phi is None else int(n_phi)
    if n_theta < minimum_theta:
        raise ValueError(f"n_theta must be at least {minimum_theta}")
    if n_phi < minimum_phi:
        raise ValueError(f"n_phi must be at least {minimum_phi}")

    x_nodes, x_weights = roots_legendre(n_theta)
    phi_nodes = 2.0 * math.pi * np.arange(n_phi, dtype=np.float64) / n_phi
    x = np.repeat(np.asarray(x_nodes, dtype=np.float64), n_phi)
    phi = np.tile(phi_nodes, n_theta)
    theta = np.arccos(x)
    weights = np.repeat(np.asarray(x_weights, dtype=np.float64), n_phi)
    weights *= 2.0 * math.pi / n_phi
    u, v = spinor(theta, phi)
    return SphereQuadrature(
        x=x,
        theta=theta,
        phi=phi,
        u=u,
        v=v,
        weights=weights,
        n_theta=n_theta,
        n_phi=n_phi,
    )


def orbital_overlap_matrix(two_q: int, grid: SphereQuadrature) -> np.ndarray:
    """Integrate the one-particle orbital overlap matrix on ``grid``."""

    orbitals = monopole_orbitals(two_q, grid.u, grid.v)
    return np.einsum(
        "pa,p,pb->ab",
        orbitals.conj(),
        grid.weights,
        orbitals,
        optimize=True,
    )


def reconstruct_lll(
    two_q: int,
    grid: SphereQuadrature,
    values: np.ndarray,
    target_u: np.ndarray | complex,
    target_v: np.ndarray | complex,
) -> np.ndarray:
    """Reconstruct sampled LLL values at target spinors with ``K_Q``."""

    values_array = np.asarray(values, dtype=np.complex128)
    if values_array.ndim == 0 or values_array.shape[0] != grid.size:
        raise ValueError("values must have the quadrature-point axis first")
    target_u_array, target_v_array = np.broadcast_arrays(
        np.asarray(target_u, dtype=np.complex128),
        np.asarray(target_v, dtype=np.complex128),
    )
    kernel = reproducing_kernel(
        two_q,
        target_u_array[..., None],
        target_v_array[..., None],
        grid.u,
        grid.v,
    )
    weight_shape = (grid.size,) + (1,) * (values_array.ndim - 1)
    weighted_values = values_array * grid.weights.reshape(weight_shape)
    return np.tensordot(kernel, weighted_values, axes=([-1], [0]))


__all__ = [
    "SphereQuadrature",
    "monopole_orbital",
    "monopole_orbitals",
    "orbital_overlap_matrix",
    "reconstruct_lll",
    "reproducing_kernel",
    "sphere_quadrature",
    "spinor",
]
