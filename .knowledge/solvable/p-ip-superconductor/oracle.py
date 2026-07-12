"""p+ip superconductor oracle: lattice spinless-fermion BdG Chern superconductor.

    H(k) = xi(k) tau_z + Delta (sin kx tau_x + sin ky tau_y),
    xi(k) = -2t (cos kx + cos ky) - mu

Nambu / BdG 2x2 Bloch matrix (tau the particle-hole Pauli matrices) for a
single-band spinless fermion with chiral p+ip pairing. Writing the d-vector
d(k) = (Delta sin kx, Delta sin ky, xi(k)), the two BdG bands are +/- E(k) with
E(k) = |d(k)| = sqrt(xi^2 + Delta^2 (sin^2 kx + sin^2 ky)); the negative band is
filled (nocc = 1) and its first Chern number is the topological invariant.

Gap closings (d = 0) require sin kx = sin ky = 0 (so kx, ky in {0, pi}) and xi = 0:
    (0,0):   xi = -4t - mu = 0  ->  mu = -4t
    (0,pi),(pi,0): xi = -mu = 0 ->  mu =  0
    (pi,pi): xi =  4t - mu = 0  ->  mu = +4t
These three critical lines separate (t > 0):
    |mu| > 4t : strong-pairing, trivial (C = 0)
    -4t < mu < 0 and 0 < mu < 4t : weak-pairing, topological (|C| = 1), the two
        sides carrying OPPOSITE Chern sign (the mu = 0 line closes TWO Dirac
        points at (0,pi) and (pi,0), so C jumps by 2 across it).

Sign convention.  With the pairing written as Delta(sin kx tau_x + sin ky tau_y)
-- lower-left Nambu entry Delta(sin kx + i sin ky) -- and the Fukui-Hatsugai-Suzuki
plaquette orientation of `_lib.topology.chern`, this script returns C = +1 for
-4t < mu < 0 and C = -1 for 0 < mu < 4t. The overall sign is convention-dependent
(it flips with Delta -> -Delta, with tau_x <-> tau_y, or with the FHS orientation),
so only |C| and the RELATIVE sign across mu = 0 are convention-independent; the
script reports whatever `_lib.topology.chern` yields and does not assert a
privileged sign.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import topology  # noqa: E402


def bloch(kx, ky, mu=0.0, t=1.0, delta=1.0):
    """2x2 BdG Bloch matrix H(k) = xi tau_z + Delta(sin kx tau_x + sin ky tau_y)."""
    xi = -2.0 * t * (np.cos(kx) + np.cos(ky)) - mu
    off = delta * (np.sin(kx) - 1j * np.sin(ky))  # upper-right = Delta(sin kx - i sin ky)
    return np.array([[xi, off], [np.conj(off), -xi]], dtype=complex)


def hk(mu=0.0, t=1.0, delta=1.0):
    def _hk(kx, ky):
        return bloch(kx, ky, mu, t, delta)
    return _hk


def gap(mu=0.0, t=1.0, delta=1.0, n=120):
    """Band gap min_k [E_+(k) - E_-(k)] = 2 min_k |d(k)|. Even n puts the possible
    closing points (0,0), (0,pi), (pi,0), (pi,pi) exactly on the grid."""
    k = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    KX, KY = np.meshgrid(k, k, indexing="ij")
    xi = -2.0 * t * (np.cos(KX) + np.cos(KY)) - mu
    E = np.sqrt(xi ** 2 + delta ** 2 * (np.sin(KX) ** 2 + np.sin(KY) ** 2))
    return float(2.0 * E.min())


def compute(mu=-1.0, t=1.0, delta=1.0, nk=60, n_gap=120):
    """p+ip superconductor exact quantities: Chern number of the filled BdG band
    (FHS), the minimum band gap over the BZ, and the pairing phase."""
    chern = topology.chern(hk(mu, t, delta), 1, nk=nk)
    g = gap(mu, t, delta, n=n_gap)
    if abs(chern) == 1:
        ph = "weak-pairing (topological)"
    elif chern == 0:
        ph = "strong-pairing (trivial)"
    else:
        ph = f"C={chern}"
    return {"chern": chern, "gap": g, "phase": ph}


def self_test():
    # anchor 1: weak-pairing phases are topological, |C| = 1 on either side of mu = 0.
    assert abs(compute(mu=-2.0, t=1.0, delta=0.5)["chern"]) == 1
    assert abs(compute(mu=2.0, t=1.0, delta=0.5)["chern"]) == 1

    # anchor 2: the two weak-pairing lobes carry opposite Chern sign (mu = 0 closes
    # two Dirac points, so C jumps by 2). Convention-independent statement.
    assert compute(mu=-2.0, t=1.0, delta=0.5)["chern"] == -compute(mu=2.0, t=1.0, delta=0.5)["chern"]

    # anchor 3: strong-pairing phase is trivial, C = 0.
    assert compute(mu=-5.0, t=1.0, delta=0.5)["chern"] == 0

    # anchor 4: gap closes at each critical chemical potential; the gap grid
    # (n even) contains the relevant closing point -- (0,0) at mu=-4, (0,pi)&(pi,0)
    # at mu=0, (pi,pi) at mu=+4.
    for mu_c in (-4.0, 0.0, 4.0):
        assert compute(mu=mu_c, t=1.0, delta=0.5)["gap"] < 1e-3

    # anchor 5: phase labels track |C|.
    assert compute(mu=-2.0, t=1.0, delta=0.5)["phase"] == "weak-pairing (topological)"
    assert compute(mu=-5.0, t=1.0, delta=0.5)["phase"] == "strong-pairing (trivial)"


if __name__ == "__main__":
    oracle_main(
        compute,
        {"mu": (float, -1.0), "t": (float, 1.0), "delta": (float, 1.0)},
    )
