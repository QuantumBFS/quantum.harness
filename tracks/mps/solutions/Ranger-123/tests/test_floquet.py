import numpy as np
from numpy.testing import assert_allclose
from scipy.linalg import expm

from floquet_if_manybody.floquet import solve_floquet


def test_static_floquet_matches_matrix_exponential():
    h = np.array([[0.2, 0.3], [0.3, -0.2]], dtype=complex)
    period = 1.7
    solution = solve_floquet(lambda _time: h, period, 32)
    assert_allclose(solution.propagator, expm(-1j * h * period), atol=1e-13)
    assert solution.unitarity_residual < 1e-13
    assert solution.eigen_residual < 1e-12
    assert np.all(solution.quasienergies >= -np.pi / period)
    assert np.all(solution.quasienergies < np.pi / period)


def test_midpoint_rule_converges_quadratically():
    period = 2 * np.pi

    def h(t):
        return np.array([[0.4, 0.2 * np.cos(t)], [0.2 * np.cos(t), -0.4]])

    reference = solve_floquet(h, period, 4096).propagator
    errors = [
        np.linalg.norm(solve_floquet(h, period, steps).propagator - reference)
        for steps in (32, 64)
    ]
    assert errors[0] / errors[1] > 3.8
