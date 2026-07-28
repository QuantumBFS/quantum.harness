#!/usr/bin/env python
"""End-to-end powder-XRD structure solver: index -> prior -> rank.

Milestone 4. Ties together everything the earlier milestones validated:

  stage 1  cell from peak positions    <- REAL indexing, see below
  stage 1b conventional-setting choice
  stage 2  CrystalFormer, conditioned on composition + space group
  stage 3  re-embed candidates in the indexed cell
  stage 3b MLFF relaxation, coordinates only, CELL HELD FIXED
  stage 4  rank by EMD + non-negative Chebyshev background
  stage 5  Wyckoff-respecting DE refinement of the top candidate
  stage 6  verify against ground truth

Both post-processing stages are included, on the m5 ablation and its m7 revision:

    MLFF relaxation improved the top-1 rms by 44-89% on the four targets with
    room to improve (perovskite 0.1448 -> 0.0166, baddeleyite 0.0351 -> 0.0195,
    rutile 0.0064 -> 0.0032, marcasite 0.0105 -> 0.0056) and cost little on the
    three that were already tight.

    DE refinement was REJECTED by m5 and REINSTATED by m7. The m5 verdict was an
    artifact of two faults: quartz -- the only target that needed refinement --
    never ran DE at all ("multiplicity 10 != 9", because Si sits on the special
    3a site), and baddeleyite was refined against a MOCKED 0.3% cell, where the
    reward's optimum is displaced from the truth and 9 free parameters let DE
    chase it. With a real indexed cell (~0.01%) and a Wyckoff-respecting
    parameterisation, DE gives quartz rms 0.1818 -> 0.0001 and baddeleyite
    0.0098 -> 0.0012.

    The rule: refinement helps when the cell is accurate and hurts when it is
    not. Every downstream stage inherits the cell's quality.

The force field must never touch the CELL: relaxing it free drifts 6 of 7
targets past the tolerance in stage 1 (CuO by 19%), because it seeks an
energetic minimum, not a diffraction one.

Why re-embedding rather than conditioning the model's lattice head: in
CrystalFormer the coordinates are generated WITHOUT seeing L -- the per-site
inference call takes (composition, G, W, A, X, Y, Z) and no lattice -- and L's
mixture parameters are read out only afterwards. So constraining the lattice
head cannot change the motif, and overwriting L post hoc is equivalent. This is
why no model modification is needed. Conditioning the *coordinates* on the cell
would require feeding L before the site loop, i.e. retraining.

STAGE 1 IS REAL by default (--index real): index_pattern.py recovers the cell
from peak positions alone, given only the space group (read off systematic
absences). Measured accuracy across the seven targets is 0.003-0.019%, against
the m2f tolerance of ~0.2-0.5% at 9 free coordinates and >=5% at 1-4 -- more
than an order of magnitude of headroom. Pass --index mock to fall back to a
ground-truth cell perturbed by --cell-error.

STAGE 1b resolves the conventional setting. Indexing fixes the LATTICE, not a
basis for it: monoclinic (a, c) is defined up to a unimodular transformation
(handled analytically by Gauss reduction), and orthorhombic axis LABELS are not
determined by the lattice at all -- Pnnm vs Pmnn is a labelling. So the six
permutations are scored by pattern fit and the best kept. This is not optional:
re-embedding motifs into a permuted setting yields structures that are
geometrically valid and completely wrong.
"""

from __future__ import annotations

import argparse
import json
import sys
from ast import literal_eval
from datetime import datetime, timezone
from pathlib import Path

import os

# awl2struct imports crystalformer.src.wyckoff, which pulls in jax; by default
# jax preallocates ~90% of a GPU and collides with the MLFF subprocess. This
# pipeline never runs jax kernels, so disable it before the import happens.
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

import numpy as np
import pandas as pd
from pymatgen.core import Composition, Lattice, Structure

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from emd_metric import SPEC, noisy_target  # noqa: E402
from index_pattern import index_pattern, setting_variants, system_of  # noqa: E402
from wyckoff_refine import refine as wyckoff_de_refine  # noqa: E402
from emd_nnls import d_emd_bg  # noqa: E402
from targets import REGISTRY, SM_GRADED, SM_STRICT  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402

CF = Path(os.environ.get("CRYSTALFORMER_DIR",
                         Path.home() / "code/CrystalFormer"))
for _p in (CF, CF / "crystalformer" / "src", CF / "scripts"):
    sys.path.insert(0, str(_p))

