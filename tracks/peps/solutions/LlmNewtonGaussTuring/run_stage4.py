#!/usr/bin/env python3
"""
PEPS-FHS Berry curvature sweep for 2D square-lattice TFIM (Challenge 73 Stage 4).

Produces CSV output compatible with C++ scan_berry_square format:
    theta,Omega,F12,F12_per_N,absU1,absU2

Usage:
    python3 run_stage4.py <L> <theta_min> <theta_max> <dtheta> <Omega_min> <Omega_max> <dOmega> <J> [--D D] [--method ed|mps]

For PEPS (MPS) route, --D controls bond dimension. Default --method=ed.
"""
import sys
import numpy as np
from peps_fhs import *


def main():
    args = sys.argv[1:]

    # Parse positional arguments
    if len(args) < 8:
        print("Usage: run_stage4.py <L> <theta_min> <theta_max> <dtheta> "
              "<Omega_min> <Omega_max> <dOmega> <J> [--D D] [--method ed|mps]")
        sys.exit(1)

    L = int(args[0])
    theta_min = float(args[1])
    theta_max = float(args[2])
    dtheta = float(args[3])
    Omega_min = float(args[4])
    Omega_max = float(args[5])
    dOmega = float(args[6])
    J = float(args[7])

    D = 4
    method = "ed"

    i = 8
    while i < len(args):
        if args[i] == "--D" and i + 1 < len(args):
            D = int(args[i + 1])
            i += 2
        elif args[i] == "--method" and i + 1 < len(args):
            method = args[i + 1]
            i += 2
        else:
            i += 1

    Lx, Ly = L, L
    N = Lx * Ly

    theta_values = []
    t = theta_min
    while t <= theta_max + 0.5 * dtheta:
        theta_values.append(t)
        t += dtheta
        if len(theta_values) > 1000:
            raise ValueError("theta grid too large")

    omega_values = []
    o = Omega_min
    while o <= Omega_max + 0.5 * dOmega:
        omega_values.append(o)
        o += dOmega
        if len(omega_values) > 1000:
            raise ValueError("omega grid too large")

    print(f"# L={L} (N={N}), J={J}, D={D}, method={method}", file=sys.stderr)
    print(f"# theta: {theta_min}..{theta_max} step {dtheta} ({len(theta_values)} pts)",
          file=sys.stderr)
    print(f"# Omega: {Omega_min}..{Omega_max} step {dOmega} ({len(omega_values)} pts)",
          file=sys.stderr)

    if method == "ed":
        grid, energies = sweep_f12_ed(Lx, Ly, J, theta_values, omega_values)
    elif method == "mps":
        grid = sweep_f12_mps(Lx, Ly, J, theta_values, omega_values, D)
    else:
        raise ValueError(f"Unknown method: {method}")

    # Output CSV
    print("theta,Omega,F12,F12_per_N,absU1,absU2")
    for ti in range(len(theta_values) - 1):
        for oi in range(len(omega_values) - 1):
            theta_c = 0.5 * (theta_values[ti] + theta_values[ti + 1])
            Omega_c = 0.5 * (omega_values[oi] + omega_values[oi + 1])
            r = grid[ti][oi]
            print(f"{theta_c:.12e},{Omega_c:.12e},"
                  f"{r.get('F12', np.nan):.12e},"
                  f"{r.get('F12', np.nan)/(Lx*Ly):.12e},"
                  f"{r.get('absU1', np.nan):.12e},"
                  f"{r.get('absU2', np.nan):.12e}")

    # Summary stats
    valid = [r for row in grid for r in row if r.get('valid', False)]
    if valid:
        f12_vals = [r['F12'] / (Lx * Ly) for r in valid]
        print(f"# F12/N range: [{min(f12_vals):.8f}, {max(f12_vals):.8f}]",
              file=sys.stderr)
        print(f"# N valid plaquettes: {len(valid)}", file=sys.stderr)
    print(f"# Done.", file=sys.stderr)


if __name__ == '__main__':
    main()
