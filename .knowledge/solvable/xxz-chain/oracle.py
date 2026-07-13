"""XXZ chain oracle: H = J sum_i (Sx Sx + Sy Sy + Delta Sz Sz)  (S=sigma/2, J=1, PBC).

T3 (Bethe ansatz / Yang-Baxter). The ground-state energy per site in the
thermodynamic limit is exactly known in three regimes (Yang & Yang 1966):

  * Delta = 1 (isotropic Heisenberg):  e0 = 1/4 - ln 2.
  * -1 < Delta < 1 (gapless Luttinger liquid, Delta = cos gamma):
        e0 = cos(gamma)/4 - sin^2(gamma) * INT_{-inf}^{inf}
                 dx / [ 2 cosh(pi x) ( cosh(2 gamma x) - cos gamma ) ].
    Pins: Delta=0 -> -1/pi ; Delta->1- -> 1/4 - ln 2.
  * Delta > 1 (gapped Ising-Neel AFM, Delta = cosh eta):
        e0 = cosh(eta)/4 - sinh(eta) ( 1/2 + 2 SUM_{n>=1} 1/(1 + e^{2 n eta}) ).
    Pins: continuity with the |Delta|<1 branch at Delta=1 ; Delta->inf -> -Delta/4.

Spin gap (Delta > 1, Delta = cosh eta) -- des Cloizeaux & Gaudin 1966:
        gap = sinh(eta) ( 1 + 2 SUM_{n>=1} (-1)^n / cosh(n eta) ).
    Pins: gap(Delta->1+) -> 0 (essential singularity) ; gap -> Delta - 2 (Delta->inf).
    Gapless for -1 < Delta <= 1 (reported as 0).

All formulas are for J=1, S = sigma/2 -- the same convention and the same
-1/pi and 1/4-ln2 anchors as .knowledge/models/xxz-chain/MODEL.md.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import quad

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402

E0_XXX = 0.25 - np.log(2.0)  # exact isotropic (Delta=1) value


def _e0_critical(Delta):
    """|Delta|<1 gapless-regime ground energy per site (Delta = cos gamma)."""
    g = np.arccos(Delta)
    # integrand decays like exp(-pi|x|); [-40,40] is exact to machine precision
    # and avoids cosh() overflow.
    integrand = lambda x: 1.0 / (2 * np.cosh(np.pi * x)
                                 * (np.cosh(2 * g * x) - np.cos(g)))
    I, _ = quad(integrand, -40.0, 40.0, limit=400)
    return np.cos(g) / 4.0 - np.sin(g) ** 2 * I


def _e0_neel(Delta):
    """Delta>1 gapped-regime ground energy per site (Delta = cosh eta)."""
    eta = np.arccosh(Delta)
    nmax = int(40.0 / eta) + 50          # term ~ e^{-2 n eta}; converge to <1e-17
    n = np.arange(1, nmax + 1)
    s = np.sum(1.0 / (1.0 + np.exp(np.clip(2 * n * eta, 0.0, 700.0))))
    return np.cosh(eta) / 4.0 - np.sinh(eta) * (0.5 + 2.0 * s)


def e0(Delta):
    """Thermodynamic-limit ground-state energy per site, all regimes."""
    if abs(Delta - 1.0) < 1e-12:
        return E0_XXX
    if Delta < -1.0:
        return Delta / 4.0               # fully polarized ferromagnet
    if Delta < 1.0:
        return _e0_critical(Delta)
    return _e0_neel(Delta)


def gap(Delta):
    """Thermodynamic spin gap. Zero for -1 < Delta <= 1; Neel form for Delta > 1."""
    if Delta <= 1.0:
        return 0.0
    eta = np.arccosh(Delta)
    nmax = int(45.0 / eta) + 50
    n = np.arange(1, nmax + 1)
    s = np.sum(((-1.0) ** n) / np.cosh(np.clip(n * eta, 0.0, 700.0)))
    return np.sinh(eta) * (1.0 + 2.0 * s)


def compute(Delta=1.0):
    """XXZ-chain exact thermodynamic-limit quantities via the Bethe ansatz."""
    return {
        "delta": Delta,
        "e0_per_site": e0(Delta),
        "gap": gap(Delta),
    }


def self_test():
    # --- e0: the three exactly-known anchor points -----------------------
    assert abs(e0(0.0) + 1.0 / np.pi) < 1e-8            # XX free-fermion point
    assert abs(e0(1.0) - E0_XXX) < 1e-15                # isotropic literal
    assert abs(e0(1 - 1e-8) - E0_XXX) < 1e-7            # critical branch -> XXX
    # Neel branch continuity across Delta=1 (both sides within 1e-5)
    assert abs(_e0_neel(1 + 1e-6) - _e0_critical(1 - 1e-6)) < 1e-5
    # Delta -> inf Neel asymptote e0 -> -Delta/4 (ratio -> 1 within 2%)
    assert abs(e0(50.0) / (-50.0 / 4.0) - 1.0) < 0.02

    # --- gap: analytic pins ----------------------------------------------
    assert gap(1.001) < 1e-3                            # essential singularity
    assert gap(1.0) == 0.0                              # gapless critical point
    # large-Delta asymptote gap -> Delta - 2 (ratio -> 1 by Delta=20)
    assert abs(gap(20.0) / (20.0 - 2.0) - 1.0) < 0.01

    # --- ED brackets: finite-L energies approach e0(Delta) monotonically -
    # (finite-size correction is NEGATIVE here: PBC rings sit below the
    #  thermodynamic value and rise toward it as L grows.)
    from _lib import ed
    for D in (0.5, 2.0):
        thermo = e0(D)
        prev = -np.inf
        for L in (8, 10, 12):
            sx, sy, sz = ed.spin_ops(L)
            H = sum(sx[i] @ sx[(i + 1) % L] + sy[i] @ sy[(i + 1) % L]
                    + D * sz[i] @ sz[(i + 1) % L] for i in range(L))
            e = ed.ground_energy(H) / L
            assert e < thermo, (D, L, e, thermo)      # below thermodynamic
            assert e > prev, (D, L, e, prev)          # monotone increasing in L
            prev = e
        assert abs(e - thermo) / abs(thermo) < 0.02   # L=12 within 2%


if __name__ == "__main__":
    oracle_main(compute, {"Delta": (float, 1.0)})
