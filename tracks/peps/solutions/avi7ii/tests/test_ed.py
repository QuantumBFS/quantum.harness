import numpy as np
import pytest

from qh147.ed import _validated_symmetric, sector_eigenvalues
from qh147.model import tfim_dense
from qh147.symmetry_ed import IRREPS


@pytest.mark.parametrize("l", [2, 3])
def test_recovered_sector_union_matches_direct_dense_spectrum(l):
    direct = np.linalg.eigvalsh(tfim_dense(l, l, j=1.0, h=3.0))
    recovered = []
    for irrep in IRREPS:
        for parity in (1, -1):
            result = sector_eigenvalues(
                l,
                j=1.0,
                h=3.0,
                irrep=irrep,
                parity=parity,
            )
            recovered.append(
                np.repeat(result.eigenvalues, result.spectral_multiplicity)
            )
    assert np.allclose(
        np.sort(np.concatenate(recovered)),
        direct,
        atol=1e-10,
    )


def test_two_e_reflection_components_have_the_same_spectrum():
    plus = sector_eigenvalues(
        3,
        j=1.0,
        h=3.0,
        irrep="E",
        parity=1,
        e_reflection=1,
    )
    minus = sector_eigenvalues(
        3,
        j=1.0,
        h=3.0,
        irrep="E",
        parity=1,
        e_reflection=-1,
    )
    assert np.allclose(plus.eigenvalues, minus.eigenvalues, atol=1e-10)


def test_non_hermitian_projected_matrix_is_rejected():
    with pytest.raises(FloatingPointError, match="non-Hermitian"):
        _validated_symmetric(np.array([[0.0, 1.0], [0.0, 0.0]]))
