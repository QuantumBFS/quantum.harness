from numpy.testing import assert_allclose

from floquet_if_manybody.config import ModelConfig
from floquet_if_manybody.models import coupling_operator, ising_hamiltonian
from floquet_if_manybody.symmetry import n2_sectors, project, sector_residual


def test_n2_singlet_is_dark_and_invariant():
    singlet, triplet = n2_sectors()
    cfg = ModelConfig(n=2)
    assert (singlet.dimension, triplet.dimension) == (1, 3)
    assert_allclose(project(coupling_operator(cfg), singlet), 0, atol=1e-14)
    assert sector_residual(ising_hamiltonian(cfg), singlet) < 1e-13
    assert sector_residual(ising_hamiltonian(cfg), triplet) < 1e-13
