"""Kitaev p-wave chain oracle: native spinless-fermion BdG model, PBC.

    H = -mu sum (c_i^dag c_i - 1/2) - t sum (c_i^dag c_{i+1} + h.c.)
                                    + Delta sum (c_i c_{i+1} + h.c.)

Single-particle dispersion eps(k) = sqrt((2t cos k + mu)^2 + 4 Delta^2 sin^2 k).
Topological (Majorana end modes under OBC) iff |mu| < 2t; bulk gap closes at
|mu| = 2t. This is a genuine fermion Hamiltonian, so its ground state spans the
full Fock space and `quadratic.bdg_ground_energy` is the exact GS energy with no
boundary-sector / parity subtlety (contrast xy-chain, where PBC spins map to a
parity-dependent fermion boundary).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed, quadratic  # noqa: E402


def matrices(L, mu=0.0, t=1.0, delta=1.0):
    """BdG matrices (A Hermitian, B antisymmetric) for the PBC Kitaev chain.

    H = sum A_ij c_i^dag c_j + 1/2 sum (B_ij c_i^dag c_j^dag + h.c.) + mu*L/2.
    Field -mu(n_i - 1/2) -> A[i,i] = -mu and an additive constant +mu/2 per site.
    Hopping -t(c^dag_i c_{i+1}+h.c.) -> A[i,i+1]=A[i+1,i]=-t.
    Pairing  Delta(c_i c_{i+1}+h.c.) -> coeff of c^dag_i c^dag_{i+1} is -Delta,
             so B[i,i+1]=-Delta, B[i+1,i]=+Delta.
    """
    A = np.zeros((L, L))
    B = np.zeros((L, L))
    for i in range(L):
        j = (i + 1) % L
        A[i, i] = -mu
        A[i, j] += -t
        A[j, i] += -t
        B[i, j] += -delta
        B[j, i] += delta
    return A, B


def compute(L=64, mu=0.0, t=1.0, delta=1.0):
    """Kitaev-chain exact quantities via BdG diagonalization (PBC)."""
    A, B = matrices(L, mu, t, delta)
    # E0 = bdg_ground_energy + mu*L/2 (constant from -mu(n-1/2)); per site + mu/2.
    e0 = quadratic.bdg_ground_energy(A, B) / L + mu / 2
    gap = float(quadratic.bdg_energies(A, B)[0])
    return {
        "e0_per_site": e0,
        "gap": gap,
        "topological": bool(abs(mu) < 2 * t),
    }


def self_test():
    # anchor 1: sweet spot t=Delta, mu=0 -> flat band eps = 2t exactly
    e = quadratic.bdg_energies(*matrices(64, mu=0.0, t=1.0, delta=1.0))
    assert np.allclose(e, 2.0, atol=1e-12), e
    # anchor 2: gap closes at |mu| = 2t
    assert compute(L=400, mu=2.0, t=1.0, delta=1.0)["gap"] < 2e-2
    # anchor 3: topological flag = (|mu| < 2t)
    assert compute(mu=1.0)["topological"] and not compute(mu=3.0)["topological"]
    # anchor 4: BdG GS energy matches brute-force ED at L=8, two parameter points
    import scipy.sparse as sp
    L = 8
    c, cd = ed.fermion_ops(L)
    Id = sp.identity(2 ** L, dtype=complex, format="csr")
    for mu, t, delta in [(0.5, 1.0, 1.0), (1.7, 0.8, 0.6)]:
        H = 0 * Id
        for i in range(L):
            j = (i + 1) % L
            H = H - mu * (cd[i] @ c[i] - 0.5 * Id)
            H = H - t * (cd[i] @ c[j] + cd[j] @ c[i])
            H = H + delta * (c[i] @ c[j] + cd[j] @ cd[i])
        assert abs(ed.ground_energy(H) / L - compute(L=L, mu=mu, t=t, delta=delta)["e0_per_site"]) < 1e-10, (mu, t, delta)


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 64), "mu": (float, 0.0), "t": (float, 1.0), "delta": (float, 1.0)})
