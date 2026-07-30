#!/usr/bin/env python3
"""Process 1: Single-hole vs extra-particle pumping asymmetry.

Compares pump response of removing vs adding one electron from half-filling
in the Rice-Mele-Hubbard model under CW, CCW, and frozen protocols.

Parameter grid (first round):
  L ∈ {8, 10}
  U = 10 (with controls U ∈ {0, 4, 8, 12})
  R_δ ∈ {0.2, 0.4}
  T ∈ {30, 60}
  k₀ ∈ {0, π/2}

Usage:
  python scripts/run_pump_asymmetry.py --L 6 --smoke       # fast smoke test
  python scripts/run_pump_asymmetry.py --L 8 --T 30         # single production point
  python scripts/run_pump_asymmetry.py --L 8 --all          # full grid for L=8
  python scripts/run_pump_asymmetry.py --L 10 --control     # U-scan controls only
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

from src.model import ThreeSectorModel  # noqa: E402
from src.evolution import compute_ground_state, evolve_midpoint_krylov  # noqa: E402
from src.hole import create_hole_wavepacket, create_particle_wavepacket  # noqa: E402
from src.pump_path import make_pump_functions  # noqa: E402
from src.observables import measure_all_per_site  # noqa: E402
from src.defect import (  # noqa: E402
    compute_all_defects_extended,
    compute_pump_odd,
    compute_all_defects,
)
from src.io import save_pump_result  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RESULTS_DIR = _PROJECT.parent.parent / "results" / "spinon-holon" / "pump-asymmetry"

# ---------------------------------------------------------------------------
# Physical parameters
# ---------------------------------------------------------------------------
SIGMA = 1.2                 # Gaussian wavepacket width
DT = 0.05                   # time step
SAVE_INTERVAL = 0.2         # save every 0.2 in τ

# Default parameter grid
U_DEFAULT = 10.0
R_DELTA_LIST = [0.2, 0.4]
T_LIST = [30, 60]
K0_LIST = [0.0, np.pi / 2.0]
L_LIST = [8, 10]
U_CONTROL_LIST = [0.0, 4.0, 8.0, 12.0]


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------

def run_single_point(
    L: int,
    U: float,
    R_delta: float,
    T: float,
    k0: float,
    smoke: bool = False,
) -> dict:
    """Run pump asymmetry for one (L, U, R_δ, T, k₀) point.

    Evolves half-filling reference, hole state, and particle state under
    CW, CCW, and frozen protocols, then computes pump-odd displacements.
    """
    T_eff = min(T, 10 * DT) if smoke else T
    save_interval = SAVE_INTERVAL

    label = f"L={L}_U={U}_Rd={R_delta}_T={T_eff}_k0={k0:.2f}"
    print(f"\n{'=' * 64}")
    print(f"Pump asymmetry: {label}")
    print(f"{'SMOKE TEST' if smoke else 'PRODUCTION'}")
    print(f"{'=' * 64}")

    t0 = time.perf_counter()

    # --- Build three-sector model ---
    print("Building three-sector model ...")
    tsm = ThreeSectorModel(L=L, U=U)
    print(f"  dim_N = {tsm.dim_N}  dim_Nm1 = {tsm.dim_Nm1}  "
          f"dim_Np1 = {tsm.dim_Np1}  antiperiodic = {tsm.antiperiodic}")

    # --- Half-filling ground state at pump start (φ=0) ---
    delta_0 = R_delta  # cos(0) = 1
    Delta_0 = 5.0       # sin(0) = 0
    print(f"Computing half-filling GS at (δ={delta_0}, Δ={Delta_0}) ...")
    gs = compute_ground_state(tsm.model_N, delta_0, Delta_0)
    print(f"  E₀(N) = {gs.energy:.8f}  residual = {gs.residual:.2e}  "
          f"converged = {gs.converged}  {gs.wall_time_s:.1f}s")

    # --- Create hole and particle wavepackets ---
    print(f"Creating hole wavepacket (σ={SIGMA}, k₀={k0:.2f}) ...")
    psi_hole = create_hole_wavepacket(
        tsm.model_N, tsm.model_Nm1, gs.state,
        sigma=SIGMA, k0=k0,
    )
    print(f"  hole norm = {float(np.linalg.norm(psi_hole)):.10f}")

    print(f"Creating particle wavepacket (σ={SIGMA}, k₀={k0:.2f}) ...")
    psi_particle = create_particle_wavepacket(
        tsm.model_N, tsm.model_Np1, gs.state,
        sigma=SIGMA, k0=k0,
    )
    print(f"  particle norm = {float(np.linalg.norm(psi_particle)):.10f}")

    # --- Evolve under each protocol ---
    protocols = ["cw", "ccw", "frozen"]
    results: dict[str, dict] = {}

    for direction in protocols:
        print(f"\n--- Protocol: {direction.upper()} ---")
        delta_fn, Delta_fn = make_pump_functions(R_delta, T_eff, direction)

        # Half-filling reference
        print("  Evolving half-filling reference ...")
        ev_N = evolve_midpoint_krylov(
            model=tsm.model_N, psi0=gs.state,
            T=T_eff, dt=DT,
            delta_of_tau=delta_fn, Delta_of_tau=Delta_fn,
            save_interval=save_interval,
        )
        max_nrm_N = max(ev_N.norm_errors) if ev_N.norm_errors else 0.0
        print(f"    n_steps={ev_N.n_steps}  n_save={len(ev_N.times)}  "
              f"max|norm-1|={max_nrm_N:.2e}  {ev_N.wall_time_s:.1f}s")

        # Hole sector
        print("  Evolving hole state ...")
        ev_hole = evolve_midpoint_krylov(
            model=tsm.model_Nm1, psi0=psi_hole,
            T=T_eff, dt=DT,
            delta_of_tau=delta_fn, Delta_of_tau=Delta_fn,
            save_interval=save_interval,
        )
        max_nrm_h = max(ev_hole.norm_errors) if ev_hole.norm_errors else 0.0
        print(f"    n_steps={ev_hole.n_steps}  n_save={len(ev_hole.times)}  "
              f"max|norm-1|={max_nrm_h:.2e}  {ev_hole.wall_time_s:.1f}s")

        # Particle sector
        print("  Evolving particle state ...")
        ev_particle = evolve_midpoint_krylov(
            model=tsm.model_Np1, psi0=psi_particle,
            T=T_eff, dt=DT,
            delta_of_tau=delta_fn, Delta_of_tau=Delta_fn,
            save_interval=save_interval,
        )
        max_nrm_p = max(ev_particle.norm_errors) if ev_particle.norm_errors else 0.0
        print(f"    n_steps={ev_particle.n_steps}  n_save={len(ev_particle.times)}  "
              f"max|norm-1|={max_nrm_p:.2e}  {ev_particle.wall_time_s:.1f}s")

        # Measure observables
        print("  Measuring observables ...")
        obs_N = measure_all_per_site(tsm.model_N, ev_N.times, ev_N.states)
        obs_hole = measure_all_per_site(tsm.model_Nm1, ev_hole.times, ev_hole.states)
        obs_particle = measure_all_per_site(tsm.model_Np1, ev_particle.times, ev_particle.states)

        # Compute extended defects
        defect_ext = compute_all_defects_extended(obs_N, obs_hole, obs_particle)

        results[direction] = {
            "defect": defect_ext,
            "norm_errors": {
                "N": max_nrm_N,
                "hole": max_nrm_h,
                "particle": max_nrm_p,
            },
            "wall_time_s": {
                "N": ev_N.wall_time_s,
                "hole": ev_hole.wall_time_s,
                "particle": ev_particle.wall_time_s,
            },
        }

    # --- Compute pump-odd displacements ---
    print("\nComputing pump-odd displacements ...")
    X_cw = {
        "X_h": results["cw"]["defect"].hole.X_h,
        "X_s": results["cw"]["defect"].hole.X_s,
        "X_p": results["cw"]["defect"].X_p,
        "X_s_plus": results["cw"]["defect"].X_s_plus,
    }
    X_ccw = {
        "X_h": results["ccw"]["defect"].hole.X_h,
        "X_s": results["ccw"]["defect"].hole.X_s,
        "X_p": results["ccw"]["defect"].X_p,
        "X_s_plus": results["ccw"]["defect"].X_s_plus,
    }
    X_frozen = {
        "X_h": results["frozen"]["defect"].hole.X_h,
        "X_s": results["frozen"]["defect"].hole.X_s,
        "X_p": results["frozen"]["defect"].X_p,
        "X_s_plus": results["frozen"]["defect"].X_s_plus,
    }

    tau = results["cw"]["defect"].tau
    pump_odd = compute_pump_odd(tau, X_cw, X_ccw, X_frozen)

    # Report
    print(f"\n  Final pump-odd displacements (τ/T = 1):")
    print(f"    ΔX_h^odd     = {pump_odd.dX_h_odd[-1]:.4f}")
    print(f"    ΔX_p^odd     = {pump_odd.dX_p_odd[-1]:.4f}")
    print(f"    ΔX_s^(-)^odd = {pump_odd.dX_s_minus_odd[-1]:.4f}")
    print(f"    ΔX_s^(+)^odd = {pump_odd.dX_s_plus_odd[-1]:.4f}")
    print(f"    ΔX_h^odd + ΔX_p^odd = {pump_odd.hole_vs_particle_diff[-1]:.4f}")
    print(f"    ΔX_h^odd - ΔX_s^(-)^odd = {pump_odd.hole_charge_vs_spin_diff[-1]:.4f}")
    print(f"    ΔX_p^odd - ΔX_s^(+)^odd = {pump_odd.particle_charge_vs_spin_diff[-1]:.4f}")

    total_wall = time.perf_counter() - t0
    print(f"\n  Total wall time: {total_wall:.1f}s ({total_wall/60:.1f} min)")

    # --- Save ---
    tag = f"L{L}_U{U}_Rd{R_delta}_T{T_eff}_k0{k0:.2f}".replace(".", "p")
    out_path = RESULTS_DIR / f"pump_asymmetry_{tag}.npz"
    save_pump_result(
        out_path=out_path,
        L=L, antiperiodic=tsm.antiperiodic,
        dt=DT, T=T_eff, U=U,
        R_delta=R_delta, k0=k0, sigma=SIGMA,
        direction="all",
        defect_ext=results["cw"]["defect"],  # save CW as representative
        pump_odd=pump_odd,
        wall_time_s=total_wall,
        extra={
            # Save ccw and frozen COMs for full analysis
            "X_h_ccw": X_ccw["X_h"],
            "X_p_ccw": X_ccw["X_p"],
            "X_s_ccw": X_ccw["X_s"],
            "X_s_plus_ccw": X_ccw["X_s_plus"],
            "X_h_frozen": X_frozen["X_h"],
            "X_p_frozen": X_frozen["X_p"],
            "X_s_frozen": X_frozen["X_s"],
            "X_s_plus_frozen": X_frozen["X_s_plus"],
        },
    )
    print(f"  Saved: {out_path}")

    return {
        "L": L, "U": U, "R_delta": R_delta, "T": T_eff, "k0": k0,
        "pump_odd": pump_odd,
        "wall_time_s": total_wall,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Single-hole vs extra-particle pump asymmetry"
    )
    parser.add_argument("--L", type=int, required=True,
                        help="System size")
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke test (10 steps only)")
    parser.add_argument("--all", action="store_true",
                        help="Run full parameter grid for this L")
    parser.add_argument("--control", action="store_true",
                        help="Run U-control scan (0,4,8,12) at best params")
    parser.add_argument("--U", type=float, default=None,
                        help="Single U value (default: 10)")
    parser.add_argument("--Rd", type=float, default=None,
                        help="Single R_delta value")
    parser.add_argument("--T", type=float, default=None,
                        help="Single T value")
    parser.add_argument("--k0", type=float, default=None,
                        help="Single k0 value")
    args = parser.parse_args()

    L = args.L

    # Determine parameter grid
    if args.control:
        # U-control: best params (R_delta=0.4, T=60, k0=0) varying U
        U_list = U_CONTROL_LIST
        Rd_list = [0.4]
        T_list = [60]
        k0_list = [0.0]
    elif args.all or (args.U is None and args.Rd is None):
        U_list = [args.U] if args.U is not None else [U_DEFAULT]
        Rd_list = [args.Rd] if args.Rd is not None else R_DELTA_LIST
        T_list = [args.T] if args.T is not None else T_LIST
        k0_list = [args.k0] if args.k0 is not None else K0_LIST
    else:
        U_list = [args.U] if args.U is not None else [U_DEFAULT]
        Rd_list = [args.Rd] if args.Rd is not None else [0.4]
        T_list = [args.T] if args.T is not None else [60]
        k0_list = [args.k0] if args.k0 is not None else [0.0]

    print(f"Parameter grid:")
    print(f"  L = {L}")
    print(f"  U ∈ {U_list}")
    print(f"  R_δ ∈ {Rd_list}")
    print(f"  T ∈ {T_list}")
    print(f"  k₀ ∈ {[f'{k:.2f}' for k in k0_list]}")
    print(f"  Total jobs: {len(U_list) * len(Rd_list) * len(T_list) * len(k0_list)}")
    print(f"  Smoke: {args.smoke}")
    print(f"  Results: {RESULTS_DIR}/")

    all_results = []
    t_total = time.perf_counter()

    for U in U_list:
        for R_delta in Rd_list:
            for T in T_list:
                for k0 in k0_list:
                    result = run_single_point(
                        L=L, U=U, R_delta=R_delta, T=T, k0=k0,
                        smoke=args.smoke,
                    )
                    all_results.append(result)

    elapsed = time.perf_counter() - t_total
    print(f"\n{'=' * 64}")
    print(f"All pump asymmetry runs complete.")
    print(f"Total: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Results: {RESULTS_DIR}/")
    print("Done.")


if __name__ == "__main__":
    main()