def mock_index(truth: Structure, rel_error: float, rng, spacegroup: int) -> Lattice:
    """Stand-in for a real indexer: true cell + error on the FREE parameters only.

    A real indexer refines the cell subject to the Laue class, so it can never
    return a != b for a tetragonal cell. Perturbing every axis independently (as
    an earlier version did) produces lattices that contradict the space group;
    `Structure.from_spacegroup` then rejects them, which silently disabled the
    downstream refinement. Only the symmetry-independent lengths are perturbed
    here, and the crystal-system constructor enforces the constraints exactly.

    Angles are left at their true values: m2f measured tolerance against length
    errors only, so this keeps the error model consistent with that calibration.
    """
    lat = truth.lattice
    if rel_error <= 0:
        return lat

    def f():
        return 1.0 + rng.normal(0.0, rel_error)

    if spacegroup > 194:                      # cubic:        a = b = c
        return Lattice.cubic(lat.a * f())
    if spacegroup > 142:                      # trigonal/hex: a = b, gamma = 120
        return Lattice.hexagonal(lat.a * f(), lat.c * f())
    if spacegroup > 74:                       # tetragonal:   a = b
        return Lattice.tetragonal(lat.a * f(), lat.c * f())
    if spacegroup > 15:                       # orthorhombic: a, b, c free
        return Lattice.orthorhombic(lat.a * f(), lat.b * f(), lat.c * f())
    if spacegroup > 2:                        # monoclinic:   a, b, c, beta
        return Lattice.monoclinic(lat.a * f(), lat.b * f(), lat.c * f(), lat.beta)
    return Lattice.from_parameters(           # triclinic:    everything free
        lat.a * f(), lat.b * f(), lat.c * f(), lat.alpha, lat.beta, lat.gamma)


MACE_PY = Path(os.environ.get("MACE_PYTHON",
                              Path.home() / "code/venv-mace/bin/python"))
RELAX = SOL / "mace_relax.py"


def _gpu_count() -> int:
    import subprocess  # noqa: PLC0415
    try:
        out = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True,
                             timeout=20)
        return sum(1 for line in out.stdout.splitlines() if line.startswith("GPU "))
    except Exception:
        return 0


