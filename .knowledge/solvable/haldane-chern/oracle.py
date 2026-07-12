"""Haldane-model oracle: honeycomb tight-binding electrons with a real
nearest-neighbor hopping t1, a complex next-nearest-neighbor hopping
t2*exp(+-i*phi) (sign set by sublattice/orientation), and a sublattice mass M
- the first Chern insulator (zero net flux, quantized sigma_xy without a net
magnetic field).

Reduced Bloch coordinates: `u = k.A1`, `v = k.A2` (each a full 2*pi period),
`A1, A2` the honeycomb's primitive Bravais vectors at 60 degrees, same
"reduced crystal momentum" convention as
tight-binding-lattices/oracle.py's honeycomb block (2 sites/cell, A-B bonds
at cell offsets 0, -A1, -A2 - a "periodic gauge" choice, i.e. the intra-cell
sublattice offset is dropped from the phase so H(u,v) is EXACTLY 2*pi
periodic in u and in v separately, which _lib.topology.chern's [0,2*pi)^2
grid requires; a naive convention using the actual A-to-B bond vectors
[thirds of A1+A2] instead of the pure-lattice offsets used here is only
6*pi periodic and breaks the FHS loop closure - checked and rejected before
settling on this form).

    f(u,v)  = 1 + exp(i*u) + exp(i*v)                 (NN Bloch factor)
    d0(u,v) = 2*t2*cos(phi) * [cos(u) + cos(v-u) + cos(v)]
    d3(u,v) = M - 2*t2*sin(phi) * [sin(u) + sin(v-u) - sin(v)]
    H(u,v)  = [[d0+d3,  t1*f], [t1*conj(f), d0-d3]]

d0, d3 use the three NNN bond vectors b1=A1, b2=A2-A1, b3=-A2 (reduced
arguments u, v-u, -v respectively; these sum to zero, the standard closed
triangle of second-neighbor hops on the triangular sublattice) - this is
exactly the "standard Haldane form" `d3 = M - 2*t2*sin(phi)*sum_i sin(k.b_i)`
quoted in the task brief, with a/b vector conventions now stated explicitly.

Dirac points (f=0): (u,v) = (2*pi/3, 4*pi/3) = K and (4*pi/3, 2*pi/3) = K',
identical to tight-binding-lattices/oracle.py's `_dirac_K()`. At these points
d1=d2=0 (f=0) so the gap is `2|d3|`; substituting gives
`d3(K) = M - 3*sqrt(3)*t2*sin(phi)`, `d3(K') = M + 3*sqrt(3)*t2*sin(phi)`
(derived below in ORACLE.md), so the gap closes at
`M = +-3*sqrt(3)*t2*sin(phi)`, i.e. `phase_boundary_M = 3*sqrt(3)*t2*|sin(phi)|`.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import topology  # noqa: E402


def bloch(u, v, t1=1.0, t2=1.0 / 3, phi=np.pi / 2, M=0.0):
    """Batched 2x2 Haldane Bloch Hamiltonian over reduced momenta u, v."""
    u = np.asarray(u, dtype=float)
    v = np.asarray(v, dtype=float)
    shape = np.broadcast(u, v).shape
    U = np.broadcast_to(u, shape)
    V = np.broadcast_to(v, shape)
    f = 1.0 + np.exp(1j * U) + np.exp(1j * V)
    d0 = 2.0 * t2 * np.cos(phi) * (np.cos(U) + np.cos(V - U) + np.cos(V))
    d3 = M - 2.0 * t2 * np.sin(phi) * (np.sin(U) + np.sin(V - U) - np.sin(V))
    H = np.zeros(shape + (2, 2), dtype=complex)
    H[..., 0, 0] = d0 + d3
    H[..., 1, 1] = d0 - d3
    H[..., 0, 1] = t1 * f
    H[..., 1, 0] = t1 * np.conj(f)
    return H


def hk(t1=1.0, t2=1.0 / 3, phi=np.pi / 2, M=0.0):
    def _hk(u, v):
        return bloch(u, v, t1, t2, phi, M)
    return _hk


def _direct_gap(uv, t1, t2, phi, M):
    H = bloch(uv[0], uv[1], t1, t2, phi, M)
    ev = np.linalg.eigvalsh(H)
    return float(ev[1] - ev[0])


def compute(t1=1.0, t2=1.0 / 3, phi=np.pi / 2, M=0.0, nk=60, nk_gap=200):
    """Haldane-model exact quantities: Chern number of the filled lower band
    (FHS), minimum direct gap over the BZ (grid scan + local refinement), and
    the closed-form topological phase boundary."""
    Hk = hk(t1, t2, phi, M)
    chern = topology.chern(Hk, 1, nk=nk)

    us = np.linspace(0.0, 2.0 * np.pi, nk_gap, endpoint=False)
    U, V = np.meshgrid(us, us, indexing="ij")
    ev = np.linalg.eigvalsh(bloch(U, V, t1, t2, phi, M))
    gaps = ev[..., 1] - ev[..., 0]
    i0 = np.unravel_index(np.argmin(gaps), gaps.shape)
    u0, v0 = us[i0[0]], us[i0[1]]
    res = minimize(_direct_gap, x0=[u0, v0], args=(t1, t2, phi, M), method="Nelder-Mead")
    gap = max(float(res.fun), 0.0)

    phase_boundary_M = float(3.0 * np.sqrt(3.0) * t2 * abs(np.sin(phi)))

    return {
        "chern": chern,
        "gap": gap,
        "phase_boundary_M": phase_boundary_M,
    }


def self_test():
    # anchor 1: deep in the topological phase (M=0, t2=1/3, phi=pi/2), |C|=1
    assert abs(compute(M=0.0, t2=1 / 3, phi=np.pi / 2)["chern"]) == 1

    # anchor 2: trivial phase, M=2.0 > phase_boundary_M = 3*sqrt(3)/3 ~ 1.732
    r_trivial = compute(M=2.0, t2=1 / 3, phi=np.pi / 2)
    assert r_trivial["chern"] == 0
    assert abs(r_trivial["phase_boundary_M"] - 3 * np.sqrt(3) / 3) < 1e-12

    # anchor 3: C is odd under phi -> -phi (time-reversal partner)
    c_plus = compute(M=0.0, t2=1 / 3, phi=np.pi / 2)["chern"]
    c_minus = compute(M=0.0, t2=1 / 3, phi=-np.pi / 2)["chern"]
    assert c_plus == -c_minus

    # anchor 4: gap closes exactly on the phase boundary M = 3*sqrt(3)*t2*sin(phi)
    Mb = 3 * np.sqrt(3) * (1 / 3) * np.sin(np.pi / 2)
    assert compute(M=Mb, t2=1 / 3, phi=np.pi / 2)["gap"] < 1e-2

    # anchor 5: C depends on t2 and phi only through sgn(t2*sin(phi)) at M=0
    # (flipping the sign of t2 at fixed phi must flip C, same as flipping phi)
    c_t2plus = compute(M=0.0, t2=1 / 3, phi=np.pi / 2)["chern"]
    c_t2minus = compute(M=0.0, t2=-1 / 3, phi=np.pi / 2)["chern"]
    assert c_t2plus == -c_t2minus
    # smaller phi, same sign(t2*sin(phi)) -> same C, smaller phase_boundary_M
    r_small_phi = compute(M=0.0, t2=1 / 3, phi=np.pi / 4)
    assert r_small_phi["chern"] == c_t2plus
    assert r_small_phi["phase_boundary_M"] < compute(M=0.0, t2=1 / 3, phi=np.pi / 2)["phase_boundary_M"]


if __name__ == "__main__":
    oracle_main(
        compute,
        {"t1": (float, 1.0), "t2": (float, 1.0 / 3), "phi": (float, np.pi / 2), "M": (float, 0.0)},
    )
