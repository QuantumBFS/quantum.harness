"""Continuous-coordinate amplitudes for the linear Route D+ scalar Ansatz."""

from __future__ import annotations

import hashlib
import math
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import cache

import numpy as np

from route_d_plus.lll import (
    SphereQuadrature,
    monopole_orbitals,
    spinor,
)
from route_d_plus.mother import LAUGHLIN_POWER, laughlin_amplitude
from route_d_plus.tensor import (
    STRICT_LLL_TOLERANCE,
    canonical_tensor,
    one_body_tensor_kernel,
    quadrature_reconstruction_error,
)


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
def compact_reproducing_quadrature(two_q: int) -> SphereQuadrature:
    """Return an exact, compact identity-resolution rule for the spin-Q LLL.

    ``two_q + 1`` uniform azimuthal nodes eliminate every nonzero orbital
    frequency difference.  The remaining diagonal orbital densities are
    polynomials of degree ``two_q`` in ``cos(theta)``, so
    ``ceil((two_q + 1) / 2)`` Gauss--Legendre nodes are sufficient.
    """

    if isinstance(two_q, bool) or not isinstance(
        two_q, (int, np.integer)
    ):
        raise TypeError("two_q must be an integer")
    two_q = int(two_q)
    if two_q < 0:
        raise ValueError("two_q must be non-negative")
    n_theta = (two_q + 2) // 2
    n_phi = two_q + 1
    x_nodes, x_weights = np.polynomial.legendre.leggauss(n_theta)
    phi_nodes = (
        2.0 * math.pi * np.arange(n_phi, dtype=np.float64) / n_phi
    )
    x = np.repeat(np.asarray(x_nodes, dtype=np.float64), n_phi)
    phi = np.tile(phi_nodes, n_theta)
    theta = np.arccos(x)
    weights = np.repeat(np.asarray(x_weights, dtype=np.float64), n_phi)
    weights *= 2.0 * math.pi / n_phi
    u, v = spinor(theta, phi)
    for value in (x, theta, phi, u, v, weights):
        value.flags.writeable = False
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


def _double_replaced_laughlin(
    spinors: np.ndarray,
    first: int,
    second: int,
    first_nodes: np.ndarray,
    second_nodes: np.ndarray,
) -> np.ndarray:
    """Evaluate ``Psi_L`` on a Cartesian product of two node sets."""

    first_array = np.asarray(first_nodes, dtype=np.complex128)
    second_array = np.asarray(second_nodes, dtype=np.complex128)
    if first_array.ndim != 2 or first_array.shape[1] != 2:
        raise ValueError("first_nodes must have shape (n_first, 2)")
    if second_array.ndim != 2 or second_array.shape[1] != 2:
        raise ValueError("second_nodes must have shape (n_second, 2)")
    batch = np.broadcast_to(
        np.asarray(spinors, dtype=np.complex128),
        (
            first_array.shape[0],
            second_array.shape[0],
            spinors.shape[0],
            2,
        ),
    ).copy()
    batch[:, :, first, :] = first_array[:, None, :]
    batch[:, :, second, :] = second_array[None, :, :]
    value = np.ones(batch.shape[:2], dtype=np.complex128)
    for left in range(batch.shape[2]):
        for right in range(left + 1, batch.shape[2]):
            contraction = (
                batch[:, :, left, 0] * batch[:, :, right, 1]
                - batch[:, :, left, 1] * batch[:, :, right, 0]
            )
            value *= contraction**LAUGHLIN_POWER
    return value


def scalar_laughlin_amplitudes_kernel(
    spinors: np.ndarray,
    quadrature: SphereQuadrature,
    *,
    ranks: tuple[int, ...] = (2, 3, 4),
    node_block_size: int = 32,
    reconstruction_tolerance: float = STRICT_LLL_TOLERANCE,
) -> np.ndarray:
    """Proof backend using two explicit LLL reproducing-kernel integrals.

    This intentionally independent backend samples the analytic mother after
    replacing both particles of every unordered pair by quadrature nodes.  It
    is slower than :func:`scalar_laughlin_amplitudes` and is reserved for
    continuous-configuration certification.
    """

    array, two_q = _validate_route_d_spinors(spinors)
    if node_block_size <= 0:
        raise ValueError("node_block_size must be positive")
    reconstruction_error = quadrature_reconstruction_error(
        two_q, quadrature
    )
    if reconstruction_error >= reconstruction_tolerance:
        raise RuntimeError(
            "quadrature fails strict LLL reconstruction: "
            f"{reconstruction_error} >= {reconstruction_tolerance}"
        )
    nodes = np.column_stack((quadrature.u, quadrature.v))
    amplitudes = np.zeros(1 + len(ranks), dtype=np.complex128)
    amplitudes[0] = laughlin_amplitude(array)
    tensors_by_rank = {
        ell: {
            m: canonical_tensor(two_q, ell, m)
            for m in range(-ell, ell + 1)
        }
        for ell in ranks
    }
    for first in range(array.shape[0]):
        for second in range(first + 1, array.shape[0]):
            right_kernels = {
                (ell, m): one_body_tensor_kernel(
                    two_q,
                    tensor,
                    array[second, 0],
                    array[second, 1],
                    quadrature.u,
                    quadrature.v,
                )
                * quadrature.weights
                for ell, tensors in tensors_by_rank.items()
                for m, tensor in tensors.items()
            }
            for start in range(0, quadrature.size, node_block_size):
                stop = min(start + node_block_size, quadrature.size)
                first_nodes = nodes[start:stop]
                sampled = _double_replaced_laughlin(
                    array,
                    first,
                    second,
                    first_nodes,
                    nodes,
                )
                for channel, ell in enumerate(ranks, start=1):
                    normalization = math.sqrt(2 * ell + 1)
                    tensors = tensors_by_rank[ell]
                    for m in range(-ell, ell + 1):
                        phase = (-1) ** m / normalization
                        left_m = one_body_tensor_kernel(
                            two_q,
                            tensors[m],
                            array[first, 0],
                            array[first, 1],
                            first_nodes[:, 0],
                            first_nodes[:, 1],
                        )
                        left_minus_m = one_body_tensor_kernel(
                            two_q,
                            tensors[-m],
                            array[first, 0],
                            array[first, 1],
                            first_nodes[:, 0],
                            first_nodes[:, 1],
                        )
                        amplitudes[channel] += phase * np.dot(
                            quadrature.weights[start:stop] * left_m,
                            sampled @ right_kernels[(ell, -m)],
                        )
                        amplitudes[channel] += phase * np.dot(
                            quadrature.weights[start:stop] * left_minus_m,
                            sampled @ right_kernels[(ell, m)],
                        )
    return amplitudes


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


