"""Unit tests for the snake-MPS primitives, validated against the dense
state-vector backend on small systems.

These pin the MPS contractions (norm, 1-site/2-site expectation values,
2-site and 1-site gate application) to the dense reference before the full
MPS METTS backend is built on top. If these pass, the MPS backend's
evolution and energy measurement are correct by construction.
"""
import numpy as np
import pytest

from metts_b.mps import MPS, svd_truncate
from metts_b.hamiltonian import (
    product_state_vector, build_hamiltonian, _bond_parity_split,
    trotter_evolve_dense, _apply_field_layer_dense,
)
from metts_b.bridge import SZ, SX, tfim_bonds, SquareLattice


# ---------------------------------------------------------------------------
# Helpers: build a non-trivial (entangled) MPS via a few Trotter steps from a
# product state, so the bond dim > 1 and the contractions are non-vacuous.
# ---------------------------------------------------------------------------

def _dense_psi_after_trotter(spins, Lx, Ly, h, beta, dtau):
    N = Lx * Ly
    psi = product_state_vector(spins, N)
    n = max(1, int(np.ceil((beta / 2.0) / dtau)))
    trotter_evolve_dense(psi, Lx, Ly, h, dtau, n)
    return psi


def _mps_from_dense(psi, Lx, Ly, chi=16):
    """Build an MPS in SNAKE order from a dense (physical-order) vector."""
    snake = SquareLattice(Lx, Ly).snake_index_map()
    return MPS.from_dense_vector(psi, chi=chi, snake=snake)


# ---------------------------------------------------------------------------
# svd_truncate
# ---------------------------------------------------------------------------

def test_svd_truncate_rank_and_weight():
    M = np.diag([3.0, 2.0, 1.0, 0.5, 0.001]).astype(float)
    U, s, Vh, disc, k = svd_truncate(M, chi=3, tol=0.0)
    assert k == 3
    assert len(s) == 3
    # discarded weight = fraction of Schmidt mass dropped = (0.5^2+0.001^2)/total
    tot = 9 + 4 + 1 + 0.25 + 0.001**2
    expect = (0.25 + 0.001**2) / tot
    assert abs(disc - expect) < 1e-9
    assert 0.0 <= disc <= 1.0


# ---------------------------------------------------------------------------
# norm2 and to_vector consistency
# ---------------------------------------------------------------------------

def test_mps_norm_matches_dense():
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    spins = np.array([1, -1, 1, -1], dtype=int)
    psi_dense = _dense_psi_after_trotter(spins, Lx, Ly, h, beta=0.4, dtau=0.05)
    mps = _mps_from_dense(psi_dense, Lx, Ly, chi=16)
    assert abs(mps.norm2() - np.vdot(psi_dense, psi_dense).real) < 1e-8
    # to_vector reconstructs the state in physical order
    assert np.allclose(mps.to_vector(), psi_dense, atol=1e-8)


# ---------------------------------------------------------------------------
# expectation values vs dense
# ---------------------------------------------------------------------------

def test_mps_1site_expectation_vs_dense():
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    spins = np.array([1, -1, 1, -1], dtype=int)
    psi = _dense_psi_after_trotter(spins, Lx, Ly, h, beta=0.4, dtau=0.05)
    mps = _mps_from_dense(psi, Lx, Ly, chi=16)
    snake = SquareLattice(Lx, Ly).snake_index_map()
    norm = np.vdot(psi, psi).real
    for pos in range(N):
        phys = int(snake[pos])                       # MPS site pos = physical site
        op = _dense_one_site_op(SZ, phys, N)
        dense_val = (np.vdot(psi, op @ psi) / norm).real
        mps_val = mps.expect_1site(pos, SZ)
        assert abs(dense_val - mps_val) < 1e-7, (pos, phys, dense_val, mps_val)


def test_mps_2site_expectation_vs_dense():
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    spins = np.array([1, -1, 1, -1], dtype=int)
    psi = _dense_psi_after_trotter(spins, Lx, Ly, h, beta=0.4, dtau=0.05)
    mps = _mps_from_dense(psi, Lx, Ly, chi=16)
    snake = SquareLattice(Lx, Ly).snake_index_map()
    norm = np.vdot(psi, psi).real
    # sz_i sz_j on MPS-ADJACENT site pairs (pos, pos+1); the corresponding
    # physical sites are (snake[pos], snake[pos+1]).
    szsz = np.kron(SZ, SZ)
    for pos in range(N - 1):
        pi, pj = int(snake[pos]), int(snake[pos + 1])
        op = _dense_two_site_op(szsz, pi, pj, N)
        dense_val = (np.vdot(psi, op @ psi) / norm).real
        mps_val = mps.expect_2site_adjacent(pos, szsz)
        assert abs(dense_val - mps_val) < 1e-7, (pos, pi, pj, dense_val, mps_val)


