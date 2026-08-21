import numpy as np

from qh147.exact import thermal_from_spectrum


def test_one_spin_matches_closed_form():
    beta, h = 0.7, 1.3
    point = thermal_from_spectrum(np.array([-h, h]), beta=beta, nsites=1)
    assert np.isclose(point.log_z, np.log(2 * np.cosh(beta * h)))
    assert np.isclose(point.u, -h * np.tanh(beta * h))
    assert np.isclose(point.c, (beta * h) ** 2 / np.cosh(beta * h) ** 2)
