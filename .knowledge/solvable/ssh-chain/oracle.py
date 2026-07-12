"""SSH (Su-Schrieffer-Heeger) chain oracle: native spinless-fermion dimerized
hopping model.

    H = sum_i (v a_i^dag b_i + w b_i^dag a_{i+1} + h.c.)

Two-site (A,B) unit cell, `v` the intracell (A-B, same cell) hopping, `w` the
intercell (B-A, cell i to i+1) hopping. Bloch off-diagonal g(k) = v + w e^{ik};
single-particle bands eps(k) = +-|g(k)|. Topological (winding nu=1, two
protected OBC zero modes) for |w|>|v|; trivial (nu=0) for |v|>|w|; bulk gap
closes at |v|=|w|. This is a genuine number-conserving fermion hopping problem (no pairing),
so the many-body ground state at half filling is exactly the Slater
determinant that fills every negative-energy single-particle eigenstate -
no BdG machinery needed, unlike kitaev-chain/xy-chain.

Density convention: `L` below counts *unit cells* (not physical sites), the
same convention used for the OBC edge-mode Hamiltonian (2L x 2L, matching the
brief's code sketch) and throughout `models/ssh/MODEL.md` ("N cells"). At
half filling exactly one fermion occupies the lower band per unit cell, so
`e0_per_site` here means "ground energy per unit cell" == "energy per
particle" (they coincide at half filling) - i.e. E_total / L, NOT E_total /
(2L). This is exactly the quantity the closed form
`-(1/2pi) int |v + w e^{ik}| dk` computes. (The ED cross-check in
self_test() compares TOTAL energies - sum of negative single-particle
eigenvalues vs ed.ground_energy - with no division, so it holds under
either density convention.)
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed, topology  # noqa: E402


def matrices(L, v=0.5, w=1.0):
    """Real-space OBC single-particle hopping matrix (2L x 2L), L unit cells.

    Site ordering: 2i = A_i, 2i+1 = B_i, i = 0..L-1.
    """
    H1 = np.zeros((2 * L, 2 * L))
    for i in range(L):
        H1[2 * i, 2 * i + 1] = H1[2 * i + 1, 2 * i] = v
        if i < L - 1:
            H1[2 * i + 1, 2 * i + 2] = H1[2 * i + 2, 2 * i + 1] = w
    return H1


def compute(L=100, v=0.5, w=1.0, nk=2001):
    """SSH-chain exact quantities: winding, gap, OBC edge modes, e0 per unit cell."""
    nu = topology.winding(lambda k: v + w * np.exp(1j * k), nk=nk)
    gap = 2.0 * abs(abs(v) - abs(w))
    H1 = matrices(L, v, w)
    ev = np.linalg.eigvalsh(H1)
    n_edge = int(np.sum(np.abs(ev) < gap / 4)) if gap > 0 else 0
    ks = np.linspace(0.0, 2.0 * np.pi, nk, endpoint=False)
    e0_per_site = -np.mean(np.abs(v + w * np.exp(1j * ks)))  # per unit cell
    xi = 1.0 / np.log(abs(w) / abs(v)) if abs(w) > abs(v) > 0 else float("nan")
    return {
        "winding": nu,
        "gap": gap,
        "n_edge_modes_obc": n_edge,
        "e0_per_site": float(e0_per_site),
        "edge_decay_length": float(xi),
    }


def self_test():
    assert compute(v=0.5, w=1.0)["winding"] == 1
    assert compute(v=1.0, w=0.5)["winding"] == 0
    assert compute(v=0.5, w=1.0)["n_edge_modes_obc"] == 2
    assert abs(compute(v=0.5, w=1.0)["gap"] - 1.0) < 1e-12

    # ED cross-check: filled-band (half-filling) many-body ground energy at
    # L=4 unit cells (8 sites) must equal the sum of negative single-particle
    # eigenvalues of the same OBC hopping matrix (pure hopping, no pairing,
    # so "fill every negative mode" is exactly the many-body ground state).
    import scipy.sparse as sp

    L, v, w = 4, 0.5, 1.0
    H1 = matrices(L, v, w)
    ev = np.linalg.eigvalsh(H1)
    e_filled = float(ev[ev < 0].sum())

    c, cd = ed.fermion_ops(2 * L)
    Id = sp.identity(2 ** (2 * L), dtype=complex, format="csr")
    H = 0 * Id
    for i in range(L):
        H = H + v * (cd[2 * i] @ c[2 * i + 1] + cd[2 * i + 1] @ c[2 * i])
        if i < L - 1:
            H = H + w * (cd[2 * i + 1] @ c[2 * i + 2] + cd[2 * i + 2] @ c[2 * i + 1])
    assert abs(e_filled - ed.ground_energy(H)) < 1e-10


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 100), "v": (float, 0.5), "w": (float, 1.0)})
