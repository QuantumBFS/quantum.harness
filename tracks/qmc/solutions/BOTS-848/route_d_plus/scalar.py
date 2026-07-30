"""Normal-ordered scalar generators for the Route D+ operator dressing."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np

from route_d_plus.lll import monopole_orbitals
from route_d_plus.tensor import angular_momentum_matrices, canonical_tensor


@dataclass(frozen=True)
class FockSpace:
    """Fixed-particle-number fermionic Fock space in the LLL orbital basis."""

    n_orbitals: int
    n_particles: int
    states: tuple[int, ...]
    index: dict[int, int]

    @classmethod
    def build(cls, n_orbitals: int, n_particles: int) -> FockSpace:
        if not 0 < n_particles <= n_orbitals:
            raise ValueError("require 0 < n_particles <= n_orbitals")
        states = tuple(
            sum(1 << orbital for orbital in occupied)
            for occupied in itertools.combinations(
                range(n_orbitals), n_particles
            )
        )
        return cls(
            n_orbitals=n_orbitals,
            n_particles=n_particles,
            states=states,
            index={state: position for position, state in enumerate(states)},
        )

    @property
    def dimension(self) -> int:
        return len(self.states)


def _annihilate(state: int, orbital: int) -> tuple[int, int] | None:
    mask = 1 << orbital
    if not state & mask:
        return None
    sign = -1 if (state & (mask - 1)).bit_count() % 2 else 1
    return state ^ mask, sign


def _create(state: int, orbital: int) -> tuple[int, int] | None:
    mask = 1 << orbital
    if state & mask:
        return None
    sign = -1 if (state & (mask - 1)).bit_count() % 2 else 1
    return state | mask, sign


def one_body_fock_matrix(
    space: FockSpace,
    orbital_matrix: np.ndarray,
) -> np.ndarray:
    """Lift ``sum_ab T_ab c_a^dagger c_b`` to ``space``."""

    matrix = np.asarray(orbital_matrix, dtype=np.complex128)
    expected = (space.n_orbitals, space.n_orbitals)
    if matrix.shape != expected:
        raise ValueError(f"orbital_matrix must have shape {expected}")
    result = np.zeros((space.dimension, space.dimension), np.complex128)
    for column, state in enumerate(space.states):
        for b in range(space.n_orbitals):
            removed = _annihilate(state, b)
            if removed is None:
                continue
            after_b, sign_b = removed
            for a in range(space.n_orbitals):
                value = matrix[a, b]
                if value == 0.0:
                    continue
                added = _create(after_b, a)
                if added is not None:
                    final, sign_a = added
                    result[space.index[final], column] += (
                        sign_b * sign_a * value
                    )
    return result


def normal_ordered_product(
    space: FockSpace,
    left: np.ndarray,
    right: np.ndarray,
) -> np.ndarray:
    """Lift ``:rho(left) rho(right):`` without an intermediate one-body term."""

    left_array = np.asarray(left, dtype=np.complex128)
    right_array = np.asarray(right, dtype=np.complex128)
    expected = (space.n_orbitals, space.n_orbitals)
    if left_array.shape != expected or right_array.shape != expected:
        raise ValueError(f"one-body matrices must have shape {expected}")
    result = np.zeros((space.dimension, space.dimension), np.complex128)
    for column, state in enumerate(space.states):
        for b in range(space.n_orbitals):
            removed_b = _annihilate(state, b)
            if removed_b is None:
                continue
            after_b, sign_b = removed_b
            for d in range(space.n_orbitals):
                removed_d = _annihilate(after_b, d)
                if removed_d is None:
                    continue
                after_d, sign_d = removed_d
                for c in range(space.n_orbitals):
                    added_c = _create(after_d, c)
                    if added_c is None:
                        continue
                    after_c, sign_c = added_c
                    right_column = right_array[c, d]
                    if right_column == 0.0:
                        continue
                    for a in range(space.n_orbitals):
                        value = left_array[a, b] * right_column
                        if value == 0.0:
                            continue
                        added_a = _create(after_c, a)
                        if added_a is not None:
                            final, sign_a = added_a
                            result[space.index[final], column] += (
                                sign_b
                                * sign_d
                                * sign_c
                                * sign_a
                                * value
                            )
    return result


def one_body_casimir(two_q: int, ell: int) -> tuple[float, float]:
    """Return the scalar contraction ``c_ell`` and its non-scalar residual."""

    tensors = [
        canonical_tensor(two_q, ell, m) for m in range(-ell, ell + 1)
    ]
    contraction = sum(
        ((-1) ** m)
        * (
            tensors[m + ell] @ tensors[-m + ell]
            + tensors[-m + ell] @ tensors[m + ell]
        )
        for m in range(-ell, ell + 1)
    ) / (2.0 * math.sqrt(2 * ell + 1))
    coefficient = float(np.trace(contraction).real / (two_q + 1))
    residual = float(
        np.max(
            np.abs(
                contraction
                - coefficient
                * np.eye(two_q + 1, dtype=np.complex128)
            )
        )
    )
    return coefficient, residual


def scalar_generator_proof(
    space: FockSpace,
    two_q: int,
    ell: int,
) -> np.ndarray:
    """Density-product definition of the normal-ordered ``G_ell``."""

    tensors = {
        m: canonical_tensor(two_q, ell, m)
        for m in range(-ell, ell + 1)
    }
    densities = {
        m: one_body_fock_matrix(space, tensor)
        for m, tensor in tensors.items()
    }
    generator = sum(
        ((-1) ** m)
        * (
            densities[m] @ densities[-m]
            + densities[-m] @ densities[m]
        )
        for m in range(-ell, ell + 1)
    ) / (2.0 * math.sqrt(2 * ell + 1))
    casimir, _ = one_body_casimir(two_q, ell)
    return np.asarray(
        generator
        - casimir
        * space.n_particles
        * np.eye(space.dimension, dtype=np.complex128),
        dtype=np.complex128,
    )


def scalar_generator_pair(
    space: FockSpace,
    two_q: int,
    ell: int,
) -> np.ndarray:
    """Direct normal-ordered pair backend for ``G_ell``."""

    tensors = {
        m: canonical_tensor(two_q, ell, m)
        for m in range(-ell, ell + 1)
    }
    generator = sum(
        ((-1) ** m)
        * (
            normal_ordered_product(space, tensors[m], tensors[-m])
            + normal_ordered_product(space, tensors[-m], tensors[m])
        )
        for m in range(-ell, ell + 1)
    ) / (2.0 * math.sqrt(2 * ell + 1))
    return np.asarray(generator, dtype=np.complex128)


def coupled_pair_eigenvalues(
    two_q: int,
    ell: int,
) -> tuple[dict[int, float], float]:
    """Extract pair-channel eigenvalues directly from the coupled subspaces."""

    space = FockSpace.build(two_q + 1, 2)
    generator = scalar_generator_pair(space, two_q, ell)
    jx, jy, jz = angular_momentum_matrices(two_q)
    total = [
        one_body_fock_matrix(space, component)
        for component in (jx, jy, jz)
    ]
    total_j2 = sum(component @ component for component in total)
    eigenvalues, eigenvectors = np.linalg.eigh(total_j2)
    channels: dict[int, float] = {}
    maximum_spread = 0.0
    for total_j in range(two_q + 1):
        selected = np.isclose(
            eigenvalues,
            total_j * (total_j + 1),
            rtol=0.0,
            atol=1.0e-9,
        )
        if not np.any(selected):
            continue
        basis = eigenvectors[:, selected]
        block = basis.conj().T @ generator @ basis
        channel_values = np.linalg.eigvalsh(block)
        channels[total_j] = float(np.mean(channel_values).real)
        maximum_spread = max(
            maximum_spread,
            float(np.max(np.abs(channel_values - channels[total_j]))),
        )
    return channels, maximum_spread


def slater_matrix(
    two_q: int,
    space: FockSpace,
    spinor_batches: np.ndarray,
) -> np.ndarray:
    """Evaluate normalized Slater basis states on continuous configurations."""

    batches = np.asarray(spinor_batches, dtype=np.complex128)
    if batches.ndim != 3 or batches.shape[1:] != (
        space.n_particles,
        2,
    ):
        raise ValueError("spinor_batches has incompatible shape")
    orbitals = monopole_orbitals(
        two_q,
        batches[..., 0],
        batches[..., 1],
    )
    values = np.empty((batches.shape[0], space.dimension), np.complex128)
    normalization = math.sqrt(math.factorial(space.n_particles))
    for column, state in enumerate(space.states):
        occupied = [
            orbital
            for orbital in range(space.n_orbitals)
            if state & (1 << orbital)
        ]
        values[:, column] = np.linalg.det(
            orbitals[:, :, occupied]
        ) / normalization
    return values


def whitening_transform(
    covariance: np.ndarray,
    *,
    relative_cutoff: float = 1.0e-12,
    regularization: float = 1.0e-14,
) -> tuple[np.ndarray, np.ndarray]:
    """Return retained eigenvalues and the symmetric inverse square root."""

    matrix = np.asarray(covariance, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("covariance must be square")
    eigenvalues, eigenvectors = np.linalg.eigh(
        0.5 * (matrix + matrix.T)
    )
    maximum = float(np.max(eigenvalues))
    retained = eigenvalues > relative_cutoff * maximum
    if maximum <= 0.0 or not np.any(retained):
        raise ValueError("covariance has no positive retained direction")
    inverse_sqrt = np.zeros_like(eigenvalues)
    inverse_sqrt[retained] = 1.0 / np.sqrt(
        eigenvalues[retained] + regularization * maximum
    )
    transform = (eigenvectors * inverse_sqrt) @ eigenvectors.T
    return eigenvalues[retained], transform


__all__ = [
    "FockSpace",
    "coupled_pair_eigenvalues",
    "normal_ordered_product",
    "one_body_casimir",
    "one_body_fock_matrix",
    "scalar_generator_pair",
    "scalar_generator_proof",
    "slater_matrix",
    "whitening_transform",
]
