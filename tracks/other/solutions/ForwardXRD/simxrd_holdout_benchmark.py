#!/usr/bin/env python
"""Held-out structure-solution benchmark, standing in for the "benchmark on
SimXRD-4M" deliverable in issue #68.

SimXRD-4M's public test split (`test_binxrd`, downloaded from its OneDrive
distribution) turned out to carry NO usable ground truth for this purpose:

  - `cell` / `positions` are zeroed for every entry -- confirmed on the real
    51 GB file, not just the repo's stripped demo db. The dataset stores only
    composition, a simulated pattern, and a label.
  - That label is not a space group. Reading the authors' own generation
    script (`ht_simxrd.py`) shows `Label = source_db_row_id + 1`, an
    unpublished foreign key into whatever internal Materials Project database
    they simulated from -- not `caobin/CrystDB`'s `MP.db` (checked directly:
    `Label - 1` does not index into it; compositions don't match).

So no structure, and not even a checkable space group, survives in the
release. Cross-referencing composition+spacegroup against `MP.db` (the one
real structure database reachable, via a HuggingFace-gated `caobin/CrystDB`)
independently confirmed this is a dead end for pairing: `MP.db` keeps exactly
one (thermodynamically stable) structure per composition, while SimXRD-4M
spans many polymorphs per composition -- of 200,630 test rows scanned, only 2
had SimXRD's chosen polymorph coincide with MP.db's stable one.

This script instead benchmarks on real, held-out crystals drawn directly from
`MP.db` -- SimXRD-4M's own source population (same "MP-2024.1 thermodynamically
stable structures" the dataset was built from) -- with self-simulated patterns
via the same `simulate_pattern` already used for the original 7 targets, and
runs the identical pipeline (index -> CrystalFormer prior -> MLFF relax ->
EMD rank -> Wyckoff refine -> StructureMatcher against ground truth).

Targets are chosen by `select_mp_targets.py`-equivalent logic: composition+
spacegroup unambiguous in `MP.db` (via spglib), spacegroup > 2 (the indexer
has no triclinic support), 2-20 atoms (CrystalFormer's n_max=21 cap),
excluding the 7 formulas already solved, capped at 4 per crystal system.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)  # always visible live, whether run
sys.stderr.reconfigure(line_buffering=True)  # under -u or not, or into a pipe/file

os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

import numpy as np
from ase.db import connect
from pymatgen.core import Lattice
from pymatgen.io.ase import AseAtomsAdaptor

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from index_pattern import setting_variants, system_of  # noqa: E402
from emd_nnls import d_emd_bg  # noqa: E402
from targets import SM_GRADED, SM_STRICT  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402
from solve_pattern import embed, choose_setting, load_motifs, mlff_relax  # noqa: E402
from emd_metric import SPEC  # noqa: E402
from wyckoff_enumerate import zero_dof_motifs  # noqa: E402

CF = Path(os.environ.get("CRYSTALFORMER_DIR", Path.home() / "code/CrystalFormer"))
RESTORE = CF / "weights/epoch_046000.pkl"
SAMPLES_DIR = CF / "samples_simxrd_bench"
CF_PYTHON = sys.executable  # this pipeline's own venv already has jax 0.10.2 + haiku
INDEX_WORKER = SOL / "index_worker.py"
REFINE_WORKER = SOL / "refine_worker.py"


def run_streaming(cmd: list[str], prefix: str, timeout: float, env: dict | None = None) -> int:
    """subprocess.run, but stdout/stderr stream live (prefixed) instead of being
    silently captured until exit -- a long stage (indexing, DE refinement) is
    otherwise a black box until it finishes or the timeout fires, which is how
    a real 13-minute stall and a legitimate-but-slow 20+ minute refinement were
    indistinguishable from the outside earlier in this benchmark's development.

    `env`, if given, REPLACES the inherited environment (merged with
    PYTHONUNBUFFERED) rather than only overriding keys on top of it -- callers
    that need to unset a variable (e.g. JAX_PLATFORMS, since an empty string
    isn't the same as unset to jax) must build the full dict themselves.

    Reads lines on a background thread rather than `for line in proc.stdout`:
    that form blocks on the next readline with no way to notice a timeout
    while the child is silent, which is exactly how a genuine hang and a
    legitimate-but-quiet stage were indistinguishable earlier in this file's
    history -- a queue.get(timeout=...) here actually enforces the deadline
    even when zero output is produced.
    """
    import queue
    import threading

    env = dict(env if env is not None else os.environ, PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    q: queue.Queue = queue.Queue()

    def _reader():
        try:
            for line in proc.stdout:
                q.put(line)
        finally:
            q.put(None)  # sentinel: stdout closed (process exited or was killed)

    threading.Thread(target=_reader, daemon=True).start()

    t0 = time.time()
    while True:
        remaining = timeout - (time.time() - t0)
        if remaining <= 0:
            proc.kill()
            proc.wait()
            raise subprocess.TimeoutExpired(cmd, timeout)
        try:
            line = q.get(timeout=min(remaining, 5.0))
        except queue.Empty:
            continue  # no output in the last 5s; loop back to re-check the deadline
        if line is None:
            break
        print(f"    [{prefix}] {line.rstrip()}", flush=True)
    proc.wait()
    return proc.returncode


def index_pattern_isolated(measured: np.ndarray, sg: int, n_jobs: int = 0):
    """index_pattern(), run in a fresh subprocess that never imports jax.

    This process has awl2struct/jax loaded (via the solve_pattern import
    above), so index_pattern's internal fork()-based Pool would risk a
    fork-with-threads deadlock if called in-process. See index_worker.py.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        infile, outfile = Path(td) / "in.json", Path(td) / "out.json"
        infile.write_text(json.dumps({"pattern": measured.tolist(),
                                      "spacegroup": sg, "n_jobs": n_jobs}))
        try:
            rc = run_streaming([sys.executable, str(INDEX_WORKER), str(infile), str(outfile)],
                               "index", timeout=600)
        except subprocess.TimeoutExpired:
            return None, {"error": "index_worker timed out (>600s)"}
        if rc != 0 or not outfile.exists():
            return None, {"error": f"index_worker failed, rc={rc}"}
        out = json.loads(outfile.read_text())
    cell = Lattice.from_parameters(*out["cell"]) if out["cell"] is not None else None
    return cell, out["info"]


def refine_isolated(struct, measured: np.ndarray, window: float, workers: int = -1,
                    timeout: float = 3600):
    """wyckoff_refine.refine(), run in a fresh subprocess that never imports jax.

    See refine_worker.py: this lets DE use scipy's workers= parallelism (a
    fork()-based Pool internally) safely and, measured on the dof=18 case that
    motivated this, ~3.6x faster than serial in-process refinement.
    """
    import tempfile
    from pymatgen.core import Structure

    with tempfile.TemporaryDirectory() as td:
        infile, outfile = Path(td) / "in.json", Path(td) / "out.json"
        infile.write_text(json.dumps({"structure": struct.as_dict(),
                                      "measured": measured.tolist(),
                                      "window": window, "workers": workers}))
        try:
            rc = run_streaming([sys.executable, str(REFINE_WORKER), str(infile), str(outfile)],
                               "refine", timeout=timeout)
        except subprocess.TimeoutExpired:
            return struct, f"refine_worker timed out (>{timeout:.0f}s)"
        if rc != 0 or not outfile.exists():
            return struct, f"refine_worker failed, rc={rc}"
        out = json.loads(outfile.read_text())
    return Structure.from_dict(out["structure"]), out["status"]


class _Stage:
    """Context manager: times a pipeline stage into `timings[name]` (seconds)."""

    def __init__(self, name: str, timings: dict):
        self.name, self.timings = name, timings

    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, *exc):
        self.timings[self.name] = time.time() - self.t0
        return False


