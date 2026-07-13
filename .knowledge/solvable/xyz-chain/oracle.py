"""XYZ chain oracle: H = sum_i [Jx Sx_i Sx_{i+1} + Jy Sy_i Sy_{i+1} + Jz Sz_i Sz_{i+1}].

S = sigma/2 spin-1/2 operators, PBC. This is Baxter's eight-vertex / anisotropic
Heisenberg chain (T3, Yang-Baxter integrable). Its thermodynamic ground-state
energy per site is exactly known in closed form (Baxter 1972, Ann. Phys. 70,
323) as an elliptic-function expression -- TABULATED in ORACLE.md, not coded
here (see the P-scope note below).

Script scope (P). What this script provides:

  * EXACT closed-form e0 in the two integrable *limits*, delegated by importlib
    to the sibling oracle cards (no duplicated physics):
      - XXZ limit (two of the three couplings equal): with in-plane pair value
        `a` and odd coupling `c`, e0 = |a| * xxz.e0(c/|a|). The XXZ card owns the
        Yang-Yang integral/series for e0(Delta).
      - XY limit (one coupling zero): the two non-zero couplings (p, q) map to the
        xy-chain parametrization H = J[(1+g) SxSx + (1-g) SySy] via J=(p+q)/2,
        g=(p-q)/(p+q); e0 is the exact free-fermion value from xy-chain.compute.
  * The GENERIC point (all three couplings distinct and non-zero) is NOT shipped
    in closed form here: it is a finite-L ED-extrapolated estimate (1/L^2
    Richardson over L in {8,10,12}), explicitly labelled non-closed-form. The
    exact statement for the generic point is Baxter's elliptic formula, tabulated
    in the card. (P-scope choice: ED-extrapolation shipped, Baxter tabulated --
    NOT a half-coded parametrization.)

Symmetries used as cheap exact self-tests (both are exact unitary equivalences on
an even-L bipartite ring): e0 is invariant under (a) any permutation of
(Jx,Jy,Jz) -- a global pi/2 spin rotation relabelling axes -- and (b) a
simultaneous sign flip of any two couplings -- a pi rotation about the third axis
on one sublattice.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
from scipy.sparse.linalg import eigsh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed  # noqa: E402

_REL = 1e-9   # relative tolerance for detecting an exact limit (coupling equal/zero)
_XY_L = 1000  # chain length for the XY-line free-fermion delegation (O(1/L^2) -> ~2.5e-7)


def _load(slug):
    """Importlib cross-load a sibling oracle card by absolute path (no duplication)."""
    path = Path(__file__).resolve().parents[1] / slug / "oracle.py"
    spec = importlib.util.spec_from_file_location(f"oracle_{slug.replace('-', '_')}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ed_energy(Jx, Jy, Jz, L):
    """Brute-force ED ground energy per site of the XYZ Hamiltonian (PBC, S=sigma/2).

    Dense `eigvalsh` for L<=10 (exact, machine precision); sparse Lanczos ground
    state for larger L (dense all-eigenvalue solve of the 4096-dim L=12 block is
    ~100x slower and unnecessary -- only the ground energy is needed).
    """
    sx, sy, sz = ed.spin_ops(L)
    H = sum(Jx * sx[i] @ sx[(i + 1) % L]
            + Jy * sy[i] @ sy[(i + 1) % L]
            + Jz * sz[i] @ sz[(i + 1) % L] for i in range(L)).tocsr()
    if H.shape[0] > 1024:
        return float(eigsh(H, k=1, which="SA", return_eigenvectors=False)[0]) / L
    return ed.ground_energy(H) / L


def _classify(Jx, Jy, Jz):
    """Return ('xxz', a, delta) | ('xy', J, gamma) | ('generic', None, None).

    XXZ limit: two couplings equal (in-plane pair `a`, odd coupling `c`); reduced
    to positive in-plane via the two-sign-flip symmetry, delta = c/|a|.
    XY limit: one coupling zero; the two non-zero (p, q) give J=(p+q)/2 (positive
    via two-sign-flip), gamma=(p-q)/(p+q) (xy e0 is even in gamma).
    """
    J = (Jx, Jy, Jz)
    scale = max(abs(v) for v in J) or 1.0
    # XY limit: some coupling is (numerically) zero
    for i in range(3):
        if abs(J[i]) <= _REL * scale:
            p, q = (J[(i + 1) % 3], J[(i + 2) % 3])
            if abs(p) <= _REL * scale or abs(q) <= _REL * scale:
                break  # a second coupling is zero too -> not an XY chain; fall through
            s = p + q
            if abs(s) <= _REL * scale:
                break  # p = -q: isotropic-plane cancellation, fall through to generic
            Jcoup = abs(s) / 2.0
            gamma = (p - q) / s
            return ("xy", Jcoup, gamma)
    # XXZ limit: two couplings equal
    for i in range(3):
        a, b, c = J[i], J[(i + 1) % 3], J[(i + 2) % 3]
        if abs(a - b) <= _REL * scale:
            if abs(a) <= _REL * scale:
                continue
            return ("xxz", abs(a), c / abs(a))
    return ("generic", None, None)


def e0_exact(Jx, Jy, Jz):
    """Exact thermodynamic e0 in an integrable limit; raises ValueError if generic."""
    kind, u, v = _classify(Jx, Jy, Jz)
    if kind == "xxz":
        return u * _load("xxz-chain").e0(v)
    if kind == "xy":
        return _load("xy-chain").compute(L=_XY_L, gamma=v, h=0.0, J=u)["e0_per_site"]
    raise ValueError("generic point has no closed form in this card; see Baxter (1972)")


def _e0_extrap(Jx, Jy, Jz, Ls=(8, 10, 12)):
    """1/L^2 Richardson extrapolation of the ED per-site energy (generic point)."""
    es = [_ed_energy(Jx, Jy, Jz, L) for L in Ls]
    x = np.array([1.0 / L ** 2 for L in Ls])
    return float(np.polyfit(x, es, 1)[1])  # intercept = L -> inf estimate


def e0(Jx, Jy, Jz):
    """Thermodynamic ground energy per site: exact in a limit, ED-extrapolated else."""
    kind, _, _ = _classify(Jx, Jy, Jz)
    if kind == "generic":
        return _e0_extrap(Jx, Jy, Jz)
    return e0_exact(Jx, Jy, Jz)


def compute(Jx=1.0, Jy=1.0, Jz=1.0, L=10):
    """XYZ-chain ground energy: exact in the XXZ/XY limits, ED-extrapolated generic."""
    kind, _, _ = _classify(Jx, Jy, Jz)
    method = {"xxz": "exact (XXZ limit, via xxz-chain)",
              "xy": "exact (XY limit, via xy-chain)",
              "generic": "ED-extrapolated (1/L^2, L in 8,10,12); Baxter formula tabulated"}[kind]
    return {
        "jx": Jx, "jy": Jy, "jz": Jz,
        "e0_per_site": e0(Jx, Jy, Jz),
        "e0_ed_finite": _ed_energy(Jx, Jy, Jz, L),
        "L": L,
        "method": method,
    }


def self_test():
    xxz = _load("xxz-chain")
    xy = _load("xy-chain")

    # (i) XXZ limit -- e0(1,1,Delta) reproduces xxz-chain's e0(Delta) to 1e-8.
    for D in (0.5, 2.0):
        assert abs(e0(1.0, 1.0, D) - xxz.e0(D)) < 1e-8, (D, e0(1.0, 1.0, D), xxz.e0(D))

    # (ii) XY limit -- Jz=0 reproduces xy-chain via J=(Jx+Jy)/2, gamma=(Jx-Jy)/(Jx+Jy).
    for Jx, Jy in [(1.4, 0.6), (1.0, 0.5)]:
        Jc = (Jx + Jy) / 2.0
        g = (Jx - Jy) / (Jx + Jy)
        # thermodynamic value agrees with the xy-chain card (same L -> exact identity)
        assert abs(e0(Jx, Jy, 0.0)
                   - xy.compute(L=_XY_L, gamma=g, h=0.0, J=Jc)["e0_per_site"]) < 1e-12, (Jx, Jy)
        # finite-L Hamiltonian identity: XYZ(Jz=0) ED == xy-chain ED at same L (dictionary check)
        assert abs(_ed_energy(Jx, Jy, 0.0, 8)
                   - xy.compute(L=8, gamma=g, h=0.0, J=Jc)["e0_per_site"]) < 1e-10, (Jx, Jy)

    # (iii) generic point -- ED cross-check at L=10 against the shipped evaluator.
    for Jx, Jy, Jz in [(1.0, 0.7, 0.4), (1.0, 0.8, 0.6)]:
        est = e0(Jx, Jy, Jz)                       # ED-extrapolated thermodynamic estimate
        ed10 = _ed_energy(Jx, Jy, Jz, 10)          # direct L=10 ground truth
        assert abs(est - ed10) < 0.05 * abs(ed10), (Jx, Jy, Jz, est, ed10)

    # (iv) permutation symmetry -- e0 invariant under axis relabelling (exact, 1e-9).
    base = _ed_energy(1.0, 0.7, 0.4, 8)
    assert abs(_ed_energy(0.7, 1.0, 0.4, 8) - base) < 1e-9   # swap Jx<->Jy
    assert abs(_ed_energy(0.4, 0.7, 1.0, 8) - base) < 1e-9   # swap Jx<->Jz

    # (v) two-sign-flip symmetry -- e0 invariant under simultaneous sign flip of two
    #     couplings (unitary equivalence on the even-L bipartite ring).
    assert abs(_ed_energy(-1.0, -0.7, 0.4, 8) - base) < 1e-9  # flip Jx,Jy
    assert abs(_ed_energy(1.0, -0.7, -0.4, 8) - base) < 1e-9  # flip Jy,Jz


if __name__ == "__main__":
    oracle_main(compute, {"Jx": (float, 1.0), "Jy": (float, 1.0),
                          "Jz": (float, 1.0), "L": (int, 10)})
