"""Gaudin central-spin oracle: exact integrable structure + ED ground state.

    H = sum_{j=1}^{N_b} A_j  S_0 . S_j,   A_j = 1/j,   all spins 1/2,

with S_0 the central spin and S_1..S_{N_b} the bath.  T3 (rational Gaudin
magnet).  This card ships the CONSERVED-CHARGE construction (route "conserved-
charges"): the central-spin H is *exactly* one of the N_b+1 mutually commuting
rational Gaudin Hamiltonians

    H_i = sum_{k != i} (S_i . S_k) / (u_i - u_k),   i = 0..N_b,

for the inhomogeneities u = (u_0, u_1, ..., u_{N_b}) = (0, -1, -2, ..., -N_b):
then u_0 - u_j = j, so H_0 = sum_j (S_0 . S_j)/j = sum_j A_j S_0 . S_j = H.
Integrability is proven *in this card* -- all pairwise commutators [H_i, H_j]
vanish numerically -- and the ground-state energy is supplied by exact
diagonalization of H (the exact numbers), with [H, S^2_tot] = 0 giving the
total-spin multiplet structure.  A second, closed-form coupling set is also
pinned: for UNIFORM coupling A_j = A, H = A S_0 . S_bath is diagonal in total
spin with ground energy -(A/4)(N_b + 2).

We take the conserved-charge route rather than a raw Gaudin-Bethe root solver:
it is an honest exact-structure oracle (integrability + commuting charges proven,
ED-exact energies) and is numerically bullet-proof, which the field-free Gaudin
root solver is not.
"""
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed as edlib  # noqa: E402


def _dot(sx, sy, sz, i, j):
    return sx[i] @ sx[j] + sy[i] @ sy[j] + sz[i] @ sz[j]


def couplings(N_bath):
    """Central-spin couplings A_j = 1/j and Gaudin inhomogeneities u."""
    A = np.array([1.0 / j for j in range(1, N_bath + 1)])
    u = np.array([0.0] + [-float(j) for j in range(1, N_bath + 1)])  # A_j=1/(u0-uj)
    return A, u


def central_spin_H(N_bath):
    """H = sum_{j=1}^{N_b} A_j S_0 . S_j (direct central-spin sum), A_j = 1/j."""
    L = N_bath + 1
    sx, sy, sz = edlib.spin_ops(L)
    A, _ = couplings(N_bath)
    H = sp.csr_matrix((2 ** L, 2 ** L), dtype=complex)
    for j in range(1, L):
        H = H + A[j - 1] * _dot(sx, sy, sz, 0, j)
    return H


def gaudin_charges(N_bath):
    """The N_b+1 rational Gaudin Hamiltonians H_i for u = (0, -1, ..., -N_b)."""
    L = N_bath + 1
    sx, sy, sz = edlib.spin_ops(L)
    _, u = couplings(N_bath)
    charges = []
    for i in range(L):
        Hi = sp.csr_matrix((2 ** L, 2 ** L), dtype=complex)
        for k in range(L):
            if k == i:
                continue
            Hi = Hi + _dot(sx, sy, sz, i, k) / (u[i] - u[k])
        charges.append(Hi)
    return charges


def total_spin_squared(N_bath):
    L = N_bath + 1
    sx, sy, sz = edlib.spin_ops(L)
    Sx, Sy, Sz = sum(sx), sum(sy), sum(sz)
    return Sx @ Sx + Sy @ Sy + Sz @ Sz


def e0(N_bath):
    """Ground-state energy of the central-spin H (A_j = 1/j) via ED."""
    return edlib.ground_energy(central_spin_H(N_bath))


def uniform_e0_closed_form(N_bath, A=1.0):
    """Uniform-coupling ground energy: H = A S_0 . S_bath, GS = -(A/4)(N_b+2)."""
    return -(A / 4.0) * (N_bath + 2)


# --------------------------------------------------------------------------

def compute(N_bath=5):
    """Central-spin (rational Gaudin) exact ground state via conserved charges."""
    return {
        "e0": float(e0(N_bath)),
        "route": "conserved-charges",
        "N_bath": int(N_bath),
        "couplings": "A_j = 1/j (j=1..N_bath)",
        "inhomogeneities": [float(x) for x in couplings(N_bath)[1]],
    }


def self_test():
    for N_bath in (4, 5):
        L = N_bath + 1
        H = central_spin_H(N_bath)
        charges = gaudin_charges(N_bath)

        # anchor 1: the central-spin H is EXACTLY the Gaudin charge H_0.
        assert np.max(np.abs((H - charges[0]).toarray())) < 1e-12

        # anchor 2 (INTEGRABILITY, proven in-card): all N_b+1 Gaudin charges
        # mutually commute.
        max_comm = 0.0
        for i in range(L):
            for j in range(i + 1, L):
                c = charges[i] @ charges[j] - charges[j] @ charges[i]
                max_comm = max(max_comm, np.max(np.abs(c.toarray())))
        assert max_comm < 1e-12, (N_bath, max_comm)

        # anchor 3 (degeneracy sanity): H conserves total spin, [H, S^2] = 0.
        S2 = total_spin_squared(N_bath)
        assert np.max(np.abs((H @ S2 - S2 @ H).toarray())) < 1e-12

        # anchor 4 (ED cross-check, exact numbers): H is Hermitian and its GS
        # energy is a real ED number; the direct sum and the charge agree so the
        # ED of either gives the same ground energy.
        assert np.max(np.abs((H - H.getH()).toarray())) < 1e-12
        assert abs(edlib.ground_energy(H)
                   - edlib.ground_energy(charges[0])) < 1e-10

        # anchor 5 (second coupling set): uniform A_j = 1 -> closed-form GS
        # -(A/4)(N_b+2), matched to ED at 1e-10.
        sx, sy, sz = edlib.spin_ops(L)
        Hu = sp.csr_matrix((2 ** L, 2 ** L), dtype=complex)
        for j in range(1, L):
            Hu = Hu + _dot(sx, sy, sz, 0, j)
        assert abs(edlib.ground_energy(Hu)
                   - uniform_e0_closed_form(N_bath)) < 1e-10


if __name__ == "__main__":
    oracle_main(compute, {"N_bath": (int, 5)})
