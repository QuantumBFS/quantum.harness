#!/usr/bin/env python3
"""Finite-size scaling analysis for Challenge 73 Berry curvature data.

Reads berry_square_L{2,3,4}.csv files, computes per-site curvature
density F12/N, and extracts finite-size scaling trends near the critical
region Omega_c / J ≈ 3.044.
"""

import sys
import csv
import math
from pathlib import Path

def load_csv(filepath):
    rows = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("#", "Square", "theta:", "Omega:", "J=")):
                continue
            parts = line.split(",")
            if len(parts) < 4:
                continue
            try:
                theta = float(parts[0])
                omega = float(parts[1])
                f12 = float(parts[2])
                f12_per_n = float(parts[3])
                abs_u1 = float(parts[4])
                rows.append({
                    "theta": theta, "Omega": omega,
                    "F12": f12, "F12_per_N": f12_per_n,
                    "absU1": abs_u1,
                })
            except (ValueError, IndexError):
                continue
    return rows


def extract_omega_slice(rows, target_theta, omega_tol=0.01):
    """Extract data at fixed theta (closest match)."""
    best_theta = None
    best_dist = float("inf")
    for r in rows:
        d = abs(r["theta"] - target_theta)
        if d < best_dist:
            best_dist = d
            best_theta = r["theta"]
    return [r for r in rows if abs(r["theta"] - best_theta) < 1e-10]


def main():
    results_dir = Path("../results")
    if not results_dir.exists():
        results_dir = Path("results")

    sizes = {2: None, 3: None, 4: None}
    for L in sizes:
        fpath = results_dir / f"berry_square_L{L}.csv"
        if fpath.exists():
            sizes[L] = load_csv(fpath)
            print(f"L={L}: {len(sizes[L])} data points")

    available = [L for L, d in sizes.items() if d is not None]
    if len(available) < 2:
        print(f"Need at least 2 lattice sizes, got {len(available)}: {available}")
        sys.exit(1)

    # --- Per-site curvature density at fixed theta=0.1, as function of Omega ---
    theta_ref = 0.1
    print(f"\n{'='*70}")
    print(f"F12/N vs Omega at theta={theta_ref}")
    print(f"{'Omega':>8}  " + "  ".join(f"L={L:>2}    " for L in available))
    print("-" * 70)

    for Omega in [v * 0.5 for v in range(1, 11)]:
        parts = [f"{Omega:8.2f}"]
        for L in available:
            data = sizes[L]
            if data is None:
                parts.append("  N/A    ")
                continue
            slice_data = extract_omega_slice(data, theta_ref)
            best = min(slice_data, key=lambda x: abs(x["Omega"] - Omega))
            parts.append(f"{best['F12_per_N']:10.6f}")
        print("  ".join(parts))

    # --- Critical region zoom ---
    J = 1.0
    Omega_c = 3.044  # 2D TFIM critical field
    print(f"\n{'='*70}")
    print(f"Critical region near Omega_c = {Omega_c}")
    print(f"{'Omega':>8}  " + "  ".join(f"L={L:>2}    " for L in available))
    print("-" * 70)

    for delta in [-0.5, -0.3, -0.1, 0.0, 0.1, 0.3, 0.5]:
        Omega = Omega_c + delta
        parts = [f"{Omega:8.2f}"]
        for L in available:
            data = sizes[L]
            if data is None:
                parts.append("  N/A    ")
                continue
            slice_data = extract_omega_slice(data, theta_ref)
            best = min(slice_data, key=lambda x: abs(x["Omega"] - Omega))
            parts.append(f"{best['F12_per_N']:10.6f}")
        print("  ".join(parts))

    # --- Finite-size difference ---
    print(f"\n{'='*70}")
    print(f"Finite-size convergence: F12/N differences")
    print(f"{'Omega':>8}  " + "  ".join(f"L={available[i]}-{available[i+1]}" for i in range(len(available)-1)))
    print("-" * 70)

    for Omega in [v * 0.5 for v in range(1, 11)]:
        parts = [f"{Omega:8.2f}"]
        for i in range(len(available)-1):
            L1, L2 = available[i], available[i+1]
            d1 = sizes[L1]
            d2 = sizes[L2]
            s1 = extract_omega_slice(d1, theta_ref)
            s2 = extract_omega_slice(d2, theta_ref)
            b1 = min(s1, key=lambda x: abs(x["Omega"] - Omega))
            b2 = min(s2, key=lambda x: abs(x["Omega"] - Omega))
            diff = abs(b1["F12_per_N"] - b2["F12_per_N"])
            parts.append(f"{diff:10.2e}")
        print("  ".join(parts))

    # --- Data quality check: minimum overlap per size ---
    print(f"\n{'='*70}")
    print("Data quality: minimum absU1 overlap")
    for L in available:
        data = sizes[L]
        min_u1 = min(r["absU1"] for r in data)
        print(f"  L={L}: min_absU1 = {min_u1:.6f}")

    print("\nAnalysis complete.")


if __name__ == "__main__":
    main()
