#!/usr/bin/env python3
"""Phase B: L=10 sparse gap scan with checkpoint/resume and array-job support.

Usage:
    # single-process (all points):
    /opt/anaconda3/bin/python scripts/scan_L10.py

    # SLURM array task:
    /opt/anaconda3/bin/python scripts/scan_L10.py --task-id $SLURM_ARRAY_TASK_ID --task-count 100
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import yaml

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))

from src.gaps import GapPointResult, solve_point
from src.io_utils import checkpoint_path, load_checkpoint, save_checkpoint, write_metadata

RESULTS_ROOT = _PROJECT.parent.parent / "results" / "rmh_gap_landscape"


def load_config(path: str) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def build_grid(cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    delta = np.linspace(cfg["delta_min"], cfg["delta_max"], cfg["n_delta"])
    Delta = np.linspace(cfg["Delta_min"], cfg["Delta_max"], cfg["n_Delta"])
    return delta, Delta


def compute_chunk(
    L: int,
    U: float,
    delta_grid: np.ndarray,
    Delta_grid: np.ndarray,
    out_dir: Path,
    start_idx: int,
    end_idx: int,
) -> list[GapPointResult]:
    """Compute a contiguous chunk of the grid."""
    n_Delta = len(Delta_grid)
    results: list[GapPointResult] = []

    for flat_idx in range(start_idx, end_idx):
        i_d = flat_idx // n_Delta
        i_D = flat_idx % n_Delta
        delta = float(delta_grid[i_d])
        Dv = float(Delta_grid[i_D])

        # checkpoint/resume
        cp_path = checkpoint_path(out_dir / "checkpoints", delta, Dv, L)
        existing = load_checkpoint(cp_path)
        if existing is not None:
            results.append(existing)
            continue

        print(f"  [{flat_idx - start_idx + 1}/{end_idx - start_idx}] "
              f"δ={delta:+.4f}  Δ={Dv:+.4f} … ", end="", flush=True)

        try:
            r = solve_point(L=L, delta=delta, Delta=Dv, U=U, method="sparse")
            results.append(r)
            print(
                f"Δ_MB={r.Delta_MB:.4f}  Δ_s={r.Delta_s:.4f}  "
                f"Δ_c={r.Delta_c:.4f}  res={max(r.residuals.values()):.1e}  "
                f"{r.wall_time_s:.1f}s"
            )
            save_checkpoint(r, cp_path)
        except Exception as exc:
            print(f"FAILED: {exc}")
            # write a NaN placeholder so the point isn't re-tried
            nan_result = GapPointResult(
                L=L, delta=delta, Delta=Dv, U=U,
                E0_half=float("nan"), E1_half=float("nan"),
                E0_triplet=float("nan"),
                E0_charge_up=float("nan"), E0_charge_down=float("nan"),
                Delta_MB=float("nan"), Delta_s=float("nan"), Delta_c=float("nan"),
                residuals={"half": -1}, converged={"half": False},
                dimensions={}, wall_time_s=-1, method="failed",
            )
            results.append(nan_result)
            save_checkpoint(nan_result, cp_path)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="L=10 gap landscape scan")
    parser.add_argument("--config", default=str(_PROJECT / "configs" / "production_L10.yaml"))
    parser.add_argument("--task-id", type=int, default=None,
                        help="SLURM array task ID (0-indexed)")
    parser.add_argument("--task-count", type=int, default=1,
                        help="Total number of array tasks")
    args = parser.parse_args()

    # Also check env var for SLURM compatibility
    task_id = args.task_id
    if task_id is None and "SLURM_ARRAY_TASK_ID" in os.environ:
        task_id = int(os.environ["SLURM_ARRAY_TASK_ID"])

    cfg = load_config(args.config)
    L = cfg["L"]
    U = cfg["U"]
    delta_grid, Delta_grid = build_grid(cfg)
    n_total = len(delta_grid) * len(Delta_grid)
    out_dir = RESULTS_ROOT / "L10"

    # split work
    chunk_size = (n_total + args.task_count - 1) // args.task_count
    start_idx = task_id * chunk_size if task_id is not None else 0
    end_idx = min(start_idx + chunk_size, n_total) if task_id is not None else n_total

    tag = f"task {task_id}/{args.task_count}" if task_id is not None else "single"
    print("=" * 64)
    print(f"PHASE B: L={L}  U={U}  {tag}")
    print(f"         δ ∈ [{delta_grid[0]:.2f}, {delta_grid[-1]:.2f}]")
    print(f"         Δ ∈ [{Delta_grid[0]:.2f}, {Delta_grid[-1]:.2f}]")
    print(f"         {len(delta_grid)}×{len(Delta_grid)} = {n_total} total points")
    print(f"         chunk: [{start_idx}, {end_idx}) = {end_idx - start_idx} points")
    print(f"         method=sparse  checkpoint/resume=ON")
    print("=" * 64)

    t_total = time.perf_counter()
    results = compute_chunk(L, U, delta_grid, Delta_grid, out_dir, start_idx, end_idx)
    elapsed = time.perf_counter() - t_total

    # chunk summary
    valid = [r for r in results if not np.isnan(r.Delta_MB)]
    n_ok = len(valid)
    n_fail = len(results) - n_ok
    if valid:
        mb = [r.Delta_MB for r in valid]
        ss = [r.Delta_s for r in valid]
        cc = [r.Delta_c for r in valid]
        print(f"\nChunk summary ({n_ok} OK, {n_fail} failed, {elapsed:.1f}s):")
        print(f"  Δ_MB: min={min(mb):.4f}  max={max(mb):.4f}")
        print(f"  Δ_s:  min={min(ss):.4f}  max={max(ss):.4f}")
        print(f"  Δ_c:  min={min(cc):.4f}  max={max(cc):.4f}")

    write_metadata(out_dir, cfg)
    print(f"\nCheckpoints: {out_dir / 'checkpoints'}/")
    print("Done.")


if __name__ == "__main__":
    main()
