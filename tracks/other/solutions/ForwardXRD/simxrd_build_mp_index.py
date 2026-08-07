#!/usr/bin/env python
"""Index a Materials Project ASE db by (reduced_formula, spacegroup) -> [ids].

Feeds simxrd_select_mp_targets.py. Uses spglib directly (not ase.spacegroup's
get_spacegroup, which is deprecated for returning symmetry ops of a standard
setting rather than the given structure's actual space group).

    .venv/bin/python simxrd_build_mp_index.py MP.db mp_index.json
"""
import json
import sys
import time

import spglib
from ase.db import connect
from pymatgen.core import Composition

MAX_ATOMS = 24  # generous headroom over CrystalFormer's n_max=21 conventional-cell cap


def main():
    db_path, out_path = sys.argv[1], sys.argv[2]
    db = connect(db_path)
    index: dict[str, list[int]] = {}
    t0 = time.time()
    n_ok = n_fail = 0
    for row in db.select():
        atoms = row.toatoms()
        if len(atoms) == 0 or len(atoms) > MAX_ATOMS:
            continue
        try:
            cell = (atoms.cell[:], atoms.get_scaled_positions(), atoms.numbers)
            ds = spglib.get_symmetry_dataset(cell, symprec=0.1)
            sg = int(ds.number)
            formula = Composition(atoms.get_chemical_formula()).reduced_formula
            index.setdefault(f"{formula}|{sg}", []).append(row.id)
            n_ok += 1
        except Exception:
            n_fail += 1
            continue
        if n_ok % 20000 == 0:
            print(f"{n_ok} done, {time.time() - t0:.0f}s", flush=True)

    print(f"total ok={n_ok} fail={n_fail} time={time.time() - t0:.0f}s")
    with open(out_path, "w") as f:
        json.dump(index, f)
    print("unique (formula,sg) keys:", len(index))
    print("unambiguous (exactly 1 match):", sum(1 for v in index.values() if len(v) == 1))
    print("wrote", out_path)


if __name__ == "__main__":
    main()
