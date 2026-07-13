"""Calogero-Sutherland (Sutherland) model oracle: N particles on a ring, 1/sin^2.

Hamiltonian (Sutherland model), N particles on a ring of circumference L:

    H = -sum_i d^2/dx_i^2
        + sum_{i<j} 2*lam*(lam-1)*(pi/L)^2 / sin^2( pi*(x_i - x_j)/L )

UNITS: hbar = 1, 2m = 1 (so the kinetic term is literally -d^2/dx^2 and a
single-particle momentum k contributes k^2 to the energy; the free case lam=0
or lam=1 gives E = sum_i k_i^2 exactly). The coupling lam >= 0 is dimensionless;
lam=0 is free bosons, lam=1 is free (spinless) fermions -- both have vanishing
interaction coefficient 2*lam*(lam-1).

WHAT IS CLOSED FORM (this is a Tier-B card but the *spectrum* is genuinely
closed form, unlike the integral-equation Bethe siblings). Every eigenstate is
labelled by a non-decreasing integer sequence I_1 <= I_2 <= ... <= I_N (the
Jack-polynomial / partition quantum numbers). The pseudo-momenta are

    k_i = (2*pi/L) * [ I_i + (lam/2)*(2*i - N - 1) ],   i = 1..N,

and the energy is E({I}) = sum_i k_i^2. The (lam/2)(2i-N-1) shift is the
asymptotic-Bethe-ansatz statistical shift; it sums to zero over i, so the total
momentum is (2*pi/L) sum_i I_i.

  * GROUND STATE  I = (0,...,0):
        E0(N,L,lam) = (pi/L)^2 * lam^2 * N*(N^2 - 1) / 3,
    from sum_i [(lam/2)(2i-N-1)]^2 = (lam^2/4) * N(N^2-1)/3. (Jastrow ground
    state psi0 = prod_{i<j} |sin(pi(x_i-x_j)/L)|^lam.)

  * FIRST EXCITED GAP  = (2*pi/L)^2 * min( N , 1 + lam*(N-1) ):
      - rigid centre-of-mass boost  I=(1,...,1):  Delta E = N*(2*pi/L)^2;
      - internal particle-hole (top I_N->1 or bottom I_1->-1):
        Delta E = [1 + lam*(N-1)]*(2*pi/L)^2.
    The two branches cross at lam=1 (the free-fermion point, where they are
    equal to N*(2*pi/L)^2); the boost wins for lam>1, the p-h branch for lam<1.

Script scope (P). The spectrum function E({I}) and the closed forms E0 and the
gap are all shipped and exact. The DYNAMICAL density-density / one-body
correlators -- also exactly known for rational lam via Jack polynomials
[@Ha1994; @Sutherland1971] -- are TABULATED in ORACLE.md, not scripted here
(that is the "P", partial, flag): they need the Jack-polynomial machinery,
out of scope for this oracle.
"""
import sys
from itertools import combinations_with_replacement
from math import pi
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402


def momenta(I, N, L, lam):
    """Pseudo-momenta k_i for the quantum-number sequence I (len N)."""
    return [(2 * pi / L) * (I[i] + 0.5 * lam * (2 * (i + 1) - N - 1)) for i in range(N)]


def energy_from_I(I, N, L, lam):
    """Eigen-energy E({I}) = sum_i k_i^2 for a non-decreasing integer sequence I."""
    return float(sum(k * k for k in momenta(I, N, L, lam)))


def e0(N, L, lam):
    """Closed-form ground-state energy E0 = (pi/L)^2 lam^2 N(N^2-1)/3."""
    return (pi / L) ** 2 * lam ** 2 * N * (N ** 2 - 1) / 3.0


def first_gap(N, L, lam):
    """First-excited gap = (2 pi/L)^2 * min(N, 1 + lam(N-1)) (see module docstring)."""
    return (2 * pi / L) ** 2 * min(N, 1.0 + lam * (N - 1))


def e0_density_limit(n, lam):
    """Thermodynamic energy per particle E0/N -> (pi^2 n^2 / 3) lam^2, n = N/L."""
    return pi ** 2 * n ** 2 * lam ** 2 / 3.0


def _e0_leading(N, L, lam):
    """Leading N->inf piece of E0/N: (pi/L)^2 lam^2 N^2/3 (drops the -1 in N^2-1)."""
    return (pi / L) ** 2 * lam ** 2 * N ** 2 / 3.0


def free_fermion_e0(N, L):
    """Direct Sigma_{filled} k^2, k=2*pi*m/L, lowest N single-particle levels (lam=1 check)."""
    ms = sorted(range(-N, N + 1), key=lambda m: (2 * pi * m / L) ** 2)[:N]
    return float(sum((2 * pi * m / L) ** 2 for m in ms))


