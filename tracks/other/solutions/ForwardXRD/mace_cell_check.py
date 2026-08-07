#!/usr/bin/env python
"""Should an MLFF be allowed to refine the CELL? Runs in venv-mace.

The proposed pipeline ends with "MLFF relaxation for precise cell parameters and
coordinates". A force field relaxes toward an ENERGETIC minimum, which is not
the same as the diffraction minimum: it carries exchange-correlation error and
describes a static 0 K structure, while the measured cell is thermally expanded.

m2f measured how much cell error the motif refinement tolerates:

    free coords   tolerated cell error
       1 - 4        >= 5%
         9          ~0.2-0.5%, dead by 1%

and indexing delivers 0.01-0.1%. So the question is simply whether MACE's
relaxed cell is closer to the truth than that. Start each target AT the true
structure and relax with the cell free; any drift is pure MLFF error, with no
search difficulty confounding it.

    venv-mace/bin/python mace_cell_check.py structures.json
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("infile", help="JSON: {name: <pymatgen Structure dict>}")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--fmax", type=float, default=0.02)
    ap.add_argument("--model", default="small")
    args = ap.parse_args()

    import torch
    from ase.filters import FrechetCellFilter
    from ase.optimize import FIRE
    from mace.calculators import mace_mp
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    calc = mace_mp(model=args.model, default_dtype="float64", device=device)
    adaptor = AseAtomsAdaptor()

    data = json.loads(Path(args.infile).read_text())
    print(f"{'target':<20} {'da/a':>9} {'db/b':>9} {'dc/c':>9} {'max':>9} {'verdict':>10}")
    print("-" * 72)

    rows = []
    for name, sd in data.items():
        truth = Structure.from_dict(sd)
        atoms = adaptor.get_atoms(truth)
        atoms.calc = calc
        FIRE(FrechetCellFilter(atoms), logfile=None).run(fmax=args.fmax, steps=args.steps)
        relaxed = adaptor.get_structure(atoms)

        d = [relaxed.lattice.a / truth.lattice.a - 1,
             relaxed.lattice.b / truth.lattice.b - 1,
             relaxed.lattice.c / truth.lattice.c - 1]
        worst = max(abs(x) for x in d)
        # m2f: 9 free coords dies by 1%, marginal 0.2-0.5%; indexing gives 0.01-0.1%
        verdict = ("ok<0.2%" if worst < 0.002 else
                   "marginal" if worst < 0.005 else
                   "TOO BIG")
        rows.append({"target": name, "da": d[0], "db": d[1], "dc": d[2],
                     "max_abs": worst, "verdict": verdict})
        print(f"{name:<20} {d[0]:>+8.3%} {d[1]:>+8.3%} {d[2]:>+8.3%} "
              f"{worst:>8.3%} {verdict:>10}")

    worst_all = max(r["max_abs"] for r in rows)
    print(f"\nworst cell drift across targets: {worst_all:.3%}")
    print("indexing delivers 0.01-0.1%; m2f tolerance is ~0.2-0.5% at 9 free coords")
    print(json.dumps({"rows": rows, "worst": worst_all}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
