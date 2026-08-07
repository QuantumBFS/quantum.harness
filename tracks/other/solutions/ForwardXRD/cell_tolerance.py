#!/usr/bin/env python
"""How accurate must the indexed cell be for coordinate refinement to survive?

Milestone 2f. m2e showed that given the EXACT cell and space group, a black-box
optimiser recovers the motif (tenorite ~620 evals, baddeleyite 3/3 at ~6800).
Real indexing does not return the exact cell; it returns one with error bars.
Since milestone 1 measured the reward losing 49% of its value at 0.5% lattice
strain, the tolerance could be tight enough to make the indexing-first
architecture impractical -- or comfortable enough to make it routine.

This is the number that decides it, and it also sets the error bars worth
supporting when injecting an indexed cell into CrystalFormer's lattice head.

Setup: the target pattern is simulated from the TRUE structure. The candidate
cell is perturbed by delta. Differential evolution then searches only the free
Wyckoff coordinates inside that wrong cell. We ask whether the resulting motif
still matches the truth.

Two perturbation models:
  isotropic   all lengths scaled by (1 + delta) -- coherent peak shift, the
              signature of a wavelength or zero-point error
  anisotropic each length scaled independently by (1 + N(0, delta)) -- closer
              to real least-squares indexing error, distorts relative peak
              positions

Note StructureMatcher's default ltol = 0.2 tolerates lattice differences well
beyond the deltas tested, so `fit` here is genuinely a test of the MOTIF, not
of the cell.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pymatgen.core import Lattice, Structure
from scipy.optimize import differential_evolution

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from emd_metric import SPEC  # noqa: E402
from emd_nnls import d_emd_bg  # noqa: E402
from targets import SM_GRADED, SM_STRICT  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402


# builders take (params, length scale factors) --------------------------------
def _rutile(p, f):
    return Structure.from_spacegroup(
        "P4_2/mnm", Lattice.tetragonal(4.5937 * f[0], 2.9587 * f[2]),
        ["Ti", "O"], [[0, 0, 0], [p[0], p[0], 0]])


def _tenorite(p, f):
    return Structure.from_spacegroup(
        "C2/c", Lattice.monoclinic(4.6837 * f[0], 3.4226 * f[1], 5.1288 * f[2], 99.54),
        ["Cu", "O"], [[0.25, 0.25, 0], [0, p[0], 0.25]])


def _quartz(p, f):
    return Structure.from_spacegroup(
        "P3_121", Lattice.hexagonal(4.9137 * f[0], 5.4047 * f[2]),
        ["Si", "O"], [[p[0], 0, 1 / 3], [p[1], p[2], p[3]]])


def _baddeleyite(p, f):
    return Structure.from_spacegroup(
        "P2_1/c",
        Lattice.monoclinic(5.1505 * f[0], 5.2116 * f[1], 5.3173 * f[2], 99.23),
        ["Zr", "O", "O"],
        [[p[0], p[1], p[2]], [p[3], p[4], p[5]], [p[6], p[7], p[8]]])


CASES = [
    ("rutile TiO2", 1, _rutile, np.array([0.3053])),
    ("tenorite CuO", 1, _tenorite, np.array([0.4184])),
    ("quartz SiO2", 4, _quartz, np.array([0.4697, 0.4135, 0.2669, 0.1191])),
    ("baddeleyite ZrO2", 9, _baddeleyite,
     np.array([0.2758, 0.0411, 0.2082, 0.0703, 0.3359, 0.3406, 0.4423, 0.7549, 0.4789])),
]

DELTAS = [0.0, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05]
ONE = np.ones(3)


def refine(build, target, factors, n_par, seeds):
    """DE over the free coordinates inside a (possibly wrong) cell."""
    def obj(p):
        return d_emd_bg(target, simulate_pattern(build(np.asarray(p), factors), SPEC))

    out = []
    for seed in range(seeds):
        res = differential_evolution(
            obj, [(0.0, 1.0)] * n_par, seed=seed, maxiter=40, popsize=12,
            tol=1e-8, polish=True, init="sobol")
        out.append((build(res.x, factors), float(res.fun), int(res.nfev)))
    return out


def score(sols, truth):
    fits, rms = [], []
    for s, _, _ in sols:
        try:
            fits.append(bool(SM_STRICT.fit(s, truth)))
        except Exception:
            fits.append(False)
        try:
            d = SM_GRADED.get_rms_dist(s, truth)
            rms.append(np.nan if d is None else float(d[0]))
        except Exception:
            rms.append(np.nan)
    return fits, rms


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--aniso-seeds", type=int, default=2)
    args = ap.parse_args()

    out = Path("tracks/other/results/m2f-cell-tolerance")
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    rows = []

    for name, n_par, build, truth_p in CASES:
        truth = build(truth_p, ONE)
        target = simulate_pattern(truth, SPEC)
        print(f"\n{'=' * 74}\n{name}  ({n_par} free coordinate"
              f"{'s' if n_par > 1 else ''})")
        print(f"  {'delta':>7} {'mode':<12} {'recovered':>10} {'rms':>18} {'reward':>9}")

        for delta in DELTAS:
            # ---- isotropic ------------------------------------------------
            f = ONE * (1.0 + delta)
            sols = refine(build, target, f, n_par, args.seeds)
            fits, rms = score(sols, truth)
            rew = np.mean([s[1] for s in sols])
            rs = ", ".join("n/a" if np.isnan(v) else f"{v:.4f}" for v in rms)
            print(f"  {delta:>6.2%} {'isotropic':<12} {sum(fits)}/{len(fits):<8} "
                  f"{rs:>18} {rew:>9.4f}")
            rows.append({"case": name, "n_free": n_par, "delta": delta,
                         "mode": "isotropic", "recovered": sum(fits),
                         "n_seeds": len(fits), "rms": rms, "reward": rew})

            # ---- anisotropic (skip delta = 0, identical) -------------------
            if delta > 0:
                afits, arms, arew = [], [], []
                for _ in range(args.aniso_seeds):
                    fa = 1.0 + rng.normal(0.0, delta, 3)
                    s2 = refine(build, target, fa, n_par, 1)
                    ff, rr = score(s2, truth)
                    afits += ff
                    arms += rr
                    arew.append(s2[0][1])
                rs2 = ", ".join("n/a" if np.isnan(v) else f"{v:.4f}" for v in arms)
                print(f"  {delta:>6.2%} {'anisotropic':<12} {sum(afits)}/{len(afits):<8} "
                      f"{rs2:>18} {np.mean(arew):>9.4f}")
                rows.append({"case": name, "n_free": n_par, "delta": delta,
                             "mode": "anisotropic", "recovered": sum(afits),
                             "n_seeds": len(afits), "rms": arms,
                             "reward": float(np.mean(arew))})

    # ---- summary: largest delta that still recovers everywhere -------------
    print("\n" + "=" * 88)
    print("SUMMARY — largest cell error still recovering the motif (all seeds)")
    print("=" * 88)
    print(f"{'case':<20} {'free':>5} {'isotropic':>12} {'anisotropic':>13}")
    print("-" * 54)
    summary = {}
    for name, n_par, _, _ in CASES:
        lim = {}
        for mode in ("isotropic", "anisotropic"):
            ok = [r["delta"] for r in rows
                  if r["case"] == name and r["mode"] == mode
                  and r["recovered"] == r["n_seeds"]]
            lim[mode] = max(ok) if ok else None
        summary[name] = lim
        def fmt(v):
            return "none" if v is None else f"{v:.2%}"
        print(f"{name:<20} {n_par:>5} {fmt(lim['isotropic']):>12} "
              f"{fmt(lim['anisotropic']):>13}")

    payload = {
        "run": "m2f-cell-tolerance",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "question": "how accurate must an indexed cell be for coordinate refinement "
                    "to still recover the motif?",
        "reward": "EMD + non-negative Chebyshev background, order 6",
        "note": "StructureMatcher ltol=0.2 tolerates these lattice errors, so `fit` "
                "tests the motif rather than the cell",
        "deltas": DELTAS,
        "rows": rows,
        "tolerance_limits": summary,
    }
    (out / "run.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
