"""Number-conserving Fock-space construction for the tensor-square Hamiltonian."""

from __future__ import annotations

from itertools import combinations
from typing import Iterable, Sequence

import numpy as np
from scipy import sparse

from .algebra import kron_sum


def basis_states(n_modes: int, n_particles: int | None = None) -> np.ndarray:
    if n_modes < 1 or n_modes > 24:
        raise ValueError("n_modes must be between 1 and 24")
    if n_particles is None:
        return np.arange(1 << n_modes, dtype=np.uint32)
    if not 0 <= n_particles <= n_modes:
        raise ValueError("invalid particle number")
    states = []
    for occupied in combinations(range(n_modes), n_particles):
        state = sum(1 << mode for mode in occupied)
        states.append(state)
    return np.asarray(states, dtype=np.uint32)


def _annihilate(state: int, mode: int) -> tuple[int, int] | None:
    bit = 1 << mode
    if not state & bit:
        return None
    sign = -1 if (state & (bit - 1)).bit_count() % 2 else 1
    return state ^ bit, sign


def _create(state: int, mode: int) -> tuple[int, int] | None:
    bit = 1 << mode
    if state & bit:
        return None
    sign = -1 if (state & (bit - 1)).bit_count() % 2 else 1
    return state | bit, sign


def d_gamma(
    one_body: np.ndarray,
    basis: np.ndarray,
    index: dict[int, int] | None = None,
) -> sparse.csr_matrix:
    """Second quantization Σ_pq M_pq c†_p c_q."""
    matrix = np.asarray(one_body)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("one_body must be square")
    if index is None:
        index = {int(state): i for i, state in enumerate(basis)}
    rows: list[int] = []
    cols: list[int] = []
    data: list[complex] = []
    nonzero = np.argwhere(np.abs(matrix) > 1.0e-14)
    for col, encoded in enumerate(basis):
        state = int(encoded)
        for p, q in nonzero:
            removed = _annihilate(state, int(q))
            if removed is None:
                continue
            intermediate, sign1 = removed
            added = _create(intermediate, int(p))
            if added is None:
                continue
            final, sign2 = added
            row = index.get(final)
            if row is not None:
                rows.append(row)
                cols.append(col)
                data.append(matrix[p, q] * sign1 * sign2)
    dtype = np.result_type(matrix.dtype, np.float64)
    return sparse.coo_matrix(
        (np.asarray(data, dtype=dtype), (rows, cols)),
        shape=(len(basis), len(basis)),
    ).tocsr()


def normal_ordered_q_square(
    one_body: np.ndarray,
    basis: np.ndarray,
    index: dict[int, int] | None = None,
) -> sparse.csr_matrix:
    """Return dΓ(M²) - Σ M_ab M_cd c†_a c†_c c_b c_d."""
    matrix = np.asarray(one_body)
    if index is None:
        index = {int(state): i for i, state in enumerate(basis)}
    result = d_gamma(matrix @ matrix, basis, index).tolil()
    nonzero = [
        (int(p), int(q), matrix[p, q])
        for p, q in np.argwhere(np.abs(matrix) > 1.0e-14)
    ]
    rows: list[int] = []
    cols: list[int] = []
    data: list[complex] = []
    for col, encoded in enumerate(basis):
        state = int(encoded)
        for a, b, mab in nonzero:
            for c, d, mcd in nonzero:
                step1 = _annihilate(state, d)
                if step1 is None:
                    continue
                step2 = _annihilate(step1[0], b)
                if step2 is None:
                    continue
                step3 = _create(step2[0], c)
                if step3 is None:
                    continue
                step4 = _create(step3[0], a)
                if step4 is None:
                    continue
                row = index.get(step4[0])
                if row is not None:
                    sign = step1[1] * step2[1] * step3[1] * step4[1]
                    rows.append(row)
                    cols.append(col)
                    data.append(-mab * mcd * sign)
    two_body = sparse.coo_matrix(
        (
            np.asarray(data, dtype=np.result_type(matrix.dtype, np.float64)),
            (rows, cols),
        ),
        shape=(len(basis), len(basis)),
    ).tocsr()
    return result.tocsr() + two_body


def many_body_hamiltonian(
    m: int,
    k: np.ndarray,
    channels: Sequence[np.ndarray],
    couplings: Sequence[float],
    *,
    n_particles: int | None = None,
) -> tuple[sparse.csr_matrix, np.ndarray, list[sparse.csr_matrix]]:
    if len(channels) != len(couplings):
        raise ValueError("channels and couplings differ in length")
    if any(coupling < 0 for coupling in couplings):
        raise ValueError("tensor-square couplings must be nonnegative")
    basis = basis_states(m * m, n_particles)
    index = {int(state): i for i, state in enumerate(basis)}
    hamiltonian = d_gamma(kron_sum(k), basis, index).astype(np.float64)
    q_operators = []
    for channel, coupling in zip(channels, couplings, strict=True):
        q_operator = d_gamma(kron_sum(channel), basis, index).astype(np.float64)
        q_operators.append(q_operator)
        hamiltonian = hamiltonian - (coupling / (2.0 * m)) * (
            q_operator @ q_operator
        )
    return hamiltonian.tocsr(), basis, q_operators


def particle_number_operator(basis: Iterable[int]) -> sparse.csr_matrix:
    diagonal = np.fromiter(
        (int(state).bit_count() for state in basis), dtype=np.float64
    )
    return sparse.diags(diagonal, format="csr")


def max_abs(matrix: sparse.spmatrix) -> float:
    if matrix.nnz == 0:
        return 0.0
    return float(np.max(np.abs(matrix.data)))
