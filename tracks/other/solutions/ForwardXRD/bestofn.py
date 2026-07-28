#!/usr/bin/env python
"""Best-of-N structure solution from the CrystalFormer prior, instrumented.

Milestone 2, framed as the experiment that decides whether RL is needed at all.

The naive scheme: sample N structures from p(X | composition), simulate each
pattern, keep the best fit. As N -> infinity this converges to argmax r(X) over
the prior's support -- the tau -> 0 limit of the variational problem. So it is
not an alternative to the challenge's framework, it is that framework solved by
brute force. It is also the "no-prior baseline" milestone 2 explicitly requires.

Four questions, in increasing order of how much they decide:

  Q1  Does the prior ever propose the target at all? (hit rate)
  Q2  Does best-of-N recover it, and how does recovery scale with N?
  Q3  Does the reward RANK candidates by structural correctness?
  Q4  Does EMD + background rank better than cosine?

Q3 is the crux, and every test so far has avoided it: all previous decoys were
perturbations of the true structure, whereas CrystalFormer proposes genuinely
different structures -- different space groups, different Wyckoff sets. If the
reward cannot rank those, no amount of RL helps, because PPO learns only by
contrasting good samples against bad ones.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from ast import literal_eval
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Composition, Lattice, Structure

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from emd_metric import SPEC, d_cosine, noisy_target  # noqa: E402
from emd_nnls import _anatase, _corundum, _quartz, _rutile, d_emd_bg  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402

def _tenorite():
    """CuO, monoclinic C2/c. Low symmetry -- the regime where the literature
    reports success collapsing (60% monoclinic vs ~100% cubic)."""
    return Structure.from_spacegroup(
        "C2/c", Lattice.monoclinic(4.6837, 3.4226, 5.1288, 99.54),
        ["Cu", "O"], [[0.25, 0.25, 0], [0, 0.4184, 0.25]],
    )


def _baddeleyite():
    """ZrO2, monoclinic P2_1/c. Three independent 4e sites -- 9 free internal
    coordinates, versus rutile's one."""
    return Structure.from_spacegroup(
        "P2_1/c", Lattice.monoclinic(5.1505, 5.2116, 5.3173, 99.23),
        ["Zr", "O", "O"],
        [[0.2758, 0.0411, 0.2082], [0.0703, 0.3359, 0.3406], [0.4423, 0.7549, 0.4789]],
    )


def _perovskite():
    """CaTiO3, orthorhombic Pnma, 20 atoms -- near CrystalFormer's n_max = 21.
    Ternary, so the composition-conditioned prior is spread far thinner."""
    return Structure.from_spacegroup(
        "Pnma", Lattice.orthorhombic(5.4423, 7.6401, 5.3800),
        ["Ca", "Ti", "O", "O"],
        [[0.0357, 0.25, -0.0064], [0, 0, 0.5],
         [0.4890, 0.25, 0.0707], [0.2887, 0.0387, 0.7113]],
    )


# ladder of increasing difficulty, per the literature's own axes:
# symmetry (cubic -> monoclinic), cell size, and chemical arity
TARGETS = {
    "rutile": (_rutile, "rutile TiO2 (P4_2/mnm, tetragonal, 6 atoms)", 136),
    "anatase": (_anatase, "anatase TiO2 (I4_1/amd, tetragonal, 12 atoms)", 141),
    "quartz": (_quartz, "quartz SiO2 (P3_121, trigonal, 9 atoms)", 152),
    "corundum": (_corundum, "corundum Al2O3 (R-3c, trigonal, 30 atoms)", 167),
    "tenorite": (_tenorite, "tenorite CuO (C2/c, MONOCLINIC, 8 atoms)", 15),
    "baddeleyite": (_baddeleyite, "baddeleyite ZrO2 (P2_1/c, MONOCLINIC, 12 atoms)", 14),
    "perovskite": (_perovskite, "perovskite CaTiO3 (Pnma, orthorhombic, 20 atoms, TERNARY)", 62),
}

CF = Path(os.environ.get("CRYSTALFORMER_DIR",
                         Path.home() / "code/CrystalFormer"))
for p in (CF, CF / "crystalformer" / "src", CF / "scripts"):
    sys.path.insert(0, str(p))


