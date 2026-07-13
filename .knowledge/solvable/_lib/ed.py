"""Brute-force sparse ED cross-check tools (spins via kron, fermions via JW)."""
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh

_PX = sp.csr_matrix(np.array([[0, 1], [1, 0]], complex))
_PY = sp.csr_matrix(np.array([[0, -1j], [1j, 0]], complex))
_PZ = sp.csr_matrix(np.array([[1, 0], [0, -1]], complex))
_ID = sp.identity(2, dtype=complex, format="csr")


def _site_op(op, i, L):
    mats = [_ID] * L
    mats[i] = op
    out = mats[0]
    for m in mats[1:]:
        out = sp.kron(out, m, format="csr")
    return out


def spin_ops(L):
    """S = sigma/2 operators, lists indexed by site."""
    sx = [_site_op(_PX, i, L) * 0.5 for i in range(L)]
    sy = [_site_op(_PY, i, L) * 0.5 for i in range(L)]
    sz = [_site_op(_PZ, i, L) * 0.5 for i in range(L)]
    return sx, sy, sz


def pauli_ops(L):
    return ([_site_op(_PX, i, L) for i in range(L)],
            [_site_op(_PY, i, L) for i in range(L)],
            [_site_op(_PZ, i, L) for i in range(L)])


def fermion_ops(L):
    """Jordan–Wigner spinless fermion annihilation/creation operators."""
    sm = sp.csr_matrix(np.array([[0, 1], [0, 0]], complex))  # |0><1|
    c = []
    for i in range(L):
        mats = [_PZ] * i + [sm] + [_ID] * (L - i - 1)
        out = mats[0]
        for m in mats[1:]:
            out = sp.kron(out, m, format="csr")
        c.append(out)
    return c, [op.conj().T.tocsr() for op in c]


def _eigs(H, k):
    if H.shape[0] <= 4096:
        return np.sort(np.linalg.eigvalsh(H.toarray()))[:k]
    return np.sort(eigsh(H, k=k, which="SA", return_eigenvectors=False))


def ground_energy(H, k=1):
    return float(_eigs(H, max(k, 1))[0])


def ground_states(H, tol=1e-10):
    ev = _eigs(H, min(H.shape[0], 16))
    return int(np.sum(ev - ev[0] < tol))


def gap(H):
    ev = _eigs(H, min(H.shape[0], 16))
    above = ev[ev - ev[0] > 1e-10]
    return float(above[0] - ev[0]) if len(above) else 0.0
