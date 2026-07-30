#!/usr/bin/env python3
"""Independent dense exact-diagonalization oracle for issue #148.

This module deliberately does not share lattice or Hamiltonian implementation
with either future QMC route.  The local basis uses bit i for site i:
bit 0 -> sigma_z=+1, bit 1 -> sigma_z=-1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


CLUSTER_SCHEMA_VERSION = "yanwang148.cluster.v1"
OPERATOR_CONVENTION = "pauli-eigenvalues-plus-minus-one"


def load_cluster(path: str | Path) -> dict[str, Any]:
    cluster_path = Path(path)
    with cluster_path.open("r", encoding="utf-8") as handle:
        cluster = json.load(handle)
    validate_cluster(cluster)
    cluster["_source_path"] = str(cluster_path)
    cluster["_sha256"] = hashlib.sha256(cluster_path.read_bytes()).hexdigest()
    return cluster


def validate_cluster(cluster: dict[str, Any]) -> dict[str, Any]:
    if cluster.get("schema_version") != CLUSTER_SCHEMA_VERSION:
        raise ValueError("unsupported cluster schema")
    if cluster.get("lattice") not in {"triangular", "honeycomb"}:
        raise ValueError("unsupported lattice")
    if cluster.get("boundary") != "periodic":
        raise ValueError("only periodic clusters are permitted")
    if cluster.get("operator_convention") != OPERATOR_CONVENTION:
        raise ValueError("operator convention mismatch")
    n_sites = cluster.get("n_sites")
    if not isinstance(n_sites, int) or isinstance(n_sites, bool) or n_sites < 1:
        raise ValueError("n_sites must be a positive integer")
    edges = cluster.get("edges")
    if not isinstance(edges, list):
        raise ValueError("edges must be a list")

    normalized: list[tuple[int, int]] = []
    degrees = [0] * n_sites
    adjacency = [[] for _ in range(n_sites)]
    for edge in edges:
        if (
            not isinstance(edge, list)
            or len(edge) != 2
            or any(not isinstance(site, int) or isinstance(site, bool) for site in edge)
        ):
            raise ValueError(f"invalid edge: {edge!r}")
        first, second = edge
        if not (0 <= first < n_sites and 0 <= second < n_sites):
            raise ValueError(f"edge endpoint out of range: {edge!r}")
        if first >= second:
            raise ValueError(f"edges must be canonical first < second: {edge!r}")
        normalized.append((first, second))
        degrees[first] += 1
        degrees[second] += 1
        adjacency[first].append(second)
        adjacency[second].append(first)
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate edge")

    reached = {0}
    frontier = [0]
    while frontier:
        site = frontier.pop()
        for neighbor in adjacency[site]:
            if neighbor not in reached:
                reached.add(neighbor)
                frontier.append(neighbor)
    return {
        "degrees": degrees,
        "connected": len(reached) == n_sites,
        "bond_count": len(normalized),
    }


def _basis_states(n_sites: int) -> np.ndarray:
    return np.arange(1 << n_sites, dtype=np.int64)


def _z_values(states: np.ndarray, site: int) -> np.ndarray:
    return 1.0 - 2.0 * ((states >> site) & 1)


def _classical_energies(cluster: dict[str, Any], J: float) -> np.ndarray:
    n_sites = int(cluster["n_sites"])
    states = _basis_states(n_sites)
    energies = np.zeros(states.size, dtype=np.float64)
    for first, second in cluster["edges"]:
        energies -= J * _z_values(states, first) * _z_values(states, second)
    return energies


def magnetization_values(n_sites: int) -> np.ndarray:
    states = _basis_states(n_sites)
    magnetization = np.zeros(states.size, dtype=np.float64)
    for site in range(n_sites):
        magnetization += _z_values(states, site)
    return magnetization / n_sites


def build_hamiltonian(
    cluster: dict[str, Any],
    *,
    J: float,
    h: float,
) -> np.ndarray:
    validate_cluster(cluster)
    if not math.isfinite(J) or J < 0:
        raise ValueError("J must be finite and nonnegative")
    if not math.isfinite(h) or h < 0:
        raise ValueError("h must be finite and nonnegative")

    n_sites = int(cluster["n_sites"])
    states = _basis_states(n_sites)
    hamiltonian = np.diag(_classical_energies(cluster, J))
    row_indices = np.arange(states.size, dtype=np.int64)
    for site in range(n_sites):
        flipped = states ^ (1 << site)
        hamiltonian[row_indices, flipped] -= h
    return hamiltonian


def _thermal_weights(eigenvalues: np.ndarray, beta: float) -> tuple[np.ndarray, float]:
    if not math.isfinite(beta) or beta < 0:
        raise ValueError("beta must be finite and nonnegative")
    shifted = eigenvalues - np.min(eigenvalues)
    weights = np.exp(-beta * shifted)
    partition_shifted = float(np.sum(weights))
    return weights, partition_shifted


def thermal_observables(
    hamiltonian: np.ndarray,
    cluster: dict[str, Any],
    *,
    beta: float,
) -> dict[str, float]:
    n_sites = int(cluster["n_sites"])
    expected_dimension = 1 << n_sites
    if hamiltonian.shape != (expected_dimension, expected_dimension):
        raise ValueError("Hamiltonian shape does not match cluster")
    hermiticity_error = float(np.max(np.abs(hamiltonian - hamiltonian.T)))
    if hermiticity_error > 1e-12:
        raise ValueError(f"Hamiltonian is not symmetric: {hermiticity_error}")

    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    weights, partition_shifted = _thermal_weights(eigenvalues, beta)
    normalized_weights = weights / partition_shifted

    magnetization = magnetization_values(n_sites)
    m2_basis = magnetization**2
    m4_basis = magnetization**4
    basis_probabilities = np.abs(eigenvectors) ** 2
    m2_eigenstate = basis_probabilities.T @ m2_basis
    m4_eigenstate = basis_probabilities.T @ m4_basis

    energy_per_site = float(np.dot(normalized_weights, eigenvalues) / n_sites)
    m2 = float(np.dot(normalized_weights, m2_eigenstate))
    m4 = float(np.dot(normalized_weights, m4_eigenstate))
    binder_q = m2 * m2 / m4
    return {
        "energy_per_site": energy_per_site,
        "m2": m2,
        "m4": m4,
        "binder_q": binder_q,
        "ground_energy_per_site": float(eigenvalues[0] / n_sites),
        "hermiticity_error": hermiticity_error,
        "hilbert_dimension": int(expected_dimension),
    }


def beta_zero_moments(n_sites: int) -> dict[str, float]:
    if not isinstance(n_sites, int) or isinstance(n_sites, bool) or n_sites < 1:
        raise ValueError("n_sites must be a positive integer")
    m2 = 1.0 / n_sites
    m4 = (3.0 * n_sites - 2.0) / (n_sites**3)
    return {"m2": m2, "m4": m4, "binder_q": m2 * m2 / m4}


def independent_spin_observables(
    n_sites: int,
    *,
    h: float,
    beta: float,
) -> dict[str, float]:
    if not math.isfinite(h) or h < 0:
        raise ValueError("h must be finite and nonnegative")
    if not math.isfinite(beta) or beta < 0:
        raise ValueError("beta must be finite and nonnegative")
    moments = beta_zero_moments(n_sites)
    return {
        "energy_per_site": -h * math.tanh(beta * h),
        **moments,
    }


def classical_enumeration(
    cluster: dict[str, Any],
    *,
    J: float,
    beta: float,
) -> dict[str, float]:
    validate_cluster(cluster)
    if not math.isfinite(J) or J < 0:
        raise ValueError("J must be finite and nonnegative")
    energies = _classical_energies(cluster, J)
    weights, partition_shifted = _thermal_weights(energies, beta)
    normalized_weights = weights / partition_shifted
    magnetization = magnetization_values(int(cluster["n_sites"]))
    m2 = float(np.dot(normalized_weights, magnetization**2))
    m4 = float(np.dot(normalized_weights, magnetization**4))
    return {
        "energy_per_site": float(
            np.dot(normalized_weights, energies) / int(cluster["n_sites"])
        ),
        "m2": m2,
        "m4": m4,
        "binder_q": m2 * m2 / m4,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", required=True, type=Path)
    parser.add_argument("--J", required=True, type=float)
    parser.add_argument("--h", required=True, type=float)
    parser.add_argument("--beta", required=True, type=float)
    args = parser.parse_args()

    cluster = load_cluster(args.cluster)
    hamiltonian = build_hamiltonian(cluster, J=args.J, h=args.h)
    result = {
        "schema_version": "yanwang148.ed-result.v1",
        "cluster": cluster["name"],
        "cluster_sha256": cluster["_sha256"],
        "operator_convention": OPERATOR_CONVENTION,
        "J": args.J,
        "h": args.h,
        "beta": args.beta,
        "observables": thermal_observables(hamiltonian, cluster, beta=args.beta),
    }
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
