from __future__ import annotations

import numpy as np
import pytest
from scipy.linalg import expm

from tensor_square.algebra import (
    relative_error,
    tensor_square_weight_direct,
    tensor_square_weight_eigenvalues,
    tensor_square_weight_factorized,
)


def test_golden_nonnormal_triangular_case() -> None:
    x = np.array(
        [
            [0.5, 0.4, -0.2],
            [0.0, -0.25, 0.3],
            [0.0, 0.0, 2.0],
        ]
    )
    expected = 5.084228515625
    assert tensor_square_weight_direct(x) == pytest.approx(expected, rel=2e-14)
    assert tensor_square_weight_factorized(x) == pytest.approx(expected, rel=2e-14)
    assert tensor_square_weight_eigenvalues(x) == pytest.approx(
        expected, rel=2e-14
    )


@pytest.mark.parametrize("m", [2, 3, 4])
def test_random_noncommuting_slice_histories(m: int) -> None:
    rng = np.random.default_rng(9103 + m)
    for _ in range(12):
        x = np.eye(m)
        for _slice in range(5):
            generator = rng.normal(scale=0.35, size=(m, m))
            x = expm(generator) @ x
        direct = tensor_square_weight_direct(x)
        factorized = tensor_square_weight_factorized(x)
        eigenvalue = tensor_square_weight_eigenvalues(x)
        assert direct >= -2e-10 * max(1.0, abs(direct))
        assert relative_error(factorized, direct) < 3e-9
        assert relative_error(eigenvalue, direct) < 3e-9


def test_exact_and_near_zero_weights_are_not_negative() -> None:
    exact_zero = np.diag([2.0, -0.5])
    near_zero = np.diag([2.0, -0.5 + 1.0e-7])
    assert abs(tensor_square_weight_direct(exact_zero)) < 1e-25
    for evaluator in (
        tensor_square_weight_direct,
        tensor_square_weight_factorized,
        tensor_square_weight_eigenvalues,
    ):
        assert evaluator(near_zero) >= -1e-24
