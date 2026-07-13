"""Richardson (reduced BCS) pairing oracle: exact Bethe/Richardson roots.

    H = sum_j eps_j (n_{j up} + n_{j dn})  -  g sum_{j,k} b^dagger_j b_k,
    b_j = c_{j dn} c_{j up},   eps_j = j  (j = 1..N),   M pairs.

T3 (Bethe ansatz / Richardson-Gaudin).  In the seniority-zero sector (every
level is either empty or doubly occupied -- no broken pairs) the M-pair
eigenstates are exact products of collective pair operators whose spectral
parameters {E_a} (the Richardson "roots", a = 1..M) solve the Richardson
equations.  Written consistently with the H above (attractive -g pairing,
pair-level energy 2 eps_j):

    1  -  g sum_{j=1}^{N} 1/(2 eps_j - E_a)  -  2 g sum_{b != a} 1/(E_a - E_b) = 0,

and the state's energy is the plain sum of roots, E = sum_a E_a.  We solve by
homotopy from g -> 0+, where the roots start at 2 eps_a of the M lowest levels,
and continue in complex arithmetic: as g grows a pair of roots can collide at a
level 2 eps_j and split into a complex-conjugate pair (the standard Richardson
complexification), so the solver runs entirely in the complex plane, uses a
linear predictor between steps, injects a conjugate imaginary seed at a near-
collision, and refines each g-step with a residual-guarded step size.

Ground truth: the seniority-zero sector Hamiltonian built directly on the
C(N,M)-dim pair-occupation (bitmask) basis -- diagonal sum_{j in occ} 2 eps_j - gM,
off-diagonal -g between configurations differing by one pair move.  self_test
pins sum(roots).real to that ED at 1e-10, and (extra) confirms the seniority-
zero ground state is the true ground state by matching a full spinful-Fock-space
ED in the 2M-particle sector.
"""
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.optimize import root

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed as edlib  # noqa: E402


def levels(N):
    """Single-particle levels eps_j = j, j = 1..N."""
    return np.arange(1, N + 1, dtype=float)


# --------------------------------------------------------------------------
# ground truth: seniority-zero exact diagonalization
# --------------------------------------------------------------------------

def seniority_zero_ed(N, M, g):
    """Ground energy of H in the seniority-zero (fully paired) sector.

    Basis = size-M subsets of the N levels (pair occupations); diagonal
    sum_{j in occ} 2 eps_j - gM, off-diagonal -g for one-pair moves.
    """
    eps = levels(N)
    configs = list(combinations(range(N), M))
    idx = {c: i for i, c in enumerate(configs)}
    H = np.zeros((len(configs), len(configs)))
    for c in configs:
        i = idx[c]
        occ = set(c)
        H[i, i] = 2.0 * sum(eps[j] for j in occ) - g * M
        for k in occ:
            for j in range(N):
                if j in occ:
                    continue
                H[idx[tuple(sorted(occ - {k} | {j}))], i] += -g
    return float(np.linalg.eigvalsh(H)[0])


def _full_fock_ed(N, M, g):
    """Ground energy of the FULL second-quantized H in the 2M-particle sector.

    Used only in self_test to prove the seniority-zero sector holds the true
    ground state (attractive reduced BCS).  Spin-orbitals ordered (0up,0dn,
    1up,1dn,...) with Jordan-Wigner; cost 4^N, so keep N small.
    """
    c, cd = edlib.fermion_ops(2 * N)
    eps = levels(N)
    dim = c[0].shape[0]
    H = sp.csr_matrix((dim, dim), dtype=complex)
    Nop = sp.csr_matrix((dim, dim), dtype=complex)
    for j in range(N):
        nju = cd[2 * j] @ c[2 * j]
        njd = cd[2 * j + 1] @ c[2 * j + 1]
        H = H + eps[j] * (nju + njd)
        Nop = Nop + nju + njd
    for j in range(N):
        bdj = cd[2 * j] @ cd[2 * j + 1]        # c^dag_{j up} c^dag_{j dn}
        for k in range(N):
            bk = c[2 * k + 1] @ c[2 * k]        # c_{k dn} c_{k up}
            H = H - g * (bdj @ bk)
    Nd = np.real(Nop.diagonal())
    mask = np.where(np.abs(Nd - 2 * M) < 0.5)[0]
    block = H.toarray()[np.ix_(mask, mask)]
    return float(np.linalg.eigvalsh(block)[0].real)


# --------------------------------------------------------------------------
# Richardson-equation solver (homotopy in g, complex arithmetic)
# --------------------------------------------------------------------------

