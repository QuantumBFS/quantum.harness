"""Dimer-covering (perfect-matching) oracle for the m x n square lattice.

Counting problem, not an energy spectrum: Z(m,n) is the number of ways to tile
an m x n grid graph with dominoes (dimers), i.e. the number of perfect matchings
of the grid, with OPEN (free) boundaries. Kasteleyn (1961) evaluated the
Pfaffian of the oriented adjacency matrix in closed product form:

    Z(m,n) = prod_{j=1}^{m} prod_{k=1}^{n}
             ( 4 cos^2(j pi/(m+1)) + 4 cos^2(k pi/(n+1)) )^{1/4}

(the symmetric full-range form; the 1/4 power compensates the j<->m+1-j and
k<->n+1-k double counting). Z is an exact integer whenever mn is even, and is
0 when mn is odd (no perfect matching exists). Evaluated in log space,
ln Z = (1/4) sum_{j,k} ln(...), then exponentiated and rounded to the integer.

Ground truth: a broken-profile / bitmask enumeration of domino tilings, which
agrees with the product formula for every board with mn <= 16.

Thermodynamic limit: the entropy per site (1/N) ln Z -> G/pi, where G is
Catalan's constant (~0.9159655942), i.e. ~0.29156 nat/site.
"""
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402

CATALAN = 0.915965594177219015  # Catalan's constant G


def ln_Z(m, n):
    """ln Z(m,n), the Kasteleyn product formula in log space (open boundaries).

    Returns -inf when mn is odd (a zero factor appears exactly, some j=(m+1)/2
    and k=(n+1)/2 making both cosines vanish); short-circuited on the parity so
    floating-point cos(pi/2) ~ 6e-17 cannot leak a spurious finite value.
    """
    if (m * n) % 2 == 1:
        return -np.inf
    j = np.arange(1, m + 1)[:, None]
    k = np.arange(1, n + 1)[None, :]
    term = 4.0 * np.cos(j * np.pi / (m + 1)) ** 2 + 4.0 * np.cos(k * np.pi / (n + 1)) ** 2
    with np.errstate(divide="ignore"):
        return 0.25 * np.sum(np.log(term))


def count(m, n):
    """Exact number of dimer coverings (perfect matchings) of the m x n grid.

    Rounds exp(ln Z) to the nearest integer; asserts the pre-rounding value is
    integral to relative tol 1e-6. The returned integer is EXACT only while
    Z < 2^53 (~9e15): true through 8x8 (Z = 12988816) and up to ~10x10; for
    larger boards (e.g. 12x12) float64 rounds the trailing digits, so trust
    ln_Z / entropy there rather than the integer.
    """
    L = ln_Z(m, n)
    if not np.isfinite(L):
        return 0
    z = np.exp(L)
    zr = round(z)
    assert abs(z - zr) <= 1e-6 * max(zr, 1.0), (m, n, z)
    return int(zr)


def entropy_per_site(m, n):
    """(1/N) ln Z, the dimer entropy per site; -> Catalan G/pi as m, n -> inf."""
    return ln_Z(m, n) / (m * n)


def catalan_limit():
    """Thermodynamic-limit dimer entropy per site, G/pi (Catalan's constant)."""
    return CATALAN / np.pi


def _brute_count(m, n):
    """Ground-truth domino-tiling count by broken-profile bitmask recursion.

    Fills cells in row-major order; the first empty cell must be covered by a
    domino going right or down. Memoized on the occupancy bitmask. Intended for
    small boards (mn <= ~20).
    """
    full = (1 << (m * n)) - 1

    @lru_cache(maxsize=None)
    def rec(mask):
        if mask == full:
            return 1
        i = 0
        while (mask >> i) & 1:
            i += 1
        r, c = divmod(i, n)
        total = 0
        if c + 1 < n and not (mask >> (i + 1)) & 1:                 # horizontal
            total += rec(mask | (1 << i) | (1 << (i + 1)))
        if r + 1 < m and not (mask >> (i + n)) & 1:                 # vertical
            total += rec(mask | (1 << i) | (1 << (i + n)))
        return total

    return rec(0)


def compute(m=8, n=8):
    """Dimer coverings of the m x n square lattice (open boundaries)."""
    return {
        "n_coverings": count(m, n),
        "ln_Z": ln_Z(m, n),
        "entropy_per_site": entropy_per_site(m, n),
        "catalan_limit": catalan_limit(),
    }


def self_test():
    # anchor 1: small-board exact integer counts (closed-form product formula)
    assert count(2, 2) == 2
    assert count(2, 3) == 3
    assert count(4, 4) == 36
    assert count(8, 8) == 12988816
    # odd area -> no perfect matching
    assert count(3, 3) == 0
    assert count(5, 5) == 0
    # anchor 2: GROUND TRUTH -- brute-force enumeration equals the product
    # formula for every board with mn <= 16 (exact integer equality)
    for m in range(1, 17):
        for n in range(1, 17):
            if m * n > 16:
                continue
            assert _brute_count(m, n) == count(m, n), (m, n)
    # anchor 3: entropy per site approaches Catalan G/pi from below. Open
    # boundaries carry an O(1/L) boundary entropy deficit (L*deviation ~ 0.297,
    # roughly constant), so convergence is only algebraic: 16x16 sits ~6% below
    # the limit -- monotone but NOT yet within 2%. We assert the honest facts:
    # strict monotone approach from below, and that 64x64 (where 1/L has decayed
    # enough) is within 2% of G/pi.
    lim = catalan_limit()
    e8 = entropy_per_site(8, 8)
    e16 = entropy_per_site(16, 16)
    e64 = entropy_per_site(64, 64)
    assert e8 < e16 < e64 < lim, (e8, e16, e64, lim)          # monotone from below
    assert abs(e16 - lim) < abs(e8 - lim), (e8, e16, lim)     # 16 closer than 8
    assert abs(e16 - lim) < 0.07 * lim, (e16, lim)            # 16x16 within ~6.3%
    assert abs(e64 - lim) < 0.02 * lim, (e64, lim)            # 64x64 within 2%
    assert abs(lim - 0.2915609040) < 1e-9


if __name__ == "__main__":
    oracle_main(compute, {"m": (int, 8), "n": (int, 8)})
