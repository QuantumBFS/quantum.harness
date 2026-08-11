from numpy.testing import assert_allclose

from floquet_if_manybody.config import ModelConfig
from floquet_if_manybody.models import ising_hamiltonian
from floquet_if_manybody.symmetry import n3_reflection_sectors, project, sector_residual


def test_n3_odd_sector_is_j_independent():
    odd, even = n3_reflection_sectors()
    h1 = project(ising_hamiltonian(ModelConfig(n=3, j=0.2)), odd)
    h2 = project(ising_hamiltonian(ModelConfig(n=3, j=2.0)), odd)
    assert_allclose(h1, h2)
    assert (odd.dimension, even.dimension) == (2, 6)
    assert sector_residual(ising_hamiltonian(ModelConfig(n=3)), odd) < 1e-13
    assert sector_residual(ising_hamiltonian(ModelConfig(n=3)), even) < 1e-13
