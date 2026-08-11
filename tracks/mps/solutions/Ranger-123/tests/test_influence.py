import numpy as np
from numpy.testing import assert_allclose

from floquet_if_manybody.config import BathConfig
from floquet_if_manybody.influence import discretize_influence


def test_zero_coupling_has_zero_coefficients():
    coefficients = discretize_influence(BathConfig(alpha=0), 0.1, 3)
    assert_allclose(coefficients.values, 0, atol=1e-15)


def test_small_cell_diagonal_limit():
    bath = BathConfig(alpha=0.05, cutoff=2.5)
    dt = 1e-3
    coefficient = discretize_influence(bath, dt, 1).values[0]
    assert_allclose(coefficient, 0.5 * bath.alpha * bath.cutoff**2 * dt**2, rtol=2e-3)
    assert np.imag(coefficient) < 0
