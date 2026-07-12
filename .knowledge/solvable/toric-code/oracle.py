"""Toric-code oracle: H = -sum_v A_v - sum_p B_p on an LxL square-lattice torus.

Qubits on edges (n = 2L^2). Star A_v = prod X over the 4 edges at vertex v;
plaquette B_p = prod Z over the 4 edges around face p. All A_v, B_p commute
(any two share 0 or 2 edges) -> commuting-projector stabilizer Hamiltonian,
solved exactly by counting stabilizer violations.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import ed, gf2  # noqa: E402


def edge_index(x, y, d, L):
    """Edge = (site (x,y), direction d): d=0 horizontal (+x), d=1 vertical (+y)."""
    return 2 * ((y % L) * L + (x % L)) + d


def star_edges(x, y, L):
    """Four edges meeting at vertex (x,y): E/W horizontals, N/S verticals."""
    return [edge_index(x, y, 0, L),        # east  (to +x)
            edge_index(x - 1, y, 0, L),    # west  (from -x)
            edge_index(x, y, 1, L),        # north (to +y)
            edge_index(x, y - 1, 1, L)]    # south (from -y)


def plaquette_edges(x, y, L):
    """Four edges around the face whose SW corner is vertex (x,y)."""
    return [edge_index(x, y, 0, L),        # bottom  horizontal
            edge_index(x, y + 1, 0, L),    # top     horizontal
            edge_index(x, y, 1, L),        # left    vertical
            edge_index(x + 1, y, 1, L)]    # right   vertical


def stabilizer_rows(L):
    """Binary symplectic rows (x|z), length 2n, for all stars then plaquettes."""
    n = 2 * L * L
    rows = []
    for y in range(L):
        for x in range(L):
            xz = [0] * (2 * n)
            for e in star_edges(x, y, L):        # A_v: X-type
                xz[e] = 1
            rows.append(xz)
    for y in range(L):
        for x in range(L):
            xz = [0] * (2 * n)
            for e in plaquette_edges(x, y, L):   # B_p: Z-type
                xz[n + e] = 1
            rows.append(xz)
    return rows, n


def compute(L=3):
    """Toric-code exact quantities on the LxL torus."""
    rows, n = stabilizer_rows(L)
    gsd = 2 ** gf2.stabilizer_gsd_log2(rows, n)
    return {
        "gsd": gsd,          # ground-state degeneracy = 2^{2g} = 4 on the torus
        "gap_pair": 4.0,     # cheapest excitation is a PAIR of anyons: dE = 4 (J=1)
        "n_qubits": n,
    }


def _ed_hamiltonian(L):
    """-sum A_v - sum B_p as a sparse operator (small L only)."""
    n = 2 * L * L
    px, _, pz = ed.pauli_ops(n)

    def prod(ops):
        out = ops[0]
        for o in ops[1:]:
            out = out @ o
        return out

    H = None
    for y in range(L):
        for x in range(L):
            A = prod([px[e] for e in star_edges(x, y, L)])
            B = prod([pz[e] for e in plaquette_edges(x, y, L)])
            H = -A - B if H is None else H - A - B
    return H


def self_test():
    # GSD = 4 on the torus for a range of sizes (size-independent, = 2^{2g})
    for L in (2, 3, 4):
        assert compute(L)["gsd"] == 4, L
        assert compute(L)["n_qubits"] == 2 * L * L
    # ED cross-check at L=2 (8 qubits, dim 256): 4-fold ground space, pair gap 4
    H = _ed_hamiltonian(2)
    assert ed.ground_states(H) == 4
    assert abs(ed.gap(H) - 4.0) < 1e-10


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 3)})
