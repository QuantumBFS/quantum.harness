"""Exact small-system thermodynamics for the cubic spin-glass model."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math

import numpy as np

from .model import EABonds, energy


@dataclass(frozen=True)
class ExactThermalRecord:
    beta: float
    log_partition: float
    partition_function: float
    partition_derivative: float
    energy: float
    heat_capacity: float
    two_point: np.ndarray
    q2: float
    q4: float
    states: np.ndarray
    energies: np.ndarray
    probabilities: np.ndarray

    def __post_init__(self) -> None:
        arrays = (
            self.two_point,
            self.states,
            self.energies,
            self.probabilities,
        )
        for value in arrays:
            value.setflags(write=False)


@dataclass(frozen=True)
class ExactPartitionRecord:
    length: int
    beta: float
    log_partition: float
    partition_function: float
    partition_derivative: float
    energy: float


def _validated_beta(beta: float) -> float:
    value = float(beta)
    if not np.isfinite(value) or value < 0.0:
        raise ValueError("beta must be finite and nonnegative")
    return value


def _spin_states(length: int) -> np.ndarray:
    n_sites = length**3
    labels = np.arange(1 << n_sites, dtype=np.uint64)[:, None]
    shifts = np.arange(n_sites, dtype=np.uint64)
    bits = ((labels >> shifts) & 1).astype(np.int8)
    return (2 * bits - 1).reshape(-1, length, length, length)


def enumerate_l2(beta: float, bonds: EABonds) -> ExactThermalRecord:
    """Enumerate all 256 states of one periodic L=2 disorder sample."""
    beta = _validated_beta(beta)
    if not isinstance(bonds, EABonds) or bonds.length != 2:
        raise ValueError("enumerate_l2 requires L=2 EABonds")

    states = _spin_states(2)
    energies = np.fromiter(
        (energy(state, bonds) for state in states),
        dtype=np.int64,
        count=states.shape[0],
    )
    log_weights = -beta * energies.astype(np.float64)
    shift = float(np.max(log_weights))
    shifted_weights = np.exp(log_weights - shift)
    shifted_partition = float(np.sum(shifted_weights, dtype=np.float64))
    probabilities = shifted_weights / shifted_partition
    log_partition = shift + math.log(shifted_partition)
    partition_function = _scaled_float(
        shifted_partition,
        shift,
        math.log(shifted_partition),
    )
    shifted_derivative = float(
        np.sum(-energies * shifted_weights, dtype=np.float64)
    )
    derivative_log_magnitude = (
        -math.inf
        if shifted_derivative == 0.0
        else math.log(abs(shifted_derivative))
    )
    partition_derivative = _scaled_float(
        shifted_derivative,
        shift,
        derivative_log_magnitude,
    )

    mean_energy = float(probabilities @ energies)
    mean_energy_squared = float(
        probabilities @ (energies.astype(np.float64) ** 2)
    )
    variance = max(0.0, mean_energy_squared - mean_energy**2)
    heat_capacity = beta**2 * variance

    flat_states = states.reshape(states.shape[0], -1).astype(np.float64)
    two_point = flat_states.T @ (probabilities[:, None] * flat_states)
    overlaps = flat_states @ flat_states.T / float(flat_states.shape[1])
    pair_probabilities = probabilities[:, None] * probabilities[None, :]
    q2 = float(np.sum(pair_probabilities * overlaps**2, dtype=np.float64))
    q4 = float(np.sum(pair_probabilities * overlaps**4, dtype=np.float64))

    return ExactThermalRecord(
        beta=beta,
        log_partition=log_partition,
        partition_function=partition_function,
        partition_derivative=partition_derivative,
        energy=mean_energy,
        heat_capacity=heat_capacity,
        two_point=two_point,
        q2=q2,
        q4=q4,
        states=states,
        energies=energies,
        probabilities=probabilities,
    )


@lru_cache(maxsize=2)
def _layer_states(length: int) -> np.ndarray:
    n_sites = length**2
    labels = np.arange(1 << n_sites, dtype=np.uint64)[:, None]
    shifts = np.arange(n_sites, dtype=np.uint64)
    bits = ((labels >> shifts) & 1).astype(np.int8)
    states = (2 * bits - 1).reshape(-1, length, length)
    states.setflags(write=False)
    return states


def _layer_matrix(
    beta: float,
    bonds: EABonds,
    z: int,
    states: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    local_energy = _layer_energies(bonds, z, states)
    log_weight = -beta * local_energy.astype(np.float64)
    shift = float(np.max(log_weight))
    matrix = np.exp(log_weight - shift)
    derivative = -local_energy * matrix
    return matrix, derivative, shift


def _layer_energies(
    bonds: EABonds,
    z: int,
    states: np.ndarray,
) -> np.ndarray:
    spins = states.astype(np.int16, copy=False)
    intra = -np.sum(
        bonds.values[:, :, z, 0][None, ...]
        * spins
        * np.roll(spins, -1, axis=1)
        + bonds.values[:, :, z, 1][None, ...]
        * spins
        * np.roll(spins, -1, axis=2),
        axis=(1, 2),
        dtype=np.int64,
    )
    flat = spins.reshape(spins.shape[0], -1)
    vertical = -(
        (flat * bonds.values[:, :, z, 2].reshape(1, -1)) @ flat.T
    ).astype(np.int64, copy=False)
    return intra[:, None] + vertical


def _scaled_float(value: float, log_scale: float, log_magnitude: float) -> float:
    if value == 0.0:
        return 0.0
    combined = log_magnitude + log_scale
    maximum_log = math.log(np.finfo(np.float64).max)
    if combined > maximum_log:
        return math.copysign(math.inf, value)
    if math.log(np.finfo(np.float64).tiny) <= log_scale <= maximum_log:
        return value * math.exp(log_scale)
    return math.copysign(math.exp(combined), value)


def _log_domain_transfer(
    beta: float,
    bonds: EABonds,
    states: np.ndarray,
) -> tuple[float, float]:
    """Return ``(log Z, mean energy)`` without exponentiating global scales."""

    energies = [
        _layer_energies(bonds, z, states).astype(np.float64)
        for z in range(bonds.length)
    ]
    log_matrices = [-beta * value for value in energies]

    if bonds.length == 2:
        closing_log_weights = log_matrices[0] + log_matrices[1].T
        closing_energies = energies[0] + energies[1].T
        maximum = float(np.max(closing_log_weights))
        weights = np.exp(closing_log_weights - maximum)
        normalizer = float(np.sum(weights, dtype=np.float64))
        log_partition = maximum + math.log(normalizer)
        mean_energy = float(
            np.sum(weights * closing_energies, dtype=np.float64) / normalizer
        )
        return log_partition, mean_energy

    log_pair = np.empty_like(log_matrices[0])
    pair_energy = np.empty_like(log_matrices[0])
    for left_index in range(states.shape[0]):
        terms = log_matrices[0][left_index, :, None] + log_matrices[1]
        maxima = np.max(terms, axis=0)
        weights = np.exp(terms - maxima[None, :])
        normalizers = np.sum(weights, axis=0, dtype=np.float64)
        log_pair[left_index] = maxima + np.log(normalizers)
        candidate_energy = (
            energies[0][left_index, :, None] + energies[1]
        )
        pair_energy[left_index] = np.sum(
            weights * candidate_energy,
            axis=0,
            dtype=np.float64,
        ) / normalizers

    closing_log_weights = log_pair + log_matrices[2].T
    closing_energies = pair_energy + energies[2].T
    maximum = float(np.max(closing_log_weights))
    weights = np.exp(closing_log_weights - maximum)
    normalizer = float(np.sum(weights, dtype=np.float64))
    if not np.isfinite(normalizer) or normalizer <= 0.0:
        raise FloatingPointError("log-domain transfer normalization failed")
    log_partition = maximum + math.log(normalizer)
    mean_energy = float(
        np.sum(weights * closing_energies, dtype=np.float64) / normalizer
    )
    return log_partition, mean_energy


def _transfer_layers(beta: float, bonds: EABonds) -> ExactPartitionRecord:
    """Evaluate the periodic layer ring for the L=2/L=3 exact checks."""
    beta = _validated_beta(beta)
    if not isinstance(bonds, EABonds) or bonds.length not in (2, 3):
        raise ValueError("layer transfer supports only L=2 or L=3 EABonds")
    length = bonds.length
    states = _layer_states(length)
    terms = [_layer_matrix(beta, bonds, z, states) for z in range(length)]
    matrices = [term[0] for term in terms]
    derivatives = [term[1] for term in terms]
    log_scale = float(sum(term[2] for term in terms))

    if length == 2:
        scaled_partition = float(
            np.sum(matrices[0] * matrices[1].T, dtype=np.float64)
        )
        scaled_derivative = float(
            np.sum(derivatives[0] * matrices[1].T, dtype=np.float64)
            + np.sum(matrices[0] * derivatives[1].T, dtype=np.float64)
        )
    else:
        first_pair = matrices[0] @ matrices[1]
        first_pair_derivative = (
            derivatives[0] @ matrices[1] + matrices[0] @ derivatives[1]
        )
        scaled_partition = float(
            np.sum(first_pair * matrices[2].T, dtype=np.float64)
        )
        scaled_derivative = float(
            np.sum(first_pair_derivative * matrices[2].T, dtype=np.float64)
            + np.sum(first_pair * derivatives[2].T, dtype=np.float64)
    )

    if not np.isfinite(scaled_partition):
        raise FloatingPointError("scaled transfer partition is not finite")
    if scaled_partition <= 0.0:
        log_partition, mean_energy = _log_domain_transfer(beta, bonds, states)
        partition_function = _scaled_float(
            1.0,
            log_partition,
            0.0,
        )
        if mean_energy == 0.0:
            partition_derivative = 0.0
        else:
            partition_derivative = _scaled_float(
                -mean_energy,
                log_partition,
                math.log(abs(mean_energy)),
            )
        return ExactPartitionRecord(
            length=length,
            beta=beta,
            log_partition=log_partition,
            partition_function=partition_function,
            partition_derivative=partition_derivative,
            energy=mean_energy,
        )
    if not np.isfinite(scaled_derivative):
        raise FloatingPointError("scaled transfer derivative is not finite")
    log_partition = log_scale + math.log(scaled_partition)
    partition_function = _scaled_float(
        scaled_partition,
        log_scale,
        math.log(scaled_partition),
    )
    derivative_log_magnitude = (
        -math.inf
        if scaled_derivative == 0.0
        else math.log(abs(scaled_derivative))
    )
    partition_derivative = _scaled_float(
        scaled_derivative,
        log_scale,
        derivative_log_magnitude,
    )
    mean_energy = -scaled_derivative / scaled_partition
    return ExactPartitionRecord(
        length=length,
        beta=beta,
        log_partition=log_partition,
        partition_function=partition_function,
        partition_derivative=partition_derivative,
        energy=mean_energy,
    )


def transfer_l3(beta: float, bonds: EABonds) -> ExactPartitionRecord:
    """Return the exact L=3 partition function and mean energy."""
    if not isinstance(bonds, EABonds) or bonds.length != 3:
        raise ValueError("transfer_l3 requires L=3 EABonds")
    return _transfer_layers(beta, bonds)
