"""Canonical one-particle irreducible tensors in the Haldane-sphere LLL."""

from __future__ import annotations

import math
from collections.abc import Callable
from functools import lru_cache

import numpy as np
from scipy.linalg import expm
from sympy import Rational
from sympy.physics.wigner import wigner_3j

from route_d_plus.lll import (
    SphereQuadrature,
    monopole_orbitals,
    reconstruct_lll,
)

STRICT_LLL_TOLERANCE = 1.0e-12


def _validate_two_j(two_j: int) -> int:
    if isinstance(two_j, bool) or not isinstance(two_j, (int, np.integer)):
        raise TypeError("two_j must be an integer")
    value = int(two_j)
    if value < 0:
        raise ValueError("two_j must be non-negative")
    return value


def _validate_rank_component(two_j: int, ell: int, m: int) -> tuple[int, int]:
    if isinstance(ell, bool) or not isinstance(ell, (int, np.integer)):
        raise TypeError("ell must be an integer")
    if isinstance(m, bool) or not isinstance(m, (int, np.integer)):
        raise TypeError("m must be an integer")
    ell_value = int(ell)
    m_value = int(m)
    if ell_value < 0 or ell_value > two_j:
        raise ValueError("ell must satisfy 0 <= ell <= two_j")
    if abs(m_value) > ell_value:
        raise ValueError("m must satisfy |m| <= ell")
    return ell_value, m_value


@lru_cache(maxsize=None)
def _canonical_tensor_cached(two_j: int, ell: int, m: int) -> np.ndarray:
    dimension = two_j + 1
    raw = np.zeros((dimension, dimension), dtype=np.complex128)
    j = Rational(two_j, 2)
    for column in range(dimension):
        two_m0 = -two_j + 2 * column
        two_m_prime = two_m0 + 2 * m
        if abs(two_m_prime) > two_j:
            continue
        row = (two_m_prime + two_j) // 2
        phase_exponent = (two_j - two_m_prime) // 2
        value = wigner_3j(
            j,
            ell,
            j,
            Rational(-two_m_prime, 2),
            m,
            Rational(two_m0, 2),
        )
        raw[row, column] = ((-1) ** phase_exponent) * float(value)

    norm = float(np.sqrt(np.vdot(raw, raw).real))
    if not math.isfinite(norm) or norm == 0.0:
        raise RuntimeError("canonical tensor has zero or non-finite norm")
    tensor = np.asarray(raw / norm, dtype=np.complex128)
    tensor.flags.writeable = False
    return tensor


def canonical_tensor(two_j: int, ell: int, m: int) -> np.ndarray:
    """Return Hilbert--Schmidt-normalized ``tau_(ell,m)``.

    The basis is ordered from ``m_j=-j`` to ``m_j=+j``. The reduced matrix
    element is determined numerically from the Hilbert--Schmidt norm rather
    than inserted as a closed-form convention.
    """

    two_j = _validate_two_j(two_j)
    ell, m = _validate_rank_component(two_j, ell, m)
    return _canonical_tensor_cached(two_j, ell, m)


