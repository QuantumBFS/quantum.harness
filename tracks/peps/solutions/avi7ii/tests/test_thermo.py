import numpy as np
import pytest

from qh147.exact import thermal_from_spectrum
from qh147.model import tfim_dense
from qh147.thermo import evolve_exact_contraction


@pytest.mark.parametrize(("lx", "ly", "max_bond"), [(2, 2, 8), (3, 3, 8)])
def test_pepo_thermodynamics_agree_with_exact(lx, ly, max_bond):
    beta = 0.1
    hmat = tfim_dense(lx, ly, j=1.0, h=3.0)
    exact = thermal_from_spectrum(
        np.linalg.eigvalsh(hmat),
        beta=beta,
        nsites=lx * ly,
    )
    got = evolve_exact_contraction(
        lx,
        ly,
        j=1.0,
        h=3.0,
        beta=beta,
        delta_beta=0.025,
        max_bond=max_bond,
    )
    assert abs(got.f - exact.f) < 3e-4
    assert abs(got.u - exact.u) < 3e-4
    assert abs(got.c - exact.c) < 3e-4


def test_beta_must_be_an_integer_number_of_steps():
    with pytest.raises(ValueError, match="integer multiple"):
        evolve_exact_contraction(
            2,
            1,
            j=1.0,
            h=0.7,
            beta=0.1,
            delta_beta=0.03,
            max_bond=16,
        )
