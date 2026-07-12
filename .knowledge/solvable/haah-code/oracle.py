"""Haah cubic-code oracle: the Type-II fracton stabilizer code (Haah code 1).

L x L x L cubic torus, TWO qubits per site (n = 2 L^3). One X-type and one Z-type
generator per site, each supported on the eight corners of a unit cube and related
by spatial inversion + qubit swap. In polynomial notation over
F2[x,y,z]/(x^L-1, y^L-1, z^L-1), with f = 1 + x + y + z and g = 1 + xy + yz + zx:

  * X-generator at site s:  qubit 0 <- f,       qubit 1 <- g
  * Z-generator at site s:  qubit 0 <- gbar,    qubit 1 <- fbar   (bar: x -> x^-1)

Commutation is automatic: the CSS symplectic overlap is f*g + g*f = 0 over F2, so
every X/Z translate pair commutes (the swapped-inverse arrangement is exactly what
makes the code well defined). Commutation is nonetheless re-checked at runtime --
`stabilizer_gsd_log2` asserts pairwise commutation, so any transcription error
throws rather than returning a wrong number. This is a Type-II fracton phase:
there are NO string logical operators at all [@Haah2011], and the ground-state
degeneracy k(L) = log2 GSD has a subextensive, number-theoretic dependence on L
with no simple closed form (bounded by 2 <= k <= 4L - 2) [@Haah2011].

Rows are built by XOR-toggling bit positions so a Pauli landing twice on a qubit
at a periodic wrap cancels rather than double-counting.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import gf2  # noqa: E402

# Monomial supports (dx, dy, dz) of the two defining polynomials.
F = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]          # f = 1 + x + y + z
G = [(0, 0, 0), (1, 1, 0), (0, 1, 1), (1, 0, 1)]          # g = 1 + xy + yz + zx
FBAR = [(-a, -b, -c) for (a, b, c) in F]                  # fbar (spatial inverse)
GBAR = [(-a, -b, -c) for (a, b, c) in G]                  # gbar


def qubit_index(x, y, z, q, L):
    """Global index of qubit q in {0,1} at site (x,y,z). n = 2 L^3."""
    return 2 * (((z % L) * L + (y % L)) * L + (x % L)) + q


def _stab_row(x, y, z, poly_q0, poly_q1, offset, n, L):
    """Symplectic row: XOR-toggle qubit-0 support poly_q0 and qubit-1 support poly_q1."""
    row = [0] * (2 * n)
    for (dx, dy, dz) in poly_q0:
        row[offset + qubit_index(x + dx, y + dy, z + dz, 0, L)] ^= 1
    for (dx, dy, dz) in poly_q1:
        row[offset + qubit_index(x + dx, y + dy, z + dz, 1, L)] ^= 1
    return row


def stabilizer_rows(L):
    """Binary symplectic rows (x|z): one X- then one Z-generator per site."""
    n = 2 * L * L * L
    rows = []
    for z in range(L):
        for y in range(L):
            for x in range(L):
                rows.append(_stab_row(x, y, z, F, G, 0, n, L))       # X-type (x block)
                rows.append(_stab_row(x, y, z, GBAR, FBAR, n, n, L))  # Z-type (z block)
    return rows, n


def compute(L=3):
    """Haah cubic-code exact quantities on the L x L x L cubic torus."""
    rows, n = stabilizer_rows(L)
    k = gf2.stabilizer_gsd_log2(rows, n)
    return {
        "gsd_log2": k,      # k = log2 GSD, subextensive & number-theoretic in L
        "n_qubits": n,      # 2 L^3
    }


def self_test():
    # Commutation is asserted inside stabilizer_gsd_log2: no throw over L in
    # {2,3,4} certifies the transcription (every X/Z generator pair commutes).
    ks = {L: compute(L=L)["gsd_log2"] for L in (2, 3, 4)}
    assert all(k >= 2 for k in ks.values()), ks          # 2 <= k always [@Haah2011]
    assert all(k <= 4 * L - 2 for L, k in ks.items()), ks  # k <= 4L-2 [@Haah2011]
    assert ks[4] >= ks[2], ks                             # more room at larger L
    # Determinism: a second construction agrees bit-for-bit.
    assert ks == {L: compute(L=L)["gsd_log2"] for L in (2, 3, 4)}, ks
    assert all(compute(L=L)["n_qubits"] == 2 * L ** 3 for L in (2, 3, 4))
    # Regression anchors (computed by this script via exact GF(2) rank; see
    # ORACLE.md benchmarks). Cross-checks against published statements [@Haah2011]:
    #   * k(3) == 2: L=3 has none of the special factors {2,15,63}, so it sits at
    #     the generic four-fold degeneracy GSD = 4 (k = 2) -- matches the
    #     literature that all factor-free L give k = 2.
    #   * k(2) == 6 == 4*2-2 and k(4) == 14 == 4*4-2: the special factor-2 sizes
    #     here saturate the published upper bound k <= 4L-2.
    assert ks == {2: 6, 3: 2, 4: 14}, ks
    assert ks[2] == 4 * 2 - 2 and ks[4] == 4 * 4 - 2, ks  # saturate 4L-2 bound


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 3)})
