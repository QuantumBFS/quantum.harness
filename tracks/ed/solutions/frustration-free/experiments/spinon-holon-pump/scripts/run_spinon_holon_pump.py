#!/usr/bin/env python3
"""Process 2: Spinon-holon dynamic unbinding and rebinding under pump.

Studies whether the pump periodically changes the relative distance and
confinement length of spinon and holon, rather than just propagating
two wavepackets with different group velocities.

Parameter grid (first round):
  L ∈ {8, 10}
  U ∈ {6, 10, 14}
  R_δ ∈ {0.2, 0.4}
  T ∈ {30, 60}
  k₀ ∈ {0, π/2}

For each point: CW, CCW, frozen, and half-filling reference.

Usage:
  python scripts/run_spinon_holon_pump.py --L 6 --smoke       # fast smoke test
  python scripts/run_spinon_holon_pump.py --L 8 --T 30 --U 10  # single point
  python scripts/run_spinon_holon_pump.py --L 8 --all          # full grid for L=8
  python scripts/run_spinon_holon_pump.py --L 10 --all         # full grid for L=10
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
    frozen protocols, then computes relative motion metrics.
    """
    T_eff = min(T, 10 * DT) if smoke else T

    label = f"L={L}_U={U}_Rd={R_delta}_T={T_eff}_k0={k0:.2f}"
    print(f"\n{'=' * 64}")
    print(f"Spinon-holon deconfinement: {label}")
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
    print(f"Creating hole wavepacket (σ={SIGMA}, k₀={k0:.2f}) ...")
    psi_hole = create_hole_wavepacket(
        tsm.model_N, tsm.model_Nm1, gs.state,
        sigma=SIGMA, k0=k0,
    )
    print(f"  hole norm = {float(np.linalg.norm(psi_hole)):.10f}")

    # --- Evolve under each protocol ---
    protocols = ["cw", "ccw", "frozen"]
    defect_results: dict[str, dict] = {}
    evolution_times: dict[str, dict] = {}

    for direction in protocols:
        print(f"\n--- Protocol: {direction.upper()} ---")
        delta_fn, Delta_fn = make_pump_functions(R_delta, T_eff, direction)

        # Half-filling reference
        print("  Evolving half-filling reference ...")
        ev_N = evolve_midpoint_krylov(
            model=tsm.model_N, psi0=gs.state,
            T=T_eff, dt=DT,
            delta_of_tau=delta_fn, Delta_of_tau=Delta_fn,
            save_interval=SAVE_INTERVAL,
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
            save_interval=SAVE_INTERVAL,
        )
        max_nrm_h = max(ev_hole.norm_errors) if ev_hole.norm_errors else 0.0
        print(f"    n_steps={ev_hole.n_steps}  n_save={len(ev_hole.times)}  "
              f"max|norm-1|={max_nrm_h:.2e}  {ev_hole.wall_time_s:.1f}s")

        # Measure observables
        print("  Measuring observables ...")
        obs_N = measure_all_per_site(tsm.model_N, ev_N.times, ev_N.states)
        obs_hole = measure_all_per_site(tsm.model_Nm1, ev_hole.times, ev_hole.states)

        # Compute defects
        defect = compute_all_defects(obs_N, obs_hole)
        defect_results[direction] = defect
        evolution_times[direction] = {
            "wall_N": ev_N.wall_time_s,
            "wall_hole": ev_hole.wall_time_s,
            "max_norm_N": max_nrm_N,
            "max_norm_hole": max_nrm_h,
        }

        # Quick report
        print(f"    X_h(T) = {defect.X_h[-1]:.4f}  X_s(T) = {defect.X_s[-1]:.4f}")
        print(f"    sum_h = {defect.sum_h[-1]:.8f}  sum_s = {defect.sum_s[-1]:.8f}")

    # --- Compute deconfinement ---
    print("\nComputing deconfinement metrics ...")
    tau = defect_results["cw"].tau
    deconf = compute_deconfinement(
        tau=tau,
        defect_cw=defect_results["cw"],
        defect_ccw=defect_results["ccw"],
        defect_frozen=defect_results["frozen"],
    )

    # Report key signals
    print(f"\n  Deconfinement at τ/T = 1:")
    print(f"    CW:  D_hs = {deconf.cw.D_hs[-1]:.4f}  "
          f"ξ_hs = {deconf.cw.xi_hs[-1]:.4f}  "
          f"O_hs = {deconf.cw.O_hs[-1]:.6f}")
    print(f"    CCW: D_hs = {deconf.ccw.D_hs[-1]:.4f}  "
          f"ξ_hs = {deconf.ccw.xi_hs[-1]:.4f}  "
          f"O_hs = {deconf.ccw.O_hs[-1]:.6f}")
    print(f"    Frozen: D_hs = {deconf.frozen.D_hs[-1]:.4f}  "
          f"ξ_hs = {deconf.frozen.xi_hs[-1]:.4f}  "
          f"O_hs = {deconf.frozen.O_hs[-1]:.6f}")
    print(f"    δD(CW-frozen) = {deconf.cw.delta_D_hs[-1]:.4f}")
    print(f"    δD(CCW-frozen) = {deconf.ccw.delta_D_hs[-1]:.4f}")
    print(f"    D_odd = {deconf.D_hs_odd[-1]:.4f}")
    print(f"    ξ_odd = {deconf.xi_hs_odd[-1]:.4f}")
    print(f"    O_odd = {deconf.O_hs_odd[-1]:.6f}")

    # --- Check for interesting unbinding/rebinding signal ---
    # O_hs ↓ and D_hs,ξ_hs ↑ then O_hs ↑ and D_hs → 0 within one period,
    # while frozen shows no corresponding structure
    cw_O = deconf.cw.O_hs
    cw_D = deconf.cw.D_hs
    fro_D = deconf.frozen.D_hs

    # Simple diagnostic: does CW show more relative motion than frozen?
    cw_D_range = float(np.max(cw_D) - np.min(cw_D))
    fro_D_range = float(np.max(fro_D) - np.min(fro_D))
    print(f"\n  Diagnostic:")
    print(f"    CW D_hs range = {cw_D_range:.4f}  "
          f"Frozen D_hs range = {fro_D_range:.4f}")

    if cw_D_range > 1.5 * fro_D_range:
        print(f"    >>> Pump-induced D_hs variation significantly exceeds frozen drift")
    else:
        print(f"    --- D_hs variation dominated by natural propagation")

    total_wall = time.perf_counter() - t0
    print(f"\n  Total wall time: {total_wall:.1f}s ({total_wall/60:.1f} min)")

    # --- Save ---
    tag = f"L{L}_U{U}_Rd{R_delta}_T{T_eff}_k0{k0:.2f}".replace(".", "p")
    out_path = RESULTS_DIR / f"deconfinement_{tag}.npz"

    # Pack defect data (h_j, s_j, X_h, X_s) for each protocol
    defect_extra = {}
    for direction in protocols:
        d = defect_results[direction]
        defect_extra[f"{direction}_h_j"] = d.h_j
        defect_extra[f"{direction}_s_j"] = d.s_j
        defect_extra[f"{direction}_X_h"] = d.X_h
        defect_extra[f"{direction}_X_s"] = d.X_s
        defect_extra[f"{direction}_h_bar"] = d.h_bar
        defect_extra[f"{direction}_s_bar"] = d.s_bar
        defect_extra[f"{direction}_sum_h"] = d.sum_h
        defect_extra[f"{direction}_sum_s"] = d.sum_s

    save_deconfinement_result(
        out_path=out_path,
        L=L, antiperiodic=tsm.antiperiodic,
        dt=DT, T=T_eff, U=U,
        R_delta=R_delta, k0=k0, sigma=SIGMA,
        deconf=deconf,
        wall_time_s=total_wall,
        extra=defect_extra,
    )
    print(f"  Saved: {out_path}")

    return {
        "L": L, "U": U, "R_delta": R_delta, "T": T_eff, "k0": k0,
        "deconf": deconf,
        "wall_time_s": total_wall,
    }


