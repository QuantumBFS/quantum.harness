"""Minimal ED for the spin-1/2 XXZ+J2 chain with PBC.

H = sum_i (Sx_i Sx_j + Sy_i Sy_j + delta Sz_i Sz_j),  j = i+1
  + j2 * sum_i Sz_i Sz_{i+2}

Conventions (per .knowledge/models/xxz-chain): S = sigma/2, J = 1, AFM > 0.
convention="pauli" uses sigma instead of S (energies x4) — a deliberate
setup-error knob exercised by the demo's bad-setup card.
"""

import numpy as np
import scipy.sparse as sp


def hamiltonian(L, delta, j2, n_up=None, convention="spin"):
    """Sparse H in the n_up sector (n_up=None -> full basis). Sizes <= 12."""
    unit = 1.0 if convention == "pauli" else 0.5
    basis = [s for s in range(1 << L) if n_up is None or bin(s).count("1") == n_up]
    idx = {s: i for i, s in enumerate(basis)}
    row, col, val = [], [], []

    def sz(s, i):
        return unit if s >> i & 1 else -unit

    for s in basis:
        diag = 0.0
        for i in range(L):
            j, k = (i + 1) % L, (i + 2) % L
            diag += delta * sz(s, i) * sz(s, j) + j2 * sz(s, i) * sz(s, k)
            if (s >> i & 1) != (s >> j & 1):  # flip-flop S+S- + S-S+ on anti-aligned pair
                t = s ^ (1 << i) ^ (1 << j)
                if t in idx:
                    row.append(idx[s])
                    col.append(idx[t])
                    val.append(2 * unit**2)
        row.append(idx[s])
        col.append(idx[s])
        val.append(diag)
    return sp.csr_matrix((val, (row, col)), shape=(len(basis),) * 2)


def low_spectrum(L, delta, j2, convention="spin", n=2):
    """Lowest n eigenvalues in the Sz=0 sector."""
    H = hamiltonian(L, delta, j2, n_up=L // 2, convention=convention)
    return np.linalg.eigvalsh(H.toarray())[:n]


def sawtooth_hamiltonian(N, j2=2.0, j1=1.0, h=0.0, n_up=None, convention="spin"):
    """Sparse H for the sawtooth (delta) chain, PBC, isotropic Heisenberg.

    N sites = N/2 unit cells; base A_i = site 2i, apex B_i = site 2i+1.
    H = sum_i [ j1 A_i.A_{i+1} + j2 (A_i.B_i + B_i.A_{i+1}) ] - h sum S^z.
    Flat band at j2 = 2*j1 (eps = -4*j1, h_sat = 4*j1); Monti-Suto point j2 = j1.
    """
    unit = 1.0 if convention == "pauli" else 0.5
    basis = [s for s in range(1 << N) if n_up is None or bin(s).count("1") == n_up]
    idx = {s: i for i, s in enumerate(basis)}
    nc = N // 2
    bonds = [((2 * i) % N, (2 * i + 2) % N, j1) for i in range(nc)]
    bonds += [((2 * i) % N, (2 * i + 1) % N, j2) for i in range(nc)]
    bonds += [((2 * i + 1) % N, (2 * i + 2) % N, j2) for i in range(nc)]
    row, col, val = [], [], []

    def sz(s, i):
        return unit if s >> i & 1 else -unit

    for s in basis:
        diag = -h * sum(sz(s, i) for i in range(N))
        for i, j, J in bonds:
            diag += J * sz(s, i) * sz(s, j)
            if (s >> i & 1) != (s >> j & 1):  # flip-flop on anti-aligned pair
                t = s ^ (1 << i) ^ (1 << j)
                if t in idx:
                    row.append(idx[s])
                    col.append(idx[t])
                    val.append(J * 2 * unit**2)
        row.append(idx[s])
        col.append(idx[s])
        val.append(diag)
    return sp.csr_matrix((val, (row, col)), shape=(len(basis),) * 2)
