#!/usr/bin/env python3
"""Merge per-point checkpoints into single CSV and NPZ files.

Usage:
    /opt/anaconda3/bin/python scripts/merge_results.py --checkpoints-dir results/rmh_gap_landscape/L10/checkpoints
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))

from src.gaps import GapPointResult
from src.io_utils import load_checkpoint, write_csv, write_grid_npz, write_metadata

RESULTS_ROOT = _PROJECT.parent.parent / "results" / "rmh_gap_landscape"


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge gap landscape checkpoints")
    parser.add_argument("--config", default=str(_PROJECT / "configs" / "production_L10.yaml"))
    parser.add_argument("--checkpoints-dir", required=True, help="Directory with per-point NPZ files")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: adjacent to checkpoints)")
    args = parser.parse_args()

    cfg = yaml.safe_load(open(args.config))
    L = cfg["L"]
    U = cfg["U"]
    delta_grid = np.linspace(cfg["delta_min"], cfg["delta_max"], cfg["n_delta"])
    Delta_grid = np.linspace(cfg["Delta_min"], cfg["Delta_max"], cfg["n_Delta"])

    cp_dir = Path(args.checkpoints_dir)
    out_dir = Path(args.output_dir) if args.output_dir else cp_dir.parent

    print(f"Scanning checkpoints in {cp_dir}/ …")
    n_total = len(delta_grid) * len(Delta_grid)

    results: list[GapPointResult] = []
    missing: list[tuple[float, float]] = []

    from src.io_utils import checkpoint_path

    for i, delta in enumerate(delta_grid):
        for j, Dv in enumerate(Delta_grid):
            cp = checkpoint_path(cp_dir, float(delta), float(Dv), L)
            r = load_checkpoint(cp)
            if r is not None:
                results.append(r)
            else:
                missing.append((float(delta), float(Dv)))

    n_found = len(results)
    print(f"Found: {n_found}/{n_total}  Missing: {len(missing)}")
    if missing:
        print(f"Example missing points: {missing[:5]}")

    if n_found == 0:
        print("No checkpoints found. Aborting.")
        return

    # write merged output
    valid = [r for r in results if not np.isnan(r.Delta_MB)]
    print(f"Valid points: {len(valid)}/{n_found}")

    suffix = cfg.get("output_dir", "merged").replace("/", "_")
    write_csv(results, out_dir / f"gaps_L{L}_merged.csv")
    write_grid_npz(results, delta_grid, Delta_grid, out_dir / f"gaps_L{L}_merged.npz")
    write_metadata(out_dir, cfg)
    print(f"Merged files saved to {out_dir}/")


if __name__ == "__main__":
    main()
