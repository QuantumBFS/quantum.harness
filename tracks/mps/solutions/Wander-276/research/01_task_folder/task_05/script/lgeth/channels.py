"""Model-independent channel geometry and exact nullity accounting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .combinatorics import laughlin_zero_mode_count, root_descendant_partition
from .lattice import (
    build_kapit_laughlin_parent,
    channel_matrix,
    manybody_one_body_operator,
    projected_site_potential,
)


@dataclass(frozen=True)
class NullityDecomposition:
    """Accessibility and pulled-back-form contributions to curvature nullity."""

    target_dimension: int
    active_rank: int
    curvature_rank: int
    total: int
    accessibility: int
    form: int
    active_cutoff: float
    curvature_cutoff: float


@dataclass(frozen=True)
class PhysicalChannelCache:
    """Task-local factorization of the physical tangent-to-channel map."""

    N: int
    n_flux: int
    rank: int
    external_dimension: int
    energies: np.ndarray
    tangent_basis: np.ndarray
    channel_basis: np.ndarray
    tangent_gram: np.ndarray
    external_gap: float
    kernel_bandwidth: float
    metadata: dict[str, Any]


def build_physical_channel_cache(
    n_particles: int = 3,
    n_flux: int = 10,
    theta_x: float = 0.17,
    theta_y: float = 0.29,
) -> PhysicalChannelCache:
    """Build the fixed Kapit--Mueller tangent-channel cache independently."""

    N = int(n_particles)
    n = int(n_flux)
    system = build_kapit_laughlin_parent(N, n, theta_x, theta_y)
    parent = system.parent.toarray()
    energies, vectors = np.linalg.eigh(0.5 * (parent + parent.conj().T))
    rank = laughlin_zero_mode_count(N, n)
    energies_p = energies[:rank]
    energies_q = energies[rank:]
    vectors_p = vectors[:, :rank]
    vectors_q = vectors[:, rank:]
    physical_sites = system.orbitals.shape[0]
    tangent_basis = np.empty(
        (physical_sites, system.basis.dimension, system.basis.dimension),
        dtype=complex,
    )
    channel_basis = np.empty(
        (physical_sites, rank, system.basis.dimension - rank),
        dtype=complex,
    )
    for site in range(physical_sites):
        potential = np.zeros(physical_sites, dtype=float)
        potential[site] = 1.0
        projected = projected_site_potential(system.orbitals, potential)
        tangent = manybody_one_body_operator(system.basis, projected)
        tangent_basis[site] = tangent.toarray()
        channel_basis[site] = channel_matrix(
            energies_p,
            vectors_p,
            energies_q,
            vectors_q,
            tangent,
        )
    tangent_gram = np.einsum(
        "iab,jab->ij",
        tangent_basis.conj(),
        tangent_basis,
        optimize=True,
    ).real
    return PhysicalChannelCache(
        N=N,
        n_flux=n,
        rank=rank,
        external_dimension=system.basis.dimension - rank,
        energies=energies,
        tangent_basis=tangent_basis,
        channel_basis=channel_basis,
        tangent_gram=tangent_gram,
        external_gap=float(energies_q[0] - energies_p[-1]),
        kernel_bandwidth=float(np.ptp(energies_p)),
        metadata={
            "theta_x": float(theta_x),
            "theta_y": float(theta_y),
            "basis_dimension": int(system.basis.dimension),
            "physical_sites": int(physical_sites),
        },
    )


def normalized_potential(
    rng: np.random.Generator,
    sites: int,
) -> np.ndarray:
    """Draw a mean-zero unit vector of local-potential coefficients."""

    values = rng.normal(size=int(sites))
    values -= np.mean(values)
    norm = float(np.linalg.norm(values))
    if norm <= 0.0:
        raise RuntimeError("local potential has zero norm")
    return values / norm


def cached_channel(
    coefficients: np.ndarray,
    cache: PhysicalChannelCache,
) -> np.ndarray:
    """Evaluate and Hilbert--Schmidt normalize a cached physical channel."""

    vector = np.asarray(coefficients, dtype=float)
    norm_squared = float(vector @ cache.tangent_gram @ vector)
    if norm_squared <= 0.0:
        raise RuntimeError("many-body tangent has zero norm")
    return (
        np.tensordot(vector, cache.channel_basis, axes=(0, 0))
        / np.sqrt(norm_squared)
    )


def root_response_partition(N: int, n: int):
    """Return the exact first-descendant root partition."""

    return root_descendant_partition(int(N), int(n), q=1, k=1, r=2)


def _validated_channel_pair(
    channel_v: np.ndarray,
    channel_w: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(channel_v, dtype=complex)
    y = np.asarray(channel_w, dtype=complex)
    if x.ndim != 2 or y.ndim != 2:
        raise ValueError("channels must be two-dimensional")
    if x.shape != y.shape:
        raise ValueError("channels must have equal shape")
    if x.shape[0] == 0 or x.shape[1] == 0:
        raise ValueError("channels must be nonempty")
    return x, y


def curvature_from_channels(
    channel_v: np.ndarray,
    channel_w: np.ndarray,
) -> np.ndarray:
    """Return the Hermitian non-Abelian curvature channel form."""

    x, y = _validated_channel_pair(channel_v, channel_w)
    curvature = 1j * (x @ y.conj().T - y @ x.conj().T)
    return 0.5 * (curvature + curvature.conj().T)


def _rank_with_cutoff(
    matrix: np.ndarray,
    rtol: float,
    atol: float,
) -> tuple[int, float]:
    if rtol < 0.0 or atol < 0.0:
        raise ValueError("rank tolerances must be nonnegative")
    singular_values = np.linalg.svd(
        np.asarray(matrix, dtype=complex),
        compute_uv=False,
    )
    if singular_values.size == 0:
        return 0, float(atol)
    cutoff = max(float(atol), float(rtol) * float(singular_values[0]))
    return int(np.count_nonzero(singular_values > cutoff)), cutoff


def nullity_decomposition(
    channel_v: np.ndarray,
    channel_w: np.ndarray,
    rtol: float = 1e-12,
    atol: float = 0.0,
) -> NullityDecomposition:
    """Return the exact rank-nullity split at a specified numerical tolerance."""

    x, y = _validated_channel_pair(channel_v, channel_w)
    stacked = np.concatenate([x, y], axis=1)
    active_rank, active_cutoff = _rank_with_cutoff(
        stacked,
        rtol=rtol,
        atol=atol,
    )
    curvature = curvature_from_channels(x, y)
    curvature_rank, curvature_cutoff = _rank_with_cutoff(
        curvature,
        rtol=rtol,
        atol=atol,
    )
    target_dimension = x.shape[0]
    accessibility = target_dimension - active_rank
    form = active_rank - curvature_rank
    if accessibility < 0 or form < 0:
        raise RuntimeError("rank accounting produced a negative nullity")
    return NullityDecomposition(
        target_dimension=target_dimension,
        active_rank=active_rank,
        curvature_rank=curvature_rank,
        total=target_dimension - curvature_rank,
        accessibility=accessibility,
        form=form,
        active_cutoff=active_cutoff,
        curvature_cutoff=curvature_cutoff,
    )