def mlff_relax(structs, steps: int = 60, n_gpus: int | None = None):
    """Relax coordinates at FIXED cell via the MACE venv. Returns (structs, ok).

    Runs as a subprocess because torch ships nvidia-* wheels that would collide
    with jax's inside this venv. `ok` is False when any shard failed, so a silent
    fall-through to unrelaxed structures can never be mistaken for a result --
    that exact failure corrupted an earlier crossover run.

    Relaxation is the pipeline's wall-clock bottleneck (~0.2 s/structure, vs
    0.3 ms to score one), and structures are independent, so the list is sharded
    one shard per GPU with CUDA_VISIBLE_DEVICES pinning each subprocess to its
    own device. Order is restored on merge.
    """
    if not structs:
        return structs, True
    import os  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    if n_gpus is None:
        n_gpus = max(1, _gpu_count())
    n_shards = max(1, min(n_gpus, len(structs)))

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        idx = np.array_split(np.arange(len(structs)), n_shards)
        procs = []
        for i, ids in enumerate(idx):
            if len(ids) == 0:
                continue
            fin, fout = td / f"in{i}.json", td / f"out{i}.json"
            fin.write_text(json.dumps(
                {"structures": [structs[j].as_dict() for j in ids]}, default=str))
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(i))
            procs.append((ids, fout, subprocess.Popen(
                [str(MACE_PY), str(RELAX), str(fin), str(fout), "--steps", str(steps)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)))

        out, ok = list(structs), True
        for ids, fout, pr in procs:
            _, err = pr.communicate()
            if pr.returncode != 0 or not fout.exists():
                print(f"    [MLFF shard FAILED rc={pr.returncode}] "
                      f"{err.strip().splitlines()[-3:]}")
                ok = False
                continue
            got = json.loads(fout.read_text())["structures"]
            for j, sd in zip(ids, got):
                out[j] = Structure.from_dict(sd)
        return out, ok


def load_motifs(csv: Path, formula: str, n_atoms: int, cap: int):
    """CrystalFormer motifs as (species, frac_coords), cell-independent.

    Kept separate from embedding so the six orthorhombic settings can be tried
    without re-parsing the sample CSV each time.
    """
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
        out.append((list(s.species), np.array(s.frac_coords)))
    return out


def embed(motifs, cell: Lattice):
    return [Structure(cell, sp, fc) for sp, fc in motifs]


def choose_setting(variants, motifs, measured, probe: int = 150):
    """Pick the conventional setting by pattern fit.

    Orthorhombic axis labels are not determined by the lattice, so the six
    permutations are genuinely distinct hypotheses about which axis is which.
    Feeding the wrong one into re-embedding yields structures that are
    geometrically valid and completely wrong, so the choice cannot be skipped.
    A subset of candidates is enough to separate them.
    """
    sub = motifs[:probe]
    scored = []
    for lat in variants:
        best = min((d_emd_bg(measured, simulate_pattern(s, SPEC))
                    for s in embed(sub, lat)), default=float("inf"))
        scored.append((best, lat))
    scored.sort(key=lambda t: t[0])
    return scored


def load_candidates(csv: Path, formula: str, n_atoms: int, cell: Lattice, cap: int):
    """CrystalFormer motifs, re-embedded in the indexed cell."""
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
        out.append(Structure(cell, s.species, s.frac_coords))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, choices=sorted(REGISTRY))
    ap.add_argument("--cell-error", type=float, default=0.001,
                    help="relative error of the mocked indexed cell (default 0.1%%)")
    ap.add_argument("--counts", type=float, default=None,
                    help="peak counts for a noisy measurement; omit for noise-free")
    ap.add_argument("--bg", type=float, default=0.10)
    ap.add_argument("--n-candidates", type=int, default=2000)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-relax", action="store_true",
                    help="skip MLFF relaxation (stage 3b)")
    ap.add_argument("--relax-steps", type=int, default=60)
    ap.add_argument("--no-refine", action="store_true",
                    help="skip stage 5 Wyckoff-respecting DE refinement")
    ap.add_argument("--refine-window", type=float, default=0.15)
    ap.add_argument("--index", choices=("real", "mock"), default="real",
                    help="'real' indexes the pattern; 'mock' perturbs the true cell")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    build, truth_p, sg, formula, n_atoms, csv = REGISTRY[args.target]
    truth = build(truth_p)

    print(f"=== ForwardXRD solver — target {args.target} ({formula}) ===")

    # ---- the measurement -------------------------------------------------
    measured = (simulate_pattern(truth, SPEC) if args.counts is None
                else noisy_target(truth, args.counts, args.bg))
    meas_label = ("noise-free" if args.counts is None
                  else f"{args.counts:.0g} counts, {args.bg:.0%} bg")
    print(f"measurement: {meas_label}")

    # ---- stage 1: indexing ------------------------------------------------
    index_info = None
    if args.index == "real":
        print(f"\n[1] index (REAL)     from peak positions, SG {sg} "
              f"(assumed from absences)")
        cell, index_info = index_pattern(measured, sg, verbose=True)
        if cell is None:
            print(f"    indexing FAILED: {index_info}")
            return 1
    else:
        cell = mock_index(truth, args.cell_error, rng, sg)
        print(f"\n[1] index (MOCKED)   cell a={cell.a:.4f} b={cell.b:.4f} "
              f"c={cell.c:.4f}")
        print(f"                     space group {sg} (assumed from absences)")
    t = truth.lattice
    err = [abs(getattr(cell, k) / getattr(t, k) - 1) for k in ("a", "b", "c")]
    err_sorted = [abs(f / x - 1) for f, x in
                  zip(sorted([cell.a, cell.b, cell.c]), sorted([t.a, t.b, t.c]))]

    # ---- stage 2/3: prior, re-embedded -----------------------------------
    if not csv.exists():
        print(f"\n[2] FAILED — no CrystalFormer samples at {csv}")
        return 1
    motifs = load_motifs(csv, formula, n_atoms, args.n_candidates)
    print(f"\n[2] prior            {len(motifs)} candidates "
          f"(composition + SG conditioned)")
    if not motifs:
        print("    no usable candidates")
        return 1

    # ---- stage 1b: which conventional setting? ---------------------------
    variants = setting_variants(cell, system_of(sg))
    chosen_rank = 0
    if len(variants) > 1:
        scored = choose_setting(variants, motifs, measured)
        cell = scored[0][1]
        chosen_rank = next(i for i, v in enumerate(variants)
                           if abs(v.a - cell.a) < 1e-9 and abs(v.b - cell.b) < 1e-9)
        print(f"[1b] setting         {len(variants)} permutations scored; "
              f"chose a={cell.a:.4f} b={cell.b:.4f} c={cell.c:.4f} "
              f"(fit {scored[0][0]:.4f} vs next {scored[1][0]:.4f})")
        err = [abs(getattr(cell, k) / getattr(t, k) - 1) for k in ("a", "b", "c")]
    else:
        print(f"[1b] setting         unambiguous for {system_of(sg)}")
    print(f"    cell error       Δa={err[0]:.3%} Δb={err[1]:.3%} Δc={err[2]:.3%}")

    cands = embed(motifs, cell)
    print(f"[3] re-embed         all candidates placed in the indexed cell")

    # ---- stage 3b: MLFF relaxation, cell held fixed ----------------------
    relaxed_ok = None
    if not args.no_relax:
        cands, relaxed_ok = mlff_relax(cands, args.relax_steps)
        print(f"[3b] MLFF relax      {len(cands)} candidates, coordinates only, "
              f"cell fixed  ({'ok' if relaxed_ok else 'FAILED — using unrelaxed'})")
    else:
        print("[3b] MLFF relax      skipped (--no-relax)")
    if not cands:
        print("    no usable candidates")
        return 1

    # ---- stage 4: rank ----------------------------------------------------
    scores = np.array([d_emd_bg(measured, simulate_pattern(c, SPEC)) for c in cands])
    order = np.argsort(scores)
    print(f"[4] rank             EMD + Chebyshev background (order 6)")

    # ---- stage 5: verify --------------------------------------------------
    print(f"\n[5] top {args.top_k} candidates")
    print(f"    {'rank':>4} {'score':>9} {'spacegroup':>12} {'correct?':>9}")
    top = []
    for r, idx in enumerate(order[:args.top_k], start=1):
        c = cands[idx]
        try:
            sgi = c.get_space_group_info(symprec=0.1)[1]
        except Exception:
            sgi = -1
        ok = bool(SM_STRICT.fit(c, truth))
        top.append({"rank": r, "score": float(scores[idx]),
                    "spacegroup": int(sgi), "correct": ok})
        print(f"    {r:>4} {scores[idx]:>9.4f} {sgi:>12} {str(ok):>9}")

    best = cands[order[0]]

    # ---- stage 5: Wyckoff-respecting DE refinement -----------------------
    # m7: this is what rescues quartz (rms 0.1818 -> 0.0001) and improves
    # baddeleyite 8x. The m5 ablation rejected DE because quartz's rebuild
    # silently failed (Si sits on the special 3a site) and because baddeleyite
    # was refined against a MOCKED 0.3% cell, where the reward's optimum is
    # displaced from the truth. With an indexed cell (~0.01%) it converges.
    refine_status = "skipped"
    if not args.no_refine:
        def _score(st):
            return d_emd_bg(measured, simulate_pattern(st, SPEC))

        before = _score(best)
        best, refine_status = wyckoff_de_refine(
            best, measured, _score, window=args.refine_window)
        print(f"[5] refine           Wyckoff DE ({refine_status}); "
              f"reward {before:.4f} -> {_score(best):.4f}")

    solved = bool(SM_STRICT.fit(best, truth))
    try:
        d = SM_GRADED.get_rms_dist(best, truth)
        rms = None if d is None else float(d[0])
    except Exception:
        rms = None
    n_correct = sum(bool(SM_STRICT.fit(cands[i], truth)) for i in order[:args.top_k])

    print(f"\n=== RESULT ===")
    print(f"  top-1 correct : {solved}"
          + (f"   (rms {rms:.4f})" if rms is not None else ""))
    print(f"  correct in top-{args.top_k}: {n_correct}/{args.top_k}")
    if args.index == "real":
        print(f"  indexing      : REAL — cell from peak positions only, "
              f"max Δ {max(err):.3%}")
    else:
        print(f"  NOTE: stage 1 MOCKED — cell taken from ground truth")

    out = Path(args.out or f"tracks/other/results/m4-solve-{args.target}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "run.json").write_text(json.dumps({
        "run": f"m4-solve-{args.target}",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target": args.target, "formula": formula, "spacegroup": sg,
        "measurement": meas_label,
        "stage1_mocked": True,
        "indexing": args.index,
        "index_info": index_info,
        "n_setting_variants": len(variants),
        "chosen_setting_rank": chosen_rank,
        "cell_error_actual_max": max(err),
        "cell_error_sorted_max": max(err_sorted),
        "n_candidates": len(cands),
        "mlff_relaxed": (not args.no_relax) and bool(relaxed_ok),
        "de_refinement": (not args.no_refine),
        "refine_status": refine_status,
        "top": top, "top1_correct": solved, "top1_rms": rms,
        "n_correct_in_topk": n_correct,
    }, indent=2, default=str) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0 if solved else 2


if __name__ == "__main__":
    raise SystemExit(main())
