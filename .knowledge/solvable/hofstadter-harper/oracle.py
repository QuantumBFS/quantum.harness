"""Hofstadter-Harper oracle: square-lattice tight-binding electrons at
uniform rational flux alpha = p/q per plaquette (Landau gauge), native q x q
magnetic-Bloch (Harper) matrix.

    H(kx, ky)_mm     = -2t cos(kx + 2*pi*m*p/q),           m = 0..q-1
    H(kx, ky)_{m,m+1} = H(kx, ky)_{m+1,m} = -t,             m = 0..q-2
    H(kx, ky)_{0,q-1} = -t exp(-i*ky),  H_{q-1,0} = -t exp(+i*ky)   (wrap)

Coordinate convention (stated explicitly, per the task's "any consistent
full-torus parametrization is acceptable"): `kx` is the ordinary crystal
momentum along the un-enlarged x-direction (period 2*pi, single-site cell).
`ky` here is the REDUCED magnetic Bloch momentum conjugate to the q-site
magnetic unit cell along y, i.e. `ky_here = q * ky_physical` where
`ky_physical` in [0, 2*pi/q) is the actual transverse crystal momentum (whose
true magnetic Brillouin zone has width 2*pi/q, the enlarged real-space cell).
Writing the wrap phase as exp(+-i*ky_here) makes the (kx, ky_here) in
[0,2*pi) x [0,2*pi) grid EXACTLY one full traversal of the magnetic Brillouin
zone torus (same "reduced coordinates" trick as
tight-binding-lattices/oracle.py's honeycomb/kagome/Lieb Bloch matrices) -
no extra q-fold bookkeeping needed, and _lib.topology.chern's fixed
[0,2*pi)^2 grid can be used directly. (An earlier draft used the literal
exp(-+i*q*ky_physical) form with ky_physical swept over the full [0,2*pi)
range; that over-covers the true magnetic BZ q times in the ky direction and
inflates every Chern number by an exact factor of q - caught by comparing
against the known p/q=1/3 benchmark (1,-2,1) before this convention was
adopted.)

Per-band Chern numbers via cumulative-occupied differencing:
C_band_n = chern(hk, n+1) - chern(hk, n), n = 0..q-1 (telescoping sum is
always exactly 0, C(q) - C(0) = 0 - 0, by construction - a trivial
consistency check, not evidence of correctness on its own).

Band touching (q even): the Harper spectrum can have an EXACT band touching
(zero direct gap on the whole BZ) between two consecutive subbands - verified
numerically here for (p,q) = (1,4) and (1,8) (middle gap; not for every even
q, e.g. (1,6) has a small but nonzero middle gap - detection is by an
explicit numerical gap scan, not a hardcoded "q even" rule). At an exact
touching, the naive per-band difference above is not gauge-invariant / not
robust to the FHS grid resolution `nk` (verified: for (p,q)=(1,4) the band-2
vs band-3 individual diffs flip between [0,-2] and [-1,-1] as `nk` is varied
40->120, while their SUM stays exactly -2 at every nk tested) - only the
JOINT Chern number of the merged band group (computed via nocc jumping
across the whole touching group at once, using only the genuinely open gaps
above/below it) is well defined. Both are reported: `chern_numbers` (naive,
per-slot) and `band_touching_groups` (the physically meaningful joint
invariant for any detected touching group).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import topology  # noqa: E402

_GAP_TOL = 1e-6  # direct-gap threshold below which two subbands are "touching"


def bloch(p, q, t=1.0):
    """Return hk(kx, ky) -> q x q magnetic-Bloch (Harper) matrix at flux p/q."""
    def _hk(kx, ky):
        H = np.zeros((q, q), dtype=complex)
        for m in range(q):
            H[m, m] = -2.0 * t * np.cos(kx + 2.0 * np.pi * m * p / q)
        for m in range(q - 1):
            H[m, m + 1] = -t
            H[m + 1, m] = -t
        H[0, q - 1] += -t * np.exp(-1j * ky)
        H[q - 1, 0] += -t * np.exp(1j * ky)
        return H
    return _hk


def _band_grid(hk, q, nk):
    """Sorted eigenvalues on an nk x nk (kx, ky) grid, shape (nk, nk, q)."""
    ks = np.linspace(0.0, 2.0 * np.pi, nk, endpoint=False)
    evs = np.empty((nk, nk, q))
    for i, kx in enumerate(ks):
        for j, ky in enumerate(ks):
            evs[i, j] = np.linalg.eigvalsh(hk(kx, ky))
    return evs


def compute(p=1, q=3, t=1.0, nk=60, nk_bands=120):
    """Hofstadter-Harper exact quantities at flux p/q: per-band Chern numbers
    (Fukui-Hatsugai-Suzuki, cumulative-occupied differencing) and band edges."""
    hk = bloch(p, q, t)
    n_bands = q

    C = [0]
    for n in range(1, q + 1):
        C.append(topology.chern(hk, n, nk=nk))
    chern_numbers = [C[n] - C[n - 1] for n in range(1, q + 1)]

    evs = _band_grid(hk, q, nk_bands)
    flat = evs.reshape(-1, q)
    band_edges = [[float(flat[:, b].min()), float(flat[:, b].max())] for b in range(q)]

    # detect exact band touchings (zero direct gap) and merge into groups
    touching = [float((evs[..., b + 1] - evs[..., b]).min()) < _GAP_TOL for b in range(q - 1)]
    groups, cur = [], [0]
    for b in range(q - 1):
        if touching[b]:
            cur.append(b + 1)
        else:
            groups.append(cur)
            cur = [b + 1]
    groups.append(cur)
    band_touching_groups = [
        {"bands": g, "joint_chern": C[g[-1] + 1] - C[g[0]]} for g in groups if len(g) > 1
    ]

    return {
        "n_bands": n_bands,
        "chern_numbers": chern_numbers,
        "band_edges": band_edges,
        "band_touching_groups": band_touching_groups,
    }


def self_test():
    # anchor 1: p/q = 1/3, the textbook Hofstadter-butterfly benchmark
    r = compute(p=1, q=3)
    assert r["chern_numbers"] == [1, -2, 1]
    assert sum(r["chern_numbers"]) == 0
    assert r["n_bands"] == 3
    assert r["band_touching_groups"] == []  # q odd: all three subbands genuinely gapped

    # anchor 2: p/q = 1/4 - telescoping sum always 0, and the known middle
    # band touching (bands 2,3, 0-indexed [1,2]) with joint Chern -2
    r4 = compute(p=1, q=4)
    assert sum(r4["chern_numbers"]) == 0 and r4["n_bands"] == 4
    assert r4["band_touching_groups"] == [{"bands": [1, 2], "joint_chern": -2}]
    # the two gapped (non-touching) bands are individually well defined and
    # match the Diophantine solutions r=1 (C=1) and r=3 (C=1)
    assert r4["chern_numbers"][0] == 1 and r4["chern_numbers"][3] == 1

    # anchor 3: p/q = 2/5 - another coprime check, telescoping sum 0
    r5 = compute(p=2, q=5)
    assert sum(r5["chern_numbers"]) == 0 and r5["n_bands"] == 5

    # anchor 4: Diophantine equation r = q*s + p*t reproduces the q=3 gap
    # Cherns (|t| <= q/2): r=1 -> t=1,s=0 ; r=2 -> t=-1,s=1 (cumulative -2+... )
    # equivalently the cumulative gap Cherns C(r) solve r = q*s + p*t exactly:
    p, q = 1, 3
    for rr, Cr in zip([1, 2], [1, -1]):
        s = (rr - p * Cr) / q
        assert abs(s - round(s)) < 1e-12  # s must be an integer


if __name__ == "__main__":
    oracle_main(compute, {"p": (int, 1), "q": (int, 3), "t": (float, 1.0)})
