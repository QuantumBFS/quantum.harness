from __future__ import annotations

from functools import lru_cache

import numpy as np

from .ising import nearest_neighbor_operator
from .exact_oracle import (
    compare_small_neural_gradients,
    ExactBlockingResult,
    enumerate_rectangular_blocking,
    exact_handoff_energy,
    exact_local_energy_delta,
    exact_objective,
    exact_objective_per_site,
    exact_parameter_gradient,
    flatten_mlp_gradient,
    jax_exact_neural_gradient,
    target_distribution_distances,
)


@lru_cache(maxsize=None)
def nearest_neighbor_spectrum(length: int) -> tuple[np.ndarray, np.ndarray]:
    """Return exact S_nn values and degeneracies for a small square lattice."""
    if length < 2:
        raise ValueError("length must be at least 2")
    n_sites = length * length
    if n_sites > 20:
        raise ValueError("exact enumeration is limited to at most 20 spins")

    counts: dict[int, int] = {}
    for state in range(1 << n_sites):
        bits = ((state >> np.arange(n_sites, dtype=np.uint64)) & 1).astype(np.int8)
        spins = (2 * bits - 1).reshape(length, length)
        value = nearest_neighbor_operator(spins)
        counts[value] = counts.get(value, 0) + 1

    values = np.asarray(sorted(counts), dtype=float)
    degeneracies = np.asarray([counts[int(value)] for value in values], dtype=float)
    return values, degeneracies


def exact_nearest_neighbor_moments(length: int, coupling: float) -> tuple[float, float]:
    """Return exact mean and variance of S_nn under exp(-coupling * S_nn)."""
    values, degeneracies = nearest_neighbor_spectrum(length)
    log_weights = np.log(degeneracies) - float(coupling) * values
    log_weights -= log_weights.max()
    weights = np.exp(log_weights)
    weights /= weights.sum()
    mean = float(np.dot(weights, values))
    variance = float(np.dot(weights, (values - mean) ** 2))
    return mean, variance
