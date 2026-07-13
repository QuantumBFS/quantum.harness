"""TFIM chain oracle: H = -J sum sz_i sz_{i+1} - h sum sx_i  (PAULI matrices, PBC).

JW solution: eps(k) = 2 sqrt(J^2 - 2 J h cos k + h^2); ground state in the
even-parity sector uses antiperiodic momenta k = pi(2n+1)/L.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.special import ellipe

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed  # noqa: E402


def eps(k, J, h):
    return 2.0 * np.sqrt(J * J - 2 * J * h * np.cos(k) + h * h)


def e0_finite(L, J, h):
    """Ground-state energy per site at finite L (PBC spin chain, ABC fermions)."""
    k = np.pi * (2 * np.arange(L) + 1) / L
    return -0.5 * eps(k, J, h).sum() / L


def e0_thermo(J, h):
    """L -> inf: e0 = -(2/pi)(J+h) E(m), m = 4Jh/(J+h)^2."""
    m = 4 * J * h / (J + h) ** 2
    return -(2 / np.pi) * (J + h) * ellipe(m)


def mx_thermo(J, h, dh=1e-5):
    """Transverse magnetization <sx> = -d e0/d h (numerical derivative)."""
    return -(e0_thermo(J, h + dh) - e0_thermo(J, h - dh)) / (2 * dh)


def compute(L=16, h=1.0, J=1.0):
    """TFIM chain exact quantities via Jordan–Wigner."""
    return {
        "e0_per_site": e0_finite(L, J, h),
        "e0_thermodynamic": e0_thermo(J, h),
        "gap_single_fermion": 2.0 * abs(J - h),
        "mx": mx_thermo(J, h),
    }


def self_test():
    # anchor 1: critical point closed form e0 = -4/pi
    assert abs(e0_thermo(1.0, 1.0) + 4 / np.pi) < 1e-12
    # anchor 2: JW finite-L energy == brute-force ED, L = 8 and 10
    for L, h in [(8, 0.5), (8, 1.0), (10, 1.3)]:
        px, _, pz = ed.pauli_ops(L)
        H = -sum(pz[i] @ pz[(i + 1) % L] for i in range(L)) - h * sum(px)
        assert abs(ed.ground_energy(H) / L - e0_finite(L, 1.0, h)) < 1e-10, (L, h)
    # anchor 3: gap closes at criticality, opens linearly
    assert compute(h=1.0)["gap_single_fermion"] == 0.0
    assert abs(compute(h=1.5)["gap_single_fermion"] - 1.0) < 1e-12


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 16), "h": (float, 1.0), "J": (float, 1.0)})
