#!/usr/bin/env python
"""Generative prior vs quasi-random Wyckoff sampling + MACE relaxation.

Milestone 3c. m3b compared the prior against RAW uniform sampling and found the
prior wins by an unbounded margin at 9 free coordinates and loses at 1. That
comparison was unfair to the classical route: arXiv:2605.24594 follows its
quasi-random sampling with MACE force-field relaxation, which pulls physically
absurd draws into nearby physical minima. This run supplies that missing step
and locates the crossover.

Design -- both arms get the same cell, the same space group, and the same
optional relaxation, so the only difference is where the motif came from:

  RANDOM  the truth's Wyckoff sites with free parameters drawn uniformly.
          Still handed the CORRECT Wyckoff assignment, which real enumeration
          would have to search: a deliberate handicap on the prior.

  PRIOR   CrystalFormer conditioned on composition + space group, re-embedded
          in the true cell. No Wyckoff hint.

Relaxation holds the cell fixed (see mace_relax.py): in an indexing-first
pipeline the cell is the best-determined quantity available.

The ladder spans free-coordinate count, which m3b identified as the variable
that actually matters (not symmetry, not cell size, not chemical arity):

  pyrite FeS2       Pa-3     S  8c (x,x,x)                       1
  rutile TiO2       P4_2/mnm O  4f (u,u,0)                       1
  marcasite FeS2    Pnnm     S  4g (x,y,0)                       2
  quartz SiO2       P3_121   Si 3a (x,0,1/3) + O 6c (x,y,z)      4
  perovskite CaTiO3 Pnma     Ca,O1 4c + O2 8d                    7
  baddeleyite ZrO2  P2_1/c   Zr,O,O all 4e (x,y,z)               9
"""

from __future__ import annotations

import argparse
import json
import subprocess
import os
import sys
import tempfile
from ast import literal_eval
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pymatgen.core import Composition, Lattice, Structure

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from targets import (  # noqa: E402
    SM_GRADED, SM_STRICT, _baddeleyite, _marcasite, _perovskite,
    _pyrite, _quartz, _rutile, _tenorite,
)

CF = Path(os.environ.get("CRYSTALFORMER_DIR",
                         Path.home() / "code/CrystalFormer"))
for _p in (CF, CF / "crystalformer" / "src", CF / "scripts"):
    sys.path.insert(0, str(_p))

MACE_PY = Path(os.environ.get("MACE_PYTHON",
                              Path.home() / "code/venv-mace/bin/python"))
RELAX = SOL / "mace_relax.py"


LADDER = [
    ("pyrite FeS2", 1, _pyrite, np.array([0.3847]),
     CF / "samples_ladder/out_sg205_FeS2.csv", "FeS2", 12),
    ("tenorite CuO", 1, _tenorite, np.array([0.4184]),
     CF / "samples_SG/output_CuO.csv", "CuO", 8),
    ("rutile TiO2", 1, _rutile, np.array([0.3053]),
     CF / "samples_ladder/out_sg136_TiO2.csv", "TiO2", 6),
    ("marcasite FeS2", 2, _marcasite, np.array([0.2003, 0.3787]),
     CF / "samples_ladder/out_sg58_FeS2.csv", "FeS2", 6),
    ("quartz SiO2", 4, _quartz, np.array([0.4697, 0.4135, 0.2669, 0.1191]),
     CF / "samples_ladder/out_sg152_SiO2.csv", "SiO2", 9),
    ("perovskite CaTiO3", 7, _perovskite,
     np.array([0.0357, -0.0064, 0.4890, 0.0707, 0.2887, 0.0387, 0.7113]),
     CF / "samples_ladder/out_sg62_CaTiO3.csv", "CaTiO3", 20),
    ("baddeleyite ZrO2", 9, _baddeleyite,
     np.array([0.2758, 0.0411, 0.2082, 0.0703, 0.3359, 0.3406, 0.4423, 0.7549, 0.4789]),
     CF / "samples_SG/output_ZrO2.csv", "ZrO2", 12),
]


def load_cf(csv: Path, formula: str, n_atoms: int, true_lat, cap: int):
    from awl2struct import get_struct_from_lawx  # noqa: PLC0415

    want = Composition(formula).reduced_formula
    out = []
    for _, row in pd.read_csv(csv).iterrows():
        if len(out) >= cap:
            break
        try:
            s = Structure.from_dict(get_struct_from_lawx(
                int(row["G"]), np.array(literal_eval(row["L"])),
                np.array(literal_eval(row["A"])), np.array(literal_eval(row["W"])),
                np.array(literal_eval(row["X"]))))
        except Exception:
            continue
        if s.composition.reduced_formula != want or len(s) != n_atoms:
            continue
        out.append(Structure(true_lat, s.species, s.frac_coords))
    return out


