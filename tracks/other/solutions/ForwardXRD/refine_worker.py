#!/usr/bin/env python
"""Run wyckoff_refine.refine() in a subprocess that never imports jax.

Same reasoning as index_worker.py: refine()'s DE step can be parallelized via
scipy's `workers=` (a fork()-based multiprocessing.Pool internally), which is
only safe from a process that hasn't already loaded jax. wyckoff_refine.py,
emd_nnls.py, and xrd_reward.py have no jax dependency of their own, so running
refine() here -- isolated from the caller's jax-loaded process -- lets DE use
real multi-core parallelism (this is the expensive stage: a target with
dof=18 costs ~34,000 pattern evaluations at ~18ms each, ~10 min single
threaded) without the fork-with-threads deadlock risk or spawn's heavy
per-worker reimport tax.

    .venv/bin/python refine_worker.py in.json out.json

in.json  : {"structure": <pymatgen Structure dict>, "measured": [...],
            "window": float, "workers": int}
out.json : {"structure": <pymatgen Structure dict>, "status": str}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from emd_metric import SPEC  # noqa: E402
from emd_nnls import d_emd_bg  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402
from wyckoff_refine import refine  # noqa: E402
from pymatgen.core import Structure  # noqa: E402


class _PatternScore:
    """Picklable score_fn: d_emd_bg(measured, simulate_pattern(candidate)).

    Must be a module-level class, not a local closure -- scipy DE's
    workers != 1 path pickles this to send to worker processes, and plain
    `pickle` can't serialize a nested function.
    """

    def __init__(self, measured, spec):
        self.measured = measured
        self.spec = spec

    def __call__(self, structure):
        return d_emd_bg(self.measured, simulate_pattern(structure, self.spec))


def main() -> int:
    infile, outfile = sys.argv[1], sys.argv[2]
    with open(infile) as f:
        data = json.load(f)

    struct = Structure.from_dict(data["structure"])
    measured = np.array(data["measured"])
    window = float(data.get("window", 0.15))
    # -1: all cores, matching scipy's own convention. Parallel is the default
    # here on purpose -- this is the pipeline's most expensive stage (measured
    # 3.6x speedup on an 18-dof case), and this worker exists specifically so
    # that parallelism is safe (see module docstring). If some future caller's
    # JSON omits "workers" entirely, defaulting to 1 (serial) would silently
    # undo that, which is exactly the class of regression to design out.
    workers = int(data.get("workers", -1))

    score_fn = _PatternScore(measured, SPEC)
    best, status = refine(struct, measured, score_fn, window=window, workers=workers,
                          verbose=True)

    Path(outfile).write_text(json.dumps({"structure": best.as_dict(), "status": status}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