def sample_prior(formula: str, sg: int, tag: str, n_samples: int) -> Path | None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    out_name = f"{tag}.csv"
    out_path = SAMPLES_DIR / f"{tag}_{formula}.csv"
    if out_path.exists():
        return out_path
    cmd = [CF_PYTHON, "main.py", "--optimizer", "none",
           "--restore_path", str(RESTORE), "--spacegroup", str(sg),
           "--num_samples", str(n_samples), "--batchsize", "500",
           "--formula", formula, "--save_path", str(SAMPLES_DIR) + "/",
           "--output_filename", out_name]
    # The parent process sets JAX_PLATFORMS=cpu for its own lightweight,
    # kernel-free jax import (see module top); CrystalFormer's actual sampling
    # needs the GPU, so scrub that override for this subprocess.
    env = dict(os.environ)
    env.pop("JAX_PLATFORMS", None)
    env["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
    old_cwd = os.getcwd()
    os.chdir(CF)
    try:
        rc = run_streaming(cmd, "sample", timeout=1800, env=env)
    except subprocess.TimeoutExpired:
        print(f"    CrystalFormer sampling TIMED OUT for {tag} (>1800s)")
        return None
    finally:
        os.chdir(old_cwd)
    if rc != 0 or not out_path.exists():
        print(f"    CrystalFormer sampling FAILED for {tag}, rc={rc}")
        return None
    return out_path


def run_target(t: dict, tag: str, mp_db, adaptor: AseAtomsAdaptor, args) -> dict:
    """Run the full pipeline for one target; returns a result row dict."""
    formula, sg, mp_id, n_atoms = t["formula"], t["spacegroup"], t["mp_id"], t["n_atoms"]
    base = {"target": tag, "formula": formula, "spacegroup": sg, "mp_id": mp_id,
            "mpid": t.get("mpid"), "system": t.get("system"), "n_atoms": n_atoms}

    timings = {}

    def stage(name):
        return _Stage(name, timings)

    mp_row = mp_db.get(id=mp_id)
    truth_prim = adaptor.get_structure(mp_row.toatoms())
    # MP.db stores primitive cells; everything downstream of indexing (CrystalFormer's
    # get_struct_from_lawx, this pipeline's own indexer) works in the CONVENTIONAL
    # cell. Comparing indexed-cell parameters against truth_prim directly is only
    # valid when the two happen to share a basis -- for centered Bravais lattices
    # they don't (e.g. Al2TcRh: primitive a=b=c=10.31, angles 124/118/88 degrees;
    # conventional a=4.83 b=10.55 c=14.87, all 90 -- same crystal, same volume,
    # incomparable parameters). Converting once here makes every downstream
    # comparison (cell-error diagnostic, StructureMatcher) apples-to-apples.
    # simulate_pattern is basis-independent either way (same physical pattern),
    # and StructureMatcher(primitive_cell=True) already reduces internally, so
    # this was never a correctness bug in top1_correct -- only in the cell-error
    # diagnostic, which reported nonsense for those cases.
    try:
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        truth = SpacegroupAnalyzer(truth_prim, symprec=0.1).get_conventional_standard_structure()
    except Exception:
        truth = truth_prim  # fall back to primitive if spglib can't standardize it
    measured = simulate_pattern(truth, SPEC)

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
        # Supplement with an exhaustive zero-dof Wyckoff-site enumeration:
        # CrystalFormer's sampling is probabilistic and can simply miss the
        # true discrete arrangement (confirmed directly on Th2Se2O -- 0/148
        # samples matched); when every occupied site has zero continuous
        # freedom, the discrete choice is a small combinatorial problem that
        # can be enumerated exactly instead of hoped for. No-op (returns [])
        # when the true structure isn't actually zero-dof, or the composition
        # can't be built from special positions at all.
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
    n_correct = sum(bool(SM_STRICT.fit(cands[j], truth)) for j in order[:args.top_k])

    total = sum(timings.values())
    print(f"    RESULT           top1_correct={solved} rms={rms} "
          f"correct_in_top{args.top_k}={n_correct}  [total {total:.0f}s]")

    return {**base, "cell_error_max": max(err), "n_candidates": len(cands),
            "mlff_relaxed": bool(relaxed_ok), "refine_status": refine_status,
            "top1_correct": solved, "top1_rms": rms,
            "n_correct_in_topk": n_correct, "top_k": args.top_k, "timings": timings}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets-json", required=True,
                    help="JSON list of {formula, spacegroup, mp_id}")
    ap.add_argument("--mp-db", required=True, help="path to MP.db (ase db)")
    ap.add_argument("--n-candidates", type=int, default=1000)
    ap.add_argument("--n-samples", type=int, default=1200)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--relax-steps", type=int, default=60)
    ap.add_argument("--refine-window", type=float, default=0.15)
    ap.add_argument("--refine-top-k", type=int, default=3,
                    help="refine this many top-ranked (by pre-refine EMD score) "
                         "candidates and keep the best post-refine result, instead "
                         "of only refining #1 -- catches cases where the true "
                         "structure narrowly loses the pre-refine ranking. Each "
                         "extra candidate costs one more refine subprocess.")
    ap.add_argument("--out", default="tracks/other/results/m-simxrd-heldout-benchmark")
    ap.add_argument("--n-solve-attempts", type=int, default=15,
                    help="stop once this many targets got nonzero prior candidates "
                         "(the rest of --targets-json is an over-provisioned pool to "
                         "absorb zero-coverage compositions)")
    ap.add_argument("--index-n-jobs", type=int, default=0,
                    help="cores for the isolated indexing subprocess's candidate-cell "
                         "scoring; <=0 (default) means cpu_count()-2. Parallel by "
                         "default -- pass 1 only to force serial, e.g. for debugging.")
    ap.add_argument("--refine-workers", type=int, default=-1,
                    help="cores for the isolated DE refinement subprocess; -1 "
                         "(default) means all cores, matching scipy's own "
                         "convention. Measured 3.6x faster than serial on an "
                         "18-dof case. Pass 1 only to force serial.")
    args = ap.parse_args()

    with open(args.targets_json) as f:
        targets = json.load(f)
    mp_db = connect(args.mp_db)
    adaptor = AseAtomsAdaptor()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []

    def checkpoint():
        (out_dir / "run.json").write_text(json.dumps({
            "run": "m-simxrd-heldout-benchmark", "partial": True,
            "n_targets": len(targets), "n_done": len(rows), "rows": rows,
        }, indent=2, default=str) + "\n")

    n_had_candidates = 0
    for i, t in enumerate(targets):
        if n_had_candidates >= args.n_solve_attempts:
            print(f"\nreached {args.n_solve_attempts} solve attempts with prior "
                  f"coverage; stopping ({len(targets) - i} pool targets unused)")
            break
        tag = f"bench{i:02d}_sg{t['spacegroup']}"
        print(f"\n=== [{i+1}/{len(targets)}] {t['formula']} (SG {t['spacegroup']}, "
              f"{t['n_atoms']} atoms, mp_id={t['mp_id']}) "
              f"[{n_had_candidates}/{args.n_solve_attempts} solve attempts so far] ===")
        try:
            row = run_target(t, tag, mp_db, adaptor, args)
        except Exception as e:
            print(f"    UNEXPECTED FAILURE for {tag}: {e!r}")
            row = {"target": tag, "formula": t["formula"], "spacegroup": t["spacegroup"],
                   "mp_id": t["mp_id"], "stage_failed": "exception", "error": repr(e)}
        if row.get("stage_failed") not in ("no_usable_candidates", "prior_sampling"):
            n_had_candidates += 1
        rows.append(row)
        checkpoint()

    no_coverage = [r for r in rows if r.get("stage_failed") in ("no_usable_candidates", "prior_sampling")]
    attempts = [r for r in rows if r not in no_coverage]
    n_solved = sum(1 for r in attempts if r.get("top1_correct"))
    n_attempted = len(attempts)
    print(f"\n=== SUMMARY: {n_solved}/{n_attempted} solved at strict tolerance "
          f"({len(no_coverage)} skipped for zero prior coverage) ===")
    for r in rows:
        in_no_cov = r in no_coverage
        status = ("SOLVED rms=%.4f" % r["top1_rms"]
                  if r.get("top1_correct") and r.get("top1_rms") is not None
                  else "NO PRIOR COVERAGE" if in_no_cov
                  else "FAILED" if "stage_failed" not in r else f"FAILED ({r['stage_failed']})")
        print(f"  {r.get('formula', '?'):14s} SG{r.get('spacegroup', '?'):<5} {status}")

    (out_dir / "run.json").write_text(json.dumps({
        "run": "m-simxrd-heldout-benchmark",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "question": "structure-match rate on a held-out benchmark, standing in for "
                    "the SimXRD-4M deliverable (SimXRD-4M's public release has no "
                    "recoverable ground truth -- see module docstring)",
        "ground_truth_source": "MP.db (caobin/CrystDB), SimXRD-4M's own source population",
        "pattern_source": "self-simulated (pymatgen XRDCalculator), noise-free, "
                          "same method as the original 7-target study",
        "n_pool": len(targets), "n_no_prior_coverage": len(no_coverage),
        "n_attempted": n_attempted, "n_solved": n_solved,
        "solve_rate": n_solved / n_attempted if n_attempted else 0.0,
        "params": {"n_candidates": args.n_candidates, "n_samples": args.n_samples,
                  "top_k": args.top_k, "relax_steps": args.relax_steps,
                  "refine_window": args.refine_window},
        "rows": rows,
    }, indent=2, default=str) + "\n")
    print(f"\nwrote {out_dir / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
