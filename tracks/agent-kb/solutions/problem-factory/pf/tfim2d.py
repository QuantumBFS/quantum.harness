"""Minimal ED for the 2D transverse-field Ising model, Pauli convention.

H = -J sum_<ij> sz_i sz_j - h sum_i sx_i,  J = 1.

Lattices on an L1 x L2 Bravais torus (PBC):
  chain      N = L1,     z = 2  (cross-validation against Jordan-Wigner)
  dimer      N = 2,      one bond (exact oracle: E0 = -sqrt(J^2 + 4h^2))
  square     N = L1*L2,  z = 4
  triangular N = L1*L2,  z = 6
  honeycomb  N = 2*L1*L2, z = 3

Diagonalization uses the even parity sector (P = prod sx = +1), which contains
the ground state for h > 0. Basis: one representative per {s, complement} pair.
"""

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def n_sites(lattice, l1, l2):
    if lattice == "chain":
        return l1
    if lattice == "dimer":
        return 2
    if lattice == "honeycomb":
        return 2 * l1 * l2
    return l1 * l2


def bonds(lattice, l1, l2):
    if lattice == "dimer":
        return [(0, 1)]
    if lattice == "chain":
        return [(i, (i + 1) % l1) for i in range(l1)]
    if lattice in ("square", "triangular"):
        b = []
        for y in range(l2):
            for x in range(l1):
                s = x + l1 * y
                b.append((s, (x + 1) % l1 + l1 * y))
                b.append((s, x + l1 * ((y + 1) % l2)))
                if lattice == "triangular":
                    b.append((s, (x + 1) % l1 + l1 * ((y + 1) % l2)))
        return b
    # honeycomb: A(x,y) = 2*(x+l1*y), B = A+1; A bonds to B(x,y), B(x-1,y), B(x,y-1)
    return [(2 * (x + l1 * y) + a_off, 2 * ((x - dx) % l1 + l1 * ((y - dy) % l2)) + 1)
            for y in range(l2) for x in range(l1)
            for a_off, dx, dy in [(0, 0, 0), (0, 1, 0), (0, 0, 1)]]


def hamiltonian(lattice, l1, l2, h, j=1.0):
    """Sparse H in the even parity sector. Returns (H, reps, n)."""
    n = n_sites(lattice, l1, l2)
    bnds = bonds(lattice, l1, l2)
    mask = (1 << n) - 1
    reps = [s for s in range(1 << n) if s < (s ^ mask)]
    idx = {s: i for i, s in enumerate(reps)}
    row, col, val = [], [], []
    for s in reps:
        diag = -j * sum(1.0 if (s >> i & 1) == (s >> k & 1) else -1.0 for i, k in bnds)
        row.append(idx[s]); col.append(idx[s]); val.append(diag)
        for i in range(n):
            t = s ^ (1 << i)
            row.append(idx[min(t, t ^ mask)]); col.append(idx[s]); val.append(-h)
    dim = len(reps)
    return sp.csr_matrix((val, (row, col)), shape=(dim, dim)), reps, n


def hamiltonian_full(lattice, l1, l2, h, j=1.0):
    """Sparse H in the full basis (symmetry checks only, N <= ~12)."""
    n = n_sites(lattice, l1, l2)
    bnds = bonds(lattice, l1, l2)
    row, col, val = [], [], []
    for s in range(1 << n):
        diag = -j * sum(1.0 if (s >> i & 1) == (s >> k & 1) else -1.0 for i, k in bnds)
        row.append(s); col.append(s); val.append(diag)
        for i in range(n):
            row.append(s ^ (1 << i)); col.append(s); val.append(-h)
    dim = 1 << n
    return sp.csr_matrix((val, (row, col)), shape=(dim, dim))


def ground_state(lattice, l1, l2, h, j=1.0):
    """(E0, psi, reps, n) in the even sector. Dense for dim <= 4096 else Lanczos."""
    H, reps, n = hamiltonian(lattice, l1, l2, h, j)
    if H.shape[0] <= 4096:
        w, v = np.linalg.eigh(H.toarray())
        return w[0], v[:, 0], reps, n
    w, v = spla.eigsh(H, k=1, which="SA")
    return w[0], v[:, 0], reps, n


def ground_energy(lattice, l1, l2, h, j=1.0):
    return ground_state(lattice, l1, l2, h, j)[0]


def binder(lattice, l1, l2, h, j=1.0):
    """Binder cumulant U = 1 - <m^4>/(3<m^2>^2), m = (1/N) sum sigma_z.

    m(s) and m(complement) differ only in sign, so <m^2>, <m^4> are diagonal
    in the parity-basis amplitudes. Returns (U, m2).
    """
    _, psi, reps, n = ground_state(lattice, l1, l2, h, j)
    p = psi * psi
    m = np.array([(2 * bin(s).count("1") - n) / n for s in reps])
    m2 = float(p @ m**2)
    m4 = float(p @ m**4)
    return 1.0 - m4 / (3 * m2 * m2), m2


def hc_from_crossings(lattice, shapes, h_grid):
    """h_c estimate per size pair from U_L(h) crossings. Returns (pairs, curves).

    pairs: list of (shape_a, shape_b, h_crossing); curves: {shape: [U(h)]}.
    """
    curves = {tuple(sh): [binder(lattice, sh[0], sh[1], h)[0] for h in h_grid]
              for sh in shapes}
    shapes = list(curves)
    pairs = []
    for a in range(len(shapes)):
        for b in range(a + 1, len(shapes)):
            diff = np.array(curves[shapes[a]]) - np.array(curves[shapes[b]])
            for i in range(len(h_grid) - 1):
                if diff[i] * diff[i + 1] < 0:
                    hc = h_grid[i] - diff[i] * (h_grid[i + 1] - h_grid[i]) / (diff[i + 1] - diff[i])
                    pairs.append((shapes[a], shapes[b], float(hc)))
    return pairs, {k: [float(u) for u in v] for k, v in curves.items()}
