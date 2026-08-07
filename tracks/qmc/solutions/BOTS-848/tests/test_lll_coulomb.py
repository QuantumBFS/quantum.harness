from __future__ import annotations

import numpy as np

from benchmark_v0.lll_coulomb import (
    antisymmetrized_pair_matrix,
    coulomb_integrals,
    monopole_orbital_grid,
)


def test_monopole_lll_orbitals_are_orthonormal() -> None:
    grid = monopole_orbital_grid(two_q=3, n_theta=24, n_phi=32)
    overlap = np.einsum(
        "pa,p,pc->ac",
        grid.orbitals.conj(),
        grid.weights,
        grid.orbitals,
    )

    np.testing.assert_allclose(overlap, np.eye(4), atol=2.0e-13)


def test_coulomb_integrals_obey_hermiticity_and_m_conservation() -> None:
    integrals = coulomb_integrals(two_q=3, n_theta=24, n_phi=32)

    np.testing.assert_allclose(
        integrals,
        integrals.transpose(2, 3, 0, 1).conj(),
        atol=2.0e-12,
    )
    violating = [
        abs(integrals[a, b, c, d])
        for a in range(4)
        for b in range(4)
        for c in range(4)
        for d in range(4)
        if a + b != c + d
    ]
    assert max(violating) < 2.0e-12


def test_antisymmetrized_pair_interaction_is_hermitian() -> None:
    integrals = coulomb_integrals(two_q=3, n_theta=24, n_phi=32)
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)

    assert pairs == tuple((a, b) for a in range(4) for b in range(a + 1, 4))
    np.testing.assert_allclose(pair_matrix, pair_matrix.T.conj(), atol=2.0e-12)
