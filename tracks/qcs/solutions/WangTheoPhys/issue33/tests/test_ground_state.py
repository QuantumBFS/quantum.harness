import numpy as np
import pytest

from vqetape.ground_state import (
    tfim_bdg_spectrum,
    tfim_ground_energy,
)
from vqetape.spec import TFIMVQESpec
from vqetape.tfim_mpo import dense_tfim_hamiltonian


@pytest.mark.parametrize("nqubits", range(2, 8))
@pytest.mark.parametrize(
    ("coupling", "field"),
    [(1.0, 1.0), (0.7, 0.3), (-0.4, 1.2)],
)
def test_bdg_ground_energy_matches_dense_diagonalization(
    nqubits,
    coupling,
    field,
):
    spec = TFIMVQESpec(
        nqubits=nqubits,
        depth=1,
        coupling=coupling,
        field=field,
    )
    expected = float(
        np.linalg.eigvalsh(
            np.asarray(dense_tfim_hamiltonian(spec))
        )[0]
    )

    assert tfim_ground_energy(spec) == pytest.approx(
        expected,
        abs=2e-5,
    )


def test_bdg_spectrum_has_particle_hole_pairs():
    spec = TFIMVQESpec(
        nqubits=7,
        depth=1,
        coupling=0.8,
        field=0.6,
    )
    spectrum = tfim_bdg_spectrum(spec)

    assert spectrum.shape == (2 * spec.nqubits,)
    np.testing.assert_allclose(
        spectrum,
        -spectrum[::-1],
        rtol=1e-12,
        atol=1e-12,
    )
