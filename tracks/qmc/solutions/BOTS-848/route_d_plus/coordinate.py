"""Continuous-coordinate amplitudes for the linear Route D+ scalar Ansatz."""

from __future__ import annotations

import math
from functools import cache

import numpy as np

from route_d_plus.lll import monopole_orbitals, spinor
from route_d_plus.mother import LAUGHLIN_POWER, laughlin_amplitude
from route_d_plus.tensor import canonical_tensor


def _validate_route_d_spinors(spinors: np.ndarray) -> tuple[np.ndarray, int]:
    array = np.asarray(spinors, dtype=np.complex128)
    if array.ndim != 2 or array.shape[1] != 2 or array.shape[0] < 2:
        raise ValueError("spinors must have shape (n_particles >= 2, 2)")
    if not np.all(np.isfinite(array)):
        raise ValueError("spinors must be finite")
    return array, LAUGHLIN_POWER * (array.shape[0] - 1)


@cache
def _orbital_normalizations(two_q: int) -> np.ndarray:
    return np.sqrt(
        (two_q + 1)
        * np.array(
            [math.comb(two_q, power) for power in range(two_q + 1)],
            dtype=np.float64,
        )
        / (4.0 * math.pi)
    )


def _multiply_axis(
    coefficients: np.ndarray,
    factor: np.ndarray,
    axis: int,
) -> np.ndarray:
    shape = list(coefficients.shape)
    shape[axis] += factor.size - 1
    result = np.zeros(shape, dtype=np.complex128)
    for power, value in enumerate(factor):
        target = [slice(None)] * coefficients.ndim
        target[axis] = slice(power, power + coefficients.shape[axis])
        result[tuple(target)] += value * coefficients
    return result


def _one_particle_factor(
    spinors: np.ndarray,
    selected: int,
    other: int,
) -> np.ndarray:
    """Coefficients by the selected particle's power of ``u``."""

    u_other, v_other = spinors[other]
    if selected < other:
        return np.array(
            [
                math.comb(LAUGHLIN_POWER, power)
                * v_other**power
                * (-u_other) ** (LAUGHLIN_POWER - power)
                for power in range(LAUGHLIN_POWER + 1)
            ],
            dtype=np.complex128,
        )
    return np.array(
        [
            math.comb(LAUGHLIN_POWER, power)
            * (-v_other) ** power
            * u_other ** (LAUGHLIN_POWER - power)
            for power in range(LAUGHLIN_POWER + 1)
        ],
        dtype=np.complex128,
    )


def laughlin_pair_polynomial(
    spinors: np.ndarray,
    first: int,
    second: int,
) -> np.ndarray:
    """Return monomial coefficients in two selected particle spinors.

    Entry ``[p, q]`` multiplies
    ``u_i**p v_i**(2Q-p) u_j**q v_j**(2Q-q)``.
    """

    array, two_q = _validate_route_d_spinors(spinors)
    if not 0 <= first < second < array.shape[0]:
        raise ValueError("require 0 <= first < second < n_particles")
    coefficients = np.ones((1, 1), dtype=np.complex128)
    for other in range(array.shape[0]):
        if other not in (first, second):
            coefficients = _multiply_axis(
                coefficients,
                _one_particle_factor(array, first, other),
                0,
            )
            coefficients = _multiply_axis(
                coefficients,
                _one_particle_factor(array, second, other),
                1,
            )
    mutual = np.zeros(
        (LAUGHLIN_POWER + 1, LAUGHLIN_POWER + 1),
        dtype=np.complex128,
    )
    for power in range(LAUGHLIN_POWER + 1):
        mutual[power, LAUGHLIN_POWER - power] = (
            math.comb(LAUGHLIN_POWER, power)
            * (-1) ** (LAUGHLIN_POWER - power)
        )
    result = np.zeros((two_q + 1, two_q + 1), dtype=np.complex128)
    for p in range(coefficients.shape[0]):
        for q in range(coefficients.shape[1]):
            result[
                p : p + LAUGHLIN_POWER + 1,
                q : q + LAUGHLIN_POWER + 1,
            ] += coefficients[p, q] * mutual

    spectator = 1.0 + 0.0j
    for left in range(array.shape[0]):
        for right in range(left + 1, array.shape[0]):
            if left in (first, second) or right in (first, second):
                continue
            spectator *= (
                array[left, 0] * array[right, 1]
                - array[left, 1] * array[right, 0]
            ) ** LAUGHLIN_POWER
    return spectator * result


def evaluate_pair_polynomial(
    coefficients: np.ndarray,
    first_spinor: np.ndarray,
    second_spinor: np.ndarray,
) -> complex:
    """Evaluate a two-particle homogeneous polynomial coefficient matrix."""

    matrix = np.asarray(coefficients, dtype=np.complex128)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("coefficients must be a square matrix")
    two_q = matrix.shape[0] - 1
    powers = np.arange(two_q + 1)
    first = (
        first_spinor[0] ** powers
        * first_spinor[1] ** (two_q - powers)
    )
    second = (
        second_spinor[0] ** powers
        * second_spinor[1] ** (two_q - powers)
    )
    return complex(first @ matrix @ second)


