import numpy as np
from numpy.testing import assert_allclose

from floquet_if_manybody.config import ModelConfig
from floquet_if_manybody.models import ising_hamiltonian
from floquet_if_manybody.spectra import diagonalize
from floquet_if_manybody.symmetry import n3_reflection_sectors, project


def test_n3_odd_gap_is_single_spin_gap():
    odd, _ = n3_reflection_sectors()
    for j in [0, 0.5, 2.0]:
        cfg = ModelConfig(n=3, j=j, omega=1)
        energies = diagonalize(project(ising_hamiltonian(cfg), odd)).energies
        assert_allclose(np.diff(energies), [1.0], atol=1e-12)


def test_n3_cat_gap_asymptotic_coefficient():
    _, even = n3_reflection_sectors()
    ratios = []
    for j in [4.0, 8.0, 16.0]:
        cfg = ModelConfig(n=3, j=j, omega=1)
        se = diagonalize(project(ising_hamiltonian(cfg), even))
        # The cat partner has opposite global spin-flip parity inside the even
        # reflection sector, so use the two lowest levels of this block.
        gap = se.energies[1] - se.energies[0]
        ratios.append(gap * 4 * j**2)
    assert abs(ratios[-1] - 1) < abs(ratios[0] - 1)
    np.testing.assert_allclose(ratios[-1], 1.0, rtol=0.02)
