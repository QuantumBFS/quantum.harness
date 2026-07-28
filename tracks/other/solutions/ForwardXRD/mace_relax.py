#!/usr/bin/env python
"""Relax structures with the MACE-MP foundation model. Runs in venv-mace.

Separate from the rest of the pipeline because torch ships its own nvidia-*
wheels that would collide with jax's inside the main .venv, so this executes as
a subprocess and exchanges structures as JSON.

Positions only -- the cell is held fixed. In the indexing-first architecture the
cell comes from the diffraction pattern and is the best-determined quantity we
have, so relaxing it away would discard information. This also keeps the
comparison honest: both arms retain the same (correct) cell throughout.

    venv-mace/bin/python mace_relax.py in.json out.json [--steps 60] [--fmax 0.05]

in.json  : {"structures": [<pymatgen Structure dict>, ...]}
out.json : same, relaxed, plus per-structure convergence flags
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument("--fmax", type=float, default=0.05)
    ap.add_argument("--model", default="small")
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    import torch
    from ase.optimize import FIRE
    from mace.calculators import mace_mp
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[mace] device={device} model={args.model} steps={args.steps}", file=sys.stderr)
    calc = mace_mp(model=args.model, default_dtype="float64", device=device)

    payload = json.loads(Path(args.infile).read_text())
    structs = payload["structures"]
    adaptor = AseAtomsAdaptor()

    out, converged = [], []
    for i, sd in enumerate(structs):
        try:
            s = Structure.from_dict(sd)
            atoms = adaptor.get_atoms(s)
            atoms.calc = calc
            opt = FIRE(atoms, logfile=None)
            opt.run(fmax=args.fmax, steps=args.steps)
            # cell untouched by FIRE without a cell filter
            out.append(adaptor.get_structure(atoms).as_dict())
            converged.append(bool(opt.converged()))
        except Exception as exc:  # a relaxation blowing up is a real outcome
            print(f"[mace] structure {i} failed: {type(exc).__name__}", file=sys.stderr)
            out.append(sd)
            converged.append(False)
        if (i + 1) % 200 == 0:
            print(f"[mace] {i + 1}/{len(structs)}", file=sys.stderr)

    Path(args.outfile).write_text(json.dumps(
        {"structures": out, "converged": converged}, default=str))
    print(f"[mace] wrote {args.outfile} "
          f"({sum(converged)}/{len(converged)} converged)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
