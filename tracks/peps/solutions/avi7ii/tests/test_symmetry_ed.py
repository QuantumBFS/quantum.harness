import numpy as np
import pytest

from qh147.model import tfim_dense
from qh147.symmetry_ed import IRREPS, d4_elements, sector_basis, state_action


def test_d4_actions_are_unique_symmetries_on_2x2_and_3x3():
    for l in (2, 3):
        elements = d4_elements(l)
        assert len(elements) == 8
        assert len({element.permutation for element in elements}) == 8
        hmat = tfim_dense(l, l, j=1.0, h=3.0)
        for element in elements:
            mapping = np.array([
                state_action(state, element.permutation)
                for state in range(hmat.shape[0])
            ])
            assert np.allclose(hmat[np.ix_(mapping, mapping)], hmat, atol=1e-12)


@pytest.mark.parametrize("l", [2, 3])
def test_sector_bases_are_orthonormal_disjoint_and_complete(l):
    blocks = [
        sector_basis(l, irrep, parity)
        for irrep in IRREPS
        for parity in (1, -1)
    ]
    for block in blocks:
        gram = (block.q.T @ block.q).toarray()
        assert np.allclose(gram, np.eye(block.q.shape[1]), atol=1e-12)
        assert block.recovered_dimension == block.q.shape[1] * block.spectral_multiplicity
    assert sum(block.recovered_dimension for block in blocks) == 1 << (l * l)
    for index, left in enumerate(blocks):
        for right in blocks[index + 1:]:
            assert np.linalg.norm((left.q.T @ right.q).toarray()) < 1e-12


def test_e_uses_one_reflection_component_with_multiplicity_two():
    plus = sector_basis(3, "E", 1, e_reflection=1)
    minus = sector_basis(3, "E", 1, e_reflection=-1)
    assert plus.spectral_multiplicity == minus.spectral_multiplicity == 2
    assert plus.q.shape == minus.q.shape
    assert np.linalg.norm((plus.q.T @ minus.q).toarray()) < 1e-12
