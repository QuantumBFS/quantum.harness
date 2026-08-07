#!/usr/bin/env python
"""Select held-out real crystal structures directly from MP.db, for
simxrd_holdout_benchmark.py -- the fallback benchmark for issue #68's
"benchmark on SimXRD-4M" deliverable (SimXRD-4M's own release has no
recoverable ground truth; see simxrd_holdout_benchmark.py's module docstring).

Ground truth is unambiguous per (reduced_formula, spacegroup) in MP.db, per
simxrd_build_mp_index.py's index (exactly one match -- polymorphism at the
same composition+spacegroup would make the pairing ambiguous).

`n_atoms` is the CONVENTIONAL cell's atom count, not MP.db's stored (usually
primitive) count -- CrystalFormer's structure builder (get_struct_from_lawx)
always expands Wyckoff orbits into a conventional cell, so a candidate at a
composition with e.g. F-centering (4x) or C-centering (2x) never lands on the
primitive atom count. Missing this the first time round meant every generated
candidate got filtered out silently (0 usable candidates, looked like a
CrystalFormer coverage gap) for compositions where the two counts differ.
"""
import argparse
import json
import random

from ase.db import connect
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

EXISTING_FORMULAS = {"FeS2", "TiO2", "CuO", "SiO2", "ZrO2", "CaTiO3"}  # the original 7 targets


def system_of(sg: int) -> str:
    if sg > 194:
        return "cubic"
    if sg > 142:
        return "hexagonal"
    if sg > 74:
        return "tetragonal"
    if sg > 15:
        return "orthorhombic"
    if sg > 2:
        return "monoclinic"
    return "triclinic"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mp_db")
    ap.add_argument("mp_index")
    ap.add_argument("out")
    ap.add_argument("--n-targets", type=int, default=35,
                    help="over-provisioned pool; simxrd_holdout_benchmark.py "
                         "stops once --n-solve-attempts targets get nonzero "
                         "CrystalFormer coverage and skips the rest")
    ap.add_argument("--per-system-cap", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    with open(args.mp_index) as f:
        mp_index = json.load(f)
    mp_db = connect(args.mp_db)
    adaptor = AseAtomsAdaptor()

    candidates = []
    for key, ids in mp_index.items():
        if len(ids) != 1:  # ambiguous: >1 real structure shares this composition+SG
            continue
        formula, sg_s = key.rsplit("|", 1)
        sg = int(sg_s)
        if sg <= 2 or formula in EXISTING_FORMULAS:  # triclinic unsupported by the indexer
            continue
        candidates.append((formula, sg, ids[0]))

    rng = random.Random(args.seed)
    rng.shuffle(candidates)

    by_system, selected = {}, []
    for formula, sg, mp_id in candidates:
        if len(selected) >= args.n_targets:
            break
        row = mp_db.get(id=mp_id)
        prim = adaptor.get_structure(row.toatoms())
        try:
            sga = SpacegroupAnalyzer(prim, symprec=0.1)
            conv = sga.get_conventional_standard_structure()
            sg_conv = sga.get_space_group_number()
        except Exception:
            continue
        n_conv = len(conv)
        if n_conv > 20 or n_conv < 2:  # CrystalFormer's n_max=21, conventional-cell count
            continue
        system = system_of(sg_conv)
        if by_system.get(system, 0) >= args.per_system_cap:
            continue
        by_system[system] = by_system.get(system, 0) + 1
        selected.append({
            "formula": formula, "spacegroup": sg_conv, "mp_id": mp_id,
            "mpid": getattr(row, "mpid", None), "n_atoms": n_conv,
            "n_atoms_primitive": len(prim), "system": system,
        })
        print(f"  [{len(selected)}/{args.n_targets}] {formula} SG{sg_conv} ({system}) "
              f"n_atoms={n_conv} (primitive={len(prim)}) mp_id={mp_id}")

    print(f"\nselected {len(selected)} targets; by system: {by_system}")
    with open(args.out, "w") as f:
        json.dump(selected, f, indent=2)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
