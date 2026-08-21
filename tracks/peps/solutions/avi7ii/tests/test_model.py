import numpy as np

from qh147.model import global_spin_flip, obc_bonds, tfim_dense


def test_2x2_has_four_open_boundary_bonds():
    assert obc_bonds(2, 2) == ((0, 2), (1, 3), (0, 1), (2, 3))


def test_h_zero_2x2_ground_energy_uses_pauli_convention():
    evals = np.linalg.eigvalsh(tfim_dense(2, 2, j=1.0, h=0.0))
    assert np.isclose(evals[0], -4.0)


def test_tfim_commutes_with_global_z2_flip():
    hmat = tfim_dense(2, 2, j=1.0, h=3.0)
    parity = global_spin_flip(4)
    assert np.linalg.norm(hmat @ parity - parity @ hmat) < 1e-12
