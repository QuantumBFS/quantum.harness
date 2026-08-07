from __future__ import annotations

import math

import numpy as np

from benchmark_v0.fock_ed import (
    apply_annihilation,
    apply_creation,
    apply_two_body,
    fixed_m_basis,
    full_basis,
    hamiltonian_matrix,
    l_squared_matrix,
    total_m,
)


def test_n6_two_q15_full_basis_has_8008_determinants() -> None:
    assert len(full_basis(n_electrons=6, two_q=15)) == math.comb(16, 6)


def test_fixed_m_basis_contains_only_requested_sector() -> None:
    basis = fixed_m_basis(n_electrons=3, two_q=5, target_m=1.5)

    assert basis
    assert all(total_m(state, two_q=5) == 1.5 for state in basis)


def test_creation_and_annihilation_use_occupied_lower_orbital_parity() -> None:
    state = (1 << 0) | (1 << 2)

    assert apply_annihilation(state, 2) == (1 << 0, -1)
    assert apply_creation(1 << 0, 1) == ((1 << 0) | (1 << 1), -1)
    assert apply_annihilation(state, 1) is None
    assert apply_creation(state, 2) is None


def test_two_body_operator_matches_ordered_slater_pair_convention() -> None:
    source = (1 << 0) | (1 << 2)
    target = (1 << 1) | (1 << 3)

    assert apply_two_body(source, a=1, b=3, c=0, d=2) == (target, 1)
    assert apply_two_body(source, a=3, b=1, c=0, d=2) == (target, -1)


def test_two_particle_hamiltonian_equals_ordered_pair_matrix() -> None:
    basis = full_basis(n_electrons=2, two_q=3)
    pairs = tuple((a, b) for a in range(4) for b in range(a + 1, 4))
    pair_matrix = np.arange(36, dtype=float).reshape(6, 6)
    pair_matrix = pair_matrix + pair_matrix.T

    np.testing.assert_allclose(
        hamiltonian_matrix(basis, pairs, pair_matrix),
        pair_matrix,
    )


def test_one_particle_l_squared_is_q_times_q_plus_one() -> None:
    q = 1.5
    for target_m in (-1.5, -0.5, 0.5, 1.5):
        basis = fixed_m_basis(n_electrons=1, two_q=3, target_m=target_m)
        l_squared = l_squared_matrix(basis, two_q=3, target_m=target_m)
        np.testing.assert_allclose(l_squared, [[q * (q + 1.0)]], atol=1.0e-13)