def load_samples(csv_path: Path) -> list[Structure]:
    """CrystalFormer (G, L, A, W, X) rows -> pymatgen Structures."""
    from awl2struct import get_struct_from_lawx  # noqa: PLC0415

    df = pd.read_csv(csv_path)
    out = []
    for _, row in df.iterrows():
        try:
            s = get_struct_from_lawx(
                int(row["G"]),
                np.array(literal_eval(row["L"])),
                np.array(literal_eval(row["A"])),
                np.array(literal_eval(row["W"])),
                np.array(literal_eval(row["X"])),
            )
            out.append(Structure.from_dict(s))
        except Exception:
            out.append(None)
    return out


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """Mann-Whitney AUC: P(a positive scores better than a negative)."""
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    wins = (pos[:, None] < neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(wins / (len(pos) * len(neg)))


def recovery_curve(is_true: np.ndarray, score: np.ndarray, ns, trials=2000, seed=0):
    """P(best-of-n candidate is the true structure) vs n, by resampling."""
    rng = np.random.default_rng(seed)
    n_total = len(score)
    out = {}
    for n in ns:
        if n > n_total:
            continue
        hits = 0
        for _ in range(trials):
            idx = rng.choice(n_total, size=n, replace=False)
            hits += bool(is_true[idx[np.argmin(score[idx])]])
        out[int(n)] = hits / trials
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True, help="output_<formula>.csv from main.py")
    ap.add_argument("--out", default="tracks/other/results/m2-bestofn")
    ap.add_argument("--formula", default="TiO2")
    ap.add_argument("--target", default="rutile", choices=sorted(TARGETS),
                    help="which structure the measured pattern came from")
    ap.add_argument("--counts", type=float, default=None,
                    help="peak counts for a noisy target; omit for noise-free")
    ap.add_argument("--bg", type=float, default=0.10)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    build, target_name, target_sg = TARGETS[args.target]
    truth = build()
    target = (simulate_pattern(truth, SPEC) if args.counts is None
              else noisy_target(truth, args.counts, args.bg))
    tgt_label = "noise-free" if args.counts is None else f"{args.counts:.0g} counts, {args.bg:.0%} bg"

    print(f"target: {target_name}, {tgt_label}")
    structs = load_samples(Path(args.csv))
    n_raw = len(structs)
    print(f"\nQ1. WHAT DID THE PRIOR PROPOSE?  ({n_raw} raw samples)")

    want = Composition(args.formula).reduced_formula
    keep = [(i, s) for i, s in enumerate(structs)
            if s is not None and s.composition.reduced_formula == want]
    print(f"  parsed OK              : {sum(s is not None for s in structs)}/{n_raw}")
    print(f"  composition = {want:<10s}: {len(keep)}/{n_raw}")
    if not keep:
        print("\n  No composition-matching samples -- nothing to score.")
        return 1

    cand = [s for _, s in keep]
    sgs = []
    for s in cand:
        try:
            sgs.append(s.get_space_group_info(symprec=0.1)[1])
        except Exception:
            sgs.append(-1)
    sgs = np.array(sgs)
    uniq, cnt = np.unique(sgs, return_counts=True)
    order = np.argsort(-cnt)
    print(f"  distinct space groups  : {len(uniq)}")
    print("  top space groups       : " + ", ".join(
        f"#{uniq[i]}({cnt[i]})" for i in order[:8]))
    print(f"  target SG {target_sg} sampled  : {int((sgs == target_sg).sum())} times")

    # ---- Q2/Q3: is any of them actually rutile? --------------------------
    sm = StructureMatcher(primitive_cell=True, attempt_supercell=True)
    is_true = np.array([bool(sm.fit(s, truth)) for s in cand])
    print(f"\nQ2. IS THE TARGET AMONG THEM?")
    print(f"  StructureMatcher hits  : {int(is_true.sum())}/{len(cand)}"
          f"  ({is_true.mean():.3%})")

    # ---- score every candidate -------------------------------------------
    pats = [simulate_pattern(s, SPEC) for s in cand]
    d_cos = np.array([d_cosine(p, target) for p in pats])
    d_emd = np.array([d_emd_bg(target, p) for p in pats])

    print(f"\nQ3/Q4. DOES THE REWARD RANK CORRECTLY?")
    hdr = f"  {'metric':<10} {'best-of-N is true':>18} {'rank of best true':>19} {'AUC':>7}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    metric_rows = []
    for name, d in (("cosine", d_cos), ("emd+bg", d_emd)):
        order_idx = np.argsort(d)
        best_is_true = bool(is_true[order_idx[0]])
        if is_true.any():
            rank_best_true = int(np.where(is_true[order_idx])[0][0]) + 1
            a = auc(d[is_true], d[~is_true])
        else:
            rank_best_true, a = -1, float("nan")
        metric_rows.append({"metric": name, "best_of_N_is_true": best_is_true,
                            "rank_of_best_true": rank_best_true, "auc": a})
        print(f"  {name:<10} {str(best_is_true):>18} {rank_best_true:>19} {a:>7.4f}")

    # ---- recovery curve ---------------------------------------------------
    curves = {}
    if is_true.any():
        ns = [n for n in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000) if n <= len(cand)]
        print(f"\n  best-of-n recovery probability")
        print(f"  {'n':>6} {'cosine':>9} {'emd+bg':>9}")
        cc = recovery_curve(is_true, d_cos, ns)
        ce = recovery_curve(is_true, d_emd, ns)
        curves = {"cosine": cc, "emd+bg": ce}
        for n in ns:
            print(f"  {n:>6} {cc[n]:>9.3f} {ce[n]:>9.3f}")

    payload = {
        "run": "m2-bestofn",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target": {"structure": target_name, "noise": tgt_label},
        "n_raw_samples": n_raw,
        "n_composition_match": len(cand),
        "n_distinct_spacegroups": int(len(uniq)),
        "target_sg": target_sg,
        "target_sg_count": int((sgs == target_sg).sum()),
        "n_structurematcher_hits": int(is_true.sum()),
        "metrics": metric_rows,
        "recovery_curves": curves,
    }
    (out / "run.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
