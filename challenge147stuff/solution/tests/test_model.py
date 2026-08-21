import numpy as np
from core.model import SZ, SX, tfim_bonds, z2_flip_invariant


def test_paulis_correct():
    assert np.allclose(SZ @ SZ, np.eye(2))
    assert np.allclose(SX @ SX, np.eye(2))
    assert np.allclose(SZ @ SX, -SX @ SZ)  # anticommute


def test_bonds_open_boundary_count():
    # open 3x3: horizontal bonds = Ly*(Lx-1)=3*2=6; vertical = (Ly-1)*Lx=2*3=6
    b = tfim_bonds(3, 3)
    assert len(b) == 12
    assert all(0 <= i < 9 and 0 <= j < 9 and i != j for i, j in b)
    # corner site 0 (x=0,y=0) bonds only to site 1 (right) and site 3 (down)
    nbrs = sorted([j if i == 0 else i for i, j in b if i == 0 or j == 0])
    assert nbrs == [1, 3]


def test_z2_invariant():
    assert z2_flip_invariant(tfim_bonds(4, 4)) is True
