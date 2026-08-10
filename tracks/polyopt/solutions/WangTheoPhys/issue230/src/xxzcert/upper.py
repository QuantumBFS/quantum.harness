"""Explicit repeated-block variational upper bounds."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.sparse.linalg import eigsh

from .model import finite_xxz, finite_xxz_sparse, local_xxz, reduced_density


@dataclass(frozen=True)
class UpperCandidate:
    delta: float
    sites: int
    raw_upper: float
    state: NDArray[np.complex128]
    normalization_residual: float
    internal_energy: float
    boundary_energy: float


def neel_state(sites: int, start: int = 0) -> NDArray[np.complex128]:
    if sites < 1:
        raise ValueError("sites must be positive")
    bits = tuple((start + i) % 2 for i in range(sites))
    index = sum(bit << (sites - 1 - i) for i, bit in enumerate(bits))
    state = np.zeros(1 << sites, dtype=np.complex128)
    state[index] = 1
    return state


def block_product_energy(delta: float, state: NDArray[np.complex128]) -> float:
    """Energy density of the infinite product of identical finite blocks."""
    vector = np.asarray(state, dtype=np.complex128).reshape(-1)
    sites = int(round(float(np.log2(vector.size))))
    if sites < 2 or vector.size != 1 << sites:
        raise ValueError("state must describe at least two qubits")
    norm = float(np.vdot(vector, vector).real)
    if norm <= 0:
        raise ValueError("state has zero norm")
    vector = vector / np.sqrt(norm)
    internal = float(
        np.vdot(vector, finite_xxz(delta, sites, periodic=False) @ vector).real
    )
    rho_last = reduced_density(vector, (sites - 1,), sites)
    rho_first = reduced_density(vector, (0,), sites)
    boundary_rho = np.kron(rho_last, rho_first)
    boundary = float(np.trace(local_xxz(delta) @ boundary_rho).real)
    return (internal + boundary) / sites


def optimize_block_state(delta: float, sites: int) -> UpperCandidate:
    """Use the normalized open-chain ground state as an explicit block ansatz."""
    if sites < 2:
        raise ValueError("sites must be at least 2")
    if sites >= 9:
        h_open_sparse = finite_xxz_sparse(delta, sites, periodic=False)
        eigenvalues, eigenvectors = eigsh(
            h_open_sparse, k=1, which="SA", tol=1e-12
        )
        state = np.asarray(eigenvectors[:, 0], dtype=np.complex128)
        internal = float(eigenvalues[0])
    else:
        h_open = finite_xxz(delta, sites, periodic=False)
        eigenvalues, eigenvectors = np.linalg.eigh(h_open)
        state = np.asarray(eigenvectors[:, 0], dtype=np.complex128)
        internal = float(eigenvalues[0])
    state /= np.linalg.norm(state)
    rho_last = reduced_density(state, (sites - 1,), sites)
    rho_first = reduced_density(state, (0,), sites)
    boundary = float(
        np.trace(local_xxz(delta) @ np.kron(rho_last, rho_first)).real
    )
    return UpperCandidate(
        delta=float(delta),
        sites=sites,
        raw_upper=(internal + boundary) / sites,
        state=state,
        normalization_residual=abs(float(np.vdot(state, state).real) - 1.0),
        internal_energy=internal,
        boundary_energy=boundary,
    )


def repeated_supercell_energy(
    delta: float, state: NDArray[np.complex128], repetitions: int
) -> float:
    """Directly contract a finite product of blocks with open outer edges.

    The returned value includes all internal block bonds and all inter-block
    bonds, divided by the number of blocks. It therefore approaches the
    per-block infinite repeated-state energy as repetitions grows.
    """
    if repetitions < 2:
        raise ValueError("repetitions must be at least 2")
    vector = np.asarray(state, dtype=np.complex128).reshape(-1)
    sites = int(round(float(np.log2(vector.size))))
    vector = vector / np.linalg.norm(vector)
    internal = float(
        np.vdot(vector, finite_xxz(delta, sites, periodic=False) @ vector).real
    )
    rho_last = reduced_density(vector, (sites - 1,), sites)
    rho_first = reduced_density(vector, (0,), sites)
    boundary = float(
        np.trace(local_xxz(delta) @ np.kron(rho_last, rho_first)).real
    )
    return (repetitions * internal + (repetitions - 1) * boundary) / repetitions
