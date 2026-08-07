#!/usr/bin/env python
"""Stratified sample from SmartCellSolver's published test set, cross-referenced
against our own MP.db for ground truth (their repo publishes patterns + formula +
spacegroup, but not the atomic structure itself -- their own success criterion is
pattern-fit R^2/Chi^2, not structure comparison, so they don't need one).

For each candidate (formula, spacegroup) parsed from their filenames, we require
an UNAMBIGUOUS match in our own MP.db index (same requirement used for
simxrd_select_mp_targets.py's held-out benchmark) so we have a real ground truth
to run StructureMatcher against, not just their looser pattern-fit criterion.

`--test-txt`/`--mono-txt` are SmartCellSolver's own test-set listings
(github.com/MaterSim/Ab-PXRD-Solver, data/test.txt and data/mono.txt);
`--test-csv`/`--mono-csv` are their published per-structure outcomes
(Status/R2/Chi2), carried through for the paired comparison in scs_benchmark.py.
"""
import argparse
import csv
import json
import random

from ase.db import connect
from pymatgen.core import Composition
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.io.ase import AseAtomsAdaptor

QUOTA = {"monoclinic": 18, "cubic": 12, "hex": 12, "tetragonal": 12, "orthorhombic": 12}


def system_of(sg: int) -> str:
    if sg > 194:
        return "cubic"
    if sg > 142:
        return "hex"  # hexagonal + trigonal, matches index_pattern.py's system_of bucketing
    if sg > 74:
        return "tetragonal"
    if sg > 15:
        return "orthorhombic"
    if sg > 2:
        return "monoclinic"
    return "triclinic"


def parse_entry(path: str):
    # "GSAS_PXRD/Ac2CuSi_225.csv" -> ("Ac2CuSi", 225)
    name = path.rsplit("/", 1)[-1].removesuffix(".csv")
    formula, sg_s = name.rsplit("_", 1)
    return formula, int(sg_s)


def load_outcomes(csv_path: str) -> dict:
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    return {r["csv_file_name"]: r for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test-txt", required=True)
    ap.add_argument("--mono-txt", required=True)
    ap.add_argument("--test-csv", required=True)
    ap.add_argument("--mono-csv", required=True)
    ap.add_argument("--mp-db", required=True)
    ap.add_argument("--mp-index", required=True, help="from simxrd_build_mp_index.py")
    ap.add_argument("--out", default="scs_targets.json")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    with open(args.test_txt) as f:
        pool = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    with open(args.mono_txt) as f:
        pool += [line.strip() for line in f if line.strip() and not line.startswith("#")]
    print(f"total published pool: {len(pool)}")

    outcomes = {}
    outcomes.update(load_outcomes(args.test_csv))
    outcomes.update(load_outcomes(args.mono_csv))
    print(f"published per-structure outcomes available for {len(outcomes)} of them")

    with open(args.mp_index) as f:
        mp_index = json.load(f)
    mp_db = connect(args.mp_db)
    adaptor = AseAtomsAdaptor()

    rng = random.Random(args.seed)
    rng.shuffle(pool)

    selected = {k: [] for k in QUOTA}
    checked = 0
    for entry in pool:
        checked += 1
        formula_raw, sg = parse_entry(entry)
        system = system_of(sg)
        if system not in QUOTA or len(selected[system]) >= QUOTA[system]:
            continue
        try:
            formula = Composition(formula_raw).reduced_formula
        except Exception:
            continue
        key = f"{formula}|{sg}"
        matches = mp_index.get(key)
        if not matches or len(matches) != 1:
            continue
        mp_id = matches[0]
        try:
            prim = adaptor.get_structure(mp_db.get(id=mp_id).toatoms())
            sga = SpacegroupAnalyzer(prim, symprec=0.1)
            conv = sga.get_conventional_standard_structure()
            sg_conv = sga.get_space_group_number()
        except Exception:
            continue
        n_atoms = len(conv)
        if n_atoms < 2 or n_atoms > 20:
            continue
        csv_name = entry.rsplit("/", 1)[-1]
        selected[system].append({
            "scs_entry": entry, "csv_name": csv_name,
            "formula": formula, "spacegroup": sg_conv, "system": system,
            "mp_id": mp_id, "n_atoms": n_atoms,
            "scs_published_outcome": outcomes.get(csv_name, {}).get("Status"),
            "scs_published_R2": outcomes.get(csv_name, {}).get("R2"),
            "scs_published_Chi2": outcomes.get(csv_name, {}).get("Chi2"),
        })
        print(f"  [{system}: {len(selected[system])}/{QUOTA[system]}] {formula} SG{sg_conv} "
              f"n_atoms={n_atoms} mp_id={mp_id} "
              f"published_outcome={outcomes.get(csv_name, {}).get('Status')}")
        if all(len(selected[s]) >= QUOTA[s] for s in QUOTA):
            break

    print(f"\nchecked {checked}/{len(pool)} pool entries")
    for s in QUOTA:
        print(f"  {s}: {len(selected[s])}/{QUOTA[s]}")

    all_selected = [t for lst in selected.values() for t in lst]
    with open(args.out, "w") as f:
        json.dump(all_selected, f, indent=2)
    print(f"\nwrote {len(all_selected)} targets to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
