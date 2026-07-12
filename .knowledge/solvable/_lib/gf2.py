"""GF(2) linear algebra for stabilizer codes."""
import numpy as np


def rank(M):
    M = np.array(M, dtype=np.uint8) % 2
    r = 0
    for col in range(M.shape[1]):
        piv = next((i for i in range(r, M.shape[0]) if M[i, col]), None)
        if piv is None:
            continue
        M[[r, piv]] = M[[piv, r]]
        M[(M[:, col] == 1) & (np.arange(M.shape[0]) != r)] ^= M[r]
        r += 1
    return r


def commute(a, b):
    """Symplectic product of binary rows a=(x|z), b=(x'|z'); True iff commuting."""
    n = len(a) // 2
    return (int(np.dot(a[:n], b[n:]) + np.dot(a[n:], b[:n])) % 2) == 0


def stabilizer_gsd_log2(stabilizers, n_qubits):
    """log2 GSD = n - rank for independent-generator counting."""
    M = np.array(stabilizers, dtype=np.uint8)
    assert M.shape[1] == 2 * n_qubits
    for i in range(len(M)):
        for j in range(i + 1, len(M)):
            assert commute(M[i], M[j]), f"stabilizers {i},{j} do not commute"
    return n_qubits - rank(M)
