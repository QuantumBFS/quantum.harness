from fractions import Fraction

import numpy as np
from scipy.linalg import expm, logm

from trottercert.algebra import PauliString, PauliSum, to_dense
from trottercert.formulas import (
    formula_log_series,
    formula_log_through_degree_three,
    leading_effective_error,
    strang_stages,
)
from trottercert.series import exponential_series, logarithm_series


def pauli(site: int, op: str) -> PauliSum:
    return PauliSum.term(PauliString({site: op}))


def test_exponential_and_logarithm_series_are_inverse() -> None:
    x = pauli(0, "X")
    series = exponential_series(x, Fraction(1, 3), 5)
    recovered = logarithm_series(series)
    assert recovered.coefficients[1] == x.scale(Fraction(1, 3))
    assert all(not recovered.coefficients[k] for k in range(2, 6))


def test_strang_log_has_only_odd_terms_through_fourth_order() -> None:
    fragments = (pauli(0, "X"), pauli(0, "Z"))
    coefficients = formula_log_series(strang_stages(fragments), order=4)
    assert not coefficients[2]
    assert not coefficients[4]


def test_leading_error_matches_small_time_matrix_logarithm() -> None:
    fragments = (pauli(0, "X"), pauli(0, "Z"))
    stages = strang_stages(fragments)
    e3 = leading_effective_error(stages)
    h = to_dense(fragments[0] + fragments[1], 1)
    predicted = to_dense(e3, 1)
    for time in (1e-2, 5e-3):
        product = np.eye(2, dtype=complex)
        for stage in stages:
            product = product @ expm(
                -1j * float(stage.coefficient) * time * to_dense(stage.fragment, 1)
            )
        effective = 1j * logm(product) / time
        residual = (effective - h) / (time**2)
        assert np.allclose(residual, predicted, atol=2e-4)


def test_graded_bch_matches_generic_series() -> None:
    stages = strang_stages((pauli(0, "X"), pauli(0, "Z")))
    generic = formula_log_series(stages, order=3)
    graded = formula_log_through_degree_three(stages)
    assert tuple(generic[1:4]) == graded
