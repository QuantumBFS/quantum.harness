#!/usr/bin/env python
"""Where does best-of-N stop working?

Milestone 2b. Best-of-N with an EMD reward solved rutile TiO2 in ~100 samples,
so for that target the RL machinery is unnecessary. The research question is
therefore not "does it work" but "how far does it get before it breaks", since
that threshold is the actual case for optimizing q(X).

Difficulty axes are taken from the literature rather than invented:

  arXiv:2605.24594 benchmarks ab-initio PXRD solution by crystal system and
  reports success collapsing with symmetry --
      cubic 100%, hexagonal 99.2%, tetragonal 98.4%, trigonal 98.1%,
      orthorhombic 94.0%, monoclinic 60.1%
  and identifies low symmetry, large cells and severe peak overlap as the
  failure modes. PXRDGen (Nat. Commun. 2025) adds that atomic coordinates stay
  wrong for >12% of MP-20 even when the cell is given, and that experimental
  patterns (RRUFF, 42%) are far harder than simulated ones (67%).

So the ladder varies symmetry, cell size and chemical arity:

  rutile TiO2      P4_2/mnm  tetragonal   6 atoms   1 free coordinate
  quartz SiO2      P3_121    trigonal     9 atoms
  anatase TiO2     I4_1/amd  tetragonal  12 atoms
  tenorite CuO     C2/c      MONOCLINIC   8 atoms
  baddeleyite ZrO2 P2_1/c    MONOCLINIC  12 atoms   9 free coordinates
  perovskite CaTiO3 Pnma     orthorhombic 20 atoms  ternary, near n_max = 21

Headline number per target: n90, the number of prior samples needed for a 90%
chance that the best-scoring candidate is the true structure. n90 = infinity
means best-of-N never gets there with the samples drawn.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pymatgen.core import Composition

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from bestofn import TARGETS, auc, load_samples, recovery_curve  # noqa: E402
from emd_metric import SPEC, d_cosine  # noqa: E402
from emd_nnls import d_emd_bg  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402

SAMPLES = Path(os.environ.get("CRYSTALFORMER_DIR",
                              Path.home() / "code/CrystalFormer")) / "samples"

# (target key, formula) -- the formula selects which sample file to score against
LADDER = [
    ("rutile", "TiO2"),
    ("quartz", "SiO2"),
    ("anatase", "TiO2"),
    ("tenorite", "CuO"),
    ("baddeleyite", "ZrO2"),
    ("perovskite", "CaTiO3"),
]

NS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000]


def n90(curve: dict[int, float]) -> str:
    for n in sorted(curve):
        if curve[n] >= 0.90:
            return str(n)
    return ">%d" % max(curve) if curve else "n/a"


def main() -> int:
    out = Path("tracks/other/results/m2b-difficulty")
    out.mkdir(parents=True, exist_ok=True)

    cache: dict[str, list] = {}
    rows = []

    for key, formula in LADDER:
        build, label, target_sg = TARGETS[key]
        csv = SAMPLES / f"output_{formula}.csv"
        if not csv.exists():
            print(f"[skip] {label}: no samples at {csv}")
            continue

        if formula not in cache:
            cache[formula] = load_samples(csv)
        structs = cache[formula]

        want = Composition(formula).reduced_formula
        cand = [s for s in structs
                if s is not None and s.composition.reduced_formula == want]
        if not cand:
            print(f"[skip] {label}: no composition-matching samples")
            continue

        truth = build()
        target = simulate_pattern(truth, SPEC)

        from pymatgen.analysis.structure_matcher import StructureMatcher

        sm = StructureMatcher(primitive_cell=True, attempt_supercell=True)
        is_true = np.array([bool(sm.fit(s, truth)) for s in cand])

        pats = [simulate_pattern(s, SPEC) for s in cand]
        d_cos = np.array([d_cosine(p, target) for p in pats])
        d_emd = np.array([d_emd_bg(target, p) for p in pats])

        row = {
            "target": key,
            "label": label,
            "formula": formula,
            "n_composition_match": len(cand),
            "n_hits": int(is_true.sum()),
            "hit_rate": float(is_true.mean()),
            "n_atoms": len(truth),
        }
        if is_true.any():
            cc = recovery_curve(is_true, d_cos, NS)
            ce = recovery_curve(is_true, d_emd, NS)
            row.update({
                "auc_cosine": auc(d_cos[is_true], d_cos[~is_true]),
                "auc_emd": auc(d_emd[is_true], d_emd[~is_true]),
                "n90_cosine": n90(cc),
                "n90_emd": n90(ce),
                "curve_cosine": cc,
                "curve_emd": ce,
                "top1_cosine": bool(is_true[np.argmin(d_cos)]),
                "top1_emd": bool(is_true[np.argmin(d_emd)]),
            })
        else:
            row.update({"auc_cosine": float("nan"), "auc_emd": float("nan"),
                        "n90_cosine": "never", "n90_emd": "never",
                        "curve_cosine": {}, "curve_emd": {},
                        "top1_cosine": False, "top1_emd": False})
        rows.append(row)
        print(f"[done] {label}: {row['n_hits']}/{len(cand)} hits "
              f"({row['hit_rate']:.2%}), n90_emd={row['n90_emd']}")

    # ---- summary ---------------------------------------------------------
    print("\n" + "=" * 104)
    print("DIFFICULTY LADDER — best-of-N structure solution from the CrystalFormer prior")
    print("=" * 104)
    hdr = (f"{'target':<13} {'sym':<12} {'at':>3} {'comp match':>11} {'hit rate':>9} "
           f"{'AUC cos':>8} {'AUC emd':>8} {'n90 cos':>9} {'n90 emd':>9}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        sym = r["label"].split("(")[1].split(",")[1].strip() if "(" in r["label"] else "?"
        print(f"{r['target']:<13} {sym:<12} {r['n_atoms']:>3} "
              f"{r['n_composition_match']:>11} {r['hit_rate']:>8.2%} "
              f"{r['auc_cosine']:>8.4f} {r['auc_emd']:>8.4f} "
              f"{r['n90_cosine']:>9} {r['n90_emd']:>9}")

    payload = {
        "run": "m2b-difficulty",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "n_prior_samples_per_formula": 2000,
        "literature": {
            "arXiv:2605.24594": "success by system: cubic 100%, hex 99.2%, tet 98.4%, "
                                "trig 98.1%, ortho 94.0%, monoclinic 60.1%",
            "PXRDGen Nat.Commun.2025": "82%/96% MP-20 1/20-sample; RRUFF experimental 42% "
                                       "vs simulated 67%; >12% coords wrong even given cell",
        },
        "rows": rows,
    }
    (out / "run.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
