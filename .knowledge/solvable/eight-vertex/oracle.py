"""Eight-vertex model oracle: square-lattice arrows with even in/out at each vertex.

Classical statistical model (Baxter 1971). Relaxing the six-vertex ice rule to
allow an EVEN number of in-arrows (0, 2, or 4) admits two extra vertices -- all
arrows in / all arrows out -- with weight d, giving eight vertex types with
weights a, b, c, d (two of each). Edge sign convention as in `six-vertex`
(+1 = right/up): the six ice configs satisfy L+B==R+T (weights a,b,c as there),
and the two d-configs are (L,B,R,T) = (+,+,-,-) (all in) and (-,-,+,+) (all out).
The anisotropy parameters are
    Delta = (a^2 + b^2 - c^2 - d^2) / (2(ab + cd)),   Gamma = (ab - cd)/(ab + cd).
d -> 0 recovers the six-vertex model (Delta, weights reduce to that card's).

*** P (partial) card. ***  Scripted here: (1) the exact ground truth -- the
row-to-row transfer matrix in the vertical-arrow basis, whose tr(V^M) equals a
brute-force enumeration of all eight-vertex configurations on the N x M torus,
for ANY weights (exact integer/float equality); (2) the FREE-FERMION point
a^2+b^2 = c^2+d^2 (equivalently Delta = 0), where the model is dimer/Pfaffian
reducible and the per-vertex free energy has the closed Fan-Wu double integral,
verified here against the six-vertex solution (d->0) and against the transfer
matrix; (3) the d->0 reduction to the six-vertex oracle (cross-loaded). NOT
scripted -- Baxter's general elliptic-theta-function free energy off the
free-fermion manifold: it is TABULATED with citation in ORACLE.md, not computed.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
from scipy import integrate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402


def _load_sixvertex():
    """Cross-load the sibling six-vertex oracle by path (not duplicated)."""
    p = Path(__file__).resolve().parents[1] / "six-vertex" / "oracle.py"
    spec = importlib.util.spec_from_file_location("six_vertex_oracle", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def delta(a, b, c, d):
    """Eight-vertex anisotropy Delta = (a^2+b^2-c^2-d^2)/(2(ab+cd))."""
    return (a * a + b * b - c * c - d * d) / (2.0 * (a * b + c * d))


def is_free_fermion(a, b, c, d, tol=1e-12):
    """Free-fermion condition a^2 + b^2 = c^2 + d^2 (equivalently Delta = 0)."""
    return abs(a * a + b * b - c * c - d * d) < tol


# ---- eight-vertex vertex weights and the row-to-row transfer matrix ----

def _vertex_weight(L, B, R, T, a, b, c, d):
    """Eight-vertex Boltzmann weight for edge values (L,B,R,T) in {+1,-1}.

    Six ice configs (L+B==R+T): a if all four equal, b if L==R and B==T, else c.
    Two d-configs: all-in (+,+,-,-) and all-out (-,-,+,+). Everything else is 0.
    """
    if L + B == R + T:
        if L == B == R == T:
            return a
        if L == R and B == T:
            return b
        return c
    if (L, B, R, T) == (1, 1, -1, -1) or (L, B, R, T) == (-1, -1, 1, 1):
        return d
    return 0.0


def transfer_matrix(N, a, b, c, d):
    """Row-to-row transfer matrix V (2^N x 2^N), width-N periodic row.

    Same construction as `six-vertex.transfer_matrix` but with the eight-vertex
    weight (so the d-vertices flip the vertical arrow across the row): V[top,bot]
    = tr( prod_j M(bot_j, top_j) ), M(B,T)[L,R] = weight(L,B,R,T).
    """
    vals = (1, -1)
    M2 = {}
    for B in vals:
        for T in vals:
            M2[(B, T)] = np.array(
                [[_vertex_weight(L, B, R, T, a, b, c, d) for R in vals]
                 for L in vals], dtype=float)
    states = [tuple(1 - 2 * ((k >> j) & 1) for j in range(N)) for k in range(2 ** N)]
    S = len(states)
    V = np.zeros((S, S))
    for ti, top in enumerate(states):
        for bi, bot in enumerate(states):
            prod = np.eye(2)
            for j in range(N):
                prod = prod @ M2[(bot[j], top[j])]
            V[ti, bi] = np.trace(prod)
    return V


def logZ_torus(N, M, a, b, c, d):
    """ln Z of the N x M eight-vertex torus via tr(V_N^M) (log space)."""
    V = transfer_matrix(N, a, b, c, d)
    m = np.abs(V).max()
    Z = np.trace(np.linalg.matrix_power(V / m, M))
    return M * np.log(m) + np.log(Z)


def _enumerate_Z(N, M, a, b, c, d):
    """Ground-truth eight-vertex partition function on the N x M torus by direct
    enumeration over all 2^{2NM} edge configurations. Vectorised, as in the
    six-vertex oracle, with the two extra d-vertices counted. 2NM <= 18."""
    ne = 2 * N * M
    idx = np.arange(2 ** ne)
    bits = (idx[:, None] >> np.arange(ne)[None, :]) & 1
    e = 1 - 2 * bits
    h = e[:, :N * M].reshape(-1, M, N)
    v = e[:, N * M:].reshape(-1, M, N)
    L = np.roll(h, 1, axis=2)
    R = h
    B = np.roll(v, 1, axis=1)
    T = v
    ice = (L + B == R + T)
    allin = (L == 1) & (B == 1) & (R == -1) & (T == -1)
    allout = (L == -1) & (B == -1) & (R == 1) & (T == 1)
    dvert = allin | allout
    valid = np.all(ice | dvert, axis=(1, 2))
    na = np.sum(ice & (L == B) & (B == R) & (R == T), axis=(1, 2))
    nb = np.sum(ice & (L == R) & (B == T)
                & ~((L == B) & (B == R) & (R == T)), axis=(1, 2))
    nd = np.sum(dvert, axis=(1, 2))
    nc = M * N - na - nb - nd
    w = np.where(valid, a ** na * b ** nb * c ** nc * d ** nd, 0.0)
    return w.sum()


# ---- free-fermion free energy (Fan-Wu 1970 double integral) ----

def free_energy_free_fermion(a, b, c, d):
    """ln kappa = (1/N) ln Z per vertex on the FREE-FERMION manifold a^2+b^2=c^2+d^2.

    Fan & Wu (Phys. Rev. B 2, 723 (1970)) reduce the free-fermion vertex model to
    a dimer/Pfaffian problem; the per-vertex free energy is the double integral
    (uniform-weight specialisation of H. Y. Wu, cond-mat/0303303 Eqs (16)-(17))

        ln kappa = 1/(16 pi^2) int_0^{2pi} int_0^{2pi}
                   ln[ 2A + 2D cos(x-y) + 2E cos(x+y)
                       + 4 D1 sin^2 y + 4 D2 sin^2 x ]  dx dy,

    with A = 4a^2 b^2 + 4c^2 d^2,  D = E = 2c^2 d^2 - 2a^2 b^2,
    D1 = (a^2 - c^2)^2,  D2 = (b^2 - c^2)^2. Raises unless the free-fermion
    condition holds. (Verified in self_test: at d->0 this equals the six-vertex
    disordered free energy, and off d=0 it matches the transfer-matrix free
    energy.)
    """
    if not is_free_fermion(a, b, c, d):
        raise ValueError("weights are not on the free-fermion manifold a^2+b^2=c^2+d^2")
    A = 4.0 * a * a * b * b + 4.0 * c * c * d * d
    D = 2.0 * c * c * d * d - 2.0 * a * a * b * b
    E = D
    D1 = (a * a - c * c) ** 2
    D2 = (b * b - c * c) ** 2

    def integrand(x, y):
        val = (2 * A + 2 * D * np.cos(x - y) + 2 * E * np.cos(x + y)
               + 4 * D1 * np.sin(y) ** 2 + 4 * D2 * np.sin(x) ** 2)
        return np.log(val)

    val, _ = integrate.dblquad(integrand, 0.0, 2 * np.pi, 0.0, 2 * np.pi,
                               epsabs=1e-10, epsrel=1e-10)
    return val / (16.0 * np.pi ** 2)


def compute(a=1.0, b=1.0, c=1.2, d=0.7483314773547883, N=4, M=4):
    """Eight-vertex exact quantities: Delta, N x M torus ln Z, free-fermion f."""
    out = {
        "Delta": delta(a, b, c, d),
        "Gamma": (a * b - c * d) / (a * b + c * d),
        "free_fermion": is_free_fermion(a, b, c, d),
        "logZ_torus": logZ_torus(N, M, a, b, c, d),
    }
    if is_free_fermion(a, b, c, d):
        out["free_energy_free_fermion"] = free_energy_free_fermion(a, b, c, d)
    return out


def self_test():
    # anchor 1: GROUND TRUTH -- tr(V_N^M) equals brute-force torus enumeration,
    # for generic weights, a free-fermion point, and the six-vertex sub-case.
    weight_sets = [
        (1.0, 0.9, 1.1, 0.4),                    # generic (not free-fermion)
        (1.0, 1.0, 1.2, np.sqrt(2 - 1.2 ** 2)),  # free-fermion a^2+b^2=c^2+d^2
        (1.2, 0.8, 1.0, 0.0),                    # d=0 six-vertex sub-case
    ]
    for (a, b, c, d) in weight_sets:
        for (N, M) in [(2, 2), (3, 2), (2, 3)]:
            tr = np.exp(logZ_torus(N, M, a, b, c, d))
            en = _enumerate_Z(N, M, a, b, c, d)
            assert abs(tr - en) <= 1e-8 * max(en, 1.0), (a, b, c, d, N, M, tr, en)
    # unit-weight eight-vertex count (a=b=c=d=1) is an exact integer
    en = _enumerate_Z(2, 2, 1.0, 1.0, 1.0, 1.0)
    assert round(en) == en and abs(np.exp(logZ_torus(2, 2, 1, 1, 1, 1)) - en) < 1e-6

    # anchor 2: d -> 0 reproduces the six-vertex oracle EXACTLY (cross-loaded):
    # identical transfer matrix and identical torus partition functions.
    sv = _load_sixvertex()
    for (a, b, c) in [(1.2, 0.8, 1.0), (0.9, 1.1, 1.0)]:
        V8 = transfer_matrix(4, a, b, c, 0.0)
        V6 = sv.transfer_matrix(4, a, b, c)
        assert np.allclose(V8, V6, atol=1e-12), (a, b, c)
        for (N, M) in [(3, 2), (2, 3)]:
            assert abs(logZ_torus(N, M, a, b, c, 0.0)
                       - sv.logZ_torus(N, M, a, b, c)) < 1e-12
    # the ice point (a=b=c=1, d=0) has Delta = 1/2 and reproduces Lieb's W count
    assert abs(delta(1.0, 1.0, 1.0, 0.0) - 0.5) < 1e-12
    assert round(np.exp(logZ_torus(4, 4, 1.0, 1.0, 1.0, 0.0))) == 2970

    # anchor 3: free-fermion condition <=> Delta = 0
    a, b, c = 1.0, 1.0, 1.2
    d = np.sqrt(a * a + b * b - c * c)
    assert is_free_fermion(a, b, c, d)
    assert abs(delta(a, b, c, d)) < 1e-12
    assert not is_free_fermion(1.0, 1.0, 1.0, 0.5)

    # anchor 4: Fan-Wu free-fermion free energy is INDEPENDENTLY verified.
    #  (a) d -> 0 free-fermion (a^2+b^2=c^2): equals the six-vertex disordered
    #      free energy from the sibling oracle, to 1e-8.
    a, b = 1.0, 1.0
    c = np.sqrt(a * a + b * b)                      # d = 0, Delta = 0
    assert abs(free_energy_free_fermion(a, b, c, 0.0)
               - sv.free_energy_disordered(a, b, c)) < 1e-8
    #  (b) d != 0 free-fermion: matches the transfer-matrix free energy
    #      f = (1/N) ln Lambda_max (these points are gapped, so the width-N strip
    #      converges fast); width 8 already agrees to < 1e-4.
    for (a, b, c) in [(1.0, 1.0, 1.2), (1.2, 0.9, 1.1)]:
        d = np.sqrt(a * a + b * b - c * c)
        ff = free_energy_free_fermion(a, b, c, d)
        lam = np.max(np.abs(np.linalg.eigvals(transfer_matrix(8, a, b, c, d))))
        f_strip = np.log(lam) / 8.0
        assert abs(ff - f_strip) < 1e-4, (a, b, c, d, ff, f_strip)


if __name__ == "__main__":
    oracle_main(compute, {"a": (float, 1.0), "b": (float, 1.0), "c": (float, 1.2),
                          "d": (float, 0.7483314773547883), "N": (int, 4), "M": (int, 4)})
