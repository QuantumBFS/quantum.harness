#!/usr/bin/env python
"""Head-to-head benchmark against SmartCellSolver (arXiv:2605.24594,
github.com/MaterSim/Ab-PXRD-Solver) -- resolves the open comparison item
named in SUMMARY.md section 7.

Targets are a stratified random sample from SmartCellSolver's OWN published
test set (data/test.txt + data/mono.txt, 1136 structures after excluding
their own commented-out entries), run on THEIR OWN pattern files (not
self-simulated) -- a true identical-input comparison, not just a similarly-
sized independent sample.

They don't publish ground-truth structures (their own success criterion is
GSAS-II Rietveld pattern fit -- R^2 >= 0.95, Chi^2 <= 0.12 -- not atomic
structure comparison, so they never needed one). We cross-reference each
sampled (formula, spacegroup) against our own MP.db for an unambiguous match,
giving us ground truth for the strict StructureMatcher criterion their own
number can't speak to -- see select_scs_targets.py.

Reports TWO criteria per target, because the two pipelines' "success" means
different things:
  - strict: StructureMatcher.fit against the true atomic structure (our bar,
    and the one the challenge's own premise cares about -- pattern fit alone
    can be satisfied by a "look-alike wrong structure").
  - comparable_r2: a weighted R^2 (via emd_nnls.refine_nnls's scale+background
    fit) against SmartCellSolver's own R^2>=0.95 gate -- NOT bit-identical to
    GSAS-II's Rietveld R^2, but the same kind of pattern-fit quantity, so we
    can report "would this have cleared their bar too" alongside the stricter
    number instead of comparing across incompatible bars.

Their published per-structure outcome (Success/C-Success/Failure, R^2, Chi^2)
is carried through from select_scs_targets.py for a genuine PAIRED comparison
-- same items, not independently-drawn samples -- wherever they published one.

Their patterns are on a 10-80deg, step 0.02deg, 3501-point grid, different
from this pipeline's default SPEC (10-90deg, 4096 points) that several
functions (d_emd_bg, index_worker.py) hardcode internally. Rather than thread
a custom spec through every one of those under time pressure, their pattern
is linearly interpolated onto our default SPEC grid once, flat-extrapolated
past 80deg (sparse region, low information cost) -- the same technique
validated earlier for SimXRD-4M's patterns.

Smoke-tested finding worth flagging up front: comparable_r2 reads LOW (~0.4)
even for a structurally exact match (rms ~1e-16, strict_match=True) -- a
self-comparison sanity check confirms the R^2 formula itself is correct
(measured against itself gives exactly 1.0), so this is a real broadening-
model mismatch (our fixed 0.25deg pseudo-Voigt vs. their more realistic peak
shapes), not a bug and not evidence of a wrong structure. Treat strict_match
as the primary result; comparable_r2 as an unvalidated secondary diagnostic.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from ase.db import connect  # noqa: E402
from pymatgen.core import Structure  # noqa: E402
from pymatgen.io.ase import AseAtomsAdaptor  # noqa: E402
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer  # noqa: E402

from emd_metric import SPEC  # noqa: E402
from emd_nnls import d_emd_bg, refine_nnls  # noqa: E402
from index_pattern import setting_variants, system_of  # noqa: E402
from targets import SM_GRADED, SM_STRICT  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402
from solve_pattern import embed, choose_setting, load_motifs, mlff_relax  # noqa: E402
from wyckoff_enumerate import zero_dof_motifs  # noqa: E402
from simxrd_holdout_benchmark import (  # noqa: E402
    _Stage, index_pattern_isolated, refine_isolated, sample_prior,
)


def load_external_pattern(csv_path: Path) -> np.ndarray:
    """Their (2theta, intensity) CSV -> intensity resampled onto our SPEC.grid."""
    data = np.loadtxt(csv_path, delimiter=",", comments="#")
    tt, inten = data[:, 0], data[:, 1]
    inten = np.maximum(inten, 0.0)  # their pattern can dip slightly negative
    return np.interp(SPEC.grid, tt, inten, left=0.0, right=inten[-1])


def comparable_r2(measured: np.ndarray, candidate: Structure) -> float:
    """Weighted R^2 of the best (scale, Chebyshev background) fit -- the same
    kind of pattern-fit quantity as SmartCellSolver's Rietveld R^2 gate, not
    a bit-identical reproduction of GSAS-II's formula.
    """
    sim = simulate_pattern(candidate, SPEC)
    scale, bg = refine_nnls(measured, sim)
    pred = scale * sim + bg
    w = 1.0 / np.maximum(measured, 1.0)
    ss_res = float(np.sum(w * (measured - pred) ** 2))
    ss_tot = float(np.sum(w * (measured - measured.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def run_target(t: dict, tag: str, mp_db, adaptor: AseAtomsAdaptor, pattern_dir: Path,
               args) -> dict:
    formula, sg, mp_id, n_atoms = t["formula"], t["spacegroup"], t["mp_id"], t["n_atoms"]
    base = {**t, "target": tag}
    timings = {}

    def stage(name):
        return _Stage(name, timings)

    mp_row = mp_db.get(id=mp_id)
    truth = SpacegroupAnalyzer(adaptor.get_structure(mp_row.toatoms()),
                               symprec=0.1).get_conventional_standard_structure()
    measured = load_external_pattern(pattern_dir / t["csv_name"])

    with stage("index"):
        cell, index_info = index_pattern_isolated(measured, sg, n_jobs=args.index_n_jobs)
    if cell is None:
        print(f"    indexing FAILED: {index_info}")
        return {**base, "stage_failed": "index", "info": index_info, "timings": timings}
    t_lat = truth.lattice
    err = [abs(getattr(cell, k) / getattr(t_lat, k) - 1) for k in ("a", "b", "c")]

    with stage("sample"):
        csv = sample_prior(formula, sg, tag, args.n_samples)
    if csv is None:
        return {**base, "stage_failed": "prior_sampling", "timings": timings}

    with stage("load_motifs"):
        motifs = load_motifs(csv, formula, n_atoms, args.n_candidates)
        n_cf = len(motifs)
        try:
            comp = {str(el): int(n) for el, n in truth.composition.get_el_amt_dict().items()}
            motifs += zero_dof_motifs(sg, comp, cap=2000)
        except Exception as e:
            print(f"    [wyckoff-enum] skipped: {e!r}")
    n_enum = len(motifs) - n_cf
    print(f"    prior            {len(motifs)} candidates ({n_cf} CrystalFormer + "
          f"{n_enum} zero-dof enumerated)  [{timings['sample']:.0f}s sample, "
          f"{timings['load_motifs']:.0f}s parse]")
    if not motifs:
        return {**base, "stage_failed": "no_usable_candidates", "timings": timings}

    with stage("setting"):
        variants = setting_variants(cell, system_of(sg))
        if len(variants) > 1:
            scored = choose_setting(variants, motifs, measured)
            cell = scored[0][1]
            err = [abs(getattr(cell, k) / getattr(t_lat, k) - 1) for k in ("a", "b", "c")]

    with stage("relax"):
        cands = embed(motifs, cell)
        cands, relaxed_ok = mlff_relax(cands, args.relax_steps)
    print(f"    MLFF relax       {len(cands)} candidates ({'ok' if relaxed_ok else 'FAILED'}) "
          f"[{timings['relax']:.0f}s]")
    if not cands:
        return {**base, "stage_failed": "no_candidates_after_relax", "timings": timings}

    with stage("rank"):
        scores = np.array([d_emd_bg(measured, simulate_pattern(c, SPEC)) for c in cands])
        order = np.argsort(scores)

    def _score(st):
        return d_emd_bg(measured, simulate_pattern(st, SPEC))

    # Refine the top-K ranked candidates, not just #1: pre-refine EMD score is a
    # weak discriminator between structurally-different candidates that both fit
    # the pattern reasonably well (confirmed directly on Ce2Ni5C3/SG127 -- the
    # true structure ranked #2, only ~4% behind the wrong #1, and DE refinement
    # inside a single Wyckoff arrangement's window can't turn one arrangement
    # into another). Refining only the top-1 silently drops these near-ties.
    before = _score(cands[order[0]])
    refine_k = max(1, min(args.refine_top_k, len(cands)))
    best, best_score, refine_status = None, None, None
    with stage("refine"):
        for rank in range(refine_k):
            cand, status = refine_isolated(cands[order[rank]], measured, args.refine_window,
                                           workers=args.refine_workers)
            score = _score(cand)
            if best_score is None or score < best_score:
                best, best_score, refine_status = cand, score, f"rank{rank}:{status}"
    print(f"    refine top{refine_k}       {refine_status}; reward {before:.4f} -> {best_score:.4f} "
          f"[{timings['refine']:.0f}s]")

    solved = bool(SM_STRICT.fit(best, truth))
    try:
        d = SM_GRADED.get_rms_dist(best, truth)
        rms = None if d is None else float(d[0])
    except Exception:
        rms = None
    r2 = comparable_r2(measured, best)
    comparable_success = r2 >= 0.95

    total = sum(timings.values())
    print(f"    RESULT           strict={solved} rms={rms} comparable_r2={r2:.4f} "
          f"(>=0.95: {comparable_success})  scs_published={t.get('scs_published_outcome')}  "
          f"[total {total:.0f}s]")

    return {**base, "cell_error_max": max(err), "n_candidates": len(cands),
            "mlff_relaxed": bool(relaxed_ok), "refine_status": refine_status,
            "strict_match": solved, "rms": rms, "comparable_r2": r2,
            "comparable_success": bool(comparable_success), "timings": timings}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets-json", required=True)
    ap.add_argument("--pattern-dir", required=True)
    ap.add_argument("--mp-db", required=True)
    ap.add_argument("--n-candidates", type=int, default=1000)
    ap.add_argument("--n-samples", type=int, default=1200)
    ap.add_argument("--relax-steps", type=int, default=60)
    ap.add_argument("--refine-window", type=float, default=0.15)
    ap.add_argument("--refine-top-k", type=int, default=3,
                    help="refine this many top-ranked (by pre-refine EMD score) "
                         "candidates and keep the best post-refine result, instead "
                         "of only refining #1 -- catches cases where the true "
                         "structure narrowly loses the pre-refine ranking. Each "
                         "extra candidate costs one more refine subprocess.")
    ap.add_argument("--index-n-jobs", type=int, default=0)
    ap.add_argument("--refine-workers", type=int, default=-1)
    ap.add_argument("--out", default="tracks/other/results/m-scs-benchmark")
    args = ap.parse_args()

    with open(args.targets_json) as f:
        targets = json.load(f)
    mp_db = connect(args.mp_db)
    adaptor = AseAtomsAdaptor()
    pattern_dir = Path(args.pattern_dir)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    def checkpoint():
        (out_dir / "run.json").write_text(json.dumps({
            "run": "m-scs-benchmark", "partial": True,
            "n_targets": len(targets), "n_done": len(rows), "rows": rows,
        }, indent=2, default=str) + "\n")

    t_run_start = time.time()
    for i, t in enumerate(targets):
        tag = f"scs{i:02d}_{t['system']}_sg{t['spacegroup']}"
        print(f"\n=== [{i + 1}/{len(targets)}] {t['formula']} (SG {t['spacegroup']}, "
              f"{t['system']}, {t['n_atoms']} atoms) [{time.time() - t_run_start:.0f}s elapsed] ===")
        try:
            row = run_target(t, tag, mp_db, adaptor, pattern_dir, args)
        except Exception as e:
            print(f"    UNEXPECTED FAILURE for {tag}: {e!r}")
            row = {**t, "target": tag, "stage_failed": "exception", "error": repr(e)}
        rows.append(row)
        checkpoint()

    # ---- per-module aggregate timing report ------------------------------
    stage_totals: dict[str, float] = {}
    stage_counts: dict[str, int] = {}
    for r in rows:
        for k, v in r.get("timings", {}).items():
            stage_totals[k] = stage_totals.get(k, 0.0) + v
            stage_counts[k] = stage_counts.get(k, 0) + 1
    total_wall = time.time() - t_run_start
    print(f"\n=== PER-MODULE TIMING (n={len(rows)} targets, {total_wall:.0f}s wall) ===")
    for k in sorted(stage_totals, key=lambda k: -stage_totals[k]):
        n = stage_counts[k]
        print(f"  {k:<14} total={stage_totals[k]:>8.0f}s  mean={stage_totals[k]/n:>7.1f}s  "
              f"n={n:<3d} ({stage_totals[k]/total_wall:.1%} of wall time)")

    # ---- strata + criterion comparison ------------------------------------
    # PRIMARY metric: strict StructureMatcher against our MP.db ground truth --
    # unaffected by any peak-broadening modeling choice, ours or theirs.
    # comparable_r2 is a SECONDARY diagnostic only: the smoke test showed it can
    # read low (~0.4) even for a structurally exact match (rms ~1e-16), because
    # our simulate_pattern's fixed 0.25deg pseudo-Voigt broadening doesn't match
    # SmartCellSolver's more realistic peak shapes closely enough for a literal
    # pointwise R^2 -- that's a broadening-model confound, not evidence of a
    # wrong structure. Don't treat comparable_success as validated; strict_match
    # is the number that means what it says.
    by_system: dict[str, list] = {}
    for r in rows:
        by_system.setdefault(r.get("system", "?"), []).append(r)

    print(f"\n=== RESULTS BY SYSTEM (strict = primary; comparable_r2 = diagnostic only, "
          f"see caveat above) ===")
    for system, rs in by_system.items():
        n = len(rs)
        n_strict = sum(1 for r in rs if r.get("strict_match"))
        n_comp = sum(1 for r in rs if r.get("comparable_success"))
        n_scs = sum(1 for r in rs if r.get("scs_published_outcome") in ("Success", "C-Success"))
        n_scs_known = sum(1 for r in rs if r.get("scs_published_outcome") is not None)
        print(f"  {system:<14} n={n:<3d} strict={n_strict}/{n} ({n_strict/n:.1%})  "
              f"comparable_r2>=0.95={n_comp}/{n} ({n_comp/n:.1%})  "
              f"scs_published_success={n_scs}/{n_scs_known if n_scs_known else 1} "
              f"(of {n_scs_known} with known outcome)")

    n_strict = sum(1 for r in rows if r.get("strict_match"))
    n_comp = sum(1 for r in rows if r.get("comparable_success"))
    print(f"\n  OVERALL strict={n_strict}/{len(rows)} ({n_strict/len(rows):.1%})  "
          f"comparable_r2>=0.95={n_comp}/{len(rows)} ({n_comp/len(rows):.1%})")

    # ---- paired comparison, where SmartCellSolver published an outcome ----
    paired = [r for r in rows if r.get("scs_published_outcome") is not None]
    a = sum(1 for r in paired if r.get("strict_match")
           and r["scs_published_outcome"] in ("Success", "C-Success"))       # both succeed
    b = sum(1 for r in paired if r.get("strict_match")
           and r["scs_published_outcome"] == "Failure")                      # us only
    c = sum(1 for r in paired if not r.get("strict_match")
           and r["scs_published_outcome"] in ("Success", "C-Success"))       # them only
    d = sum(1 for r in paired if not r.get("strict_match")
           and r["scs_published_outcome"] == "Failure")                     # neither
    print(f"\n=== PAIRED (n={len(paired)} targets with a published SCS outcome; "
          f"strict criterion vs. their published Success/C-Success) ===")
    print(f"  both succeed={a}  us-only={b}  them-only={c}  neither={d}")
    if b + c > 0:
        from scipy.stats import binomtest
        p = binomtest(min(b, c), b + c, 0.5).pvalue
        print(f"  McNemar-style exact test on discordant pairs (b={b}, c={c}): p={p:.4f}")
    else:
        print("  no discordant pairs -- test not applicable at this N")

    (out_dir / "run.json").write_text(json.dumps({
        "run": "m-scs-benchmark",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "question": "head-to-head against SmartCellSolver (arXiv:2605.24594) on their "
                    "own published test set and pattern files",
        "n_targets": len(targets), "total_wall_seconds": total_wall,
        "stage_totals": stage_totals, "stage_counts": stage_counts,
        "rows": rows,
    }, indent=2, default=str) + "\n")
    print(f"\nwrote {out_dir / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
