#!/usr/bin/env python3
"""
Route B2 one-command helper for the Kharkov public high-T Δ=1 dataset.

On your machine (macOS Apple Silicon), run:

    python scripts/b2_run_kharkov_delta1.py

What it does:
  1) Download `data/highT_delta1.npy` (if missing)
  2) Convert to `data/kharkov_highT_delta1.npz` (if missing)
  3) Run full Burgers fit & drift analysis into `results_kharkov_B2/`

This script intentionally avoids any non-stdlib download dependency.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parent.parent

def run(cmd: list[str]):
    print("\n[B2] $", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(REPO))

def main():
    npy = REPO/"data"/"highT_delta1.npy"
    npz = REPO/"data"/"kharkov_highT_delta1.npz"
    outdir = REPO/"results_kharkov_B2"

    # 1) download
    if not npy.exists():
        run(["bash", "scripts/b2_download_kharkov_highT_delta1.sh"])
    else:
        print("[B2] Found", npy)

    # 2) convert
    if not npz.exists():
        run([
            sys.executable, "scripts/b2_convert_kharkov_npy_to_npz.py",
            "--npy", str(npy),
            "--out", str(npz),
            "--center-x",
            "--drop-first", "250",
            "--savgol-x", "31", "7",
        ])
    else:
        print("[B2] Found", npz)

    # 3) full analysis
    run([
        sys.executable, "scripts/run_full_on_npz.py",
        "--input", str(npz),
        "--outdir", str(outdir),
        "--x-crop", "-120", "120",
        "--t-ref", "50",
        "--t-min-inst", "80",
        "--deriv-x", "finite",
        "--window", "40",
        "--step", "10",
        "--t0-pred", "50",
    ])

    print("\n[B2] All done.")
    print("     Summary:", outdir/"summary.json")
    print("     Plots:  ", outdir/"plots")
    print("     Tables: ", outdir/"tables")

if __name__ == "__main__":
    main()
