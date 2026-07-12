"""Kitaev honeycomb oracle: exact free-Majorana solution in the flux-free sector.

    H = -Jx sum_{<ij>_x} sx_i sx_j - Jy sum_{<ij>_y} sy_i sy_j - Jz sum_{<ij>_z} sz_i sz_j
    (PAULI operators; three bond-dependent "compass" Ising couplings on the honeycomb)

Kitaev's four-Majorana representation sx=i b^x c, sy=i b^y c, sz=i b^z c (with the
gauge-fixing constraint b^x b^y b^z c = 1 per site) turns each bond operator
i b^a_j b^a_k =: u_{jk} into a CONSERVED Z2 gauge field, leaving a quadratic
Majorana hopping of the single c-Majorana per site:

    s^a_j s^a_k = -i u_{jk} c_j c_k   ->   H = i sum_{<jk>, j in A} J_a u_{jk} c_j c_k

By Lieb's theorem the ground state lives in the flux-free sector (all plaquette
fluxes W_p = +1), realized by the gauge u_{jk} = +1 on every bond. With two sites
(sublattices A, B) per unit cell and the three bond directions attaching A(r) to
B(r) [z-bond, Jz], B(r+n1) [x-bond, Jx] and B(r+n2) [y-bond, Jy], the Fourier
transform gives the 2x2 Majorana Bloch problem with off-diagonal

    f(k) = Jz + Jx e^{i k.n1} + Jy e^{i k.n2}

and single-particle (quasiparticle) dispersion eps(k) = 2|f(k)|.

Basis (stated explicitly): primitive Bravais vectors n1 = (1, 0), n2 = (1/2, sqrt3/2)
(lattice constant 1). The Dirac point of the isotropic model sits at
K = (2*pi/3, 2*pi/sqrt3), i.e. reduced coordinates (k.n1, k.n2) = (2*pi/3, 4*pi/3),
where e^{i2pi/3} + e^{i4pi/3} + 1 = 0 exactly.

Because |f| depends on k only through the reduced coordinates u = k.n1 and
v = k.n2 (each a full 2*pi period, constant Jacobian), every BZ average and BZ
minimum below is computed on a uniform (u, v) grid on [0, 2*pi)^2 -- exact
quadrature for the smooth periodic integrand away from the isolated Dirac cone.

Ground-state energy per site -- prefactor derivation.  A quadratic Majorana
Hamiltonian written as H = (i/2) sum_{j<k} A_{jk} c_j c_k has ground energy
E0 = -(1/2) sum_m eps_m over its non-negative single-particle levels eps_m. Here
eps(k) = 2|f(k)| (one level per unit cell), so

    E0 = -(1/2) sum_k eps(k) = -sum_k |f(k)| = -N_uc * mean_BZ |f|,

and with TWO sites per unit cell,

    e0_per_site = E0 / (2 N_uc) = -(1/2) * mean_BZ |f(k)|.

The -1/2 (not -1/4) prefactor is pinned exactly by the decoupled-dimer limit
Jx=Jy=0, Jz=1: |f| = 1 everywhere, so e0_per_site = -1/2, which is the exact
energy per site of an isolated z-dimer H = -sz sz (ground energy -1 for two
sites). This limit is checked in self_test().
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402

# Primitive Bravais vectors (lattice constant 1) and the isotropic Dirac point.
N1 = np.array([1.0, 0.0])
N2 = np.array([0.5, np.sqrt(3.0) / 2.0])
K_POINT = np.array([2.0 * np.pi / 3.0, 2.0 * np.pi / np.sqrt(3.0)])


def f_k(k, Jx=1.0, Jy=1.0, Jz=1.0):
    """Majorana off-diagonal Bloch factor at physical momentum k = (kx, ky)."""
    k = np.asarray(k, dtype=float)
    return Jz + Jx * np.exp(1j * (k @ N1)) + Jy * np.exp(1j * (k @ N2))


def f_uv(u, v, Jx=1.0, Jy=1.0, Jz=1.0):
    """Same Bloch factor in reduced coordinates u = k.n1, v = k.n2."""
    return Jz + Jx * np.exp(1j * u) + Jy * np.exp(1j * v)


def _uv_grid(n):
    u = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    return np.meshgrid(u, u, indexing="ij")


def e0(Jx=1.0, Jy=1.0, Jz=1.0, n=600):
    """Ground-state energy per site: -(1/2) * mean_BZ |f|. See module docstring."""
    U, V = _uv_grid(n)
    return -0.5 * np.abs(f_uv(U, V, Jx, Jy, Jz)).mean()


def gap(Jx=1.0, Jy=1.0, Jz=1.0, n=600):
    """Quasiparticle gap min_k eps(k) = 2 min_BZ |f|. Grid n divisible by 6 puts
    both the Dirac point (2pi/3, 4pi/3) and the A-phase minimum (pi, pi) on-grid."""
    U, V = _uv_grid(n)
    return float(2.0 * np.abs(f_uv(U, V, Jx, Jy, Jz)).min())


def phase(Jx, Jy, Jz):
    """A-gapped iff the triangle inequality is violated (one |J| exceeds the sum
    of the other two); else B-gapless (Majorana Dirac cones)."""
    ax, ay, az = abs(Jx), abs(Jy), abs(Jz)
    if ax > ay + az or ay > ax + az or az > ax + ay:
        return "A-gapped"
    return "B-gapless"


def compute(Jx=1.0, Jy=1.0, Jz=1.0, n=600):
    """Kitaev honeycomb exact quantities (flux-free sector, Lieb's theorem)."""
    return {
        "e0_per_site": e0(Jx, Jy, Jz, n),
        "gap": gap(Jx, Jy, Jz, n),
        "phase": phase(Jx, Jy, Jz),
    }


def self_test():
    # anchor 1: f vanishes EXACTLY at the analytic K point for isotropic couplings,
    # in both the physical-k and reduced-coordinate forms.
    assert abs(f_k(K_POINT, 1.0, 1.0, 1.0)) < 1e-12
    assert abs(f_uv(2 * np.pi / 3, 4 * np.pi / 3, 1.0, 1.0, 1.0)) < 1e-12

    # anchor 2: grid convergence of e0 (exactness of the quadrature), grids
    # divisible by 3 so the Dirac cone sits on-grid at both resolutions.
    assert abs(e0(1, 1, 1, n=300) - e0(1, 1, 1, n=600)) < 1e-5

    # anchor 3: prefactor pin -- decoupled z-dimer limit gives exactly -1/2 per site.
    assert abs(e0(0.0, 0.0, 1.0, n=300) + 0.5) < 1e-12

    # anchor 4: A phase (|Jz| > |Jx| + |Jy|) is gapped; analytic gap 2*(2.5-2)=1.0.
    r_a = compute(Jx=1.0, Jy=1.0, Jz=2.5)
    assert r_a["gap"] > 0.4
    assert r_a["phase"] == "A-gapped"
    assert abs(r_a["gap"] - 1.0) < 1e-9

    # anchor 5: B phase (isotropic) is gapless -- gap ~ 0 with K exactly on-grid.
    r_b = compute(Jx=1.0, Jy=1.0, Jz=1.0)
    assert r_b["gap"] < 1e-6
    assert r_b["phase"] == "B-gapless"


if __name__ == "__main__":
    oracle_main(
        compute,
        {"Jx": (float, 1.0), "Jy": (float, 1.0), "Jz": (float, 1.0), "n": (int, 600)},
    )