def _enum_gap(N, L, lam, w=4):
    """Brute-force first gap: min positive E({I})-E0 over non-decreasing I in [-w,w]."""
    base = energy_from_I([0] * N, N, L, lam)
    best = None
    for combo in combinations_with_replacement(range(-w, w + 1), N):
        d = energy_from_I(list(combo), N, L, lam) - base
        if d > 1e-9 and (best is None or d < best):
            best = d
    return best


def compute(N=5, L=6.283185307179586, lam=2.0):
    """Sutherland-model ground energy, first gap, and thermodynamic density limit."""
    n = N / L
    return {
        "N": N,
        "L": L,
        "lam": lam,
        "e0": e0(N, L, lam),
        "e0_over_N": e0(N, L, lam) / N,
        "first_gap": first_gap(N, L, lam),
        "density_limit_e0_over_N": e0_density_limit(n, lam),
        "method": "closed form (Sutherland spectrum, asymptotic Bethe ansatz)",
    }


def self_test():
    TWO_PI = 2 * pi

    # (0) closed E0 == direct spectrum sum for the all-zero (ground) config.
    for N in (2, 3, 4, 5, 6):
        assert abs(e0(N, TWO_PI, 1.7) - energy_from_I([0] * N, N, TWO_PI, 1.7)) < 1e-12, N

    # (i) lam=1 -> free spinless fermions on the ring. E0 equals the directly
    #     computed Fermi-sea energy Sigma_{filled} k^2 (closed shell for N odd).
    for N in (3, 5, 7):
        L = 3.3
        assert abs(e0(N, L, 1.0) - free_fermion_e0(N, L)) < 1e-12, (N, e0(N, L, 1.0), free_fermion_e0(N, L))

    # (ii) N=2: relative motion is a Poeschl-Teller-on-a-ring problem whose GS
    #     energy is hand-derivable. psi0_rel = |sin(pi x/L)|^lam gives, for
    #     H_rel = -2 d^2/dx^2 + 2 lam(lam-1)(pi/L)^2/sin^2, E_rel = 2 lam^2 (pi/L)^2;
    #     the CM is at rest (E=0), so E0(N=2) = 2 lam^2 (pi/L)^2. For lam=2, L=2pi
    #     this is exactly 2. Assert both the general form and the pinned number.
    for lam in (0.5, 1.3, 2.0, 3.0):
        L = 2.7
        assert abs(e0(2, L, lam) - 2.0 * lam ** 2 * (pi / L) ** 2) < 1e-12, (lam, L)
    assert abs(e0(2, TWO_PI, 2.0) - 2.0) < 1e-12, e0(2, TWO_PI, 2.0)   # hand value

    # (iii) large-N scaling. The closed form's own N->inf limit of E0/N is
    #     (pi/L)^2 lam^2 N^2/3, algebraically identical to (pi^2 n^2/3) lam^2 with
    #     n=N/L -- assert that identity to 1e-10 at N=1e4, and that the *full*
    #     E0/N (with the -1) sits within the expected O(1/N^2) of the limit.
    N = 10 ** 4
    for lam in (1.0, 2.5):
        L = float(N)          # n = N/L = 1
        n = N / L
        assert abs(_e0_leading(N, L, lam) - e0_density_limit(n, lam)) <= 1e-10 * e0_density_limit(n, lam), lam
        rel = abs(e0(N, L, lam) / N - e0_density_limit(n, lam)) / e0_density_limit(n, lam)
        assert rel < 1.1e-8, (lam, rel)   # == 1/N^2 finite-size correction

    # (iv) first_gap closed form matches brute-force enumeration across N and lam
    #     (the CM-boost branch N for lam>1, the particle-hole branch 1+lam(N-1)
    #     for lam<1, equal at lam=1).
    for N in (2, 3, 4, 5):
        for lam in (0.3, 0.7, 1.0, 1.5, 2.0, 3.5):
            L = TWO_PI
            assert abs(first_gap(N, L, lam) - _enum_gap(N, L, lam)) < 1e-9, (N, lam)

    # (v) lam=1 gap reduces to the free-fermion particle-hole gap N*(2pi/L)^2.
    for N in (3, 5, 7):
        L = 4.1
        assert abs(first_gap(N, L, 1.0) - N * (2 * pi / L) ** 2) < 1e-12, N


if __name__ == "__main__":
    oracle_main(compute, {"N": (int, 5), "L": (float, 6.283185307179586), "lam": (float, 2.0)})
