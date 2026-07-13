"""Tonks-Girardeau gas oracle: impenetrable bosons in 1D (Bose-Fermi mapping).

    H = -sum_i d^2/dx_i^2 + 2c sum_{i<j} delta(x_i - x_j),   c -> +infinity

the hard-core (gamma = c/n -> infinity) limit of the Lieb-Liniger gas.  In Lieb-
Liniger units (hbar = 1, m = 1/2) the kinetic term is -d^2/dx^2; a general mass m
is carried symbolically below so the free-fermion identities read in physical
units too.

Girardeau's Bose-Fermi mapping [@Girardeau1960]: an impenetrable Bose wavefunction
is the modulus of a free spinless-fermion Slater determinant,
Psi_B = |Psi_F|.  Every LOCAL, permutation-symmetric observable (density,
energy, pair correlation, density-density response) is therefore identical to the
free Fermi gas; the ground state fills a Fermi sea to k_F = pi n, giving

    E/L = (1/2pi) int_{-k_F}^{k_F} (hbar^2 k^2 / 2m) dk = pi^2 hbar^2 n^3 / (6 m),
    E/N = pi^2 hbar^2 n^2 / (6 m).

In Lieb-Liniger units (hbar = 1, m = 1/2) this is E/N = n^2 e with the universal
coefficient

    e = pi^2 / 3,

which is exactly the gamma -> infinity limit of the Lieb-Liniger e(gamma) (checked
here by cross-loading the `lieb-liniger` oracle).

Not scripted (exact but not a closed number): g2(0) = 0 (the mapping forbids two
bosons at the same point, so the pair-correlation contact value vanishes exactly);
and the momentum distribution n(k), which -- unlike energy or density -- is NOT a
local observable and so is NOT the free-fermion step function: it develops a
1/|k| tail near k_F and a characteristic 1/sqrt(k) singularity, an interaction
signature computable only from the reduced density matrix (Lenard).
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402

PI = np.pi
LL_UNITS_E = PI ** 2 / 3.0  # e = pi^2/3 (hbar = 1, m = 1/2)


def compute(n=1.0, m=0.5, hbar=1.0):
    """Tonks-Girardeau (impenetrable-boson) energies via the free-fermion mapping."""
    k_F = PI * n
    E_over_L = PI ** 2 * hbar ** 2 * n ** 3 / (6.0 * m)
    E_over_N = PI ** 2 * hbar ** 2 * n ** 2 / (6.0 * m)
    return {
        "k_F": float(k_F),                       # pi n
        "E_over_L": float(E_over_L),             # pi^2 hbar^2 n^3 / (6 m)
        "E_over_N": float(E_over_N),             # pi^2 hbar^2 n^2 / (6 m)
        "e_ll_units": float(LL_UNITS_E),         # E/N = n^2 e; e = pi^2/3
        "g2_zero": 0.0,                          # exact: no two bosons coincide
    }


def _load_lieb_liniger():
    path = Path(__file__).resolve().parents[1] / "lieb-liniger" / "oracle.py"
    spec = importlib.util.spec_from_file_location("oracle_lieb_liniger", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def self_test():
    r = compute(n=1.0, m=0.5, hbar=1.0)

    # anchor 1: the three free-fermion arithmetic identities (m = 1/2, hbar = 1).
    assert abs(r["k_F"] - PI) < 1e-12
    assert abs(r["E_over_L"] - PI ** 2 / 3.0) < 1e-12   # n^3 = 1
    assert abs(r["E_over_N"] - PI ** 2 / 3.0) < 1e-12   # n^2 = 1
    assert abs(r["e_ll_units"] - PI ** 2 / 3.0) < 1e-12

    # anchor 2: general-mass / general-density scaling is internally consistent:
    #   E/L = n * E/N, and E/N = pi^2 hbar^2 n^2 / (6 m).
    r2 = compute(n=2.3, m=0.75, hbar=1.4)
    assert abs(r2["E_over_L"] - 2.3 * r2["E_over_N"]) < 1e-12
    assert abs(r2["E_over_N"] - PI ** 2 * 1.4 ** 2 * 2.3 ** 2 / (6.0 * 0.75)) < 1e-12

    # anchor 3 (CROSS-CARD): e = pi^2/3 equals the gamma -> infinity limit of the
    # Lieb-Liniger e(gamma).  Import the sibling oracle rather than duplicate it;
    # at gamma = 1000 the Lieb value sits within the O(4/gamma) correction band.
    ll = _load_lieb_liniger()
    e_ll = ll.e_of_gamma(1000.0)
    assert abs(e_ll - LL_UNITS_E) / LL_UNITS_E < 5e-3, (e_ll, LL_UNITS_E)
    # exact identity in the strict limit (Tonks value is literally e(inf)):
    assert abs(r["e_ll_units"] - ll.TONKS_E) < 1e-12

    # anchor 4: g2(0) = 0 exactly (Bose-Fermi mapping contact value).
    assert r["g2_zero"] == 0.0


if __name__ == "__main__":
    oracle_main(compute, {"n": (float, 1.0), "m": (float, 0.5), "hbar": (float, 1.0)})
