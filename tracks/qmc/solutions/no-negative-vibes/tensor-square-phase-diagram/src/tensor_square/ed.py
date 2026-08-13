"""Exact-diagonalization helpers for the approved tensor-square models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh

from .algebra import kron_sum
from .fock import basis_states, d_gamma


def edge_matrix(m: int, i: int, j: int) -> np.ndarray:
    matrix = np.zeros((m, m), dtype=np.float64)
    matrix[i, j] = matrix[j, i] = 1.0
    return matrix


def approved_channels(
    m: int, variant: str = "noncommuting"
) -> tuple[list[np.ndarray], list[int], list[int]]:
    if m == 3:
        a12 = edge_matrix(m, 0, 1)
        if variant == "commuting":
            second = np.diag([1.0, 1.0, -2.0]) / np.sqrt(3.0)
        elif variant == "noncommuting":
            second = edge_matrix(m, 1, 2)
        else:
            raise ValueError(f"unknown m=3 variant {variant}")
        return [a12, second], [0], [1]
    if m % 2 or m < 4:
        raise ValueError("scalable product-cycle geometry requires even m >= 4")
    channels = [edge_matrix(m, i, (i + 1) % m) for i in range(m)]
    group_a = [i for i in range(m) if i % 2 == 0]
    group_b = [i for i in range(m) if i % 2 == 1]
    return channels, group_a, group_b


@dataclass
class SectorOperators:
    m: int
    n_particles: int
    basis: np.ndarray
    kinetic: sparse.csr_matrix
    potential: sparse.csr_matrix
    interaction_a: sparse.csr_matrix
    interaction_b: sparse.csr_matrix
    q_a: sparse.csr_matrix
    q_b: sparse.csr_matrix
    q_group_a: tuple[sparse.csr_matrix, ...]
    q_group_b: tuple[sparse.csr_matrix, ...]
    nematic: sparse.csr_matrix
    group_a_size: int
    group_b_size: int

    @property
    def dimension(self) -> int:
        return len(self.basis)


def build_sector_operators(
    m: int, n_particles: int, variant: str = "noncommuting"
) -> SectorOperators:
    channels, group_a, group_b = approved_channels(m, variant)
    basis = basis_states(m * m, n_particles)
    index = {int(state): i for i, state in enumerate(basis)}
    adjacency = sum(channels, start=np.zeros((m, m)))
    kinetic = d_gamma(kron_sum(adjacency), basis, index).astype(np.float64)
    if m == 3:
        potential_pattern = np.array([-1.0, 0.0, 1.0])
    else:
        potential_pattern = np.zeros(m)
    potential = d_gamma(
        kron_sum(np.diag(potential_pattern)), basis, index
    ).astype(np.float64)
    q_ops = [
        d_gamma(kron_sum(channel), basis, index).astype(np.float64)
        for channel in channels
    ]
    shape = (len(basis), len(basis))
    interaction_a = sparse.csr_matrix(shape, dtype=np.float64)
    interaction_b = sparse.csr_matrix(shape, dtype=np.float64)
    for channel_index in group_a:
        interaction_a = interaction_a + (
            q_ops[channel_index] @ q_ops[channel_index]
        ) / (2.0 * m)
    for channel_index in group_b:
        interaction_b = interaction_b + (
            q_ops[channel_index] @ q_ops[channel_index]
        ) / (2.0 * m)
    q_a = sum(
        (q_ops[channel_index] for channel_index in group_a),
        start=sparse.csr_matrix(shape, dtype=np.float64),
    )
    q_b = sum(
        (q_ops[channel_index] for channel_index in group_b),
        start=sparse.csr_matrix(shape, dtype=np.float64),
    )
    if m == 3:
        weights = np.array([1.0, -2.0, 1.0])
    else:
        weights = np.array([1.0 if i % 2 == 0 else -1.0 for i in range(m)])
    nematic = d_gamma(kron_sum(np.diag(weights)), basis, index).astype(
        np.float64
    )
    return SectorOperators(
        m=m,
        n_particles=n_particles,
        basis=basis,
        kinetic=kinetic.tocsr(),
        potential=potential.tocsr(),
        interaction_a=interaction_a.tocsr(),
        interaction_b=interaction_b.tocsr(),
        q_a=q_a.tocsr(),
        q_b=q_b.tocsr(),
        q_group_a=tuple(q_ops[channel_index] for channel_index in group_a),
        q_group_b=tuple(q_ops[channel_index] for channel_index in group_b),
        nematic=nematic.tocsr(),
        group_a_size=len(group_a),
        group_b_size=len(group_b),
    )


def hamiltonian(
    operators: SectorOperators,
    t: float,
    g_a: float,
    g_b: float,
    v_asymmetry: float = 0.0,
) -> sparse.csr_matrix:
    return (
        -t * operators.kinetic
        + v_asymmetry * operators.potential
        - g_a * operators.interaction_a
        - g_b * operators.interaction_b
    ).tocsr()


def lowest_states(
    matrix: sparse.csr_matrix, *, seed: int = 0
) -> tuple[np.ndarray, np.ndarray, float]:
    dimension = matrix.shape[0]
    if dimension <= 1800:
        eigenvalues, eigenvectors = np.linalg.eigh(matrix.toarray())
        keep = min(8, dimension)
        values = eigenvalues[:keep]
        vectors = eigenvectors[:, :keep]
    else:
        rng = np.random.default_rng(seed)
        values, vectors = eigsh(
            matrix,
            k=min(8, dimension - 1),
            which="SA",
            v0=rng.normal(size=dimension),
            tol=2.0e-10,
            maxiter=12000,
        )
        order = np.argsort(values)
        values, vectors = values[order], vectors[:, order]
    residual = np.linalg.norm(matrix @ vectors[:, 0] - values[0] * vectors[:, 0])
    return values, vectors, float(residual)


def ground_observables(
    operators: SectorOperators, state: np.ndarray
) -> dict[str, float]:
    if state.ndim == 2:
        values = [
            ground_observables(operators, state[:, column])
            for column in range(state.shape[1])
        ]
        return {
            key: float(np.mean([value[key] for value in values]))
            for key in values[0]
        }
    modes = operators.m * operators.m
    qa_state = operators.q_a @ state
    qb_state = operators.q_b @ state
    qa2 = float(np.vdot(qa_state, qa_state).real) / (
        operators.group_a_size * modes
    )
    qb2 = float(np.vdot(qb_state, qb_state).real) / (
        operators.group_b_size * modes
    )
    cross = float(
        np.vdot(qa_state, qb_state).real + np.vdot(qb_state, qa_state).real
    ) / (2.0 * modes)
    commutator_total = 0.0
    for q_a_local in operators.q_group_a:
        for q_b_local in operators.q_group_b:
            commutator_state = 1j * (
                q_a_local @ (q_b_local @ state)
                - q_b_local @ (q_a_local @ state)
            )
            commutator_total += float(
                np.vdot(commutator_state, commutator_state).real
            )
    commutator_sq = commutator_total / (
        len(operators.q_group_a)
        * len(operators.q_group_b)
        * modes
        * modes
    )
    nematic_state = operators.nematic @ state
    nematic_sq = float(np.vdot(nematic_state, nematic_state).real) / (
        modes * modes
    )
    bond_state = qa_state + qb_state
    bond_sq = float(np.vdot(bond_state, bond_state).real) / modes
    balance = (qb2 - qa2) / max(1.0e-14, qb2 + qa2)
    return {
        "q_a_sq": qa2,
        "q_b_sq": qb2,
        "q_cross": cross,
        "channel_balance": balance,
        "commutator_sq": commutator_sq,
        "nematic_sq": nematic_sq,
        "bond_sq": bond_sq,
    }


def sector_result(
    operators: SectorOperators,
    *,
    t: float,
    g_a: float,
    g_b: float,
    v_asymmetry: float = 0.0,
    seed: int,
) -> dict[str, object]:
    matrix = hamiltonian(
        operators, t, g_a, g_b, v_asymmetry=v_asymmetry
    )
    values, vectors, residual = lowest_states(matrix, seed=seed)
    splittings = values - values[0]
    distinct = splittings[splittings > 2.0e-9]
    gap = float(distinct[0]) if len(distinct) else float("nan")
    multiplicity = int(np.sum(splittings <= 2.0e-9))
    ground_subspace = vectors[:, :multiplicity]
    return {
        "n_particles": operators.n_particles,
        "energy": float(values[0]),
        "sector_gap": gap,
        "ground_multiplicity": multiplicity,
        "state": vectors[:, 0],
        "subspace": ground_subspace,
        "residual": residual,
        **ground_observables(operators, ground_subspace),
    }


def charge_gap(sector_energies: Sequence[float], n_particles: int) -> float:
    if n_particles <= 0 or n_particles >= len(sector_energies) - 1:
        return float("nan")
    return float(
        sector_energies[n_particles + 1]
        + sector_energies[n_particles - 1]
        - 2.0 * sector_energies[n_particles]
    )
