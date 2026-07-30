import numpy as np

from floquet_if_manybody.config import ModelConfig
from floquet_if_manybody.models import coupling_operator, ising_hamiltonian
from floquet_if_manybody.symmetry import n4_reflection_sectors, sector_residual


def test_n4_reflection_dimensions_and_invariance() -> None:
    odd, even = n4_reflection_sectors()
    assert odd.dimension == 6
    assert even.dimension == 10
    model = ModelConfig(n=4, j=0.5)
    h0 = ising_hamiltonian(model)
    coupling = coupling_operator(model)
    for sector in (odd, even):
        assert sector_residual(h0, sector) < 1e-13
        assert sector_residual(coupling, sector) < 1e-13
        assert np.allclose(
            sector.isometry.conj().T @ sector.isometry,
            np.eye(sector.dimension),
        )
