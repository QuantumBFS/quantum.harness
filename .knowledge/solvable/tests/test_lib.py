import numpy as np
from _lib import quadratic, ed, gf2, topology, bethe


def _xxx_ed_energy(N):
    """Brute-force ED ground energy of H = sum_i S_i . S_{i+1} (PBC, S=sigma/2)."""
    sx, sy, sz = ed.spin_ops(N)
    H = sum(sx[i] @ sx[(i + 1) % N] + sy[i] @ sy[(i + 1) % N]
            + sz[i] @ sz[(i + 1) % N] for i in range(N))
    return ed.ground_energy(H)


def test_bethe_xxx_ground_energy_matches_ed():
    # GROUND TRUTH: Bethe-ansatz roots reproduce brute-force ED to 1e-10.
    for N in (8, 10, 12):
        roots = bethe.xxx_ground_roots(N)
        assert len(roots) == N // 2, (N, len(roots))
        e_bethe = bethe.xxx_energy(roots, N)
        e_ed = _xxx_ed_energy(N)
        assert abs(e_bethe - e_ed) < 1e-10, (N, e_bethe, e_ed)


def test_bethe_roots_are_real_and_symmetric():
    for N in (8, 10, 12):
        r = bethe.xxx_ground_roots(N)
        # roots are symmetric about 0 as a SET: {r} == {-r}
        assert np.allclose(np.sort(r), np.sort(-r), atol=1e-12), N
        # roots genuinely solve the logarithmic Bethe equations
        M = N // 2
        I = np.arange(M) - (M - 1) / 2.0
        diff = r[:, None] - r[None, :]
        residual = (2 * np.arctan(2 * r)
                    - 2 * np.pi * I / N
                    - 2 * np.arctan(diff).sum(axis=1) / N)
        assert np.max(np.abs(residual)) < 1e-12, (N, np.max(np.abs(residual)))


def test_bdg_matches_ed_random_quadratic():
    rng = np.random.default_rng(7)
    L = 4
    A = rng.normal(size=(L, L)); A = (A + A.T) / 2
    B = rng.normal(size=(L, L)); B = (B - B.T) / 2
    c, cdag = ed.fermion_ops(L)
    H = sum(A[i, j] * (cdag[i] @ c[j]) for i in range(L) for j in range(L))
    H = H + sum(0.5 * B[i, j] * (cdag[i] @ cdag[j]) for i in range(L) for j in range(L))
    H = H + H.conj().T.tocsr() - sum(A[i, j] * (cdag[i] @ c[j]) for i in range(L) for j in range(L))
    e_ed = ed.ground_energy(H)
    e_bdg = quadratic.bdg_ground_energy(A, B)
    assert abs(e_ed - e_bdg) < 1e-10


def test_ed_spin_tfim_l2():
    # H = -sz.sz - h(sx1+sx2) with PAULIS, h=0: E0 = -1, doubly degenerate
    sx, sy, sz = ed.spin_ops(2)
    H = -4 * (sz[0] @ sz[1]) # Pauli = 2*S
    assert abs(ed.ground_energy(H) + 1.0) < 1e-12
    assert ed.ground_states(H) == 2


def test_gf2_rank():
    assert gf2.rank(np.eye(3, dtype=np.uint8)) == 3
    assert gf2.rank(np.array([[1, 1], [1, 1]], dtype=np.uint8)) == 1
    assert gf2.rank(np.array([[1, 0, 1], [0, 1, 1], [1, 1, 0]], dtype=np.uint8)) == 2


def test_chern_qwz():
    sx = np.array([[0, 1], [1, 0]], complex)
    sy = np.array([[0, -1j], [1j, 0]], complex)
    sz = np.diag([1.0 + 0j, -1.0])

    def hk(m):
        return lambda kx, ky: (np.sin(kx) * sx + np.sin(ky) * sy
                               + (m + np.cos(kx) + np.cos(ky)) * sz)

    assert abs(topology.chern(hk(1.0), 1)) == 1
    assert topology.chern(hk(3.0), 1) == 0
    assert topology.chern(hk(1.0), 1) == -topology.chern(hk(-1.0), 1)


def test_winding_ssh():
    assert topology.winding(lambda k: 0.5 + 1.0 * np.exp(1j * k)) == 1
    assert topology.winding(lambda k: 1.0 + 0.5 * np.exp(1j * k)) == 0
