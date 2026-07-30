#!/usr/bin/env python3
"""Process 2: Spinon-holon deconfinement/reconfinement under Thouless pump.

Studies whether the pump periodically changes the relative distance and
binding length between spinon and holon, rather than just propagating
two wavepackets at different group velocities.

Parameter grid (first round):
  L ∈ {8, 10}
  U ∈ {6, 10, 14}
  R_δ ∈ {0.2, 0.4}
  T ∈ {30, 60}
  k₀ ∈ {0, π/2}

Each (L, U, R_δ, T, k₀) runs:
  - CW pump
  - CCW pump
  - frozen Hamiltonian
  - half-filling reference

Usage:
  python scripts/run_deconfinement.py --L 6 --smoke       # fast smoke test
  python scripts/run_deconfinement.py --L 8 --T 30         # single point
  python scripts/run_deconfinement.py --L 8 --all          # full grid for L=8
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
from src.pump_path import make_pump_functions  # noqa: E402
from src.observables import measure_all_per_site  # noqa: E402
from src.defect import compute_all_defects  # noqa: E402
from src.relative_motion import compute_deconfinement  # noqa: E402
from src.io import save_deconfinement_result  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RESULTS_DIR = _PROJECT.parent.parent / "results" / "spinon-holon" / "deconfinement"

# ---------------------------------------------------------------------------
# Physical parameters
# ---------------------------------------------------------------------------
SIGMA = 1.2                 # Gaussian wavepacket width
DT = 0.05                   # time step
SAVE_INTERVAL = 0.2         # save every 0.2 in τ

# Default parameter grid
U_LIST = [6.0, 10.0, 14.0]
R_DELTA_LIST = [0.2, 0.4]
T_LIST = [30, 60]
K0_LIST = [0.0, np.pi / 2.0]
L_LIST = [8, 10]


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
    """Run deconfinement analysis for one (L, U, R_δ, T, k₀) point.

    Evolves half-filling reference and hole state under CW, CCW, and
    frozen protocols, computes defect densities, then relative motion
    metrics with pump-induced changes and CW-CCW odd components.
    """
    T_eff = min(T, 10 * DT) if smoke else T
    save_interval = SAVE_INTERVAL

    label = f"L={L}_U={U}_Rd={R_delta}_T={T_eff}_k0={k0:.2f}"
    print(f"\n{'=' * 64}")
    print(f"Deconfinement: {label}")
    print(f"{'SMOKE TEST' if smoke else 'PRODUCTION'}")
    print(f"{'=' * 64}")

    t0 = time.perf_counter()

    # --- Build two-sector model ---
    print("Building two-sector model ...")
    tsm = TwoSectorModel(L=L, U=U)
    print(f"  dim_N = {tsm.dim_N}  dim_Nm1 = {tsm.dim_Nm1}  "
          f"antiperiodic = {tsm.antiperiodic}")

    # --- Half-filling ground state at pump start (φ=0) ---
    delta_0 = R_delta  # cos(0) = 1
    Delta_0 = 5.0       # sin(0) = 0
    print(f"Computing half-filling GS at (δ={delta_0}, Δ={Delta_0}) ...")
    gs = compute_ground_state(tsm.model_N, delta_0, Delta_0)
    print(f"  E₀(N) = {gs.energy:.8f}  residual = {gs.residual:.2e}  "
          f"converged = {gs.converged}  {gs.wall_time_s:.1f}s")

    # --- Create hole wavepacket ---
    print(f"Creating hole wavepacket (σ={SIGMA}, k₀={k0:.2f}, j₀={L//2}) ...")
    psi_hole = create_hole_wavepacket(
        tsm.model_N, tsm.model_Nm1, gs.state,
        sigma=SIGMA, k0=k0,
    )
    print(f"  hole norm = {float(np.linalg.norm(psi_hole)):.10f}")

    # --- Evolve under each protocol ---
    protocols = ["cw", "ccw", "frozen"]
    defect_results: dict[str, object] = {}
    timing: dict[str, dict] = {}

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

        # Measure observables
        print("  Measuring observables ...")
        obs_N = measure_all_per_site(tsm.model_N, ev_N.times, ev_N.states)
        obs_hole = measure_all_per_site(tsm.model_Nm1, ev_hole.times, ev_hole.states)

        # Compute defect densities
        defect = compute_all_defects(obs_N, obs_hole)
        defect_results[direction] = defect

        timing[direction] = {
            "norm_error_N": max_nrm_N,
            "norm_error_hole": max_nrm_h,
            "wall_N_s": ev_N.wall_time_s,
            "wall_hole_s": ev_hole.wall_time_s,
        }

    # --- Compute relative motion metrics ---
    print("\nComputing spinon-holon relative motion ...")
    tau = defect_results["cw"].tau
    deconf = compute_deconfinement(
        tau=tau,
        defect_cw=defect_results["cw"],
        defect_ccw=defect_results["ccw"],
        defect_frozen=defect_results["frozen"],
    )

    # --- Report ---
    tau_T_idx_mid = len(tau) // 2
    tau_T_idx_end = len(tau) - 1
    print(f"\n  At τ/T ≈ 0.5 (t={tau[tau_T_idx_mid]:.1f}):")
    print(f"    CW:  D_hs={deconf.cw.D_hs[tau_T_idx_mid]:.4f}  "
          f"ξ_hs={deconf.cw.xi_hs[tau_T_idx_mid]:.4f}  "
          f"O_hs={deconf.cw.O_hs[tau_T_idx_mid]:.6f}")
    print(f"    Fro: D_hs={deconf.frozen.D_hs[tau_T_idx_mid]:.4f}  "
          f"ξ_hs={deconf.frozen.xi_hs[tau_T_idx_mid]:.4f}  "
          f"O_hs={deconf.frozen.O_hs[tau_T_idx_mid]:.6f}")
    print(f"    δD_hs^pump(CW) = {deconf.cw.delta_D_hs[tau_T_idx_mid]:.4f}")
    print(f"\n  At τ/T = 1 (t={tau[tau_T_idx_end]:.1f}):")
    print(f"    CW:  D_hs={deconf.cw.D_hs[tau_T_idx_end]:.4f}  "
          f"ξ_hs={deconf.cw.xi_hs[tau_T_idx_end]:.4f}  "
          f"O_hs={deconf.cw.O_hs[tau_T_idx_end]:.6f}")
    print(f"    Fro: D_hs={deconf.frozen.D_hs[tau_T_idx_end]:.4f}  "
          f"ξ_hs={deconf.frozen.xi_hs[tau_T_idx_end]:.4f}  "
          f"O_hs={deconf.frozen.O_hs[tau_T_idx_end]:.6f}")
    print(f"    δD_hs^pump(CW) = {deconf.cw.delta_D_hs[tau_T_idx_end]:.4f}")
    print(f"    D_hs^odd(τ=T) = {deconf.D_hs_odd[tau_T_idx_end]:.4f}")

    # --- Signal detection heuristic ---
    dD_cw = deconf.cw.delta_D_hs
    dD_range = float(np.max(dD_cw) - np.min(dD_cw))
    O_cw = deconf.cw.O_hs
    O_range = float(np.max(O_cw) - np.min(O_cw))
    print(f"\n  Signal heuristics:")
    print(f"    max δD_hs^pump = {float(np.max(np.abs(dD_cw))):.4f}")
    print(f"    δD_hs range     = {dD_range:.4f}")
    print(f"    O_hs range      = {O_range:.6f}")

    total_wall = time.perf_counter() - t0
    print(f"\n  Total wall time: {total_wall:.1f}s ({total_wall/60:.1f} min)")

    # --- Save ---
    tag = f"L{L}_U{U}_Rd{R_delta}_T{T_eff}_k0{k0:.2f}".replace(".", "p")
    out_path = RESULTS_DIR / f"deconfinement_{tag}.npz"

    # Collect per-site and COM data for plotting
    dcw = defect_results["cw"]
    save_deconfinement_result(
        out_path=out_path,
        L=L, antiperiodic=tsm.antiperiodic,
        dt=DT, T=T_eff, U=U,
        R_delta=R_delta, k0=k0, sigma=SIGMA,
        deconf=deconf,
        wall_time_s=total_wall,
        extra={
            "signal_dD_range": dD_range,
            "signal_O_range": O_range,
            "max_abs_delta_D": float(np.max(np.abs(dD_cw))),
            # Per-site densities (CW protocol for heatmaps)
            "h_j_cw": dcw.h_j,
            "s_j_cw": dcw.s_j,
            "h_bar_cw": dcw.h_bar,
            "s_bar_cw": dcw.s_bar,
            # COMs for all protocols (for trajectory plots)
            "X_h_cw": defect_results["cw"].X_h,
            "X_s_cw": defect_results["cw"].X_s,
            "X_h_ccw": defect_results["ccw"].X_h,
            "X_s_ccw": defect_results["ccw"].X_s,
            "X_h_frozen": defect_results["frozen"].X_h,
            "X_s_frozen": defect_results["frozen"].X_s,
        },
    )
    print(f"  Saved: {out_path}")

    return {
        "L": L, "U": U, "R_delta": R_delta, "T": T_eff, "k0": k0,
        "deconf": deconf,
        "wall_time_s": total_wall,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Spinon-holon deconfinement/reconfinement under pump"
    )
    parser.add_argument("--L", type=int, required=True,
                        help="System size")
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke test (10 steps only)")
    parser.add_argument("--all", action="store_true",
                        help="Run full parameter grid for this L")
    parser.add_argument("--U", type=float, default=None,
                        help="Single U value")
    parser.add_argument("--Rd", type=float, default=None,
                        help="Single R_delta value")
    parser.add_argument("--T", type=float, default=None,
                        help="Single T value")
    parser.add_argument("--k0", type=float, default=None,
                        help="Single k0 value")
    args = parser.parse_args()

    L = args.L

    # Determine parameter grid
    if args.all or (args.U is None and args.Rd is None):
        U_list = [args.U] if args.U is not None else U_LIST
        Rd_list = [args.Rd] if args.Rd is not None else R_DELTA_LIST
        T_list = [args.T] if args.T is not None else T_LIST
        k0_list = [args.k0] if args.k0 is not None else K0_LIST
    else:
        U_list = [args.U] if args.U is not None else [10.0]
        Rd_list = [args.Rd] if args.Rd is not None else [0.4]
        T_list = [args.T] if args.T is not None else [60]
        k0_list = [args.k0] if args.k0 is not None else [0.0]

    n_jobs = len(U_list) * len(Rd_list) * len(T_list) * len(k0_list)
    print(f"Parameter grid:")
    print(f"  L = {L}")
    print(f"  U ∈ {U_list}")
    print(f"  R_δ ∈ {Rd_list}")
    print(f"  T ∈ {T_list}")
    print(f"  k₀ ∈ {[f'{k:.2f}' for k in k0_list]}")
    print(f"  Total jobs: {n_jobs}")
    print(f"  Smoke: {args.smoke}")
    print(f"  Results: {RESULTS_DIR}/")

    all_results = []
    t_total = time.perf_counter()

    for U in U_list:
        for R_delta in Rd_list:
            for T_val in T_list:
                for k0 in k0_list:
                    result = run_single_point(
                        L=L, U=U, R_delta=R_delta, T=T_val, k0=k0,
                        smoke=args.smoke,
                    )
                    all_results.append(result)

    elapsed = time.perf_counter() - t_total
    print(f"\n{'=' * 64}")
    print(f"All deconfinement runs complete.")
    print(f"Total: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Results: {RESULTS_DIR}/")
    print("Done.")


if __name__ == "__main__":
    main()
