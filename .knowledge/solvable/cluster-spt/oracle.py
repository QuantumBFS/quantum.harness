"""Cluster-state SPT oracle: H = -sum_i Z_{i-1} X_i Z_{i+1} (Pauli, 1D chain).

The stabilizers K_i = Z_{i-1} X_i Z_{i+1} all commute -> commuting-projector
Hamiltonian whose unique (PBC) ground state is the 1D cluster state, a
Z2 x Z2 symmetry-protected topological (SPT) state and the canonical
measurement-based-quantum-computation resource state.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed, gf2  # noqa: E402


def stabilizer_rows(L, pbc=True):
    """Binary (x|z) rows for K_i = Z_{i-1} X_i Z_{i+1}.

    PBC: one stabilizer per site (indices mod L). OBC: only the L-2 interior
    sites i = 1..L-2 carry a stabilizer (the two boundary sites lose one each).
    """
    sites = range(L) if pbc else range(1, L - 1)
    rows = []
    for i in sites:
        xz = [0] * (2 * L)
        xz[i] = 1                    # X_i
        xz[L + (i - 1) % L] = 1      # Z_{i-1}
        xz[L + (i + 1) % L] = 1      # Z_{i+1}
        rows.append(xz)
    return rows


def _in_rowspan(rows, target):
    """True iff GF(2) `target` lies in the row span of `rows` (rank test)."""
    r = gf2.rank(rows)
    return gf2.rank(list(rows) + [target]) == r


def _pauli_row(L, paulis):
    """Symplectic (x|z) row from {site: 'X'|'Y'|'Z'} (built independently of K_i)."""
    xz = [0] * (2 * L)
    for i, p in paulis.items():
        if p in ("X", "Y"):
            xz[i] = 1
        if p in ("Z", "Y"):
            xz[L + i] = 1
    return xz


def string_order_value(L, a, b):
    """Exact <O> in the cluster ground state for the decorated SPT string
    operator on endpoints a < b:

    O = Z_a Y_{a+1} X_{a+2}...X_{b-2} Y_{b-1} Z_b = prod_{i=a+1}^{b-1} K_i.

    The symplectic vector of O is constructed directly from its Pauli content
    (NOT by multiplying K_i together) and then checked for membership in the
    GF(2) row span of the stabilizers — so the check can genuinely fail. Being
    a product of stabilizers, O has <O> = +1 exactly in every ground state.
    As a negative control, the naive undecorated string Z_a X...X Z_b is
    checked to be OUTSIDE the row span (its ground-state expectation is 0).
    """
    assert b - a >= 3
    rows = stabilizer_rows(L, pbc=True)
    decorated = {a: "Z", a + 1: "Y", b - 1: "Y", b: "Z"}
    decorated.update({i: "X" for i in range(a + 2, b - 1)})
    naive = {a: "Z", b: "Z"}
    naive.update({i: "X" for i in range(a + 1, b)})
    assert _in_rowspan(rows, _pauli_row(L, decorated)), \
        "decorated string op is not a stabilizer product"
    assert not _in_rowspan(rows, _pauli_row(L, naive)), \
        "naive ZX...XZ string unexpectedly in the stabilizer span"
    return 1.0


def compute(L=8):
    """Cluster-SPT exact quantities on the L-site chain."""
    gsd_pbc = 2 ** gf2.stabilizer_gsd_log2(stabilizer_rows(L, pbc=True), L)
    gsd_obc = 2 ** gf2.stabilizer_gsd_log2(stabilizer_rows(L, pbc=False), L)
    return {
        "gsd_pbc": gsd_pbc,                       # unique GS (trivial in bulk)
        "gsd_obc": gsd_obc,                       # 4 = 2 protected edge modes
        "gap": 2.0,                               # one flipped stabilizer, PBC
        "string_order": string_order_value(L, 1, L - 2),  # SPT order = 1 exactly
    }


def _ed_hamiltonian(L, pbc=True):
    px, py, pz = ed.pauli_ops(L)
    sites = range(L) if pbc else range(1, L - 1)
    H = None
    for i in sites:
        K = pz[(i - 1) % L] @ px[i] @ pz[(i + 1) % L]
        H = -K if H is None else H - K
    return H


def self_test():
    # GF(2) degeneracy counting
    assert compute(L=8)["gsd_pbc"] == 1
    assert compute(L=8)["gsd_obc"] == 4
    assert compute(L=8)["string_order"] == 1.0
    # ED cross-check, L = 8 (dim 256)
    Hp = _ed_hamiltonian(8, pbc=True)
    assert ed.ground_states(Hp) == 1
    assert abs(ed.gap(Hp) - 2.0) < 1e-10
    Ho = _ed_hamiltonian(8, pbc=False)
    assert ed.ground_states(Ho) == 4
    # ED value of the SPT string operator in the unique PBC ground state
    px, py, pz = ed.pauli_ops(8)
    a, b = 1, 6
    O = pz[a]
    for k in range(a + 1, b):
        O = O @ (py[k] if k in (a + 1, b - 1) else px[k])
    O = O @ pz[b]
    Hd = Hp.toarray()
    w, v = np.linalg.eigh(Hd)
    gs = v[:, 0]
    assert abs((gs.conj() @ (O @ gs)) - 1.0) < 1e-10


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 8)})
