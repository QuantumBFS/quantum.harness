#!/usr/bin/env python3
"""Phase A: L=6 dense ED benchmark with sparse cross-validation.

Usage:
    /opt/anaconda3/bin/python scripts/smoke_L6.py
    /opt/anaconda3/bin/python scripts/smoke_L6.py --validate
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import yaml

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))

from src.gaps import GapPointResult, solve_point
from src.io_utils import (
    checkpoint_path,
    save_checkpoint,
    write_csv,
    write_grid_npz,
    write_metadata,
)

RESULTS_ROOT = _PROJECT.parent.parent / "results" / "rmh_gap_landscape"


def load_config(path: str) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def build_grid(cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    delta = np.linspace(cfg["delta_min"], cfg["delta_max"], cfg["n_delta"])
    Delta = np.linspace(cfg["Delta_min"], cfg["Delta_max"], cfg["n_Delta"])
    return delta, Delta


def main() -> None:
    parser = argparse.ArgumentParser(description="L=6 gap landscape smoke test")
    parser.add_argument("--config", default=str(_PROJECT / "configs" / "smoke_L6.yaml"))
    parser.add_argument("--validate", action="store_true",
                        help="Cross-validate ~10% of points with sparse solver")
    args = parser.parse_args()

    cfg = load_config(args.config)
    L = cfg["L"]
    U = cfg["U"]
    delta_grid, Delta_grid = build_grid(cfg)
    n_total = len(delta_grid) * len(Delta_grid)
    out_dir = RESULTS_ROOT / "L6_smoke"

    print("=" * 64)
    print(f"PHASE A: L={L}  U={U}  δ ∈ [{delta_grid[0]:.2f}, {delta_grid[-1]:.2f}]")
    print(f"         Δ ∈ [{Delta_grid[0]:.2f}, {Delta_grid[-1]:.2f}]")
    print(f"         {len(delta_grid)}×{len(Delta_grid)} = {n_total} points")
    print(f"         method=dense  validate={'ON' if args.validate else 'off'}")
    print("=" * 64)

    results: list[GapPointResult] = []
    t_total = time.perf_counter()

    for i, delta in enumerate(delta_grid):
        for j, Dv in enumerate(Delta_grid):
            idx = i * len(Delta_grid) + j
            print(f"  [{idx+1}/{n_total}] δ={delta:+.4f}  Δ={Dv:+.4f} … ",
                  end="", flush=True)
            try:
                r = solve_point(L=L, delta=delta, Delta=Dv, U=U, method="dense")
                results.append(r)
                print(
                    f"Δ_MB={r.Delta_MB:.4f}  Δ_s={r.Delta_s:.4f}  "
                    f"Δ_c={r.Delta_c:.4f}  res={max(r.residuals.values()):.1e}  "
                    f"{r.wall_time_s:.2f}s"
                )
                cp_path = checkpoint_path(out_dir / "checkpoints", delta, Dv, L)
                save_checkpoint(r, cp_path)
            except Exception as exc:
                print(f"FAILED: {exc}")
                continue

    elapsed = time.perf_counter() - t_total

    # summary
    mb = [r.Delta_MB for r in results]
    ss = [r.Delta_s for r in results]
    cc = [r.Delta_c for r in results]
    print(f"\nSummary ({len(results)}/{n_total} points, {elapsed:.1f}s):")
    print(f"  Δ_MB: min={min(mb):.4f}  max={max(mb):.4f}  mean={np.mean(mb):.4f}")
    print(f"  Δ_s:  min={min(ss):.4f}  max={max(ss):.4f}  mean={np.mean(ss):.4f}")
    print(f"  Δ_c:  min={min(cc):.4f}  max={max(cc):.4f}  mean={np.mean(cc):.4f}")

    # merged output
    write_csv(results, out_dir / "gaps_L6_smoke.csv")
    write_grid_npz(results, delta_grid, Delta_grid, out_dir / "gaps_L6_smoke.npz")
    write_metadata(out_dir, cfg)
    print(f"\nSaved: {out_dir}/")

    # ---- sparse cross-validation ----
    if args.validate:
        n_val = max(5, n_total // 10)
        rng = np.random.default_rng(42)
        val_indices = rng.choice(n_total, size=n_val, replace=False)
        print(f"\n{'=' * 64}")
        print(f"SPARSE CROSS-VALIDATION ({n_val} random points)")
        print(f"{'=' * 64}")
        max_e_diff = 0.0
        for vi in val_indices:
            i_d = vi // len(Delta_grid)
            i_D = vi % len(Delta_grid)
            delta = float(delta_grid[i_d])
            Dv = float(Delta_grid[i_D])
            print(f"  δ={delta:+.4f}  Δ={Dv:+.4f} … ", end="", flush=True)
            try:
                r_sp = solve_point(L=L, delta=delta, Delta=Dv, U=U, method="sparse")
                r_dense = results[vi]
                de_half = abs(r_sp.E0_half - r_dense.E0_half)
                de_trip = abs(r_sp.E0_triplet - r_dense.E0_triplet)
                de_up = abs(r_sp.E0_charge_up - r_dense.E0_charge_up)
                de_down = abs(r_sp.E0_charge_down - r_dense.E0_charge_down)
                de_max = max(de_half, de_trip, de_up, de_down)
                ok = de_max < 1e-8
                print(f"max|ΔE|={de_max:.2e}  {'PASS' if ok else 'FAIL'}")
                max_e_diff = max(max_e_diff, de_max)
            except Exception as exc:
                print(f"FAILED: {exc}")
        print(f"\nSparse cross-validation complete: max|ΔE| = {max_e_diff:.2e}")

    print("Done.")


if __name__ == "__main__":
    main()
