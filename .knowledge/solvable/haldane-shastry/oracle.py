"""Haldane–Shastry chain oracle: H = J sum_{i<j} S_i . S_j / d_ij^2  (S=sigma/2, J=1).

T3 (Bethe ansatz / Yang–Baxter, Yangian). The 1/r^2 exchange uses the chord
distance d_ij = (N/pi)|sin(pi(i-j)/N)| on the N-site ring, so the coupling is
J (pi/N)^2 / sin^2(pi(i-j)/N). The finite-N ground state is the Gutzwiller-
projected filled Fermi sea; its energy is the *closed form*
    E0(N) = -J (pi^2/24) (N + 5/N),
verified here against dense ED at N in {6, 8, 10} to 1e-10. Per site this is
e0(N) = -(pi^2/24)(1 + 5/N^2), which decreases to the thermodynamic constant
e0_thermodynamic = -pi^2/24 as N -> inf.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed  # noqa: E402

E0_THERMO = -(np.pi ** 2) / 24.0  # -0.41123351671... exact GS energy per site, N->inf


def e0_total(N, J=1.0):
    """Closed-form finite-N ground-state energy E0(N) = -J(pi^2/24)(N + 5/N)."""
    return -J * (np.pi ** 2 / 24.0) * (N + 5.0 / N)


def e0_per_site(N, J=1.0):
    """Closed-form ground energy per site, e0(N) = -J(pi^2/24)(1 + 5/N^2)."""
    return e0_total(N, J) / N


def hs_hamiltonian(N, J=1.0):
    """Dense-ED Hamiltonian with 1/r^2 chord-distance exchange (ground truth)."""
    sx, sy, sz = ed.spin_ops(N)
    H = 0
    for i in range(N):
        for j in range(i + 1, N):
            d = (N / np.pi) * abs(np.sin(np.pi * (i - j) / N))
            coup = J / d ** 2
            H = H + coup * (sx[i] @ sx[j] + sy[i] @ sy[j] + sz[i] @ sz[j])
    return H


def compute(N=12):
    """Haldane–Shastry 1/r^2 chain exact ground-state energetics (closed form)."""
    return {
        "e0_per_site": e0_per_site(N),
        "e0_thermodynamic": E0_THERMO,
    }


def self_test():
    # anchor 1 (GROUND TRUTH): closed form == dense ED at N in {6, 8, 10}, tol 1e-10.
    for N in (6, 8, 10):
        assert abs(e0_total(N) - ed.ground_energy(hs_hamiltonian(N))) < 1e-10

    # anchor 2: N -> inf consistency — e0(N=1e4) reaches -pi^2/24 within 1e-6.
    assert abs(e0_per_site(10 ** 4) - E0_THERMO) < 1e-6

    # anchor 3: the thermodynamic constant is the literal -pi^2/24.
    assert abs(compute()["e0_thermodynamic"] - (-(np.pi ** 2) / 24.0)) < 1e-15


if __name__ == "__main__":
    oracle_main(compute, {"N": (int, 12)})
