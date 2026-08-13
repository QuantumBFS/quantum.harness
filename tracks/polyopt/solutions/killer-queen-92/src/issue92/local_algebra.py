"""Exact one-site algebra for occupation-truncated bosons."""

from __future__ import annotations

import numpy as np


def local_operators(nmax: int) -> dict[str, np.ndarray]:
    """Return exact matrices for a bosonic site with occupations 0,...,nmax."""
    if nmax < 1:
        raise ValueError("nmax must be at least one")
    dim = nmax + 1
    annihilation = np.zeros((dim, dim), dtype=np.complex128)
    for occupation in range(1, dim):
        annihilation[occupation - 1, occupation] = np.sqrt(occupation)
    creation = annihilation.conj().T
    number = np.diag(np.arange(dim, dtype=float)).astype(np.complex128)
    identity = np.eye(dim, dtype=np.complex128)
    top_projector = np.zeros_like(identity)
    top_projector[-1, -1] = 1.0
    fluctuation = (number - identity) @ (number - identity)
    interaction = 0.5 * number @ (number - identity)
    return {
        "b": annihilation,
        "bdag": creation,
        "n": number,
        "identity": identity,
        "top_projector": top_projector,
        "fluctuation": fluctuation,
        "interaction": interaction,
    }


def atomic_energies(nmax: int, interaction: float = 1.0, mu: float = 0.5) -> np.ndarray:
    """Eigenvalues U*n*(n-1)/2 - mu*n of the one-site Hamiltonian."""
    occupation = np.arange(nmax + 1, dtype=float)
    return 0.5 * interaction * occupation * (occupation - 1.0) - mu * occupation


def cutoff_commutator_error(nmax: int) -> float:
    """Residual of [b,b†] = I - (nmax+1)|nmax><nmax|."""
    operators = local_operators(nmax)
    lhs = operators["b"] @ operators["bdag"] - operators["bdag"] @ operators["b"]
    rhs = operators["identity"] - (nmax + 1) * operators["top_projector"]
    return float(np.linalg.norm(lhs - rhs, ord=np.inf))
