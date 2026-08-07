#!/usr/bin/env python
"""Run index_pattern() in a subprocess that never imports jax.

Exists for the same reason mace_relax.py runs the MLFF relaxation in a
separate venv: index_pattern.py's candidate-cell scoring is parallelized with
multiprocessing.Pool, which defaults to fork(). Forking a process that has
already imported jax (multithreaded internally -- confirmed: a bare `import
jax` burns ~3s of CPU across threads for 0.4s wall) risks a classic
fork-with-threads deadlock: a child can inherit a lock some other thread held
at fork time, and that thread doesn't exist in the child to ever release it.

Running index_pattern in its own process sidesteps this cleanly: this process
tree never imports jax (index_pattern.py's own deps are numpy/scipy/pymatgen
only), so its internal Pool can use the fast default fork() safely -- no
per-worker reimport tax either, unlike routing this through
multiprocessing's spawn context from within the (jax-loaded) main process,
which forces every worker to re-execute the entire main script's import chain
from scratch. Measured: spawn-from-jax-loaded-process turned a 35s indexing
call into 20+ minutes on this NFS-backed $HOME, from ~46 workers each
re-importing the full jax/haiku/optax/crystalformer stack concurrently.

    .venv/bin/python index_worker.py in.json out.json

in.json  : {"pattern": [...], "spacegroup": int, "n_jobs": int (optional)}
out.json : {"cell": [a,b,c,alpha,beta,gamma] | null, "info": {...}}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from index_pattern import index_pattern  # noqa: E402


def main() -> int:
    infile, outfile = sys.argv[1], sys.argv[2]
    with open(infile) as f:
        data = json.load(f)

    pattern = np.array(data["pattern"])
    sg = int(data["spacegroup"])
    n_jobs = int(data.get("n_jobs", 0))

    cell, info = index_pattern(pattern, sg, verbose=True, n_jobs=n_jobs)

    out = {"info": info}
    out["cell"] = ([cell.a, cell.b, cell.c, cell.alpha, cell.beta, cell.gamma]
                   if cell is not None else None)
    Path(outfile).write_text(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
