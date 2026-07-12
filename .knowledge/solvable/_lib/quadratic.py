"""Exact diagonalization of quadratic fermion Hamiltonians (BdG)."""
import numpy as np


def _bdg_matrix(A, B):
    A = np.asarray(A, dtype=complex)
    B = np.asarray(B, dtype=complex)
    assert np.allclose(A, A.conj().T), "A must be Hermitian"
    assert np.allclose(B, -B.T), "B must be antisymmetric"
    return np.block([[A, B], [-B.conj(), -A.conj()]])


def bdg_energies(A, B):
    """Non-negative single-particle energies, ascending."""
    ev = np.linalg.eigvalsh(_bdg_matrix(A, B))
    n = len(ev) // 2
    return np.sort(ev)[n:]  # upper half = non-negative branch


def bdg_ground_energy(A, B):
    """E_GS = 1/2 tr A - 1/2 sum_m eps_m for H = A c†c + (B c†c† + h.c.)/2."""
    eps = bdg_energies(A, B)
    return 0.5 * float(np.real(np.trace(A))) - 0.5 * float(eps.sum())
