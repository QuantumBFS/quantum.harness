#!/usr/bin/env python3
"""
Route B2: convert Kharkov public .npy dataset to this repo's external .npz format (x,t,u,meta).

Input:
  - data/highT_delta1.npy (downloaded from GitHub; binary numpy .npy storing a Python dict)

Output:
  - data/kharkov_highT_delta1.npz with arrays:
        x: (Nx,)
        t: (Nt,)
        u: (Nt,Nx)
        meta: dict (stored via numpy allow_pickle)

Why:
  Our Burgers fitting scripts expect a single .npz with explicit x,t,u arrays.

Usage:
  python scripts/b2_convert_kharkov_npy_to_npz.py \
      --npy data/highT_delta1.npy \
      --out data/kharkov_highT_delta1.npz \
      --center-x \
      --drop-first 250 \
      --savgol-x 31 7

Notes:
  - The upstream notebook `domain_wall_T=infty.ipynb` in that repo sets:
        data_dict = load_dict('./data/highT_delta=1.npy')
        t = data_dict['t'][start:]
        u = data_dict['u'][start:]
        x = np.arange(u.shape[1])
    i.e. the Δ=1 file may not contain 'x'. We reproduce that logic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np

try:
    from scipy.signal import savgol_filter
except Exception:
    savgol_filter = None

def load_dict_npy(path: str) -> dict:
    obj = np.load(path, allow_pickle=True)
    if hasattr(obj, "shape") and obj.shape == ():
        return obj.item()
    if isinstance(obj, dict):
        return obj
    raise TypeError(f"Unexpected .npy content type: {type(obj)}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npy", required=True, help="Input highT_delta1.npy (downloaded)")
    ap.add_argument("--out", required=True, help="Output .npz path")
    ap.add_argument("--drop-first", type=int, default=0, help="Drop first N time-slices (remove transient)")
    ap.add_argument("--center-x", action="store_true", help="Shift x so that x=0 at the domain-wall center")
    ap.add_argument("--savgol-x", nargs=2, type=int, metavar=("WINDOW", "POLY"),
                    help="Apply Savitzky-Golay smoothing along x to u(t,x). Requires scipy.")
    ap.add_argument("--flip-sign", action="store_true", help="Multiply u by -1 (if your convention differs)")
    args = ap.parse_args()

    d = load_dict_npy(args.npy)
    if "u" not in d or "t" not in d:
        raise KeyError(f"Expected keys 'u' and 't'. Found keys={list(d.keys())}")

    u = np.asarray(d["u"], float)
    t = np.asarray(d["t"], float)
    if u.ndim != 2:
        raise ValueError(f"Expected u to be 2D (Nt,Nx), got shape {u.shape}")

    # optional drop
    if args.drop_first > 0:
        if args.drop_first >= u.shape[0]:
            raise ValueError("--drop-first too large")
        u = u[args.drop_first:, :]
        t = t[args.drop_first:]

    # x: use provided x if exists, else site index
    if "x" in d and isinstance(d["x"], np.ndarray) and d["x"].ndim == 1 and d["x"].shape[0] == u.shape[1]:
        x = np.asarray(d["x"], float)
    else:
        x = np.arange(u.shape[1], dtype=float)

    if args.center_x:
        x = x - 0.5*(x[0] + x[-1])  # center at mid-point

    if args.flip_sign:
        u = -u

    # optional smoothing along x
    if args.savgol_x is not None:
        if savgol_filter is None:
            raise RuntimeError("scipy not available, cannot use --savgol-x")
        win, poly = args.savgol_x
        if win % 2 == 0:
            win += 1
        if win >= u.shape[1]:
            win = u.shape[1] - (1 - u.shape[1] % 2)  # largest odd < Nx
        u = savgol_filter(u, window_length=win, polyorder=min(poly, win-1), axis=1, mode="interp")

    meta = {
        "source": "yourball/pde-many-body domain_wall_xxz/data/highT_delta=1.npy",
        "kind": "kharkov_highT_delta1",
        "drop_first": int(args.drop_first),
        "center_x": bool(args.center_x),
        "savgol_x": args.savgol_x,
        "flip_sign": bool(args.flip_sign),
        "original_keys": list(d.keys()),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, x=x, t=t, u=u, meta=np.array(meta, dtype=object))

    print("[B2] wrote", out)
    print("     x:", x.shape, "t:", t.shape, "u:", u.shape)
    print("     meta:", json.dumps(meta, indent=2))

if __name__ == "__main__":
    main()
