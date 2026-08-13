from __future__ import annotations

import numpy as np
import sympy as sp

from oracle.exterior_candidates import candidate_card, exact_atoms_from_card
from oracle.exterior_seed61_positive_realization import (
    binary_words_upto,
    canonical_positive_closure_gate,
    exact_determinant_weight,
    exact_hankel,
    rank_mod_prime,
    transpose_reversal_word,
)


def test_seed61_small_hankel_has_exact_full_nonnegative_rank() -> None:
    atoms = exact_atoms_from_card(
        candidate_card(template="exact5-shear-loop-pair", seed=61)
    )
    words = binary_words_upto(2)
    hankel = exact_hankel(atoms, words, words)

    assert hankel.shape == (7, 7)
    assert all(entry > 0 for entry in hankel)
    assert rank_mod_prime(hankel, 2_147_483_647) == 7
    assert all(
        exact_determinant_weight(atoms, word)
        == exact_determinant_weight(
            atoms,
            transpose_reversal_word(word),
        )
        for word in binary_words_upto(4)
    )


def test_canonical_positive_closure_gate_reports_hit_and_failure() -> None:
    hankel = np.eye(2)
    hit = canonical_positive_closure_gate(
        hankel,
        np.asarray([[1.0, 2.0], [0.0, 1.0]]),
    )
    right_hit = canonical_positive_closure_gate(
        hankel,
        np.asarray([[1.0, 2.0], [0.0, 1.0]]),
        factorization="identity-right",
    )
    failure = canonical_positive_closure_gate(
        hankel,
        np.asarray([[1.0, -0.25], [0.0, 1.0]]),
    )

    assert hit["status"] == "canonical-positive-closure"
    assert right_hit["status"] == "canonical-positive-closure"
    assert hit["nnls_relative_residual"] <= 1.0e-12
    assert failure["status"] == "canonical-positive-closure-failed"
    assert failure["negative_transition_entries"] == 1
    assert failure["nnls_relative_residual"] > 0.0
