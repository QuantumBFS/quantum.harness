"""Sparse many-electron Hamiltonians assembled from two-body pair tables."""

from __future__ import annotations

import numpy as np
from scipy import sparse

from .basis import FockBasis, apply_two_body
from .interactions import PairTable


def build_hamiltonian(basis: FockBasis, pair_table: PairTable) -> sparse.csr_matrix:
    """Build a two-body Hamiltonian in one fixed-Lz sector."""

    if basis.system.two_q != pair_table.two_q:
        raise ValueError("pair table and basis use different monopole flux")

    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    state_index = basis.index
    pair_lookup = {pair: i for i, pair in enumerate(pair_table.pairs)}

    for col, state in enumerate(basis.states):
        occupied = basis.occupied(state)
        occupied_pairs = ((c, d) for i, c in enumerate(occupied) for d in occupied[i + 1 :])
        for c, d in occupied_pairs:
            source_pair = pair_lookup[(c, d)]
            couplings = pair_table.matrix[:, source_pair]
            for target_pair in np.flatnonzero(np.abs(couplings) > 1e-14):
                a, b = pair_table.pairs[int(target_pair)]
                applied = apply_two_body(state, a, b, c, d)
                if applied is None:
                    continue
                new_state, sign = applied
                row = state_index.get(new_state)
                if row is None:
                    continue
                rows.append(row)
                cols.append(col)
                data.append(float(sign * couplings[target_pair]))

    matrix = sparse.coo_matrix(
        (data, (rows, cols)), shape=(basis.dimension, basis.dimension), dtype=np.float64
    ).tocsr()
    matrix.sum_duplicates()
    return matrix


def relative_hermiticity_error(matrix: sparse.spmatrix) -> float:
    """Return ||H-H^dagger||_F / max(||H||_F,1)."""

    difference = matrix - matrix.conjugate().transpose()
    numerator = float(sparse.linalg.norm(difference))
    denominator = max(float(sparse.linalg.norm(matrix)), 1.0)
    return numerator / denominator
