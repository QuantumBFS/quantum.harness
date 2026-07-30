"""Multiplet-invariant sampling and SR primitives for Route D+ D+0."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm

from route_d_plus.coordinate import linear_dplus0_amplitudes
from route_d_plus.lll import spinor

ChannelEvaluator = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class ChainResult:
    samples: np.ndarray
    channel_values: np.ndarray
    accepted_local: int
    proposed_local: int
    global_rotation_residual: float
    delta_max: float

    @property
    def acceptance(self) -> float:
        return self.accepted_local / self.proposed_local


@dataclass(frozen=True)
class SRTrace:
    coefficients: np.ndarray
    energies: np.ndarray
    effective_sample_sizes: np.ndarray
    step_norms: np.ndarray


def spinors_to_vectors(spinors: np.ndarray) -> np.ndarray:
    array = np.asarray(spinors, dtype=np.complex128)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("spinors must have shape (n_particles, 2)")
    overlap = array[:, 0] * array[:, 1].conj()
    return np.column_stack(
        (
            2.0 * overlap.real,
            2.0 * overlap.imag,
            np.abs(array[:, 0]) ** 2 - np.abs(array[:, 1]) ** 2,
        )
    )


def vectors_to_spinors(vectors: np.ndarray) -> np.ndarray:
    array = np.asarray(vectors, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("vectors must have shape (n_particles, 3)")
    norms = np.linalg.norm(array, axis=1)
    if np.max(np.abs(norms - 1.0)) > 1.0e-12:
        raise ValueError("vectors must be unit vectors")
    theta = np.arccos(np.clip(array[:, 2], -1.0, 1.0))
    phi = np.mod(np.arctan2(array[:, 1], array[:, 0]), 2.0 * np.pi)
    u, v = spinor(theta, phi)
    return np.column_stack((u, v))


def random_configuration(
    rng: np.random.Generator,
    n_particles: int,
) -> np.ndarray:
    vectors = rng.normal(size=(n_particles, 3))
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors_to_spinors(vectors)


def geodesic_proposal(
    spinors: np.ndarray,
    particle: int,
    delta: float,
    rng: np.random.Generator,
) -> np.ndarray:
    vectors = spinors_to_vectors(spinors)
    normal = vectors[particle]
    tangent = rng.normal(size=3)
    tangent -= np.dot(tangent, normal) * normal
    tangent /= np.linalg.norm(tangent)
    proposed = vectors.copy()
    proposed[particle] = (
        math.cos(delta) * normal + math.sin(delta) * tangent
    )
    result = np.asarray(spinors, dtype=np.complex128).copy()
    result[particle] = vectors_to_spinors(
        proposed[particle : particle + 1]
    )[0]
    return result


def random_global_rotation(
    spinors: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    axis = rng.normal(size=3)
    axis /= np.linalg.norm(axis)
    angle = rng.uniform(-math.pi, math.pi)
    pauli = (
        np.array([[0.0, 1.0], [1.0, 0.0]]) * axis[0]
        + np.array([[0.0, -1.0j], [1.0j, 0.0]]) * axis[1]
        + np.diag([1.0, -1.0]) * axis[2]
    )
    rotation = expm(-0.5j * angle * pauli)
    return np.asarray(spinors) @ rotation.T


def channel_weight(
    channels: np.ndarray,
    coefficients: np.ndarray,
) -> float:
    amplitudes = linear_dplus0_amplitudes(channels, coefficients)
    return float(np.sum(np.abs(amplitudes) ** 2))


def metropolis_chain(
    evaluator: ChannelEvaluator,
    *,
    n_particles: int,
    coefficients: np.ndarray,
    seed: int,
    burn_in_sweeps: int,
    sample_sweeps: int,
    thin_sweeps: int = 1,
    delta_max: float = 0.35,
    global_rotation_interval: int = 8,
) -> ChainResult:
    """Sample either a scalar state or a full multiplet from one chain."""

    if burn_in_sweeps < 0 or sample_sweeps <= 0 or thin_sweeps <= 0:
        raise ValueError("invalid sweep counts")
    rng = np.random.default_rng(seed)
    configuration = random_configuration(rng, n_particles)
    channels = evaluator(configuration)
    weight = channel_weight(channels, coefficients)
    accepted = 0
    proposed = 0
    rotation_residual = 0.0
    samples = []
    values = []
    total_sweeps = burn_in_sweeps + sample_sweeps * thin_sweeps
    for sweep in range(total_sweeps):
        for _ in range(n_particles):
            particle = int(rng.integers(n_particles))
            delta = rng.uniform(-delta_max, delta_max)
            proposal = geodesic_proposal(
                configuration, particle, delta, rng
            )
            proposal_channels = evaluator(proposal)
            proposal_weight = channel_weight(
                proposal_channels, coefficients
            )
            ratio = proposal_weight / max(weight, np.finfo(float).tiny)
            proposed += 1
            if rng.random() < min(1.0, ratio):
                configuration = proposal
                channels = proposal_channels
                weight = proposal_weight
                accepted += 1
        if sweep < burn_in_sweeps and (sweep + 1) % 8 == 0:
            acceptance = accepted / max(proposed, 1)
            if acceptance < 0.35:
                delta_max *= 0.85
            elif acceptance > 0.60:
                delta_max *= 1.15
            delta_max = float(np.clip(delta_max, 0.02, math.pi))
        if global_rotation_interval and (
            sweep + 1
        ) % global_rotation_interval == 0:
            rotated = random_global_rotation(configuration, rng)
            rotated_channels = evaluator(rotated)
            rotated_weight = channel_weight(
                rotated_channels, coefficients
            )
            residual = abs(rotated_weight - weight) / max(weight, 1.0e-300)
            rotation_residual = max(rotation_residual, residual)
            configuration = rotated
            channels = rotated_channels
            weight = rotated_weight
        measurement = sweep - burn_in_sweeps
        if measurement >= 0 and measurement % thin_sweeps == 0:
            samples.append(configuration.copy())
            values.append(channels.copy())
    return ChainResult(
        samples=np.asarray(samples),
        channel_values=np.asarray(values),
        accepted_local=accepted,
        proposed_local=proposed,
        global_rotation_residual=rotation_residual,
        delta_max=delta_max,
    )


def coulomb_potential(spinor_batches: np.ndarray, two_q: int) -> np.ndarray:
    """Pair-only chord Coulomb estimator in ``e^2/(epsilon l_B)`` units."""

    batches = np.asarray(spinor_batches, dtype=np.complex128)
    if batches.ndim == 2:
        batches = batches[None, ...]
    if batches.ndim != 3 or batches.shape[2] != 2 or two_q <= 0:
        raise ValueError("invalid spinor batches or flux")
    values = np.zeros(batches.shape[0], dtype=np.float64)
    for first in range(batches.shape[1]):
        for second in range(first + 1, batches.shape[1]):
            contraction = (
                batches[:, first, 0] * batches[:, second, 1]
                - batches[:, first, 1] * batches[:, second, 0]
            )
            chord = 2.0 * np.abs(contraction)
            values += 1.0 / (math.sqrt(0.5 * two_q) * chord)
    return values


def linear_log_derivatives(
    channels: np.ndarray,
    coefficients: np.ndarray,
) -> np.ndarray:
    """Real-PyTree log derivatives for complex linear coefficients."""

    values = np.asarray(channels, dtype=np.complex128)
    amplitudes = linear_dplus0_amplitudes(values, coefficients)
    derivatives = values[..., 1:] / amplitudes[..., None]
    return np.concatenate((derivatives, 1.0j * derivatives), axis=-1)


def multiplet_log_derivatives(
    channels: np.ndarray,
    coefficients: np.ndarray,
) -> np.ndarray:
    """Multiplet-weighted real-parameter log derivatives."""

    values = np.asarray(channels, dtype=np.complex128)
    if values.ndim != 3:
        raise ValueError("multiplet channels must have sample and M axes")
    amplitudes = linear_dplus0_amplitudes(values, coefficients)
    derivatives = values[..., 1:]
    denominator = np.sum(np.abs(amplitudes) ** 2, axis=1)
    real_part = np.einsum(
        "sm,sma->sa", amplitudes.conj(), derivatives, optimize=True
    ) / denominator[:, None]
    imaginary_part = 1.0j * real_part
    return np.concatenate((real_part, imaginary_part), axis=-1)


def energy_gradient_metric(
    energy: np.ndarray,
    log_derivatives: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Return energy, real gradient, and Fubini--Study metric."""

    values = np.asarray(energy, dtype=np.float64)
    derivatives = np.asarray(log_derivatives, dtype=np.complex128)
    mean_energy = float(np.mean(values))
    centered_energy = values - mean_energy
    mean_derivative = np.mean(derivatives, axis=0)
    centered = derivatives - mean_derivative
    gradient = 2.0 * np.real(
        np.mean(centered.conj() * centered_energy[:, None], axis=0)
    )
    metric = np.real(centered.conj().T @ centered) / values.size
    return mean_energy, gradient, 0.5 * (metric + metric.T)


