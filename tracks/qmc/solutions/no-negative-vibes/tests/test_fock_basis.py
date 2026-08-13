from __future__ import annotations

import numpy as np
import pytest
import sympy as sp

from oracle.fock_basis import (
    annihilation_operator,
    creation_operator,
    exact_to_numpy,
    one_body_operator,
    parity_indices,
    quadratic_term,
)


def test_exact_creation_annihilation_operators_satisfy_car() -> None:
    modes = 3
    identity = sp.eye(1 << modes)
    annihilation = [annihilation_operator(modes, i) for i in range(modes)]
    creation = [creation_operator(modes, i) for i in range(modes)]

    for i in range(modes):
        for j in range(modes):
            expected = identity if i == j else sp.zeros(1 << modes)
            assert annihilation[i] * creation[j] + creation[j] * annihilation[i] == expected
            assert annihilation[i] * annihilation[j] + annihilation[j] * annihilation[i] == sp.zeros(1 << modes)


def test_jordan_wigner_sign_uses_lower_occupied_modes() -> None:
    operator = creation_operator(3, 2)
    source = 0b011
    target = 0b111
    assert operator[target, source] == 1

    operator = creation_operator(3, 1)
    source = 0b001
    target = 0b011
    assert operator[target, source] == -1


def test_quadratic_terms_preserve_parity() -> None:
    even, odd = parity_indices(4)
    for kind in ("hop", "pair_create", "pair_annihilate"):
        matrix = quadratic_term(4, kind, 0, 2)
        assert matrix.extract(even, odd) == sp.zeros(len(even), len(odd))
        assert matrix.extract(odd, even) == sp.zeros(len(odd), len(even))


def test_one_body_operator_matches_direct_sum_over_hops() -> None:
    matrix = sp.Matrix([[2, 3], [5, 7]])
    expected = (
        2 * quadratic_term(2, "hop", 0, 0)
        + 3 * quadratic_term(2, "hop", 0, 1)
        + 5 * quadratic_term(2, "hop", 1, 0)
        + 7 * quadratic_term(2, "hop", 1, 1)
    )
    assert one_body_operator(matrix) == expected
    assert exact_to_numpy(expected).dtype == np.float64


@pytest.mark.parametrize(("modes", "index"), [(0, 0), (2, -1), (2, 2)])
def test_invalid_mode_indices_are_rejected(modes: int, index: int) -> None:
    with pytest.raises(ValueError):
        annihilation_operator(modes, index)
