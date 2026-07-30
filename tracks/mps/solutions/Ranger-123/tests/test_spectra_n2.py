import numpy as np
from numpy.testing import assert_allclose

from floquet_if_manybody.config import ModelConfig
from floquet_if_manybody.models import coupling_operator, ising_hamiltonian
from floquet_if_manybody.spectra import diagonalize, transitions
from floquet_if_manybody.symmetry import n2_sectors, project


def test_n2_analytic_triplet_spectrum_and_weights():
    _, triplet = n2_sectors()
    omega = 1.0
    for j in [0.0, 0.25, 0.5, 1.0, 2.0]:
        cfg = ModelConfig(n=2, j=j, omega=omega)
        spectrum = diagonalize(project(ising_hamiltonian(cfg), triplet))
        e = np.sqrt(j**2 + omega**2)
        assert_allclose(spectrum.energies, [-e, -j, e], atol=1e-12)
        items = transitions(
            spectrum, spectrum, project(coupling_operator(cfg), triplet), threshold=1e-10
        )
        from_ground = sorted(
            [x for x in items if x.source == 0 and x.frequency > 0],
            key=lambda x: x.frequency,
        )
        assert_allclose([x.frequency for x in from_ground], [e - j], atol=1e-12)
        expected_low = 2 * cfg.eta**2 * (1 + j / e)
        assert_allclose(from_ground[0].weight, expected_low, atol=1e-12)
        high = [x for x in items if x.source == 1 and x.target == 2]
        expected_high = 2 * cfg.eta**2 * (1 - j / e)
        assert_allclose(high[0].frequency, e + j, atol=1e-12)
        assert_allclose(high[0].weight, expected_high, atol=1e-12)
