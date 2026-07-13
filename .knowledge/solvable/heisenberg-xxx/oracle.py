"""Heisenberg XXX chain oracle: H = J sum_i S_i . S_{i+1}  (S=sigma/2, J=1, PBC).

T3 (Bethe ansatz / Yang-Baxter). The antiferromagnetic ground state is the
1-string (all-real-roots) Bethe state in the S^z=0 sector; finite-N energies come
from the shared solver `_lib.bethe`, the thermodynamic limit is the closed form
e0 = 1/4 - ln 2, and the spinon velocity is v = pi/2 (J=1, S-convention).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed, bethe  # noqa: E402

E0_THERMO = 0.25 - np.log(2.0)  # -0.4431471805599453..., exact Bethe/Hulthen
SPINON_VELOCITY = np.pi / 2.0   # des Cloizeaux-Pearson, J=1, S-convention


def e0_finite(N):
    """Ground-state energy per site at finite (even) N via the Bethe solver."""
    return bethe.xxx_energy(bethe.xxx_ground_roots(N), N) / N


def e0_extrapolated(sizes=(32, 64, 128)):
    """1/N^2 (Richardson) extrapolation of e0(N) to the thermodynamic limit."""
    e = np.array([e0_finite(N) for N in sizes])
    x = 1.0 / np.array(sizes, dtype=float) ** 2
    A = np.vstack([x, np.ones_like(x)]).T
    coef, *_ = np.linalg.lstsq(A, e, rcond=None)
    return float(coef[1])  # intercept = e0(N -> inf)


def compute(N=12):
    """XXX Heisenberg chain exact quantities via the coordinate Bethe ansatz."""
    return {
        "e0_per_site_finite": e0_finite(N),
        "e0_thermodynamic": E0_THERMO,
        "spinon_velocity": SPINON_VELOCITY,
    }


def self_test():
    # anchor 1 (GROUND TRUTH): Bethe solver == brute-force ED at N=10, PBC.
    N = 10
    sx, sy, sz = ed.spin_ops(N)
    H = sum(sx[i] @ sx[(i + 1) % N] + sy[i] @ sy[(i + 1) % N]
            + sz[i] @ sz[(i + 1) % N] for i in range(N))
    assert abs(bethe.xxx_energy(bethe.xxx_ground_roots(N), N)
               - ed.ground_energy(H)) < 1e-10

    # anchor 2: 1/N^2 extrapolation of e0(N) reaches the closed form.
    assert abs(e0_extrapolated() - E0_THERMO) < 1e-4

    # anchor 3: the thermodynamic constant is the literal 1/4 - ln 2.
    assert abs(compute()["e0_thermodynamic"] - (0.25 - np.log(2.0))) < 1e-15

    # anchor 4: spinon velocity is pi/2 in this convention.
    assert abs(compute()["spinon_velocity"] - np.pi / 2) < 1e-15


if __name__ == "__main__":
    oracle_main(compute, {"N": (int, 12)})
