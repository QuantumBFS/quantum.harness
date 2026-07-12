"""Long-range Kitaev chain oracle: NN hopping + power-law p-wave pairing, PBC.

    H = -mu sum (c_i^dag c_i - 1/2) - t sum_NN (c_i^dag c_{i+1} + h.c.)
        + sum_{i<j} Delta_ij (c_i c_j + h.c.),   Delta_ij = Delta / d(i,j)^alpha

with d(i,j) the minimum-image chain distance on the ring and a cutoff at L/2.
Still a Bogoliubov-diagonalizable (quadratic) fermion model, so the ground-state
energy and BdG spectrum are exact; a native fermion Hamiltonian, so no boundary
parity subtlety. As alpha -> infinity the pairing collapses to nearest neighbor
and the model recovers the NN Kitaev chain. Following Vodola et al., for
alpha < 1 the model hosts massive Dirac-like edge modes and violates the area
law -- physics beyond spectrum/energy, out of this script's scope.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed, quadratic  # noqa: E402


def _pairs(L, alpha, delta):
    """List (i, j, amp) for the term amp*(c_i c_j + h.c.), each unordered pair once.

    Range ell = 1..L//2 with minimum-image distance ell; the antipodal bond
    (ell == L/2, even L) is counted once by restricting i < L/2.
    """
    out = []
    for ell in range(1, L // 2 + 1):
        amp = delta / ell ** alpha
        for i in range(L):
            if ell == L // 2 and L % 2 == 0 and i >= L // 2:
                continue  # antipodal pair {i, i+L/2} already taken from the other end
            j = (i + ell) % L
            out.append((i, j, amp))
    return out


def matrices(L, mu=0.0, t=1.0, delta=1.0, alpha=1.0):
    """BdG matrices (A Hermitian, B antisymmetric) for the long-range chain."""
    A = np.zeros((L, L))
    B = np.zeros((L, L))
    for i in range(L):
        A[i, i] = -mu
        j = (i + 1) % L
        A[i, j] += -t  # NN hopping only
        A[j, i] += -t
    for i, j, amp in _pairs(L, alpha, delta):
        # amp*(c_i c_j + h.c.): coeff of c^dag_i c^dag_j is -amp -> B[i,j]=-amp.
        B[i, j] += -amp
        B[j, i] += amp
    return A, B


def compute(L=64, mu=0.0, t=1.0, delta=1.0, alpha=1.0):
    """Long-range Kitaev exact quantities via BdG diagonalization (PBC)."""
    A, B = matrices(L, mu, t, delta, alpha)
    e0 = quadratic.bdg_ground_energy(A, B) / L + mu / 2
    gap = float(quadratic.bdg_energies(A, B)[0])
    return {"e0_per_site": e0, "gap": gap}


def _load_kitaev():
    path = Path(__file__).resolve().parents[1] / "kitaev-chain" / "oracle.py"
    spec = importlib.util.spec_from_file_location("oracle_kitaev_chain", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def self_test():
    # anchor 1: alpha -> inf recovers the NN Kitaev chain e0 (import, do not duplicate)
    kitaev = _load_kitaev()
    lr = compute(L=64, alpha=30.0, mu=0.5, t=1.0, delta=1.0)
    nn = kitaev.compute(L=64, mu=0.5, t=1.0, delta=1.0)
    assert abs(lr["e0_per_site"] - nn["e0_per_site"]) < 1e-6, (lr, nn)
    # anchor 2: BdG GS energy matches brute-force ED at L=8, alpha=1.5
    import scipy.sparse as sp
    L, mu, t, delta, alpha = 8, 0.5, 1.0, 1.0, 1.5
    c, cd = ed.fermion_ops(L)
    Id = sp.identity(2 ** L, dtype=complex, format="csr")
    H = 0 * Id
    for i in range(L):
        H = H - mu * (cd[i] @ c[i] - 0.5 * Id)
        j = (i + 1) % L
        H = H - t * (cd[i] @ c[j] + cd[j] @ c[i])
    for i, j, amp in _pairs(L, alpha, delta):
        H = H + amp * (c[i] @ c[j] + cd[j] @ cd[i])
    assert abs(ed.ground_energy(H) / L - compute(L=L, mu=mu, t=t, delta=delta, alpha=alpha)["e0_per_site"]) < 1e-10


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 64), "mu": (float, 0.0), "t": (float, 1.0),
                          "delta": (float, 1.0), "alpha": (float, 1.0)})
