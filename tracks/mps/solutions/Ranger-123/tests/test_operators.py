import numpy as np
from numpy.testing import assert_allclose

from floquet_if_manybody.operators import collective_operator, pauli, site_operator


def test_collective_z_eigenvalues():
    s = collective_operator("z", n=2, eta=0.5)
    assert_allclose(np.diag(s), [1, 0, 0, -1])


def test_site_algebra():
    x0 = site_operator("x", 0, 2)
    y0 = site_operator("y", 0, 2)
    z0 = site_operator("z", 0, 2)
    assert_allclose(x0 @ y0, 1j * z0)
    assert_allclose(pauli("x") @ pauli("x"), np.eye(2))
