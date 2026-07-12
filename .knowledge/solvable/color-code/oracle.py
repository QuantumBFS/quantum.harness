"""Color-code oracle: 6.6.6 (hexagonal) color code on a 3-colorable torus.

Qubits live on the VERTICES of a honeycomb lattice (degree 3); every hexagonal
face carries one X-stabilizer (X^6) AND one Z-stabilizer (Z^6). A cells x cells
torus of unit cells has F = cells^2 hexagons and n = 2*cells^2 qubits. Any two
hexagons share 0 or 2 vertices, so all face stabilizers commute (CSS) -> a
commuting-projector stabilizer Hamiltonian. Face 3-colorability (needed to read
the code as two toric codes) requires cells divisible by 3.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import gf2  # noqa: E402


def vertex_index(sub, i, j, cells):
    """Global qubit index for sublattice sub in {0=A,1=B}, unit cell (i,j)."""
    return sub * cells * cells + (i % cells) * cells + (j % cells)


def hexagon(i, j, cells):
    """Six vertices of the hexagon of unit cell (i,j) (traced 6-cycle)."""
    A, B = 0, 1
    return [
        vertex_index(A, i, j, cells),
        vertex_index(B, i, j, cells),
        vertex_index(A, i + 1, j, cells),
        vertex_index(B, i + 1, j - 1, cells),
        vertex_index(A, i + 1, j - 1, cells),
        vertex_index(B, i, j - 1, cells),
    ]


def stabilizer_rows(cells):
    """Binary symplectic rows (x|z): one X-face then one Z-face per hexagon."""
    n = 2 * cells * cells
    rows = []
    for i in range(cells):
        for j in range(cells):
            verts = hexagon(i, j, cells)
            xrow = [0] * (2 * n)
            zrow = [0] * (2 * n)
            for v in verts:
                xrow[v] = 1          # X-type face
                zrow[n + v] = 1      # Z-type face
            rows.append(xrow)
            rows.append(zrow)
    return rows, n


def compute(cells=3):
    """Color-code exact quantities on the cells x cells honeycomb torus."""
    rows, n = stabilizer_rows(cells)
    gsd = 2 ** gf2.stabilizer_gsd_log2(rows, n)
    return {
        "gsd": gsd,          # ground-state degeneracy = 2^{4g} = 16 on the torus
        "n_qubits": n,
        "n_hexagons": cells * cells,
    }


def _three_coloring_ok(cells):
    """c(i,j)=(i-j) mod 3 gives distinct colors to every pair of adjacent faces.

    Adjacent hexagons (sharing 2 vertices) sit at triangular-lattice offsets
    {(+-1,0),(0,+-1),(+1,-1),(-1,+1)}; requires cells % 3 == 0 to close on the
    torus.
    """
    if cells % 3 != 0:
        return False
    faces = {(i, j): set(hexagon(i, j, cells))
             for i in range(cells) for j in range(cells)}
    for (i, j), va in faces.items():
        for (k, l), vb in faces.items():
            if (i, j) < (k, l) and len(va & vb) == 2:  # adjacent
                if (i - j) % 3 == (k - l) % 3:
                    return False
    return True


def self_test():
    # GSD = 16 on the torus, size-independent (= 2^{4g}, g = 1)
    assert compute(cells=3)["gsd"] == 16
    assert compute(cells=6)["gsd"] == 16
    assert compute(cells=3)["n_qubits"] == 18
    assert compute(cells=3)["n_hexagons"] == 9
    # stabilizer_gsd_log2 asserts pairwise commutation internally: reaching 16
    # already proves every X-/Z-face pair commutes on this honeycomb torus.
    # Face 3-coloring is proper exactly when cells is a multiple of 3.
    assert _three_coloring_ok(3)
    assert _three_coloring_ok(6)


if __name__ == "__main__":
    oracle_main(compute, {"cells": (int, 3)})
