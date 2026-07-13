"""Hard-hexagon lattice-gas oracle: triangular lattice, nearest-neighbour exclusion.

Classical statistical model (Baxter 1980). Particles sit on the sites of a
triangular lattice; NO two nearest neighbours may be occupied simultaneously
(hard-hexagon exclusion). Each occupied site carries an activity (fugacity) z,
so the grand partition function is Z = sum_{independent sets} z^{#particles}.
Conventions: a triangular lattice is drawn as a square grid of sites with the
extra down-right diagonal bonds; site (i,j) is adjacent to (i,j+-1), (i+-1,j),
and (i+1,j+1)/(i-1,j-1) -- six neighbours. Boundaries are periodic (torus).

Exact results (Baxter 1980, corner-transfer-matrix / Rogers-Ramanujan): a
fluid-to-solid critical point at the activity
    z_c = (11 + 5 sqrt5)/2 = phi^5 = 11.0901699...,  phi = (1+sqrt5)/2 the golden
ratio, with critical exponents alpha=1/3, beta=1/9 (tabulated). Ground truth:
the row-to-row transfer matrix on occupation states of a width-W triangular
strip, whose tr(T^N) equals a brute-force enumeration of hard-hexagon
configurations on the N x W torus (exact integer count at z=1, exact float at
generic z). The density rho(z) follows from the largest eigenvalue.

*** P (partial) card. ***  Scripted: z_c and its golden-ratio identity, the
transfer-matrix/enumeration ground truth, and the density rho(z). NOT scripted
(TABULATED with citation in ORACLE.md): the critical exponents alpha, beta, the
correlation-length exponent, and the sublattice order parameter R -- Baxter's
Rogers-Ramanujan results are quoted, not recomputed.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402

GOLDEN = (1.0 + np.sqrt(5.0)) / 2.0


def zc():
    """Critical activity z_c = (11 + 5 sqrt5)/2 (Baxter 1980), closed form."""
    return (11.0 + 5.0 * np.sqrt(5.0)) / 2.0


# ---- triangular-strip transfer matrix (ground truth vs enumeration) ----

def _row_states(W):
    """Occupation states of a width-W periodic row with no two adjacent particles
    (intra-row hard-core, PBC). Returns a list of 0/1 tuples (Lucas(W) of them)."""
    out = []
    for bits in range(2 ** W):
        s = tuple((bits >> j) & 1 for j in range(W))
        if all(not (s[j] and s[(j + 1) % W]) for j in range(W)):
            out.append(s)
    return out


def transfer_matrix(W, z):
    """Row-to-row transfer matrix T for a width-W triangular strip (PBC).

    Rows carry hard-core occupation states s (bottom) and s' (top). They are
    compatible iff no particle sits on adjacent triangular-lattice sites across
    the rows: for every column j, not(s[j] & s'[j]) [vertical bond] and
    not(s[j] & s'[j+1]) [down-right diagonal bond], PBC in j. The activity of a
    row is assigned to its appearance as the top state, T[s',s] = z^{|s'|}, so
    tr(T^N) = sum over the N x W torus of z^{#particles}.
    """
    states = _row_states(W)
    S = len(states)
    T = np.zeros((S, S))
    for ti, top in enumerate(states):
        wt = z ** sum(top)
        for bi, bot in enumerate(states):
            if all(not (bot[j] and top[j]) and not (bot[j] and top[(j + 1) % W])
                   for j in range(W)):
                T[ti, bi] = wt
    return T


def logZ_torus(N, W, z):
    """ln Z of the N x W hard-hexagon torus via tr(T^N) (log space)."""
    T = transfer_matrix(W, z)
    m = T.max()
    Z = np.trace(np.linalg.matrix_power(T / m, N))
    return N * np.log(m) + np.log(Z)


def _enumerate_Z(N, W, z):
    """Ground-truth hard-hexagon partition function on the N x W torus by direct
    enumeration over all 2^{NW} site occupations (vectorised).

    A config is valid iff none of the three triangular bond families has both
    endpoints occupied: right (j,j+1), vertical (i,i+1), and down-right diagonal
    (i+1,j+1) -- each of the six neighbours covered exactly once, PBC. NW <= 20.
    """
    n = N * W
    idx = np.arange(2 ** n)
    occ = ((idx[:, None] >> np.arange(n)[None, :]) & 1).reshape(-1, N, W)
    right = occ & np.roll(occ, -1, axis=2)
    vert = occ & np.roll(occ, -1, axis=1)
    diag = occ & np.roll(np.roll(occ, -1, axis=1), -1, axis=2)
    valid = ~(right.any(axis=(1, 2)) | vert.any(axis=(1, 2)) | diag.any(axis=(1, 2)))
    npart = occ.sum(axis=(1, 2))
    return np.where(valid, z ** npart, 0.0).sum()


def density(z, W=6, dz=1e-6):
    """Particle density rho(z) = z d/dz ln Lambda_max / W of the width-W strip.

    Lambda_max is the largest eigenvalue of the width-W transfer matrix; the
    strip density converges to the 2D bulk density as W -> infinity (it already
    reproduces the low-z virial series rho = z - 7z^2 + 58z^3 - ... at W>=4).
    """
    def lnlam(zz):
        lam = np.max(np.abs(np.linalg.eigvals(transfer_matrix(W, zz))))
        return np.log(lam)
    return z * (lnlam(z + dz) - lnlam(z - dz)) / (2.0 * dz) / W


def compute(z=1.0, N=4, W=4):
    """Hard-hexagon exact quantities: z_c, N x W torus ln Z, density(z)."""
    return {
        "zc": zc(),
        "logZ_torus": logZ_torus(N, W, z),
        "density_width6": density(z, W=6),
    }


def self_test():
    # anchor 1: z_c closed form == golden^5 (derive: phi^5 = 5 phi + 3 =
    # (11 + 5 sqrt5)/2), both algebraic, 1e-12
    assert abs(zc() - GOLDEN ** 5) < 1e-12
    assert abs(zc() - (5.0 * GOLDEN + 3.0)) < 1e-12          # phi^5 = 5 phi + 3
    assert abs(zc() - 11.090169943749475) < 1e-12

    # anchor 2: GROUND TRUTH -- tr(T^N) equals brute-force torus enumeration.
    # z=1 gives the exact integer count of hard-hexagon configurations; z=0.7 a
    # generic float partition function.
    for (N, W) in [(3, 3), (4, 3), (4, 4)]:
        tr = np.exp(logZ_torus(N, W, 1.0))
        en = _enumerate_Z(N, W, 1.0)
        assert round(en) == en                               # integer count
        assert abs(tr - en) <= 1e-9 * en, (N, W, tr, en)
    for (N, W) in [(3, 3), (4, 4)]:
        tr = np.exp(logZ_torus(N, W, 0.7))
        en = _enumerate_Z(N, W, 0.7)
        assert abs(tr - en) <= 1e-10 * en, (N, W, tr, en)
    assert round(np.exp(logZ_torus(4, 4, 1.0))) == 201       # 4x4 config count

    # anchor 3: density rho(z) is monotone increasing in z across z_c, and is
    # resolution-consistent between widths 4, 5, 6 in the low-activity phase.
    zc_val = zc()
    zs = [1.0, 5.0, zc_val, 15.0, 25.0]
    rhos = [density(z, W=6) for z in zs]
    assert all(r2 > r1 for r1, r2 in zip(rhos, rhos[1:])), rhos    # monotone up
    assert 0.0 < rhos[0] and rhos[-1] < 0.5                        # bounded (rho<1/2)
    for z in [0.05, 0.2]:
        r4, r5, r6 = density(z, 4), density(z, 5), density(z, 6)
        assert abs(r4 - r6) < 1e-3 and abs(r5 - r6) < 1e-3, (z, r4, r5, r6)

    # anchor 4: low-activity series -- rho -> z and (rho - z)/z^2 -> -7 as z->0
    # (Baxter's virial series rho = z - 7z^2 + 58z^3 - ...); the width-6 strip
    # reproduces the leading coefficients.
    z = 1e-3
    r = density(z, W=6)
    assert abs(r / z - 1.0) < 1e-2                            # rho ~ z
    assert abs((r - z) / z ** 2 - (-7.0)) < 0.1              # coefficient -7 (+58z)


if __name__ == "__main__":
    oracle_main(compute, {"z": (float, 1.0), "N": (int, 4), "W": (int, 4)})