# ---------------------------------------------------------------------------
# Grid runner
# ---------------------------------------------------------------------------

def run_grid(L: int, smoke: bool = False):
    """Run the full parameter grid for given L."""
    U_list = U_LIST
    Rd_list = R_DELTA_LIST
    T_list = T_LIST
    k0_list = K0_LIST

    n_jobs = len(U_list) * len(Rd_list) * len(T_list) * len(k0_list)
    print(f"Parameter grid for L={L}:")
    print(f"  U ∈ {U_list}")
    print(f"  R_δ ∈ {Rd_list}")
    print(f"  T ∈ {T_list}")
    print(f"  k₀ ∈ {[f'{k:.2f}' for k in k0_list]}")
    print(f"  Total jobs: {n_jobs}")
    print(f"  Smoke: {smoke}")
    print(f"  Results: {RESULTS_DIR}/")

    all_results = []
    t_total = time.perf_counter()
    job_idx = 0

    for U in U_list:
        for R_delta in Rd_list:
            for T in T_list:
                for k0 in k0_list:
                    job_idx += 1
                    print(f"\n{'#' * 64}")
                    print(f"# Job {job_idx}/{n_jobs}")
                    print(f"{'#' * 64}")
                    result = run_single_point(
                        L=L, U=U, R_delta=R_delta, T=T, k0=k0,
                        smoke=smoke,
                    )
                    all_results.append(result)

    elapsed = time.perf_counter() - t_total
    print(f"\n{'=' * 64}")
    print(f"All deconfinement runs complete for L={L}.")
    print(f"Total: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Results: {RESULTS_DIR}/")
    print("Done.")
    return all_results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Spinon-holon deconfinement under RMH pump"
    )
    parser.add_argument("--L", type=int, required=True,
                        help="System size (8 or 10)")
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke test (T = 10*dt only)")
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

    if args.smoke or not args.all:
        # Single point
        U = args.U if args.U is not None else 10.0
        Rd = args.Rd if args.Rd is not None else 0.4
        T = args.T if args.T is not None else 60
        k0 = args.k0 if args.k0 is not None else 0.0

        run_single_point(L=L, U=U, R_delta=Rd, T=T, k0=k0, smoke=args.smoke)
    else:
        run_grid(L=L)


if __name__ == "__main__":
    main()
