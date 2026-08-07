#!/usr/bin/env python
"""Exhaustive enumeration of zero-dof (special-position) Wyckoff site
assignments for a given (space group, composition).

Motivation: CrystalFormer's sampling is probabilistic and can simply miss the
true discrete structure -- confirmed directly on Th2Se2O (SG123, dof=0): none
of 148 samples matched, and with zero continuous degrees of freedom there is
no refinement mechanism to recover from a wrong discrete pick (see
SUMMARY.md §6/§8). When every occupied site is a special (zero-dof) position,
the discrete choice is a small, exactly-enumerable combinatorial problem --
which special Wyckoff site of the space group does each element occupy --
unlike CrystalFormer's search over the full generative distribution. Exhaustive
enumeration is guaranteed to include the true structure (if within the search
cap); sampling is not.

Reuses CrystalFormer's own Wyckoff table (`crystalformer.src.wyckoff`) rather
than re-deriving one, so the notion of "which site" matches what CrystalFormer
itself would generate -- this is a supplementary candidate source for the same
pipeline, not an independent implementation that could disagree with it.
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np

CF = Path(__import__("os").environ.get("CRYSTALFORMER_DIR", Path.home() / "code/CrystalFormer"))
for _p in (CF, CF / "crystalformer" / "src"):
    sys.path.insert(0, str(_p))


def _zero_dof_sites(sg: int) -> list[tuple[int, np.ndarray]]:
    """(multiplicity, fixed fractional coordinate) for every special position
    of space group `sg` with zero continuous degrees of freedom."""
    from wyckoff import wyckoff_positions, from_xyz_str  # noqa: PLC0415

    sites = []
    for orbit in wyckoff_positions[sg - 1]:
        op0 = from_xyz_str(orbit[0])
        if np.linalg.matrix_rank(op0[:, :3]) == 0:  # pure translation: a fixed point
            sites.append((len(orbit), np.mod(op0[:, 3], 1.0)))
    return sites


def _orbit(sg: int, coord: np.ndarray, tol: float = 1e-4) -> np.ndarray:
    """Full symmetry-equivalent set of points for a fixed-coordinate site."""
    from pymatgen.symmetry.groups import SpaceGroup  # noqa: PLC0415

    ops = SpaceGroup.from_int_number(sg).symmetry_ops
    pts = []
    for op in ops:
        q = np.mod(op.operate(coord), 1.0)
        if not any(np.allclose((q - u) - np.round(q - u), 0.0, atol=tol) for u in pts):
            pts.append(q)
    return np.array(pts)


def _assignments(elements: list[tuple[str, int]], sites: list[tuple[int, np.ndarray]],
                 cap: int) -> list[list[tuple[str, int]]]:
    """All ways to assign disjoint subsets of `sites` (by index) to each
    element so each element's assigned multiplicities sum to its count.
    Returns a list of assignments; each assignment is [(element, site_idx), ...].
    """
    results: list[list[tuple[str, int]]] = []

    def backtrack(elem_i: int, used: set, assignment: list):
        if len(results) >= cap:
            return
        if elem_i == len(elements):
            results.append(list(assignment))
            return
        elem, need = elements[elem_i]
        avail = [i for i in range(len(sites)) if i not in used]
        # subsets of available sites whose multiplicities sum exactly to `need`
        for r in range(1, len(avail) + 1):
            for combo in combinations(avail, r):
                if sum(sites[i][0] for i in combo) != need:
                    continue
                for i in combo:
                    assignment.append((elem, i))
                backtrack(elem_i + 1, used | set(combo), assignment)
                del assignment[-len(combo):]
                if len(results) >= cap:
                    return

    backtrack(0, set(), [])
    return results


def zero_dof_motifs(sg: int, composition: dict[str, int], cap: int = 2000
                    ) -> list[tuple[list[str], np.ndarray]]:
    """All zero-dof structures (as cell-independent motifs, matching
    load_motifs' output format) consistent with `composition` under space
    group `sg`. Empty if the composition can't be built from special
    positions alone (i.e. the true structure isn't dof=0), the search space
    exceeds `cap`, or no assignment exists.
    """
    sites = _zero_dof_sites(sg)
    if not sites:
        return []
    elements = sorted(composition.items(), key=lambda kv: -kv[1])  # largest first: prunes faster
    assignments = _assignments(elements, sites, cap)

    motifs = []
    for assignment in assignments:
        species, coords = [], []
        for elem, site_idx in assignment:
            mult, coord = sites[site_idx]
            orbit = _orbit(sg, coord)
            if len(orbit) != mult:
                break  # symmetry-operation count didn't match the table; skip, don't silently corrupt
            species.extend([elem] * len(orbit))
            coords.append(orbit)
        else:
            motifs.append((species, np.concatenate(coords, axis=0)))
    return motifs


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spacegroup", type=int, required=True)
    ap.add_argument("--formula", required=True, help='e.g. "Th2Se2O"')
    ap.add_argument("--cap", type=int, default=2000)
    args = ap.parse_args()

    from pymatgen.core import Composition
    comp = {str(el): int(n) for el, n in Composition(args.formula).get_el_amt_dict().items()}
    motifs = zero_dof_motifs(args.spacegroup, comp, args.cap)
    print(f"composition {comp}, SG{args.spacegroup}: {len(motifs)} zero-dof assignments found")
    for species, coords in motifs[:5]:
        print(f"  {len(species)} atoms: {species}")
