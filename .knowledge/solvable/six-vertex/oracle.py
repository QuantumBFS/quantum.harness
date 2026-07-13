"""Six-vertex (ice-type) model oracle: arrows on square-lattice edges, ice rule.

Classical statistical model. Each edge of the square lattice carries an arrow;
the ICE RULE requires exactly two arrows in and two out at every vertex, leaving
six allowed vertex configurations with Boltzmann weights a, b, c (two of each).
Conventions: edge value +1 = arrow points right (horizontal) or up (vertical),
-1 = left/down. With this sign, the ice rule at a vertex (L,B,R,T) = (left,
bottom, right, top edges) is exactly L + B == R + T. The six configs split as
  a: (+,+,+,+),(-,-,-,-)   b: (+,-,+,-),(-,+,-,+)   c: (+,-,-,+),(-,+,+,-).
The anisotropy parameter is Delta = (a^2+b^2-c^2)/(2ab); the ICE POINT a=b=c=1
has Delta=1/2 and lies in the disordered regime |Delta|<1.

Exact results: at the ice point the partition function per vertex is Lieb's
square-ice constant W = (4/3)^{3/2} = 1.5396007... (residual entropy per vertex
ln W = (3/2)ln(4/3) = 0.4315231...). Ground truth: the row-to-row transfer
matrix in the vertical-arrow basis, whose tr(V^M) equals a direct brute-force
enumeration of all ice configurations on the N x M torus (exact integer at unit
weights, exact float at generic weights). The disordered-regime free energy
(Lieb 1967, Sutherland; Bethe ansatz) is a convergent integral that reproduces
ln W at the ice point. All partition functions handled in log space.
"""
import sys
from pathlib import Path

import numpy as np
from scipy import integrate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402


def lieb_constant():
    """Lieb's square-ice constant W = (4/3)^{3/2} (partition function per vertex).

    Algebraic closed form (Lieb 1967) -- no quadrature: the residual entropy per
    vertex of square ice is ln W = (3/2) ln(4/3) = 0.4315231...
    """
    return (4.0 / 3.0) ** 1.5


# ---- ice-rule vertex weights and the row-to-row transfer matrix ----

def _vertex_weight(L, B, R, T, a, b, c):
    """Six-vertex Boltzmann weight for edge values (L,B,R,T) in {+1,-1}; 0 if the
    ice rule L+B==R+T is violated."""
    if L + B != R + T:
        return 0.0
    if L == B == R == T:
        return a
    if L == R and B == T:
        return b
    return c


def transfer_matrix(N, a, b, c):
    """Row-to-row transfer matrix V (2^N x 2^N) for a width-N periodic row.

    Basis states are the vertical-arrow configurations s in {+1,-1}^N on a
    horizontal cut. V[top, bot] sums over the N periodic horizontal edges h of
    the row the product of vertex weights, vertex j having L=h[j-1], R=h[j],
    B=bot[j], T=top[j]. Built as a trace of a product of 2x2 transfer factors
    (one per column) so the horizontal periodicity is handled exactly:
    V[top,bot] = tr( prod_j M(bot_j, top_j) ), M(B,T)[L,R] = weight(L,B,R,T).
    """
    vals = (1, -1)
    # M2[(B,T)] is the 2x2 matrix indexed by horizontal edge values (rows L, cols R)
    M2 = {}
    for B in vals:
        for T in vals:
            m = np.array([[_vertex_weight(L, B, R, T, a, b, c) for R in vals]
                          for L in vals], dtype=float)
            M2[(B, T)] = m
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


def logZ_torus(N, M, a, b, c):
    """ln Z of the N x M six-vertex torus via tr(V_N^M) (log space)."""
    V = transfer_matrix(N, a, b, c)
    m = np.abs(V).max()
    Z = np.trace(np.linalg.matrix_power(V / m, M))
    return M * np.log(m) + np.log(Z)


def _enumerate_Z(N, M, a, b, c):
    """Ground-truth six-vertex partition function on the N x M torus by direct
    enumeration over all 2^{2NM} edge configurations (horizontal + vertical).

    Vectorised: edge j of a config is +1/-1; horizontal edges h[i,j] (row i,
    between columns j and j+1) and vertical edges v[i,j] (column j, between rows
    i and i+1). Vertex (i,j) has L=h[i,j-1], R=h[i,j], B=v[i-1,j], T=v[i,j].
    Returns the exact weighted sum (an integer at a=b=c=1). Tractable for 2NM<=18.
    """
    ne = 2 * N * M
    idx = np.arange(2 ** ne)
    bits = (idx[:, None] >> np.arange(ne)[None, :]) & 1
    e = 1 - 2 * bits                                  # +-1 edge values
    h = e[:, :N * M].reshape(-1, M, N)
    v = e[:, N * M:].reshape(-1, M, N)
    L = np.roll(h, 1, axis=2)
    R = h
    B = np.roll(v, 1, axis=1)
    T = v
    ice = np.all(L + B == R + T, axis=(1, 2))         # valid configs
    na = np.sum((L == B) & (B == R) & (R == T), axis=(1, 2))
    nb = np.sum((L == R) & (B == T) & ~((L == B) & (B == R) & (R == T)), axis=(1, 2))
    nc = M * N - na - nb
    w = np.where(ice, a ** na * b ** nb * c ** nc, 0.0)
    return w.sum()


# ---- disordered-regime free energy (Lieb / Bethe ansatz), |Delta| < 1 ----

def _logsinh(x):
    return x + np.log1p(-np.exp(-2.0 * x)) - np.log(2.0)