def angular_momentum_matrices(
    two_j: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(Jx, Jy, Jz)`` in the same ascending-``m`` basis."""

    two_j = _validate_two_j(two_j)
    dimension = two_j + 1
    j = 0.5 * two_j
    m_values = np.arange(dimension, dtype=np.float64) - j
    raising = np.zeros((dimension, dimension), dtype=np.complex128)
    for column, m_value in enumerate(m_values[:-1]):
        raising[column + 1, column] = math.sqrt(
            (j - m_value) * (j + m_value + 1.0)
        )
    lowering = raising.conj().T
    jx = 0.5 * (raising + lowering)
    jy = (raising - lowering) / (2.0j)
    jz = np.diag(m_values).astype(np.complex128)
    return jx, jy, jz


def rotation_matrix(
    two_j: int,
    rotation_vector: np.ndarray,
) -> np.ndarray:
    """Return ``exp(-i rotation_vector dot J)`` for spin ``j=two_j/2``."""

    vector = np.asarray(rotation_vector, dtype=np.float64)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError("rotation_vector must be a finite length-three vector")
    jx, jy, jz = angular_momentum_matrices(two_j)
    generator = vector[0] * jx + vector[1] * jy + vector[2] * jz
    return np.asarray(expm(-1.0j * generator), dtype=np.complex128)


def one_body_tensor_kernel(
    two_q: int,
    tensor_matrix: np.ndarray,
    u: np.ndarray | complex,
    v: np.ndarray | complex,
    u_prime: np.ndarray | complex,
    v_prime: np.ndarray | complex,
) -> np.ndarray:
    """Evaluate ``sum_ab phi_a(x) T_ab phi_b(x')*``."""

    two_q = _validate_two_j(two_q)
    matrix = np.asarray(tensor_matrix, dtype=np.complex128)
    expected_shape = (two_q + 1, two_q + 1)
    if matrix.shape != expected_shape:
        raise ValueError(f"tensor_matrix must have shape {expected_shape}")
    target = monopole_orbitals(two_q, u, v)
    source = monopole_orbitals(two_q, u_prime, v_prime)
    return np.asarray(
        np.einsum(
            "...a,ab,...b->...",
            target,
            matrix,
            source.conj(),
            optimize=True,
        ),
        dtype=np.complex128,
    )


def quadrature_reconstruction_error(
    two_q: int,
    quadrature: SphereQuadrature,
) -> float:
    """Measure all-orbital reconstruction on fixed off-grid target points."""

    two_q = _validate_two_j(two_q)
    target_theta = np.array(
        [0.07, 0.51, 1.02, 1.68, 2.49, 3.03],
        dtype=np.float64,
    )
    target_phi = np.array(
        [5.91, 0.33, 2.72, 4.81, 1.39, 3.57],
        dtype=np.float64,
    )
    target_u = np.cos(0.5 * target_theta) * np.exp(0.5j * target_phi)
    target_v = np.sin(0.5 * target_theta) * np.exp(-0.5j * target_phi)
    source_orbitals = monopole_orbitals(
        two_q,
        quadrature.u,
        quadrature.v,
    )
    expected = monopole_orbitals(two_q, target_u, target_v)
    reconstructed = reconstruct_lll(
        two_q,
        quadrature,
        source_orbitals,
        target_u,
        target_v,
    )
    return float(np.max(np.abs(reconstructed - expected)))


def apply_one_body_tensor(
    psi_fn: Callable[[np.ndarray], complex],
    spinors: np.ndarray,
    particle_index: int,
    tensor_matrix: np.ndarray,
    quadrature: SphereQuadrature,
    *,
    reconstruction_tolerance: float = STRICT_LLL_TOLERANCE,
) -> complex:
    """Apply a one-body LLL tensor to one particle by sphere quadrature."""

    spinor_array = np.asarray(spinors, dtype=np.complex128)
    if spinor_array.ndim != 2 or spinor_array.shape[1] != 2:
        raise ValueError("spinors must have shape (n_particles, 2)")
    if (
        isinstance(particle_index, bool)
        or not isinstance(particle_index, (int, np.integer))
        or not 0 <= int(particle_index) < spinor_array.shape[0]
    ):
        raise ValueError("particle_index is outside the spinor array")
    matrix = np.asarray(tensor_matrix, dtype=np.complex128)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("tensor_matrix must be square")
    two_q = matrix.shape[0] - 1
    reconstruction_error = quadrature_reconstruction_error(two_q, quadrature)
    if reconstruction_error >= reconstruction_tolerance:
        raise RuntimeError(
            "quadrature fails strict LLL reconstruction: "
            f"{reconstruction_error} >= {reconstruction_tolerance}"
        )

    index = int(particle_index)
    target_u, target_v = spinor_array[index]
    kernel = one_body_tensor_kernel(
        two_q,
        matrix,
        target_u,
        target_v,
        quadrature.u,
        quadrature.v,
    )
    sampled_wavefunction = np.empty(quadrature.size, dtype=np.complex128)
    for grid_index in range(quadrature.size):
        replaced = spinor_array.copy()
        replaced[index, 0] = quadrature.u[grid_index]
        replaced[index, 1] = quadrature.v[grid_index]
        sampled_wavefunction[grid_index] = complex(psi_fn(replaced))
    return complex(
        np.sum(quadrature.weights * kernel * sampled_wavefunction)
    )


__all__ = [
    "STRICT_LLL_TOLERANCE",
    "angular_momentum_matrices",
    "apply_one_body_tensor",
    "canonical_tensor",
    "one_body_tensor_kernel",
    "quadrature_reconstruction_error",
    "rotation_matrix",
]
