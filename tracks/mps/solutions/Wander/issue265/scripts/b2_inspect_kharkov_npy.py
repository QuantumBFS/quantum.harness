#!/usr/bin/env python3
"""
Route B2 utility: inspect Kharkov public dataset (.npy) from https://github.com/yourball/pde-many-body

The file `highT_delta=1.npy` is stored as a Python dict serialized with `np.save`.
We load with `allow_pickle=True` and print keys/shapes, plus basic sanity diagnostics.

Usage:
    python scripts/b2_inspect_kharkov_npy.py --npy data/highT_delta1.npy

Outputs:
    - prints a concise report to stdout
"""
from __future__ import annotations

import argparse
import numpy as np

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npy", required=True, help="Path to downloaded highT_delta1.npy (stored dict via np.save)")
    ap.add_argument("--show-head", type=int, default=5, help="Show first N elements of 1D arrays")
    args = ap.parse_args()

    obj = np.load(args.npy, allow_pickle=True)
    # Typically it's a 0-d array containing a dict
    if isinstance(obj, np.lib.npyio.NpzFile):
        raise TypeError("Got .npz; expected .npy")
    if hasattr(obj, "shape") and obj.shape == ():
        d = obj.item()
    elif isinstance(obj, dict):
        d = obj
    else:
        # fall back: maybe it's saved as array directly
        d = {"__array__": obj}

    print("=== Kharkov B2 dataset inspection ===")
    print("file:", args.npy)
    print("keys:", list(d.keys()))

    for k,v in d.items():
        if isinstance(v, np.ndarray):
            print(f"- {k}: ndarray shape={v.shape} dtype={v.dtype}")
            if v.ndim == 1:
                head = v[:args.show_head]
                tail = v[-args.show_head:]
                print(f"    head={head}")
                print(f"    tail={tail}")
        else:
            print(f"- {k}: type={type(v)} value={v}")

    # Heuristics for typical keys
    u = d.get("u", None)
    t = d.get("t", None)
    x = d.get("x", None)

    if u is not None and isinstance(u, np.ndarray) and u.ndim == 2:
        Nt, Nx = u.shape
        print(f"\n[Sanity] u(t,x) looks 2D: Nt={Nt}, Nx={Nx}")
        # plateau check: left/right 10% sites
        nedge = max(1, Nx//10)
        uL = u[:, :nedge].mean(axis=1)
        uR = u[:, -nedge:].mean(axis=1)
        print(f"[Sanity] left plateau mean over time:  mean={uL.mean():.6g} std={uL.std():.6g}")
        print(f"[Sanity] right plateau mean over time: mean={uR.mean():.6g} std={uR.std():.6g}")
        print(f"[Sanity] domain-wall amplitude (median): {np.median(uL-uR):.6g}")

    if t is not None and isinstance(t, np.ndarray) and t.ndim == 1:
        dt = np.median(np.diff(t))
        print(f"\n[Sanity] t grid: t[0]={t[0]:.6g}, t[-1]={t[-1]:.6g}, Nt={t.size}, median dt={dt:.6g}")

    if x is not None and isinstance(x, np.ndarray) and x.ndim == 1:
        dx = np.median(np.diff(x))
        print(f"\n[Sanity] x grid: x[0]={x[0]:.6g}, x[-1]={x[-1]:.6g}, Nx={x.size}, median dx={dx:.6g}")

    print("\nDone.")

if __name__ == "__main__":
    main()
