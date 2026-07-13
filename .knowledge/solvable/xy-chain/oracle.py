"""Anisotropic XY chain oracle: H = J sum [(1+g) Sx Sx + (1-g) Sy Sy] - h sum Sz.

S = sigma/2 spin operators, J = 1 default, PBC. Jordan–Wigner maps the chain to
free (Bogoliubov-diagonalizable) fermions. With c_i = (prod_{j<i} sigma^z_j)
sigma^-_i and sigma^z = 1 - 2 n:

  J[(1+g)Sx Sx + (1-g)Sy Sy]_bond = (J/2)(c^dag_i c_{i+1} + h.c.)
                                    + (J g/2)(c^dag_i c^dag_{i+1} + h.c.)
  -h Sz_i = h c^dag_i c_i - h/2   (per site)

so A[i,i]=h, A[i,i+1]=A[i+1,i]=J/2, B[i,i+1]=J g/2 (B antisymmetric), plus an
additive constant -h/2 per site.

Boundary sector: a PBC spin chain maps to a *parity-dependent* fermion boundary
condition. The even-fermion-parity sector uses antiperiodic (ABC) hopping across
the seam (wrap bond sign flipped); the odd sector uses periodic (PBC) fermions.
The true ground-state energy is the lower of the two BdG ground energies (the
Gaussian BdG ground state of the winning sector lands in the allowed parity for
every point tested here). At the XX point (g=0, h=0) e0 = -1/pi.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed, quadratic  # noqa: E402


def matrices(L, gamma, h, J=1.0, sector="abc"):
    """BdG matrices for the JW-transformed XY chain in the given boundary sector.

    sector="abc": antiperiodic fermions (even parity) -> wrap bond sign flipped.
    sector="pbc": periodic fermions (odd parity)      -> wrap bond sign +1.
    """
    A = np.zeros((L, L))
    B = np.zeros((L, L))
    for i in range(L):
        j = (i + 1) % L
        wrap = j < i  # the (L-1)->0 seam bond
        s = (-1.0 if sector == "abc" else 1.0) if wrap else 1.0
        A[i, i] = h
        A[i, j] += s * J / 2
        A[j, i] += s * J / 2
        B[i, j] += s * J * gamma / 2
        B[j, i] -= s * J * gamma / 2
    return A, B


def _sector(L, gamma, h, J, sector):
    """Return (e0_per_site, gap) for one boundary sector via a single BdG solve."""
    A, B = matrices(L, gamma, h, J, sector)
    eps = quadratic.bdg_energies(A, B)  # non-negative branch, ascending
    # E0 = 1/2 tr A - 1/2 sum eps + (-h/2)*L ; per site: (that)/L - h/2.
    e0 = (0.5 * float(np.real(np.trace(A))) - 0.5 * float(eps.sum())) / L - h / 2
    return e0, float(eps[0])


def compute(L=64, gamma=0.0, h=0.0, J=1.0):
    """XY-chain exact quantities via Jordan–Wigner; e0 = min over parity sectors."""
    e_abc, gap_abc = _sector(L, gamma, h, J, "abc")
    e_pbc, gap_pbc = _sector(L, gamma, h, J, "pbc")
    if e_abc <= e_pbc:
        return {"e0_per_site": e_abc, "gap": gap_abc, "sector": "abc"}
    return {"e0_per_site": e_pbc, "gap": gap_pbc, "sector": "pbc"}


def self_test():
    # anchor 1: XX point (g=0, h=0) -> e0 = -1/pi in the thermodynamic limit
    # finite-size correction is O(1/L^2); at L=400 the deviation is ~3e-6, well
    # inside the 1e-4 tolerance below.
    assert abs(compute(L=400, gamma=0.0, h=0.0)["e0_per_site"] + 1 / np.pi) < 1e-4
    # anchor 2: JW energy matches brute-force ED at L=8 for three (g,h) points
    for gamma, h in [(0.0, 0.0), (0.7, 0.3), (1.0, 0.5)]:
        sx, sy, sz = ed.spin_ops(8)
        H = sum((1 + gamma) * sx[i] @ sx[(i + 1) % 8] + (1 - gamma) * sy[i] @ sy[(i + 1) % 8]
                for i in range(8)) - h * sum(sz)
        assert abs(ed.ground_energy(H) / 8 - compute(L=8, gamma=gamma, h=h)["e0_per_site"]) < 1e-10, (gamma, h)


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 64), "gamma": (float, 0.0), "h": (float, 0.0), "J": (float, 1.0)})
