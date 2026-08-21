"""Custom TeNPy MPOGraph for the periodized exponential Ising Hamiltonian."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike
from tenpy.networks.mpo import MPO, MPOGraph
from tenpy.networks.site import SpinHalfSite


def build_periodized_mpo_graph(
    length: int,
    lambdas: ArrayLike,
    coefficients: ArrayLike,
    gamma: float,
    *,
    prune_zero_channels: bool = False,
) -> MPOGraph:
    """Build the finite MPO graph using direct and wrapped channels."""
    return _build_periodized_mpo_graph(
        length,
        lambdas,
        coefficients,
        gamma,
        site=SpinHalfSite(conserve=None),
        interaction_operator="Sigmaz",
        field_operator="Sigmax",
        prune_zero_channels=prune_zero_channels,
    )


def _build_periodized_mpo_graph(
    length: int,
    lambdas: ArrayLike,
    coefficients: ArrayLike,
    gamma: float,
    *,
    site: SpinHalfSite,
    interaction_operator: str,
    field_operator: str,
    prune_zero_channels: bool = False,
) -> MPOGraph:
    decay, weights = _validated_parameters(
        length,
        lambdas,
        coefficients,
        gamma,
    )
    if prune_zero_channels:
        decay, weights, _ = active_exponential_channels(decay, weights)
    graph = MPOGraph(
        [site] * length,
        bc="finite",
        max_range=length - 1,
        unit_cell_width=1,
    )

    for k, (lambda_k, coefficient) in enumerate(zip(decay, weights, strict=True)):
        amplitude = coefficient / (1.0 - lambda_k**length)
        direct = (0, 0, k)
        wrapped = (0, 1, k)

        for i in range(length):
            if i < length - 1:
                graph.add(i, "IdL", direct, interaction_operator, lambda_k)
                graph.add(
                    i,
                    "IdL",
                    wrapped,
                    interaction_operator,
                    lambda_k**i,
                )
            if 0 < i < length - 1:
                graph.add(i, direct, direct, "Id", lambda_k)
                graph.add(i, wrapped, wrapped, "Id", 1.0)
            if i > 0:
                graph.add(
                    i,
                    direct,
                    "IdR",
                    interaction_operator,
                    -amplitude,
                )
                graph.add(
                    i,
                    wrapped,
                    "IdR",
                    interaction_operator,
                    -amplitude * lambda_k ** (length - i),
                )

    if gamma != 0.0:
        for i in range(length):
            graph.add(i, "IdL", "IdR", field_operator, -float(gamma))
    graph.add_missing_IdL_IdR()
    return graph


def build_periodized_mpo(
    length: int,
    lambdas: ArrayLike,
    coefficients: ArrayLike,
    gamma: float,
    *,
    prune_zero_channels: bool = False,
) -> MPO:
    """Build the finite MPO represented by :func:`build_periodized_mpo_graph`."""
    return build_periodized_mpo_graph(
        length,
        lambdas,
        coefficients,
        gamma,
        prune_zero_channels=prune_zero_channels,
    ).build_MPO()


def build_rotated_periodized_mpo(
    length: int,
    lambdas: ArrayLike,
    coefficients: ArrayLike,
    gamma: float,
    *,
    prune_zero_channels: bool = False,
) -> MPO:
    """Build the periodized long-range MPO in the physical-X parity basis."""
    return _build_periodized_mpo_graph(
        length,
        lambdas,
        coefficients,
        gamma,
        site=SpinHalfSite(conserve="parity"),
        interaction_operator="Sigmax",
        field_operator="Sigmaz",
        prune_zero_channels=prune_zero_channels,
    ).build_MPO()


def build_nearest_neighbor_tfim_mpo_graph(length: int, gamma: float) -> MPOGraph:
    """Build the periodic nearest-neighbor Pauli TFIM as a finite MPO graph."""
    return _build_nearest_neighbor_tfim_mpo_graph(
        length,
        gamma,
        site=SpinHalfSite(conserve=None),
        interaction_operator="Sigmaz",
        field_operator="Sigmax",
    )


def _build_nearest_neighbor_tfim_mpo_graph(
    length: int,
    gamma: float,
    *,
    site: SpinHalfSite,
    interaction_operator: str,
    field_operator: str,
) -> MPOGraph:
    if not isinstance(length, (int, np.integer)) or length < 3:
        raise ValueError("length must be an integer >= 3")
    if not np.isfinite(gamma):
        raise ValueError("gamma must be finite")

    graph = MPOGraph(
        [site] * length,
        bc="finite",
        max_range=length - 1,
        unit_cell_width=1,
    )
    nearest = (1, 0, 0)
    wrapped = (1, 1, 0)

    for i in range(length):
        if i < length - 1:
            graph.add(i, "IdL", nearest, interaction_operator, 1.0)
        if i > 0:
            graph.add(i, nearest, "IdR", interaction_operator, -1.0)

        if i == 0:
            graph.add(i, "IdL", wrapped, interaction_operator, 1.0)
        elif i < length - 1:
            graph.add(i, wrapped, wrapped, "Id", 1.0)
        else:
            graph.add(i, wrapped, "IdR", interaction_operator, -1.0)

        if gamma != 0.0:
            graph.add(i, "IdL", "IdR", field_operator, -float(gamma))

    graph.add_missing_IdL_IdR()
    return graph


def build_nearest_neighbor_tfim_mpo(length: int, gamma: float) -> MPO:
    """Build H = -sum_i Z_i Z_(i+1) - gamma sum_i X_i with periodic bonds."""
    return build_nearest_neighbor_tfim_mpo_graph(length, gamma).build_MPO()


def build_rotated_nearest_neighbor_tfim_mpo(length: int, gamma: float) -> MPO:
    """Build the periodic NN TFIM in the physical-X parity basis."""
    site = SpinHalfSite(conserve="parity")
    return _build_nearest_neighbor_tfim_mpo_graph(
        length,
        gamma,
        site=site,
        interaction_operator="Sigmax",
        field_operator="Sigmaz",
    ).build_MPO()


def _validated_parameters(
    length: int,
    lambdas: ArrayLike,
    coefficients: ArrayLike,
    gamma: float,
) -> tuple[np.ndarray, np.ndarray]:
    if not isinstance(length, (int, np.integer)) or length < 2:
        raise ValueError("length must be an integer >= 2")
    decay = np.asarray(lambdas, dtype=float)
    weights = np.asarray(coefficients, dtype=float)
    if decay.ndim != 1 or weights.ndim != 1 or len(decay) != len(weights):
        raise ValueError("lambdas and coefficients must be equal-length vectors")
    if len(decay) == 0:
        raise ValueError("at least one exponential is required")
    if np.any(~np.isfinite(decay)) or np.any((decay <= 0.0) | (decay >= 1.0)):
        raise ValueError("all lambdas must be finite and satisfy 0 < lambda < 1")
    if np.any(~np.isfinite(weights)) or np.any(weights < 0.0):
        raise ValueError("all coefficients must be finite and non-negative")
    if not np.isfinite(gamma):
        raise ValueError("gamma must be finite")
    return decay, weights


def active_exponential_channels(
    lambdas: ArrayLike,
    coefficients: ArrayLike,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return only exactly nonzero fitted modes and their original indices."""
    decay = np.asarray(lambdas, dtype=float)
    weights = np.asarray(coefficients, dtype=float)
    if decay.ndim != 1 or weights.ndim != 1 or len(decay) != len(weights):
        raise ValueError("lambdas and coefficients must be equal-length vectors")
    active = np.flatnonzero(weights != 0.0)
    return decay[active], weights[active], active
