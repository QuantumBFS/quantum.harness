"""Anchor tests for pf/tfim2d.py — written before the implementation (TDD).

Anchors (all exact or first-principles):
  dimer          E0(h) = -sqrt(J^2 + 4h^2) exactly, all h
  classical      h = 0: E0 = -#bonds exactly (triangular, honeycomb, square, chain)
  strong field   h >> J: -h - z/(4h) <= E0/N <= -h  (variational upper bound is rigorous)
  parity         [H, P] = 0 with P = prod sigma_x (full basis, N=8)
  jordan-wigner  chain N=16 PBC: E0 vs closed-form JW sum, independent code path
  binder         h=0 cat state: U = 2/3 exactly; h >> J: U -> 0

Run: python3 tests/test_tfim2d.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pf import tfim2d


def test_dimer_exact():
    for h in (0.0, 0.3, 1.0, 3.0):
        e0 = tfim2d.ground_energy("dimer", 1, 1, h)
        assert abs(e0 + np.sqrt(1.0 + 4 * h * h)) < 1e-12, (h, e0)


def test_classical_limit():
    cases = [("triangular", 3, 3, 27), ("honeycomb", 2, 2, 12),
             ("square", 4, 4, 32), ("chain", 16, 1, 16)]
    for lattice, l1, l2, nbonds in cases:
        e0 = tfim2d.ground_energy(lattice, l1, l2, 0.0)
        assert abs(e0 + nbonds) < 1e-10, (lattice, e0, nbonds)


def test_strong_field():
    z = {"triangular": 6, "honeycomb": 3, "square": 4}
    h = 50.0
    for lattice, l1, l2 in [("triangular", 3, 3), ("honeycomb", 2, 2), ("square", 4, 4)]:
        n = tfim2d.n_sites(lattice, l1, l2)
        e = tfim2d.ground_energy(lattice, l1, l2, h) / n
        assert -h - z[lattice] / (4 * h) <= e <= -h + 1e-12, (lattice, e)


def test_parity_conservation():
    import scipy.sparse as sp
    n = 8
    mask = (1 << n) - 1
    perm = np.array([s ^ mask for s in range(1 << n)])
    p = sp.csr_matrix((np.ones(1 << n), (np.arange(1 << n), perm)), shape=(1 << n,) * 2)
    h_full = tfim2d.hamiltonian_full("honeycomb", 2, 2, 0.7)
    comm = h_full @ p - p @ h_full
    assert abs(comm).max() < 1e-12


def test_chain_jordan_wigner():
    n = 16
    for h in (0.5, 1.0, 2.0):
        k = np.array([(2 * j - 1) * np.pi / n for j in range(1, n // 2 + 1)])
        e_jw = -np.sum(2 * np.sqrt(1 + h * h - 2 * h * np.cos(k)))
        e0 = tfim2d.ground_energy("chain", n, 1, h)
        assert abs(e0 - e_jw) < 1e-10, (h, e0, e_jw)


def test_binder_limits():
    u0, _ = tfim2d.binder("triangular", 3, 3, 0.0)
    assert abs(u0 - 2 / 3) < 1e-10, u0
    # h >> J: product state, m binomial -> U = 2/(3N) exactly (N=9: 0.074)
    n = 9
    u_hi, _ = tfim2d.binder("triangular", 3, 3, 50.0)
    assert abs(u_hi - 2 / (3 * n)) < 0.02, u_hi


if __name__ == "__main__":
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        fn()
        print(f"[pass] {name}")
    print("all anchors green")
