"""X-cube fracton oracle: the X-cube commuting-projector stabilizer model.

L x L x L cubic torus, spin-1/2 qubits on the EDGES (n = 3 L^3). Two stabilizer
families:

  * one X-type cube operator per elementary cube = product of X over its 12 edges;
  * three planar Z-type "crosses" per vertex = product of Z over the 4 coplanar
    edges incident to the vertex in the xy, yz and zx planes (only two of the
    three are independent at each vertex; all three are included and the GF(2)
    rank removes the dependency).

Any cube and any planar cross share an even number of edges, so every stabilizer
commutes -> a commuting-projector stabilizer Hamiltonian. The subextensive
ground-state degeneracy log2 GSD = 6L - 3 is the headline exact result
[@VijayHaahFu2016]. Rows are built by XOR-toggling bit positions so that any edge
appearing twice (e.g. a periodic wrap at L=2) cancels rather than double-counts.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import gf2  # noqa: E402


def edge_index(x, y, z, d, L):
    """Edge = (vertex (x,y,z), direction d): d=0 +x, d=1 +y, d=2 +z. n = 3L^3."""
    return 3 * (((z % L) * L + (y % L)) * L + (x % L)) + d


def cube_edges(x, y, z, L):
    """The 12 edges of the elementary cube with SW-bottom corner (x,y,z)."""
    return [
        # 4 x-edges (span +x) on the four (y,z) corners of the cube
        edge_index(x, y, z, 0, L),     edge_index(x, y + 1, z, 0, L),
        edge_index(x, y, z + 1, 0, L), edge_index(x, y + 1, z + 1, 0, L),
        # 4 y-edges (span +y) on the four (x,z) corners
        edge_index(x, y, z, 1, L),     edge_index(x + 1, y, z, 1, L),
        edge_index(x, y, z + 1, 1, L), edge_index(x + 1, y, z + 1, 1, L),
        # 4 z-edges (span +z) on the four (x,y) corners
        edge_index(x, y, z, 2, L),     edge_index(x + 1, y, z, 2, L),
        edge_index(x, y + 1, z, 2, L), edge_index(x + 1, y + 1, z, 2, L),
    ]


def vertex_crosses(x, y, z, L):
    """Three planar 4-edge crosses at vertex (x,y,z), in the xy, yz, zx planes."""
    ex_p, ex_m = edge_index(x, y, z, 0, L), edge_index(x - 1, y, z, 0, L)  # +/-x
    ey_p, ey_m = edge_index(x, y, z, 1, L), edge_index(x, y - 1, z, 1, L)  # +/-y
    ez_p, ez_m = edge_index(x, y, z, 2, L), edge_index(x, y, z - 1, 2, L)  # +/-z
    return [
        [ex_p, ex_m, ey_p, ey_m],   # xy-plane cross
        [ey_p, ey_m, ez_p, ez_m],   # yz-plane cross
        [ez_p, ez_m, ex_p, ex_m],   # zx-plane cross
    ]


def _xor_row(support, offset, n):
    """Symplectic row of length 2n; XOR-toggle each edge (duplicates cancel)."""
    row = [0] * (2 * n)
    for e in support:
        row[offset + e] ^= 1
    return row


def stabilizer_rows(L):
    """Binary symplectic rows (x|z): X-type cubes then Z-type vertex crosses."""
    n = 3 * L * L * L
    rows = []
    for z in range(L):
        for y in range(L):
            for x in range(L):
                rows.append(_xor_row(cube_edges(x, y, z, L), 0, n))     # X-type
    for z in range(L):
        for y in range(L):
            for x in range(L):
                for cross in vertex_crosses(x, y, z, L):
                    rows.append(_xor_row(cross, n, n))                  # Z-type
    return rows, n


def compute(L=3):
    """X-cube exact quantities on the L x L x L cubic torus."""
    rows, n = stabilizer_rows(L)
    gsd_log2 = gf2.stabilizer_gsd_log2(rows, n)
    return {
        "gsd_log2": gsd_log2,   # log2 GSD = 6L - 3 (subextensive) [@VijayHaahFu2016]
        "n_qubits": n,          # 3 L^3 edges
    }


def self_test():
    # Subextensive topological degeneracy log2 GSD = 6L - 3 (Vijay-Haah-Fu).
    # Reaching it certifies (via the assertion inside stabilizer_gsd_log2) that
    # every cube / planar-cross pair commutes on the cubic torus.
    for L in (2, 3):
        out = compute(L=L)
        assert out["gsd_log2"] == 6 * L - 3, (L, out["gsd_log2"])
        assert out["n_qubits"] == 3 * L ** 3, L


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 3)})