def pair_tensor_action_on_laughlin(
    spinors: np.ndarray,
    first: int,
    second: int,
    left: np.ndarray,
    right: np.ndarray,
) -> complex:
    """Evaluate ``tau_left(first) tau_right(second) Psi_L`` exactly."""

    array, two_q = _validate_route_d_spinors(spinors)
    coefficients = laughlin_pair_polynomial(array, first, second)
    normalizations = _orbital_normalizations(two_q)
    orbital_coefficients = coefficients / np.outer(
        normalizations, normalizations
    )
    transformed = np.asarray(left) @ orbital_coefficients @ np.asarray(
        right
    ).T
    monomial_coefficients = transformed * np.outer(
        normalizations, normalizations
    )
    return evaluate_pair_polynomial(
        monomial_coefficients,
        array[first],
        array[second],
    )


def scalar_laughlin_amplitudes(
    spinors: np.ndarray,
    *,
    ranks: tuple[int, ...] = (2, 3, 4),
) -> np.ndarray:
    """Return ``[Psi_L, G_ell Psi_L ...]`` at one configuration."""

    array, two_q = _validate_route_d_spinors(spinors)
    amplitudes = [laughlin_amplitude(array)]
    normalizations = _orbital_normalizations(two_q)
    orbitals = monopole_orbitals(two_q, array[:, 0], array[:, 1])
    pair_coefficients = {
        (first, second): laughlin_pair_polynomial(
            array, first, second
        )
        / np.outer(normalizations, normalizations)
        for first in range(array.shape[0])
        for second in range(first + 1, array.shape[0])
    }
    for ell in ranks:
        tensors = {
            m: canonical_tensor(two_q, ell, m)
            for m in range(-ell, ell + 1)
        }
        value = 0.0 + 0.0j
        normalization = math.sqrt(2 * ell + 1)
        for first in range(array.shape[0]):
            for second in range(first + 1, array.shape[0]):
                coefficients = pair_coefficients[(first, second)]
                for m in range(-ell, ell + 1):
                    phase = (-1) ** m / normalization
                    value += phase * (
                        orbitals[first]
                        @ tensors[m]
                        @ coefficients
                        @ tensors[-m].T
                        @ orbitals[second]
                    )
                    value += phase * (
                        orbitals[first]
                        @ tensors[-m]
                        @ coefficients
                        @ tensors[m].T
                        @ orbitals[second]
                    )
        amplitudes.append(value)
    return np.asarray(amplitudes, dtype=np.complex128)


@cache
def lll_interpolation_rule(two_q: int) -> tuple[np.ndarray, np.ndarray]:
    """Return equatorial DFT nodes and inverse orbital evaluation matrix."""

    phi = 2.0 * math.pi * np.arange(two_q + 1) / (two_q + 1)
    theta = np.full(two_q + 1, 0.5 * math.pi)
    u, v = spinor(theta, phi)
    nodes = np.column_stack((u, v))
    orbital_values = monopole_orbitals(two_q, u, v)
    inverse = np.linalg.inv(orbital_values)
    nodes.flags.writeable = False
    inverse.flags.writeable = False
    return nodes, inverse


def scalar_tower_amplitudes(
    spinors: np.ndarray,
    *,
    ranks: tuple[int, ...] = (2, 3, 4),
) -> np.ndarray:
    """Return five rank-two components for every scalar-dressed channel.

    The result has shape ``(5, 1 + len(ranks))``. Scalarity permits evaluating
    ``rho_(2M) G_ell Psi_L`` instead of a higher-body ``G_ell rho_(2M)``.
    """

    array, two_q = _validate_route_d_spinors(spinors)
    nodes, inverse = lll_interpolation_rule(two_q)
    target_orbitals = monopole_orbitals(
        two_q, array[:, 0], array[:, 1]
    )
    tensors = [
        canonical_tensor(two_q, 2, m) for m in range(-2, 3)
    ]
    result = np.zeros((5, 1 + len(ranks)), dtype=np.complex128)
    for particle in range(array.shape[0]):
        values = np.empty(
            (two_q + 1, 1 + len(ranks)), dtype=np.complex128
        )
        for node_index, node in enumerate(nodes):
            replaced = array.copy()
            replaced[particle] = node
            values[node_index] = scalar_laughlin_amplitudes(
                replaced, ranks=ranks
            )
        coefficients = inverse @ values
        for component, tensor in enumerate(tensors):
            result[component] += (
                target_orbitals[particle] @ tensor @ coefficients
            )
    return result


def linear_dplus0_amplitudes(
    channels: np.ndarray,
    coefficients: np.ndarray,
) -> np.ndarray:
    """Combine mother and dressed channels with explicit complex coefficients."""

    values = np.asarray(channels, dtype=np.complex128)
    parameters = np.asarray(coefficients, dtype=np.complex128)
    if values.shape[-1] != parameters.size + 1:
        raise ValueError("channel count must equal coefficient count plus one")
    return values[..., 0] + values[..., 1:] @ parameters


__all__ = [
    "evaluate_pair_polynomial",
    "laughlin_pair_polynomial",
    "linear_dplus0_amplitudes",
    "lll_interpolation_rule",
    "pair_tensor_action_on_laughlin",
    "scalar_laughlin_amplitudes",
    "scalar_tower_amplitudes",
]
