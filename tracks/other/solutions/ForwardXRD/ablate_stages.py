#!/usr/bin/env python
"""Ablation: does MLFF relaxation and/or DE refinement help the solver?

Milestone 5. solve_pattern.py currently stops at ranking -- index, prior,
re-embed, rank. Two optional stages are candidates for addition:

  MLFF   relax every candidate at FIXED cell before ranking (m3c showed this
         lifts hit rates hugely: baddeleyite 20.2% -> 87.2%)
  DE     refine the top-ranked candidate's free coordinates against the pattern
         -- the Rietveld-like stage 5, and the thing m2e proved is solvable

Note DE is NOT a form of q(X). q(X) is a distribution tethered to the prior by a
KL term; DE is a point optimiser inside a fixed parameterisation. The current
workflow contains no q(X) at all -- it is best-of-N plus post-processing.

Four conditions, full factorial:

    A  rank only                (current solve_pattern.py)
    B  MLFF -> rank
    C  rank -> DE
    D  MLFF -> rank -> DE

Run at 0.3% cell error on NOISY patterns, because at 0.1% and noise-free every
condition already gets top-1 right and the comparison saturates.

DE refinement here is LOCAL: it perturbs the top candidate's symmetry-distinct
sites within +/- `--de-window` and rebuilds through the space group, rejecting
any move that changes the atom count (which would mean a site left its Wyckoff
position). It therefore refines the candidate rather than re-solving from
scratch.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pymatgen.core import Structure

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from emd_metric import SPEC, noisy_target  # noqa: E402
from emd_nnls import d_emd_bg  # noqa: E402
from targets import SM_GRADED, SM_STRICT  # noqa: E402
from wyckoff_refine import refine as wyckoff_refine  # noqa: E402
from solve_pattern import load_candidates, mock_index  # noqa: E402
from targets import REGISTRY  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402

MACE_PY = Path(os.environ.get("MACE_PYTHON",
                              Path.home() / "code/venv-mace/bin/python"))
RELAX = SOL / "mace_relax.py"


def mace_relax(structs, steps, tmp, tag):
    if not structs:
        return structs
    fin, fout = tmp / f"{tag}_in.json", tmp / f"{tag}_out.json"
    fin.write_text(json.dumps({"structures": [s.as_dict() for s in structs]}, default=str))
    res = subprocess.run([str(MACE_PY), str(RELAX), str(fin), str(fout),
                          "--steps", str(steps)], capture_output=True, text=True)
    if res.returncode != 0 or not fout.exists():
        print(f"    [relax FAILED rc={res.returncode}]")
        for line in res.stderr.strip().splitlines()[-6:]:
            print(f"      | {line}")
        return structs
    return [Structure.from_dict(x) for x in json.loads(fout.read_text())["structures"]]


def de_refine(cand: Structure, measured, window: float, seed: int = 0):
    """Delegates to the corrected Wyckoff-respecting refiner.

    The original in-file version perturbed all three coordinates of every site
    and rebuilt via from_spacegroup, which knocks atoms off special positions --
    quartz failed with "multiplicity 10 != 9" and its DE column silently
    reported the unrefined result. wyckoff_refine derives each site's degrees of
    freedom from its site symmetry instead.
    """
    def _score(st):
        return d_emd_bg(measured, simulate_pattern(st, SPEC))

    return wyckoff_refine(cand, measured, _score, window=window)


def evaluate(struct, truth):
    try:
        ok = bool(SM_STRICT.fit(struct, truth))
    except Exception:
        ok = False
    try:
        d = SM_GRADED.get_rms_dist(struct, truth)
        rms = None if d is None else float(d[0])
    except Exception:
        rms = None
    return ok, rms


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cell-error", type=float, default=0.003)
    ap.add_argument("--counts", type=float, default=1e4)
    ap.add_argument("--bg", type=float, default=0.10)
    ap.add_argument("--cap", type=int, default=500)
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument("--de-window", type=float, default=0.05)
    ap.add_argument("--targets", nargs="+", default=sorted(REGISTRY))
    args = ap.parse_args()

    out = Path("tracks/other/results/m5-ablation")
    out.mkdir(parents=True, exist_ok=True)
    rows = []

    print(f"ablation: cell error {args.cell_error:.2%}, "
          f"{args.counts:.0g} counts / {args.bg:.0%} bg, cap {args.cap}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name in args.targets:
            build, truth_p, sg, formula, n_atoms, csv = REGISTRY[name]
            if not csv.exists():
                print(f"[skip] {name}: no samples")
                continue
            truth = build(truth_p)
            rng = np.random.default_rng(0)
            measured = noisy_target(truth, args.counts, args.bg)
            cell = mock_index(truth, args.cell_error, rng, sg)
            cands = load_candidates(csv, formula, n_atoms, cell, args.cap)
            if not cands:
                print(f"[skip] {name}: no candidates")
                continue

            print(f"\n{'=' * 70}\n{name}  ({len(cands)} candidates)")
            relaxed = mace_relax(cands, args.steps, tmp, f"{name}")

            row = {"target": name, "n_candidates": len(cands)}
            for cond, pool, use_de in (("A rank only", cands, False),
                                       ("B MLFF+rank", relaxed, False),
                                       ("C rank+DE", cands, True),
                                       ("D MLFF+rank+DE", relaxed, True)):
                sc = np.array([d_emd_bg(measured, simulate_pattern(c, SPEC)) for c in pool])
                best = pool[int(np.argmin(sc))]
                status = "-"
                if use_de:
                    best, status = de_refine(best, measured, args.de_window)
                ok, rms = evaluate(best, truth)
                row[cond] = {"top1_correct": ok, "rms": rms, "de_status": status}
                rs = "n/a" if rms is None else f"{rms:.4f}"
                flag = "" if status in ("-", "ok") else f"   << {status}"
                print(f"  {cond:<16} top1={str(ok):<5}  rms={rs}  de={status}{flag}")
            rows.append(row)

    conds = ["A rank only", "B MLFF+rank", "C rank+DE", "D MLFF+rank+DE"]
    print("\n" + "=" * 92)
    print("ABLATION SUMMARY — top-1 correct / rms to ground truth")
    print("=" * 92)
    hdr = f"{'target':<14}" + "".join(f"{c:>19}" for c in conds)
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        line = f"{r['target']:<14}"
        for c in conds:
            v = r.get(c, {})
            rms = v.get("rms")
            line += f"{('Y' if v.get('top1_correct') else 'n'):>4}" \
                    f"{('  n/a' if rms is None else f'{rms:8.4f}'):>15}"
        print(line)
    print("-" * len(hdr))
    tally = f"{'correct':<14}"
    for c in conds:
        tally += f"{sum(1 for r in rows if r.get(c, {}).get('top1_correct')):>8}/{len(rows):<11}"
    print(tally)

    (out / "run.json").write_text(json.dumps({
        "run": "m5-ablation", "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "question": "do MLFF relaxation and/or DE refinement improve the solver?",
        "note": "DE is a point optimiser (stage-5 refiner), NOT a form of q(X)",
        "settings": {"cell_error": args.cell_error, "counts": args.counts,
                     "bg": args.bg, "cap": args.cap, "de_window": args.de_window},
        "rows": rows,
    }, indent=2, default=str) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
