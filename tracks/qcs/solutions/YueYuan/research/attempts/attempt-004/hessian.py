from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config import require_jax
from dynamics import gate_infidelity


jax, jnp = require_jax()


@dataclass(frozen=True)
class EigenspaceResult:
    values: np.ndarray
    vectors: np.ndarray


def dense_hessian(system, theta: np.ndarray) -> np.ndarray:
    loss_fn = lambda candidate: gate_infidelity(candidate, system)
    hess = jax.hessian(loss_fn)(jnp.asarray(theta, dtype=jnp.float64))
    return np.asarray(0.5 * (hess + hess.T), dtype=float)


def hessian_vector_product(system, theta: np.ndarray, vector: np.ndarray) -> np.ndarray:
    loss_fn = lambda candidate: gate_infidelity(candidate, system)
    theta_j = jnp.asarray(theta, dtype=jnp.float64)
    vector_j = jnp.asarray(vector, dtype=jnp.float64)
    _, hvp = jax.jvp(jax.grad(loss_fn), (theta_j,), (vector_j,))
    return np.asarray(hvp, dtype=float)


def leading_eigenspace(hess: np.ndarray, k: int) -> EigenspaceResult:
    hess = np.asarray(hess, dtype=float)
    if k < 0 or k > hess.shape[0]:
        raise ValueError("k must be between 0 and the Hessian dimension")
    if k == 0:
        return EigenspaceResult(np.zeros(0), np.zeros((hess.shape[0], 0)))
    values, vectors = np.linalg.eigh(hess)
    order = np.argsort(np.abs(values))[::-1][:k]
    return EigenspaceResult(values=values[order], vectors=vectors[:, order])


def effective_rank(eigenvalues: np.ndarray, threshold: float = 1e-8) -> int:
    values = np.asarray(eigenvalues, dtype=float)
    return int(np.sum(np.abs(values) > threshold))


def curvature_fraction(eigenvalues: np.ndarray, k: int) -> float:
    values = np.sort(np.abs(np.asarray(eigenvalues, dtype=float)))[::-1]
    total = float(np.sum(values))
    if total <= 0.0 or k <= 0:
        return 0.0
    return min(1.0, float(np.sum(values[:k])) / total)


def min_k_for_curvature(eigenvalues: np.ndarray, fraction: float) -> int:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between 0 and 1")
    values = np.sort(np.abs(np.asarray(eigenvalues, dtype=float)))[::-1]
    total = float(np.sum(values))
    if total <= 0.0 or fraction <= 0.0:
        return 0
    cumulative = np.cumsum(values) / total
    return int(np.searchsorted(cumulative, fraction, side="left") + 1)
