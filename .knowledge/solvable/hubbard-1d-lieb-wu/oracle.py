"""1D Hubbard chain oracle (Lieb–Wu): H = -t Σ_{iσ}(c†_{iσ}c_{i+1σ}+h.c.) + U Σ_i n_{i↑}n_{i↓}.

T3 (Bethe ansatz / Lieb–Wu). Half filling, t=1, thermodynamic limit. The exact
ground-state energy per site is the Lieb–Wu integral
    e0(U) = -4 ∫_0^∞ dω J0(ω)J1(ω) / (ω (1 + e^{ωU/2})),
the Mott charge gap is
    Δ(U) = U - 4 + 8 ∫_0^∞ dω J1(ω) / (ω (1 + e^{ωU/2})),
and both are cross-checked against a two-species Jordan–Wigner ED at L=6.

The Lieb–Wu integrand decays only as 1/ω² and oscillates as cos(2ω) at U=0
(the exp-damping vanishes), so a plain quad to ∞ loses accuracy there; e0() sums
the integral over whole cos(2ω)-periods (per-period cancellation → 1/N² tail) and
Richardson-extrapolates. For U>0 the exponential tail makes a direct quad exact,
which self_test uses as the independent second strategy.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.special import j0, j1

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed  # noqa: E402

E0_FREE = -4.0 / np.pi  # e0(U=0): two half-filled free-fermion bands, exact


def _damp(w, U):
    """1 / (1 + e^{wU/2}), overflow-safe."""
    z = w * U / 2.0
    return np.where(z < 700.0, 1.0 / (1.0 + np.exp(np.clip(z, 0.0, 700.0))), 0.0)


def _e0_integrand(w, U):
    return j0(w) * j1(w) / w * _damp(w, U)


def e0(U, nseg=200, npts=60):
    """Lieb–Wu ground energy per site — period-segmented + Richardson (robust at U=0)."""
    period = np.pi  # cos(2ω) has period π; per-period cancellation gives a 1/N² tail
    seg = [quad(_e0_integrand, n * period, (n + 1) * period, args=(U,), limit=60)[0]
           for n in range(nseg)]
    partial = np.cumsum(seg)                    # partial sums P_N ≈ P_∞ + c/N² + d/N³
    Ns = np.arange(1, nseg + 1, dtype=float)
    x = 1.0 / Ns[-npts:]
    A = np.vstack([np.ones_like(x), x ** 2, x ** 3]).T
    coef, *_ = np.linalg.lstsq(A, partial[-npts:], rcond=None)
    return -4.0 * float(coef[0])                # intercept = P_∞


def e0_quad(U):
    """Independent strategy: direct quad to ∞ (exact for U>0, weak at U=0)."""
    val, _ = quad(_e0_integrand, 0.0, np.inf, args=(U,), limit=400)
    return -4.0 * val


def mott_gap(U):
    """Mott charge gap Δ(U) = U - 4 + 8 ∫_0^∞ J1(ω)/(ω(1+e^{ωU/2})) dω (t=1)."""
    val, _ = quad(lambda w: j1(w) / w * _damp(w, U), 0.0, np.inf, limit=400)
    return U - 4.0 + 8.0 * val


# -------------------- two-species Jordan–Wigner ED (ground truth) --------------------

def _hubbard_ed_H(L, t, U):
    """Spinful Hubbard on an L-site PBC ring as a 2L-site JW chain.

    Site ordering (0↑ … (L-1)↑, 0↓ … (L-1)↓): each spin lives in its own length-L
    JW block, so intra-species hops telescope to the standard form and the boundary
    bond reproduces PBC free fermions in the odd-N sector (validated at U=0). The
    number operators are string-free, so the U-term is a simple product.
    """
    c, cd = ed.fermion_ops(2 * L)
    n = [cd[k] @ c[k] for k in range(2 * L)]

    def up(i):
        return i

    def dn(i):
        return L + i

    H = 0
    for i in range(L):
        j = (i + 1) % L
        for site in (up, dn):
            a, b = site(i), site(j)
            H = H - t * (cd[a] @ c[b] + cd[b] @ c[a])
    for i in range(L):
        H = H + U * (n[up(i)] @ n[dn(i)])
    return H.tocsr(), n, up, dn


def hubbard_ed_energy(L, U, t=1.0):
    """Ground energy in the half-filled (N↑=N↓=L/2) sector via dense sector ED."""
    H, n, up, dn = _hubbard_ed_H(L, t, U)
    nup = np.array(sum(n[up(i)] for i in range(L)).diagonal()).real
    ndn = np.array(sum(n[dn(i)] for i in range(L)).diagonal()).real
    half = L // 2
    idx = np.where((np.round(nup) == half) & (np.round(ndn) == half))[0]
    sub = H[np.ix_(idx, idx)].toarray()
    return float(np.linalg.eigvalsh(sub)[0])


def _free_fermion_pbc(L, N):
    """Sum of the N lowest single-particle energies of an L-site tight-binding ring."""
    eps = np.sort([-2.0 * np.cos(2.0 * np.pi * m / L) for m in range(L)])
    return float(np.sum(eps[:N]))


def compute(U=4.0):
    """1D Hubbard chain (Lieb–Wu) exact half-filling quantities, t=1."""
    return {
        "e0_thermodynamic": e0(U),
        "mott_gap": mott_gap(U),
        "e0_strong_coupling_asymptote": -4.0 * np.log(2.0) / U,
        "e0_ed_per_site_L6": hubbard_ed_energy(6, U) / 6.0,
    }


def self_test():
    # anchor 1 (GROUND TRUTH): two-species JW ED at U=0 == exact free-fermion energy.
    #   L=6, N↑=N↓=3 (odd) -> the JW ring reproduces PBC free fermions exactly.
    e_ed0 = hubbard_ed_energy(6, 0.0)
    e_ff0 = 2.0 * _free_fermion_pbc(6, 3)          # two spin species
    assert abs(e_ed0 - e_ff0) < 1e-10
    assert abs(e_ff0 - (-8.0)) < 1e-10             # 2 × (-2 -1 -1)

    # anchor 2: e0(0) = -4/π to 1e-8 (period-segmented + Richardson; the plain quad
    #   only reaches ~1e-5 at U=0, which is why the segmented strategy exists).
    assert abs(e0(0.0) - E0_FREE) < 1e-8

    # anchor 3: two independent quadrature strategies agree to 1e-8 for U>0.
    for U in (1.0, 4.0, 8.0):
        assert abs(e0(U) - e0_quad(U)) < 1e-8

    # anchor 4: e0(U) is monotone increasing in U.
    Us = np.linspace(0.5, 16.0, 12)
    es = [e0_quad(u) for u in Us]
    assert all(np.diff(es) > 0)

    # anchor 5: strong-coupling (effective-Heisenberg) limit e0 → -4 ln2 / U.
    assert abs(e0_quad(64.0) / (-4.0 * np.log(2.0) / 64.0) - 1.0) < 0.05

    # anchor 6: Mott gap opens for any U>0. Δ(1) exponentially small (<0.01);
    #   Δ(U→∞) → U - 4 (ratio → 1 within 2% at U=64); Δ closes at U=0.
    assert mott_gap(1.0) < 0.01
    assert mott_gap(0.5) < 1e-3
    assert abs(mott_gap(64.0) / (64.0 - 4.0) - 1.0) < 0.02
    assert mott_gap(4.0) > mott_gap(2.0) > mott_gap(1.0)  # monotone increasing

    # anchor 7: L=6 half-filled ED bracket at U=4. The finite PBC ring sits *below*
    #   the thermodynamic e0(4) (closed-shell 6-ring over-binds); documented band.
    e_thermo4 = e0(4.0)                            # ≈ -0.573729
    e_ed4 = hubbard_ed_energy(6, 4.0) / 6.0        # ≈ -0.611451 (PBC, L=6)
    assert e_thermo4 - 0.06 < e_ed4 < e_thermo4 + 0.005


if __name__ == "__main__":
    oracle_main(compute, {"U": (float, 4.0)})