# ---------------------------------------------------------------------------
# gate application vs dense
# ---------------------------------------------------------------------------

def test_mps_2site_gate_vs_dense():
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    spins = np.array([1, -1, 1, -1], dtype=int)
    psi = _dense_psi_after_trotter(spins, Lx, Ly, h, beta=0.2, dtau=0.05)
    mps = _mps_from_dense(psi, Lx, Ly, chi=16)
    snake = SquareLattice(Lx, Ly).snake_index_map()
    # apply a bond gate e^{J dtau sz sz} (diagonal) on MPS-adjacent sites (1,2)
    dtau = 0.1
    gate = _bond_gate_zz(dtau)
    mps.apply_2site_gate(1, gate, direction="R")
    # dense equivalent: same gate on the physical sites snake[1], snake[2]
    phys_i, phys_j = int(snake[1]), int(snake[2])
    op = _dense_two_site_op(gate, phys_i, phys_j, N)
    psi2 = op @ psi
    assert np.allclose(mps.to_vector(), psi2, atol=1e-7)


def test_mps_1site_gate_vs_dense():
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    spins = np.array([1, -1, 1, -1], dtype=int)
    psi = _dense_psi_after_trotter(spins, Lx, Ly, h, beta=0.2, dtau=0.05)
    mps = _mps_from_dense(psi, Lx, Ly, chi=16)
    snake = SquareLattice(Lx, Ly).snake_index_map()
    theta = h * 0.05 / 2.0
    gate = _field_gate_sx(theta)
    mps.apply_1site_gate(2, gate)                    # MPS site 2 = physical snake[2]
    op = _dense_one_site_op(gate, int(snake[2]), N)
    psi2 = op @ psi
    assert np.allclose(mps.to_vector(), psi2, atol=1e-7)


# ---------------------------------------------------------------------------
# dense helpers used by the tests above
# ---------------------------------------------------------------------------

def _dense_one_site_op(op2, site, N):
    """Full 2^N operator = op2 at `site`, identity elsewhere, matching the
    product_state_vector bit convention (bit k = site N-1-k)."""
    import scipy.sparse as sp
    mats = []
    for i in range(N):
        mats.append(sp.csr_matrix(op2 if i == site else np.eye(2)))
    out = mats[0]
    for m in mats[1:]:
        out = sp.kron(out, m, format="csr")
    return out


def _dense_two_site_op(op4, i, j, N):
    """Full 2^N operator acting as the 4x4 ``op4`` on physical sites (i,j)
    (arbitrary, possibly non-adjacent), identity elsewhere. Built as a dense
    ndarray via the tensor-product-over-sites construction, matching the
    product_state_vector bit convention. For our tests N<=6 so dense is fine.
    """
    op = np.asarray(op4, dtype=complex).reshape(2, 2, 2, 2)
    # start from identity on all sites as a (2,2,...,2) tensor with 2N axes
    # (bra,ket per site); too heavy in general. Instead build by successive
    # sparse krons placing a 1-site factor at each site, and for sites i,j
    # use the reshaped 2-site op via an explicit embedding:
    # O = sum_{a,b,c,d} op[a,b,c,d] |a><c|_i (x) |b><d|_j  with identities elsewhere.
    import scipy.sparse as sp
    dim = 2 ** N
    out = sp.csr_matrix((dim, dim), dtype=complex)
    for a in range(2):
        for b in range(2):
            for c in range(2):
                for d in range(2):
                    coef = op[a, b, c, d]
                    if coef == 0:
                        continue
                    mats = []
                    for s in range(N):
                        if s == i:
                            m = np.zeros((2, 2), dtype=complex)
                            m[a, c] = 1.0
                            mats.append(sp.csr_matrix(m))
                        elif s == j:
                            m = np.zeros((2, 2), dtype=complex)
                            m[b, d] = 1.0
                            mats.append(sp.csr_matrix(m))
                        else:
                            mats.append(sp.eye(2, format="csr"))
                    term = mats[0]
                    for m in mats[1:]:
                        term = sp.kron(term, m, format="csr")
                    out = out + coef * term
    return out


def _bond_gate_zz(dtau, J=1.0):
    """e^{+J dtau sz sz} as a 4x4 (diagonal): diag(e^{Jdtau}, e^{-Jdtau},
    e^{-Jdtau}, e^{Jdtau}) in basis (++, +-, -+, --) = (up,up),(up,down),..."""
    e = np.exp(J * dtau)
    em = np.exp(-J * dtau)
    return np.diag([e, em, em, e]).astype(complex)


def _field_gate_sx(theta):
    """e^{+theta sx} = cosh I + sinh sx (2x2)."""
    c, s = np.cosh(theta), np.sinh(theta)
    return np.array([[c, s], [s, c]], dtype=complex)
