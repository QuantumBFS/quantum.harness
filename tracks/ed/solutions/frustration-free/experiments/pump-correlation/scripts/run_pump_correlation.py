#!/usr/bin/env python3
"""Reproduce Fig. 5(d,e) from arXiv:2308.03756v2.

Charge and spin correlation dynamics in the Rice-Mele-Hubbard pump.

Usage:
    /opt/anaconda3/bin/python scripts/run_pump_correlation.py --L 6          # single size
    /opt/anaconda3/bin/python scripts/run_pump_correlation.py --L 6 --smoke  # 10-step smoke test
    /opt/anaconda3/bin/python scripts/run_pump_correlation.py --all           # L=6,8,10,12,14
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

from src.model import SplitRMHModel, _is_antiperiodic  # noqa: E402
from src.evolution import compute_ground_state, evolve_midpoint_krylov  # noqa: E402
from src.observables import measure_correlations  # noqa: E402
from src.io import save_result, save_summary_csv  # noqa: E402

# ---------------------------------------------------------------------------
# Physical parameters (arXiv:2308.03756v2)
# ---------------------------------------------------------------------------
U = 10.0
T_TOTAL = 100.0

# Elliptical pump path (clockwise)
DELTA_C = U / 2          # = 5.0
R_DELTA = 2.10
R_DELTA_PHASE = 0.88     # R_δ in the paper

# Time evolution
DT_DEFAULT = 0.1
DT_CONVERGENCE = 0.05
SAVE_INTERVAL = 0.2
KRYLOV_TOL = 1e-12

# System sizes (open-shell convention)
L_DEFAULT_LIST = [6, 8, 10, 12, 14]

# Results root
RESULTS_DIR = _PROJECT.parent.parent / "results" / "pump-correlation"


# ---------------------------------------------------------------------------
# Pump path functions
# ---------------------------------------------------------------------------

def theta_of_tau(tau: float) -> float:
    """Clockwise pump: θ(τ) = -2πτ/T."""
    return -2.0 * np.pi * tau / T_TOTAL


def delta_of_tau(tau: float) -> float:
    """δ(τ) = R_δ cos(θ(τ))."""
    return R_DELTA_PHASE * np.cos(theta_of_tau(tau))


def Delta_of_tau(tau: float) -> float:
    """Δ(τ) = Δ_c + R_Δ sin(θ(τ))."""
    return DELTA_C + R_DELTA * np.sin(theta_of_tau(tau))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_single_L(L: int, dt: float = DT_DEFAULT, smoke: bool = False) -> dict:
    """Run pump correlation dynamics for one system size."""
    anti = _is_antiperiodic(L)
    bc_label = "anti-PBC" if anti else "PBC"
    T_eff = min(T_TOTAL, 10 * dt) if smoke else T_TOTAL

    print(f"\n{'=' * 64}")
    print(f"L = {L}  ({bc_label})  dim = {L//2} choose {L//2} squared")
    print(f"U = {U}  T = {T_eff}  dt = {dt}  save_interval = {SAVE_INTERVAL}")
    print(f"{'SMOKE TEST — 10 steps only' if smoke else 'PRODUCTION RUN'}")
    print(f"{'=' * 64}")

    # --- Build model ---
    t0 = time.perf_counter()
    model = SplitRMHModel(L=L, U=U)
    print(f"Basis dimension: {model.dim}")
    print(f"Build time: {time.perf_counter() - t0:.1f}s")

    # --- Initial ground state at θ = 0 (δ = R_δ, Δ = Δ_c) ---
    print("\nComputing initial ground state at θ = 0 ...")
    delta_i = delta_of_tau(0.0)
    Delta_i = Delta_of_tau(0.0)
    gs = compute_ground_state(model, delta_i, Delta_i)
    print(f"  E₀ = {gs.energy:.8f}  residual = {gs.residual:.2e}  "
          f"converged = {gs.converged}  {gs.wall_time_s:.1f}s")

    # --- Time evolution ---
    print(f"\nEvolving for T = {T_eff} with dt = {dt} ...")
    ev = evolve_midpoint_krylov(
        model=model,
        psi0=gs.state,
        T=T_eff,
        dt=dt,
        delta_of_tau=delta_of_tau,
        Delta_of_tau=Delta_of_tau,
        save_interval=SAVE_INTERVAL,
    )
    max_norm_err = max(ev.norm_errors) if ev.norm_errors else 0.0
    print(f"  n_steps = {ev.n_steps}  n_save = {len(ev.times)}  "
          f"max|norm-1| = {max_norm_err:.2e}  {ev.wall_time_s:.1f}s")

    # --- Measure correlations ---
    print("Measuring correlations ...")
    corr = measure_correlations(model, ev.times, ev.states, ev.norm_errors)
    total_wall = time.perf_counter() - t0

    print(f"\n  Final: C_S = {corr.C_spin[-1]:.6f}  C_n = {corr.C_charge[-1]:.6f}")
    print(f"  Total wall time: {total_wall:.1f}s")

    # --- Save ---
    out_path = RESULTS_DIR / f"L{L}" / f"pump_correlation_L{L}_dt{dt}.npz"
    save_result(
        out_path=out_path,
        L=L, antiperiodic=anti, dt=dt, T=T_eff, U=U,
        delta_of_tau=delta_of_tau,
        Delta_of_tau=Delta_of_tau,
        times=ev.times,
        C_spin=corr.C_spin,
        C_charge=corr.C_charge,
        bond_spin=corr.bond_spin,
        bond_charge=corr.bond_charge,
        norm_errors=ev.norm_errors,
        wall_time_s=total_wall,
    )
    print(f"Saved: {out_path}")

    return {
        "L": L,
        "tau": ev.times,
        "tau_over_T": ev.times / T_eff,
        "C_spin": corr.C_spin,
        "C_charge": corr.C_charge,
        "bond_spin": corr.bond_spin,
        "bond_charge": corr.bond_charge,
        "norm_errors": ev.norm_errors,
        "antiperiodic": anti,
        "wall_time_s": total_wall,
    }


def main():
    parser = argparse.ArgumentParser(
        description="RMH pump correlation dynamics — Fig. 5(d,e) reproduction"
    )
    parser.add_argument("--L", type=int, default=None,
                        help="Single system size to run")
    parser.add_argument("--all", action="store_true",
                        help="Run all L = 6, 8, 10, 12, 14")
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke test (10 steps only)")
    parser.add_argument("--dt", type=float, default=DT_DEFAULT,
                        help=f"Time step (default: {DT_DEFAULT})")
    parser.add_argument("--dt-convergence", action="store_true",
                        help=f"Run dt={DT_CONVERGENCE} convergence check (L=6,10 only)")
    args = parser.parse_args()

    if args.all:
        L_list = L_DEFAULT_LIST
    elif args.L is not None:
        L_list = [args.L]
    else:
        print("Specify --L or --all")
        sys.exit(1)

    all_results: dict[int, dict] = {}

    for L in L_list:
        result = run_single_L(L, dt=args.dt, smoke=args.smoke)
        all_results[L] = result

    # --- dt convergence check ---
    if args.dt_convergence and not args.smoke:
        for L in [6, 10]:
            if L in L_list:
                print(f"\n{'=' * 64}")
                print(f"DT CONVERGENCE CHECK: L={L}  dt={DT_CONVERGENCE}")
                print(f"{'=' * 64}")
                result_fine = run_single_L(L, dt=DT_CONVERGENCE)

                # Compare with default dt result
                coarse = all_results[L]
                # interpolate to common τ grid
                common_tau = np.arange(0, T_TOTAL + 1e-12, SAVE_INTERVAL)
                C_spin_coarse = np.interp(common_tau, coarse["tau"], coarse["C_spin"])
                C_spin_fine = np.interp(common_tau, result_fine["tau"], result_fine["C_spin"])
                C_ch_coarse = np.interp(common_tau, coarse["tau"], coarse["C_charge"])
                C_ch_fine = np.interp(common_tau, result_fine["tau"], result_fine["C_charge"])

                max_dC_spin = np.max(np.abs(C_spin_coarse - C_spin_fine))
                max_dC_charge = np.max(np.abs(C_ch_coarse - C_ch_fine))
                print(f"  max|ΔC_S| = {max_dC_spin:.2e}  max|ΔC_n| = {max_dC_charge:.2e}")

    # --- Summary CSV ---
    if len(all_results) > 1 and not args.smoke:
        csv_path = RESULTS_DIR / "summary.csv"
        save_summary_csv(csv_path, all_results)
        print(f"\nSummary CSV: {csv_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