def relax(structs, steps: int, tmp: Path, tag: str):
    """Round-trip through the MACE venv. Returns structures unchanged on failure."""
    if not structs:
        return structs, 0
    fin, fout = tmp / f"{tag}_in.json", tmp / f"{tag}_out.json"
    fin.write_text(json.dumps({"structures": [s.as_dict() for s in structs]}, default=str))
    res = subprocess.run(
        [str(MACE_PY), str(RELAX), str(fin), str(fout), "--steps", str(steps)],
        capture_output=True, text=True)
    if res.returncode != 0 or not fout.exists():
        # keep the whole tail: the informative line is rarely the last one
        tail = res.stderr.strip().splitlines()[-12:]
        print(f"    [relax FAILED] rc={res.returncode}")
        for line in tail:
            print(f"      | {line}")
        return structs, 0
    d = json.loads(fout.read_text())
    return [Structure.from_dict(x) for x in d["structures"]], int(sum(d["converged"]))


def hit_rate(structs, truth) -> float:
    if not structs:
        return float("nan")
    hits = 0
    for s in structs:
        try:
            hits += bool(SM_STRICT.fit(s, truth))
        except Exception:
            pass
    return hits / len(structs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-random", type=int, default=1000)
    ap.add_argument("--cap-prior", type=int, default=1000)
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument("--no-relax", action="store_true")
    args = ap.parse_args()

    out = Path("tracks/other/results/m3c-crossover")
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    rows = []

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name, nfree, build, truth_p, csv, formula, n_atoms in LADDER:
            truth = build(truth_p)
            print(f"\n{'=' * 78}\n{name}  —  {nfree} free coordinate"
                  f"{'s' if nfree > 1 else ''}")
            if not csv.exists():
                print(f"  [skip] no prior samples at {csv}")
                continue

            rand = [build(rng.random(nfree)) for _ in range(args.n_random)]
            prior = load_cf(csv, formula, n_atoms, truth.lattice, args.cap_prior)
            print(f"  candidates: random {len(rand)} | prior {len(prior)}")

            r_raw, p_raw = hit_rate(rand, truth), hit_rate(prior, truth)
            print(f"  raw          random {r_raw:>8.3%} | prior {p_raw:>8.3%}")

            if args.no_relax:
                r_rel = p_rel = float("nan")
                nc_r = nc_p = 0
            else:
                rand_r, nc_r = relax(rand, args.steps, tmp, f"{formula}{nfree}_rand")
                prior_r, nc_p = relax(prior, args.steps, tmp, f"{formula}{nfree}_prior")
                r_rel, p_rel = hit_rate(rand_r, truth), hit_rate(prior_r, truth)
                print(f"  +MACE        random {r_rel:>8.3%} | prior {p_rel:>8.3%}"
                      f"   (converged {nc_r}/{len(rand)}, {nc_p}/{len(prior)})")

            def enr(p, r):
                if not np.isfinite(p) or not np.isfinite(r):
                    return float("nan")
                return p / r if r > 0 else (float("inf") if p > 0 else float("nan"))

            rows.append({
                "case": name, "n_free": nfree,
                "n_random": len(rand), "n_prior": len(prior),
                "random_raw": r_raw, "prior_raw": p_raw, "enrich_raw": enr(p_raw, r_raw),
                "random_mace": r_rel, "prior_mace": p_rel, "enrich_mace": enr(p_rel, r_rel),
                "converged_random": nc_r, "converged_prior": nc_p,
            })

    rows.sort(key=lambda r: r["n_free"])
    print("\n" + "=" * 104)
    print("CROSSOVER — prior vs quasi-random Wyckoff sampling (+ MACE relaxation), "
          "same cell + space group")
    print("=" * 104)
    hdr = (f"{'case':<20} {'free':>5} | {'rand raw':>9} {'prior raw':>10} {'enr':>8} "
           f"| {'rand+MACE':>10} {'prior+MACE':>11} {'enr':>8}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        def f(x):
            return "  n/a" if not np.isfinite(x) else f"{x:.3%}"

        def e(x):
            return "  n/a" if not np.isfinite(x) else ("   inf" if np.isinf(x) else f"{x:.2f}x")

        print(f"{r['case']:<20} {r['n_free']:>5} | {f(r['random_raw']):>9} "
              f"{f(r['prior_raw']):>10} {e(r['enrich_raw']):>8} | "
              f"{f(r['random_mace']):>10} {f(r['prior_mace']):>11} {e(r['enrich_mace']):>8}")

    xs = [r for r in rows if np.isfinite(r["enrich_mace"])]
    below = [r["n_free"] for r in xs if r["enrich_mace"] < 1]
    above = [r["n_free"] for r in xs if r["enrich_mace"] >= 1]
    if below and above:
        print(f"\ncrossover (with MACE): prior loses up to {max(below)} free coords, "
              f"wins from {min(above)} onward")

    payload = {
        "run": "m3c-crossover", "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "question": "where in free-coordinate count does a generative motif prior "
                    "overtake quasi-random Wyckoff sampling with MACE relaxation?",
        "caveats": [
            "the random arm is GIVEN the correct Wyckoff sites; the prior is not",
            "relaxation holds the cell fixed, as an indexed cell would be trusted",
            f"MACE FIRE, max {args.steps} steps, fmax 0.05",
        ],
        "rows": rows,
    }
    (out / "run.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
