#!/usr/bin/env python3
"""Phase 1: Static benchmark of spin-charge separation in the RMH model.

Creates a hole wavepacket in a half-filled Mott state and evolves under
static H(φ₀) to observe whether the charge defect (holon) and spin defect
(spinon) propagate independently at U > 0.

Protocol:
  φ₀ = 5π/3  (Mott-like region, avoids δ=0 gapless line)
  δ_fixed = R_δ cos(φ₀)
  Δ_fixed = 5 + 2.1 sin(φ₀)
  Static evolution: H(φ₀) for 0 ≤ t ≤ 10

Scans:
  U ∈ {0, 10}
  R_δ ∈ {0.2, 0.4, 0.88}
  k₀ ∈ {0, π/2}

Output per (U, R_δ, k₀):
  - h_j(t), s_j(t) heatmaps
  - X_h(t), X_s(t) center trajectories
  - Widths, sum checks

Usage:
  python scripts/run_benchmark.py --L 6 --smoke     # fast smoke test
  python scripts/run_benchmark.py --L 10             # full production run
  python scripts/run_benchmark.py --L 10 --U 10 --R 0.88 --k0 0  # single point
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))

from src.model import TwoSectorModel  # noqa: E402
from src.evolution import compute_ground_state, evolve_midpoint_krylov  # noqa: E402
from src.hole import create_hole_wavepacket  # noqa: E402
from src.observables import measure_all_per_site  # noqa: E402
from src.defect import compute_all_defects  # noqa: E402
from src.io import save_defect_result  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RESULTS_DIR = _PROJECT.parent.parent / "results" / "spinon-holon" / "benchmark"

# ---------------------------------------------------------------------------
# Physical parameters
# ---------------------------------------------------------------------------
PHI_0 = 5.0 * np.pi / 3.0  # initial pump phase
SIGMA = 1.2                 # Gaussian hole width
T_STATIC = 10.0             # static evolution time
DT = 0.05                   # time step
SAVE_INTERVAL = 0.1         # save every 0.1 in τ


# ---------------------------------------------------------------------------
# Pump path at fixed φ
# ---------------------------------------------------------------------------

def make_static_functions(R_delta: float):
    """Return (delta_of_tau, Delta_of_tau) for static H(φ₀)."""
    delta_fixed = R_delta * np.cos(PHI_0)
    Delta_fixed = 5.0 + 2.1 * np.sin(PHI_0)

    def delta_of_tau(tau: float) -> float:
        return delta_fixed

    def Delta_of_tau(tau: float) -> float:
        return Delta_fixed

    return delta_of_tau, Delta_of_tau, delta_fixed, Delta_fixed


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------

def run_benchmark_single(
    L: int,
    U: float,
    R_delta: float,
    k0: float,
    smoke: bool = False,
) -> dict:
    """Run static benchmark for one (U, R_δ, k₀) point."""
    T_eff = min(T_STATIC, 10 * DT) if smoke else T_STATIC
    save_interval = SAVE_INTERVAL

    delta_of_tau, Delta_of_tau, delta_fixed, Delta_fixed = \
        make_static_functions(R_delta)

    label = f"L={L}_U={U}_Rd={R_delta}_k0={k0:.2f}"
    print(f"\n{'=' * 64}")
    print(f"Static benchmark: {label}")
    print(f"  δ={delta_fixed:.6f}  Δ={Delta_fixed:.6f}  T={T_eff}  dt={DT}")
    print(f"{'=' * 64}")

    t0 = time.perf_counter()

    # --- Build two-sector model ---
    print("Building models ...")
    tsm = TwoSectorModel(L=L, U=U)
    print(f"  dim_N = {tsm.dim_N}  dim_Nm1 = {tsm.dim_Nm1}  "
          f"antiperiodic = {tsm.antiperiodic}")

    # --- Half-filling ground state ---
    print("Computing half-filling GS ...")
    gs = compute_ground_state(tsm.model_N, delta_fixed, Delta_fixed)
    print(f"  E₀(N) = {gs.energy:.8f}  residual = {gs.residual:.2e}  "
          f"converged = {gs.converged}  {gs.wall_time_s:.1f}s")

    # --- Create hole wavepacket ---
    print(f"Creating hole wavepacket (σ={SIGMA}, k₀={k0:.2f}) ...")
    psi_hole = create_hole_wavepacket(
        tsm.model_N, tsm.model_Nm1, gs.state,
        sigma=SIGMA, k0=k0,
    )
    norm_wp = float(np.linalg.norm(psi_hole))
    print(f"  wavepacket norm = {norm_wp:.10f}")

    # --- Static evolution: half-filling reference ---
    print("Evolving half-filling reference (static) ...")
    ev_N = evolve_midpoint_krylov(
        model=tsm.model_N, psi0=gs.state,
        T=T_eff, dt=DT,
        delta_of_tau=delta_of_tau,
        Delta_of_tau=Delta_of_tau,
        save_interval=save_interval,
    )
    max_norm_err_N = max(ev_N.norm_errors) if ev_N.norm_errors else 0.0
    print(f"  n_steps = {ev_N.n_steps}  n_save = {len(ev_N.times)}  "
          f"max|norm-1| = {max_norm_err_N:.2e}  {ev_N.wall_time_s:.1f}s")

    # --- Static evolution: one-hole sector ---
    print("Evolving one-hole state (static) ...")
    ev_hole = evolve_midpoint_krylov(
        model=tsm.model_Nm1, psi0=psi_hole,
        T=T_eff, dt=DT,
        delta_of_tau=delta_of_tau,
        Delta_of_tau=Delta_of_tau,
        save_interval=save_interval,
    )
    max_norm_err_h = max(ev_hole.norm_errors) if ev_hole.norm_errors else 0.0
    print(f"  n_steps = {ev_hole.n_steps}  n_save = {len(ev_hole.times)}  "
          f"max|norm-1| = {max_norm_err_h:.2e}  {ev_hole.wall_time_s:.1f}s")

    # --- Measure per-site observables ---
    print("Measuring observables ...")
    obs_N = measure_all_per_site(tsm.model_N, ev_N.times, ev_N.states)
    obs_hole = measure_all_per_site(tsm.model_Nm1, ev_hole.times, ev_hole.states)

    # --- Compute defects ---
    defect = compute_all_defects(obs_N, obs_hole)

    total_wall = time.perf_counter() - t0

    # --- Report ---
    print(f"\n  Final (t={T_eff:.1f}):")
    print(f"    X_h = {defect.X_h[-1]:.4f}  width_h = {defect.width_h[-1]:.4f}")
    print(f"    X_s = {defect.X_s[-1]:.4f}  width_s = {defect.width_s[-1]:.4f}")
    print(f"    max|h_j - s_j| = {np.max(np.abs(defect.h_j[-1] - defect.s_j[-1])):.6f}")
    print(f"    sum_h = {defect.sum_h[-1]:.8f}  sum_s = {defect.sum_s[-1]:.8f}")
    print(f"  Wall time: {total_wall:.1f}s")

    # --- Save ---
    tag = f"L{L}_U{U}_Rd{R_delta}_k0{k0:.2f}".replace(".", "p")
    out_path = RESULTS_DIR / f"benchmark_{tag}.npz"
    save_defect_result(
        out_path=out_path,
        L=L, antiperiodic=tsm.antiperiodic,
        dt=DT, T=T_eff, U=U,
        R_delta=R_delta, phi_0=PHI_0,
        k0=k0, sigma=SIGMA,
        protocol="static",
        defect=defect,
        wall_time_s=total_wall,
    )
    print(f"  Saved: {out_path}")

    return {
        "L": L, "U": U, "R_delta": R_delta, "k0": k0,
        "defect": defect,
        "wall_time_s": total_wall,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Static spin-charge separation benchmark"
    )
    parser.add_argument("--L", type=int, default=10,
                        help="System size (default: 10)")
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke test (10 steps only)")
    parser.add_argument("--U", type=float, default=None,
                        help="Single U value")
    parser.add_argument("--R", type=float, default=None,
                        help="Single R_delta value")
    parser.add_argument("--k0", type=float, default=None,
                        help="Single k0 value")
    args = parser.parse_args()

    if args.U is not None and args.R is not None and args.k0 is not None:
        U_list = [args.U]
        Rd_list = [args.R]
        k0_list = [args.k0]
    else:
        U_list = [0.0, 10.0]
        Rd_list = [0.2, 0.4, 0.88]
        k0_list = [0.0, np.pi / 2.0]

    all_results = []
    t_total = time.perf_counter()

    for U in U_list:
        for R_delta in Rd_list:
            for k0 in k0_list:
                result = run_benchmark_single(
                    L=args.L, U=U, R_delta=R_delta, k0=k0,
                    smoke=args.smoke,
                )
                all_results.append(result)

    elapsed = time.perf_counter() - t_total
    print(f"\n{'=' * 64}")
    print(f"All benchmarks complete. Total: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Results: {RESULTS_DIR}/")
    print("Done.")


if __name__ == "__main__":
    main()
