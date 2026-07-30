import numpy as np
import sympy as sp

from oracle.oddcycle_local_hs_exact import (
    diagonal_sign_gauge_audit,
    exact_positive_null_vector,
)


def test_exact_positive_null_vector_replays_over_rationals():
    matrix = sp.ImmutableMatrix([[1, -1], [2, -2]])

    weights = exact_positive_null_vector(matrix, np.array([0.5, 0.5]))

    assert weights == (sp.Rational(1, 2), sp.Rational(1, 2))
    assert matrix * sp.Matrix(weights) == sp.zeros(2, 1)


def test_positive_triangle_is_not_diagonal_gauge_stoquastic():
    hamiltonian = sp.ImmutableMatrix(
        [[0, 1, 1], [1, 0, 1], [1, 1, 0]]
    )

    audit = diagonal_sign_gauge_audit(hamiltonian)

    assert audit["status"] == "exact-gauge-frustrated"
    assert len(audit["conflict_cycle_zero_based"]) == 3