def importance_weights(
    channels: np.ndarray,
    coefficients: np.ndarray,
) -> np.ndarray:
    """Normalized candidate/base weights for fixed mother-distribution samples."""

    values = np.asarray(channels, dtype=np.complex128)
    numerator = np.sum(
        np.abs(linear_dplus0_amplitudes(values, coefficients)) ** 2,
        axis=tuple(range(1, values.ndim - 1)),
    )
    denominator = np.sum(
        np.abs(values[..., 0]) ** 2,
        axis=tuple(range(1, values.ndim - 1)),
    )
    ratios = numerator / np.maximum(denominator, np.finfo(float).tiny)
    return ratios / np.sum(ratios)


def weighted_energy_gradient_metric(
    energy: np.ndarray,
    log_derivatives: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray, float]:
    """Weighted energy, gradient, metric, and importance-sampling ESS."""

    values = np.asarray(energy, dtype=np.float64)
    derivatives = np.asarray(log_derivatives, dtype=np.complex128)
    probabilities = np.asarray(weights, dtype=np.float64)
    probabilities /= np.sum(probabilities)
    mean_energy = float(probabilities @ values)
    mean_derivative = np.sum(
        probabilities[:, None] * derivatives, axis=0
    )
    centered = derivatives - mean_derivative
    gradient = 2.0 * np.real(
        np.sum(
            probabilities[:, None]
            * centered.conj()
            * (values - mean_energy)[:, None],
            axis=0,
        )
    )
    metric = np.real(
        centered.conj().T @ (probabilities[:, None] * centered)
    )
    effective_sample_size = float(1.0 / np.sum(probabilities**2))
    return (
        mean_energy,
        gradient,
        0.5 * (metric + metric.T),
        effective_sample_size,
    )