def configuration_digest(spinors: np.ndarray) -> str:
    """Return the canonical digest used by coordinate-amplitude caches."""

    array, _ = _validate_route_d_spinors(spinors)
    canonical = np.ascontiguousarray(array.astype("<c16", copy=False))
    digest = hashlib.sha256()
    digest.update(np.asarray(canonical.shape, dtype="<i8").tobytes())
    digest.update(canonical.tobytes())
    return digest.hexdigest()


@dataclass
class CoordinateAmplitudeCache:
    """Bounded cache with the Route D+ configuration-scoped key contract."""

    max_entries: int = 4096
    _values: OrderedDict[
        tuple[int, int, int, int, str, str], complex
    ] = field(default_factory=OrderedDict, init=False, repr=False)
    _hits: int = field(default=0, init=False, repr=False)
    _misses: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_entries <= 0:
            raise ValueError("max_entries must be positive")

    def _get(
        self, key: tuple[int, int, int, int, str, str]
    ) -> complex | None:
        value = self._values.get(key)
        if value is not None:
            self._hits += 1
            self._values.move_to_end(key)
        else:
            self._misses += 1
        return value

    def _put(
        self,
        key: tuple[int, int, int, int, str, str],
        value: complex,
    ) -> None:
        self._values[key] = complex(value)
        self._values.move_to_end(key)
        while len(self._values) > self.max_entries:
            self._values.popitem(last=False)

    def channels(
        self,
        spinors: np.ndarray,
        *,
        total_l: int,
        ranks: tuple[int, ...] = (2, 3, 4),
    ) -> np.ndarray:
        """Evaluate and cache every operator word for one scalar or tower."""

        array, two_q = _validate_route_d_spinors(spinors)
        if total_l not in (0, 2):
            raise ValueError("total_l must be 0 or 2")
        digest = configuration_digest(array)
        words = ("identity", *(f"G{ell}" for ell in ranks))
        magnetic_values = (0,) if total_l == 0 else tuple(range(-2, 3))
        shape = (len(words),) if total_l == 0 else (5, len(words))
        result = np.empty(shape, dtype=np.complex128)
        missing = False
        for component, magnetic in enumerate(magnetic_values):
            for word_index, word in enumerate(words):
                key = (
                    array.shape[0],
                    two_q,
                    total_l,
                    magnetic,
                    word,
                    digest,
                )
                value = self._get(key)
                if value is None:
                    missing = True
                    break
                if total_l == 0:
                    result[word_index] = value
                else:
                    result[component, word_index] = value
            if missing:
                break
        if missing:
            computed = (
                scalar_laughlin_amplitudes(array, ranks=ranks)
                if total_l == 0
                else scalar_tower_amplitudes(array, ranks=ranks)
            )
            result[...] = computed
            for component, magnetic in enumerate(magnetic_values):
                for word_index, word in enumerate(words):
                    value = (
                        result[word_index]
                        if total_l == 0
                        else result[component, word_index]
                    )
                    self._put(
                        (
                            array.shape[0],
                            two_q,
                            total_l,
                            magnetic,
                            word,
                            digest,
                        ),
                        value,
                    )
        return result

    def batch(
        self,
        spinor_batches: np.ndarray,
        *,
        total_l: int,
        ranks: tuple[int, ...] = (2, 3, 4),
    ) -> np.ndarray:
        """Evaluate an isolated batch while sharing immutable word results."""

        batches = np.asarray(spinor_batches, dtype=np.complex128)
        if batches.ndim != 3 or batches.shape[2] != 2:
            raise ValueError(
                "spinor_batches must have shape (batch, particles, 2)"
            )
        return np.stack(
            [
                self.channels(item, total_l=total_l, ranks=ranks)
                for item in batches
            ],
            axis=0,
        )

    def clear(self) -> None:
        self._values.clear()
        self._hits = 0
        self._misses = 0

    @property
    def entries(self) -> int:
        return len(self._values)

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses


__all__ = [
    "CoordinateAmplitudeCache",
    "compact_reproducing_quadrature",
    "configuration_digest",
    "evaluate_pair_polynomial",
    "laughlin_pair_polynomial",
    "linear_dplus0_amplitudes",
    "lll_interpolation_rule",
    "pair_tensor_action_on_laughlin",
    "scalar_laughlin_amplitudes",
    "scalar_laughlin_amplitudes_kernel",
    "scalar_tower_amplitudes",
]
