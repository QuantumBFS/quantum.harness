"""Analytic Laughlin and quadrupole mother states for Route D+."""

from __future__ import annotations

import math

import numpy as np

from route_d_plus.lll import SphereQuadrature
from route_d_plus.tensor import (
    STRICT_LLL_TOLERANCE,
    canonical_tensor,
    one_body_tensor_kernel,
    quadrature_reconstruction_error,
)

LAUGHLIN_POWER = 3


def _validate_spinors(spinors: np.ndarray) -> np.ndarray:
    array = np.asarray(spinors, dtype=np.complex128)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("spinors must have shape (n_particles, 2)")
    if array.shape[0] < 2:
        raise ValueError("at least two particle spinors are required")
    if not np.all(np.isfinite(array)):
        raise ValueError("spinors must be finite")
    return array


def pair_contractions(spinors: np.ndarray) -> np.ndarray:
    """Return all singlet contractions ``[ij] = u_i v_j - v_i u_j``."""

    array = _validate_spinors(spinors)
    contractions = [
        array[i, 0] * array[j, 1] - array[i, 1] * array[j, 0]
        for i in range(array.shape[0])
        for j in range(i + 1, array.shape[0])
    ]
    return np.asarray(contractions, dtype=np.complex128)


def log_psi_laughlin(spinors: np.ndarray) -> tuple[float, complex]:
    """Return stable ``(log_abs, phase)`` for the fermionic Laughlin mother."""

    contractions = pair_contractions(spinors)
    magnitudes = np.abs(contractions)
    if np.any(magnitudes == 0.0):
        return -math.inf, 0.0 + 0.0j
    log_abs = float(LAUGHLIN_POWER * np.sum(np.log(magnitudes)))
    phase_angle = float(LAUGHLIN_POWER * np.sum(np.angle(contractions)))
    phase = complex(np.exp(1.0j * phase_angle))
    return log_abs, phase


def laughlin_amplitude(spinors: np.ndarray) -> complex:
    """Return the analytic Laughlin amplitude, preserving exact nodes."""

    log_abs, phase = log_psi_laughlin(spinors)
    if log_abs == -math.inf:
        return 0.0 + 0.0j
    return complex(math.exp(log_abs) * phase)


def _sample_replaced_laughlin(
    spinors: np.ndarray,
    particle_index: int,
    quadrature: SphereQuadrature,
) -> np.ndarray:
    """Evaluate the mother after replacing one particle by every grid point."""

    array = _validate_spinors(spinors)
    batch = np.broadcast_to(array, (quadrature.size, *array.shape)).copy()
    batch[:, particle_index, 0] = quadrature.u
    batch[:, particle_index, 1] = quadrature.v
    contractions = np.stack(
        [
            batch[:, i, 0] * batch[:, j, 1]
            - batch[:, i, 1] * batch[:, j, 0]
            for i in range(array.shape[0])
            for j in range(i + 1, array.shape[0])
        ],
        axis=1,
    )
    magnitudes = np.abs(contractions)
    nodes = np.any(magnitudes == 0.0, axis=1)
    safe_magnitudes = np.where(magnitudes == 0.0, 1.0, magnitudes)
    log_abs = LAUGHLIN_POWER * np.sum(np.log(safe_magnitudes), axis=1)
    phase = np.exp(
        1.0j * LAUGHLIN_POWER * np.sum(np.angle(contractions), axis=1)
    )
    values = np.exp(log_abs) * phase
    values[nodes] = 0.0
    return np.asarray(values, dtype=np.complex128)


def gmp_quadrupole_tower(
    spinors: np.ndarray,
    quadrature: SphereQuadrature,
    *,
    two_q: int | None = None,
    reconstruction_tolerance: float = STRICT_LLL_TOLERANCE,
) -> np.ndarray:
    """Evaluate ``Phi_(2M)=rho_bar_(2M) Psi_L`` for ``M=-2,...,+2``."""

    array = _validate_spinors(spinors)
    expected_two_q = LAUGHLIN_POWER * (array.shape[0] - 1)
    two_q = expected_two_q if two_q is None else int(two_q)
    if two_q != expected_two_q:
        raise ValueError(
            "Laughlin flux must satisfy two_q = 3 * (n_particles - 1)"
        )
    reconstruction_error = quadrature_reconstruction_error(two_q, quadrature)
    if reconstruction_error >= reconstruction_tolerance:
        raise RuntimeError(
            "quadrature fails strict LLL reconstruction: "
            f"{reconstruction_error} >= {reconstruction_tolerance}"
        )

    components = np.zeros(5, dtype=np.complex128)
    tensors = [canonical_tensor(two_q, 2, m) for m in range(-2, 3)]
    for particle_index in range(array.shape[0]):
        sampled_mother = _sample_replaced_laughlin(
            array,
            particle_index,
            quadrature,
        )
        target_u, target_v = array[particle_index]
        for component_index, tensor in enumerate(tensors):
            kernel = one_body_tensor_kernel(
                two_q,
                tensor,
                target_u,
                target_v,
                quadrature.u,
                quadrature.v,
            )
            components[component_index] += np.sum(
                quadrature.weights * kernel * sampled_mother
            )
    return components


__all__ = [
    "LAUGHLIN_POWER",
    "gmp_quadrupole_tower",
    "laughlin_amplitude",
    "log_psi_laughlin",
    "pair_contractions",
]