def center_whiten_channels(
    channels: np.ndarray,
    mean: np.ndarray,
    whitening: np.ndarray,
) -> np.ndarray:
    """Replace raw generator channels by centered, whitened channels."""

    values = np.asarray(channels, dtype=np.complex128)
    centers = np.asarray(mean, dtype=np.float64)
    transform = np.asarray(whitening, dtype=np.float64)
    if values.shape[-1] != centers.size + 1:
        raise ValueError("mean does not match raw generator channels")
    if transform.ndim != 2 or transform.shape[1] != centers.size:
        raise ValueError("whitening has incompatible shape")
    centered = values[..., 1:] - values[..., :1] * centers
    dressed = centered @ transform.T
    return np.concatenate((values[..., :1], dressed), axis=-1)


def correlated_sr_optimize(
    channels: np.ndarray,
    energy: np.ndarray,
    initial_coefficients: np.ndarray,
    *,
    updates: int,
    learning_rate: float = 0.1,
    diagonal_shift: float = 1.0e-2,
    trust_radius: float = 0.05,
) -> SRTrace:
    """Optimize one D+0 sector using mother-distribution correlated samples."""

    coefficients = np.asarray(
        initial_coefficients, dtype=np.complex128
    ).copy()
    energies = []
    effective_sizes = []
    step_norms = []
    for _ in range(updates):
        weights = importance_weights(channels, coefficients)
        if channels.ndim == 2:
            derivatives = linear_log_derivatives(channels, coefficients)
        elif channels.ndim == 3:
            derivatives = multiplet_log_derivatives(
                channels, coefficients
            )
        else:
            raise ValueError("channels must describe a scalar or multiplet")
        estimate, gradient, metric, effective_size = (
            weighted_energy_gradient_metric(
                energy, derivatives, weights
            )
        )
        step = sr_update(
            metric,
            gradient,
            learning_rate=learning_rate,
            diagonal_shift=diagonal_shift,
            trust_radius=trust_radius,
        )
        count = coefficients.size
        coefficients += step[:count] + 1.0j * step[count:]
        energies.append(estimate)
        effective_sizes.append(effective_size)
        step_norms.append(float(np.linalg.norm(step)))
    return SRTrace(
        coefficients=coefficients,
        energies=np.asarray(energies),
        effective_sample_sizes=np.asarray(effective_sizes),
        step_norms=np.asarray(step_norms),
    )


def sr_update(
    metric: np.ndarray,
    gradient: np.ndarray,
    *,
    learning_rate: float,
    diagonal_shift: float,
    trust_radius: float,
) -> np.ndarray:
    """Solve a regularized SR step and enforce a Fubini--Study trust region."""

    matrix = np.asarray(metric, dtype=np.float64)
    force = np.asarray(gradient, dtype=np.float64)
    regularized = matrix + diagonal_shift * np.eye(matrix.shape[0])
    step = -learning_rate * np.linalg.solve(regularized, force)
    distance_squared = max(float(step @ matrix @ step), 0.0)
    if distance_squared > trust_radius**2:
        step *= trust_radius / math.sqrt(distance_squared)
    return step


__all__ = [
    "ChainResult",
    "SRTrace",
    "center_whiten_channels",
    "channel_weight",
    "coulomb_potential",
    "energy_gradient_metric",
    "geodesic_proposal",
    "linear_log_derivatives",
    "importance_weights",
    "metropolis_chain",
    "multiplet_log_derivatives",
    "random_configuration",
    "random_global_rotation",
    "spinors_to_vectors",
    "sr_update",
    "correlated_sr_optimize",
    "vectors_to_spinors",
    "weighted_energy_gradient_metric",
]
