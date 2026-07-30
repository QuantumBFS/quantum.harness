"""Small two-site iTEBD optimizer for candidate MPS/RG maps."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import expm

from .model import local_xxz
from .rg_relaxation import normalize_mps_tensor, uniform_mps_energy


@dataclass(frozen=True)
class ITEBDResult:
    tensor: NDArray[np.complex128]
    energy: float
    bond_dimension: int
    discarded_weight: float


def _update_bond(
    left_gamma: NDArray[np.complex128],
    middle_lambda: NDArray[np.float64],
    right_gamma: NDArray[np.complex128],
    outer_lambda: NDArray[np.float64],
    gate: NDArray[np.complex128],
    max_bond: int,
) -> tuple[
    NDArray[np.complex128],
    NDArray[np.float64],
    NDArray[np.complex128],
    float,
]:
    bond = len(outer_lambda)
    theta = np.einsum(
        "a,asb,b,btc,c->astc",
        outer_lambda,
        left_gamma,
        middle_lambda,
        right_gamma,
        outer_lambda,
        optimize=True,
    )
    theta = np.einsum("uvst,astc->auvc", gate, theta, optimize=True)
    matrix = theta.reshape(2 * bond, 2 * bond)
    left, singular, right = np.linalg.svd(matrix, full_matrices=False)
    kept = min(max_bond, len(singular))
    discarded = float(np.sum(singular[kept:] ** 2))
    singular = singular[:kept]
    norm = float(np.linalg.norm(singular))
    if norm == 0:
        raise ArithmeticError("iTEBD produced a zero Schmidt spectrum")
    singular /= norm
    left = left[:, :kept].reshape(bond, 2, kept)
    right = right[:kept, :].reshape(kept, 2, bond)
    inverse_outer = np.zeros_like(outer_lambda)
    mask = outer_lambda > 1e-14
    inverse_outer[mask] = 1 / outer_lambda[mask]
    left_gamma_new = np.einsum("a,asb->asb", inverse_outer, left)
    right_gamma_new = np.einsum("btc,c->btc", right, inverse_outer)
    return left_gamma_new, singular, right_gamma_new, discarded


def alternating_to_uniform(
    gamma_a: NDArray[np.complex128],
    lambda_a: NDArray[np.float64],
    gamma_b: NDArray[np.complex128],
    lambda_b: NDArray[np.float64],
) -> NDArray[np.complex128]:
    """Encode an AB unit cell as a one-site uniform block-cyclic MPS."""
    bond = len(lambda_a)
    site_a = np.einsum("asb,b->asb", gamma_a, lambda_a)
    site_b = np.einsum("asb,b->asb", gamma_b, lambda_b)
    tensor = np.zeros((2 * bond, 2, 2 * bond), dtype=np.complex128)
    tensor[:bond, :, bond:] = site_a
    tensor[bond:, :, :bond] = site_b
    return normalize_mps_tensor(tensor)


def block_two_site_tensor(
    uniform_block_cyclic: NDArray[np.complex128],
) -> NDArray[np.complex128]:
    """Recover and contract the AB tensors into a four-level cell tensor."""
    total_bond, physical, _ = uniform_block_cyclic.shape
    if physical != 2 or total_bond % 2:
        raise ValueError("expected an even-bond qubit block-cyclic tensor")
    bond = total_bond // 2
    site_a = uniform_block_cyclic[:bond, :, bond:]
    site_b = uniform_block_cyclic[bond:, :, :bond]
    cell = np.empty((bond, 4, bond), dtype=np.complex128)
    for first in range(2):
        for second in range(2):
            cell[:, 2 * first + second, :] = (
                site_a[:, first, :] @ site_b[:, second, :]
            )
    return normalize_mps_tensor(cell)


def blocked_xxz_cell_operator(delta: float) -> NDArray[np.complex128]:
    """Two-cell operator whose expectation is energy per original site."""
    h = local_xxz(delta)
    identity = np.eye(2, dtype=np.complex128)
    within_first_cell = np.kron(h, np.eye(4, dtype=np.complex128))
    # Cell basis is (A0,B0,A1,B1); couple B0 to A1.
    between = np.kron(np.kron(identity, h), identity)
    return (within_first_cell + between) / 2


def optimize_itebd(
    delta: float,
    bond_dimension: int = 2,
    *,
    seed: int = 230,
    schedule: tuple[tuple[float, int], ...] = (
        (0.1, 100),
        (0.03, 200),
        (0.01, 300),
        (0.003, 400),
        (0.001, 500),
    ),
) -> ITEBDResult:
    """Optimize an AB MPS and return its one-site block-cyclic tensor."""
    if bond_dimension < 1:
        raise ValueError("bond dimension must be positive")
    rng = np.random.default_rng(seed)
    gamma_a = rng.normal(size=(bond_dimension, 2, bond_dimension)).astype(
        np.complex128
    )
    gamma_b = rng.normal(size=(bond_dimension, 2, bond_dimension)).astype(
        np.complex128
    )
    lambda_a = np.ones(bond_dimension) / np.sqrt(bond_dimension)
    lambda_b = np.ones(bond_dimension) / np.sqrt(bond_dimension)
    discarded_total = 0.0
    for step, iterations in schedule:
        gate = expm(-step * local_xxz(delta)).reshape(2, 2, 2, 2)
        for _ in range(iterations):
            gamma_a, lambda_a, gamma_b, discarded = _update_bond(
                gamma_a,
                lambda_a,
                gamma_b,
                lambda_b,
                gate,
                bond_dimension,
            )
            discarded_total += discarded
            gamma_b, lambda_b, gamma_a, discarded = _update_bond(
                gamma_b,
                lambda_b,
                gamma_a,
                lambda_a,
                gate,
                bond_dimension,
            )
            discarded_total += discarded
    tensor = alternating_to_uniform(
        gamma_a, lambda_a, gamma_b, lambda_b
    )
    energy = uniform_mps_energy(tensor, delta)
    return ITEBDResult(
        tensor=tensor,
        energy=energy,
        bond_dimension=2 * bond_dimension,
        discarded_weight=discarded_total,
    )