def _logcosh(x):
    return x + np.log1p(np.exp(-2.0 * x)) - np.log(2.0)


def free_energy_disordered(a, b, c):
    """ln kappa = (1/N) ln Z per vertex in the disordered regime -1 < Delta < 1.

    Bethe-ansatz solution (Lieb 1967; Sutherland; here in the form of
    Duminil-Copin, Karrila, Manolescu, Oulamara, Comm. Math. Phys. 2022,
    Thm 1). With Delta = -cos(zeta), zeta in (0,pi), and phi = arcsin(b*sin(zeta)/c)
    (so that a=b corresponds to phi = zeta/2),

        ln kappa = ln b + int_{-inf}^{inf}
            sinh[(2 zeta - 2 phi) t] sinh[(pi - zeta) t]
            / ( 2 t cosh[zeta t] sinh[pi t] )  dt .

    The integrand is even and decays like exp(-2 phi |t|); evaluated in a
    log-stable form (0<phi<zeta<pi). At the ice point a=b=c it returns ln W.
    """
    Delta = (a * a + b * b - c * c) / (2 * a * b)
    if not -1.0 < Delta < 1.0:
        raise ValueError(f"Delta={Delta} outside disordered regime (-1,1)")
    zeta = np.arccos(-Delta)
    phi = np.arcsin(b * np.sin(zeta) / c)
    coeff = 2.0 * (zeta - phi)

    def g(t):
        if t <= 0.0:
            return coeff * (np.pi - zeta) / (2.0 * np.pi)      # even, finite limit
        return np.exp(_logsinh(coeff * t) + _logsinh((np.pi - zeta) * t)
                      - np.log(2.0 * t) - _logcosh(zeta * t) - _logsinh(np.pi * t))

    val, _ = integrate.quad(g, 0.0, np.inf, limit=200)
    return np.log(b) + 2.0 * val


def compute(a=1.0, b=1.0, c=1.0, N=4, M=4):
    """Six-vertex exact quantities: Lieb constant, N x M torus ln Z, disordered f."""
    Delta = (a * a + b * b - c * c) / (2 * a * b)
    out = {
        "lieb_constant": lieb_constant(),
        "entropy_per_vertex": np.log(lieb_constant()),
        "Delta": Delta,
        "logZ_torus": logZ_torus(N, M, a, b, c),
    }
    if -1.0 < Delta < 1.0:
        out["free_energy_disordered"] = free_energy_disordered(a, b, c)
    return out


def self_test():
    W = lieb_constant()
    # anchor 1: Lieb's square-ice constant, algebraic closed form, 1e-12
    assert abs(W - (4.0 / 3.0) ** 1.5) < 1e-12
    assert abs(W - 1.5396007178390020) < 1e-12
    assert abs(np.log(W) - 1.5 * np.log(4.0 / 3.0)) < 1e-12   # entropy = (3/2)ln(4/3)

    # anchor 2: GROUND TRUTH -- tr(V_N^M) equals brute-force torus enumeration.
    # Unit weights give the exact integer count of ice configurations; a generic
    # (a,b,c) gives the exact weighted partition function. Small tori with
    # 2NM <= 18 edges are enumerated exactly.
    for (N, M) in [(2, 2), (3, 2), (4, 2), (2, 3), (2, 4)]:
        tr = np.exp(logZ_torus(N, M, 1.0, 1.0, 1.0))
        en = _enumerate_Z(N, M, 1.0, 1.0, 1.0)
        assert abs(tr - round(en)) < 1e-6, (N, M, tr, en)
        assert round(en) == en                                # integer count
    for (a, b, c) in [(1.3, 0.8, 1.1), (0.9, 1.2, 1.0)]:
        for (N, M) in [(3, 2), (2, 3)]:
            tr = np.exp(logZ_torus(N, M, a, b, c))
            en = _enumerate_Z(N, M, a, b, c)
            assert abs(tr - en) <= 1e-8 * en, (a, b, c, N, M, tr, en)
    # the 4x4 ice-configuration count (transfer matrix on validated V) is 2970
    assert round(np.exp(logZ_torus(4, 4, 1.0, 1.0, 1.0))) == 2970

    # anchor 3: disordered free-energy integral reproduces ln W at the ice point
    assert abs(free_energy_disordered(1.0, 1.0, 1.0) - np.log(W)) < 1e-8
    # the free-fermion (Delta=0) point a=b=1,c=sqrt2 has higher per-vertex
    # entropy than the ice point (more disordered), both finite and positive
    assert free_energy_disordered(1.0, 1.0, np.sqrt(2.0)) > free_energy_disordered(1.0, 1.0, 1.0) > 0

    # anchor 4: convergence of Lambda_max(N)^{1/N} -> W. Slow (power-law): the
    # exact-count anchor above is the real gate. Assert width-6 within 5% of W
    # and strictly closer than width-2 (honest slow-convergence statement).
    def lam_root(N):
        lam = np.max(np.abs(np.linalg.eigvals(transfer_matrix(N, 1.0, 1.0, 1.0))))
        return lam ** (1.0 / N)
    r2, r6 = lam_root(2), lam_root(6)
    assert abs(r6 - W) < 0.05 * W, (r6, W)
    assert abs(r6 - W) < abs(r2 - W), (r2, r6, W)


if __name__ == "__main__":
    oracle_main(compute, {"a": (float, 1.0), "b": (float, 1.0), "c": (float, 1.0),
                          "N": (int, 4), "M": (int, 4)})