def richardson_roots(N, M, g_target, dg=0.01):
    """Ground-state Richardson roots {E_a} at coupling g_target.

    Homotopy from g -> 0+ (roots at 2 eps of the M lowest levels), continued in
    the complex plane through root collisions.  Returns a length-M complex array.
    """
    d = 2.0 * levels(N)

    def Fc(E, g):
        return np.array([
            1.0 - g * np.sum(1.0 / (d - E[a]))
            - 2.0 * g * np.sum([1.0 / (E[a] - E[b]) for b in range(M) if b != a])
            for a in range(M)])

    def resid(x, g):
        E = x[:M] + 1j * x[M:]
        f = Fc(E, g)
        return np.concatenate([f.real, f.imag])

    def solve_at(g, guess):
        sol = root(resid, np.concatenate([guess.real, guess.imag]),
                   args=(g,), method="hybr", tol=1e-14)
        E = sol.x[:M] + 1j * sol.x[M:]
        return E, np.max(np.abs(Fc(E, g)))

    def split_collisions(E):
        """Break a near-degenerate (near-real) pair into a conjugate pair."""
        E = E.copy()
        used = [False] * M
        for a in range(M):
            for b in range(a + 1, M):
                if used[a] or used[b]:
                    continue
                if (abs(E[a] - E[b]) < 0.3
                        and abs(E[a].imag) < 1e-2 and abs(E[b].imag) < 1e-2):
                    mid = 0.5 * (E[a] + E[b]).real
                    E[a] = mid + 0.06j
                    E[b] = mid - 0.06j
                    used[a] = used[b] = True
        return E

    if g_target == 0.0:
        return d[:M].astype(complex)
    g = min(dg, g_target)
    E, _ = solve_at(g, d[:M].astype(complex) - g)
    prev_g, prev_E = g, E.copy()
    step = dg
    while g < g_target - 1e-13:
        ng = min(g + step, g_target)
        if g > prev_g + 1e-15:
            pred = E + (E - prev_E) * ((ng - g) / (g - prev_g))
        else:
            pred = E.copy()
        pred = split_collisions(pred)
        E_try, r = solve_at(ng, pred)
        if r < 1e-9:
            prev_g, prev_E = g, E.copy()
            E, g = E_try, ng
            step = min(step * 1.3, dg)
        else:
            step *= 0.5
            if step < 1e-8:
                raise RuntimeError(f"Richardson continuation stalled at g={g}")
    return E


def energy_from_roots(N, M, g):
    """Ground-state energy E = sum_a E_a (real part) from the Richardson roots."""
    return float(np.sum(richardson_roots(N, M, g)).real)


# --------------------------------------------------------------------------

def compute(N=6, M=3, g=0.5):
    """Reduced-BCS ground state via the Richardson equations (seniority zero)."""
    roots = richardson_roots(N, M, g)
    return {
        "e0": float(np.sum(roots).real),
        "richardson_roots": [[float(z.real), float(z.imag)] for z in roots],
        "n_levels": int(N),
        "n_pairs": int(M),
    }


def self_test():
    N, M = 6, 3
    eps = levels(N)

    # anchor 1 (GROUND TRUTH): sum of Richardson roots == seniority-zero ED.
    for g in (0.1, 0.5, 1.0):
        roots = richardson_roots(N, M, g)
        e_bethe = np.sum(roots)
        e_ed = seniority_zero_ed(N, M, g)
        assert abs(e_bethe.real - e_ed) < 1e-10, (g, e_bethe.real, e_ed)
        # anchor 2: the energy (sum of roots) is real -- complex roots pair up.
        assert abs(e_bethe.imag) < 1e-12, (g, e_bethe.imag)
        # the roots genuinely solve the Richardson equations.
        d = 2.0 * eps
        res = [1.0 - g * np.sum(1.0 / (d - roots[a]))
               - 2.0 * g * np.sum([1.0 / (roots[a] - roots[b])
                                   for b in range(M) if b != a]) for a in range(M)]
        assert np.max(np.abs(res)) < 1e-9, (g, np.max(np.abs(res)))

    # anchor 3: g -> 0 limit.  Roots start at 2 eps of the M lowest levels, so
    # the energy approaches 2(eps_1+...+eps_M); the approach is LINEAR in g
    # (the -gM diagonal shift), so at g=1e-8 the offset is ~ M*g = 3e-8.  We pin
    # the exact ground-truth match to the ED at that g (1e-10), and the physical
    # limit 2*sum(eps[:M]) to 1e-6.
    g0 = 1e-8
    r0 = richardson_roots(N, M, g0)
    assert abs(np.sum(r0).real - seniority_zero_ed(N, M, g0)) < 1e-10
    assert abs(np.sum(r0).real - 2.0 * eps[:M].sum()) < 1e-6
    assert np.max(np.abs(r0 - 2.0 * eps[:M])) < 1e-6   # roots -> 2 eps_a

    # anchor 4: the seniority-zero sector holds the TRUE ground state -- match a
    # full spinful-Fock-space ED in the 2M-particle sector (small cases).
    for (n, m, g) in [(3, 1, 0.7), (4, 2, 0.5), (4, 2, 1.0)]:
        assert abs(seniority_zero_ed(n, m, g) - _full_fock_ed(n, m, g)) < 1e-9

    # anchor 5: continuation is robust for other (N, M) -- Bethe == ED.
    for (n, m, g) in [(6, 2, 0.8), (8, 4, 0.6)]:
        assert abs(energy_from_roots(n, m, g) - seniority_zero_ed(n, m, g)) < 1e-10


if __name__ == "__main__":
    oracle_main(compute, {"N": (int, 6), "M": (int, 3), "g": (float, 0.5)})
