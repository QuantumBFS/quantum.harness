from __future__ import annotations

from itertools import product

import sympy as sp

from oracle.exterior_candidates import candidate_card
from oracle.exterior_inverse_hs import (
    TRACE_CLEAN_EXACT5_ODDCYCLE_SEEDS,
    exact_history_weight,
    exact_taylor_trace,
    inverse_hs_from_card,
)


def test_trace_clean_exact5_cards_have_exact_hermitian_positive_hs_map() -> None:
    for seed in TRACE_CLEAN_EXACT5_ODDCYCLE_SEEDS:
        decomposition = inverse_hs_from_card(
            candidate_card(
                template="exact5-oddcycle-block-pair",
                seed=seed,
            )
        )
        first, second = decomposition.one_particle_branches
        first_fock, second_fock = decomposition.gaussian_branches

        assert decomposition.coefficient > 0
        assert second == first.T
        assert second_fock == first_fock.T
        assert decomposition.hamiltonian == decomposition.hamiltonian.T
        assert decomposition.minus_hamiltonian == (
            decomposition.coefficient * first_fock
            + decomposition.coefficient * second_fock
        )


def test_exact5_ct_expansion_matches_determinants_and_hamiltonian_taylor_trace() -> None:
    decomposition = inverse_hs_from_card(
        candidate_card(
            template="exact5-oddcycle-block-pair",
            seed=13,
        )
    )

    for order in range(5):
        taylor = exact_taylor_trace(decomposition, order)
        assert taylor.direct_trace == taylor.auxiliary_sum
        for word in product((0, 1), repeat=order):
            history = exact_history_weight(decomposition, word)
            assert history.fock_trace == history.determinant
            assert history.scalar_coefficient > 0
            assert history.total_weight >= sp.Integer(0)
