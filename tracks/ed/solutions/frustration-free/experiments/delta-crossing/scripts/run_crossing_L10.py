#!/usr/bin/env python3
"""L=10 production run: non-adiabatic excitation probability P_ex(T).

Supports SLURM array jobs via --task-id/--task-count.

Usage:
    /opt/anaconda3/bin/python scripts/run_crossing_L10.py
    /opt/anaconda3/bin/python scripts/run_crossing_L10.py --task-id 0 --task-count 7
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import yaml

# ---- path setup ----
_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))

from crossing.model_split import SplitRMHModel  # noqa: E402
from crossing.time_evolution import solve_ground_state, evolve_midpoint  # noqa: E402
from crossing.io_utils import (  # noqa: E402
    DT_CONVERGENCE_FIELDS,
    CSV_FIELDS,
    load_result,
    result_path,
    save_result,
    write_csv,
    write_metadata,
)

RESULTS_ROOT = _PROJECT.parent.parent / "results" / "delta-crossing"


def compute_ground_state(L: int, delta: float, Delta: float, U: float) -> tuple:
    """Lightweight GS solver — builds QuSpin H directly, no toarray()."""
    r = solve_ground_state(
        L=L, delta=delta, Delta=Delta, U=U, k=1, which="SA",
    )
    return r.energy, r.state, r.residual


def run_single(L: int, U: float, Delta: float, delta0: float,
               T: float, dt: float, out_dir: Path) -> dict:
    """Run one (L, T, dt) evolution and return result dict."""
    cp_path = result_path(out_dir, L, T, dt)

    existing = load_result(cp_path)
    if existing is not None:
        print(f"    [skip] checkpoint exists: {cp_path.name}")
        return existing

    t_wall = time.perf_counter()

    # --- initial ground state ---
    print("GS_i ... ", end="", flush=True)
    E_i, psi_i, res_i = compute_ground_state(L, -delta0, Delta, U)

    # --- final ground state ---
    print("GS_f ... ", end="", flush=True)
    E_f, psi_f_gs, res_f = compute_ground_state(L, +delta0, Delta, U)

    # --- time evolution ---
    print("evolve ... ", end="", flush=True)
    split_model = SplitRMHModel(L=L, Delta=Delta, U=U)
    ev = evolve_midpoint(split_model, psi_i, T=T, dt=dt, delta0=delta0)

    # --- fidelity ---
    overlap = np.vdot(psi_f_gs, ev.psi_final)
    F_GS = float(np.abs(overlap) ** 2)
    P_ex = 1.0 - F_GS

    wall_time = time.perf_counter() - t_wall
    converged = (
        ev.max_norm_error < 1e-8
        and res_i < 1e-9
        and res_f < 1e-9
        and 0.0 <= F_GS <= 1.0
    )

    result = {
        "L": L, "U": U, "Delta": Delta, "delta0": delta0,
        "T": T, "dt": dt,
        "E_i": E_i, "E_f": E_f,
        "F_GS": F_GS, "P_ex": P_ex,
        "max_norm_error": ev.max_norm_error,
        "residual_i": res_i, "residual_f": res_f,
        "wall_time_s": wall_time, "n_steps": ev.n_steps,
        "converged": converged,
    }

    save_result(result, cp_path)
    print(f"P_ex={P_ex:.6f}  norm_err={ev.max_norm_error:.2e}  {wall_time:.1f}s")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="P_ex(T) scan for RMH delta-crossing")
    parser.add_argument("--config", type=str, default="crossing_L10.yaml",
                        help="Config file name in configs/")
    parser.add_argument("--task-id", type=int, default=None,
                        help="SLURM array task ID (0-indexed)")
    parser.add_argument("--task-count", type=int, default=None,
                        help="Total number of SLURM array tasks")
    args = parser.parse_args()

    # SLURM env fallback
    if args.task_id is None:
        env_task = os.environ.get("SLURM_ARRAY_TASK_ID")
        if env_task is not None:
            args.task_id = int(env_task)
    if args.task_count is None:
        env_count = os.environ.get("SLURM_ARRAY_TASK_COUNT")
        if env_count is not None:
            args.task_count = int(env_count)

    cfg_path = _PROJECT / "configs" / args.config
    with open(cfg_path) as fh:
        cfg = yaml.safe_load(fh)

    L = cfg["L"]
    U = cfg["U"]
    Delta = cfg["Delta"]
    delta0 = cfg["delta0"]
    T_list_all = cfg["T_list"]
    dt_default = cfg["dt_default"]
    dt_conv = cfg["dt_convergence"]
    dt_conv_T = cfg["dt_convergence_T"]

    # ---- task splitting ----
    if args.task_id is not None and args.task_count is not None:
        # Split T_list across tasks
        n_total = len(T_list_all)
        chunk_size = (n_total + args.task_count - 1) // args.task_count
        start = args.task_id * chunk_size
        end = min(start + chunk_size, n_total)
        T_list = T_list_all[start:end]
        task_tag = f"task {args.task_id}/{args.task_count}"
    else:
        T_list = T_list_all
        task_tag = "single-task"

    out_dir = RESULTS_ROOT / f"L{L}" / "checkpoints"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print(f"L={L} PRODUCTION  U={U}  Δ={Delta}  δ₀={delta0}")
    print(f"T ∈ {T_list}  dt_default={dt_default}  [{task_tag}]")
    print(f"dt convergence at T ∈ {dt_conv_T}: {dt_conv}")
    print("=" * 64)

    t_total = time.perf_counter()

    # ---- Main scan ----
    main_results: list[dict] = []
    for T in T_list:
        print(f"\nT={T:.1f}  dt={dt_default} … ", end="", flush=True)
        r = run_single(L, U, Delta, delta0, T, dt_default, out_dir)
        main_results.append(r)

    # ---- dt convergence (only for T values in this task's range) ----
    conv_results: list[dict] = []
    for T in dt_conv_T:
        if T not in T_list:
            continue
        for dt in dt_conv:
            print(f"\nT={T:.1f}  dt={dt} (convergence) … ", end="", flush=True)
            r = run_single(L, U, Delta, delta0, T, dt, out_dir)
            conv_results.append({
                "L": L, "T": T, "dt": dt,
                "P_ex": r["P_ex"], "max_norm_error": r["max_norm_error"],
                "wall_time_s": r["wall_time_s"], "n_steps": r["n_steps"],
            })

    # ---- Save ----
    csv_dir = RESULTS_ROOT / f"L{L}"
    task_suffix = f"_task{args.task_id:03d}" if args.task_id is not None else ""
    write_csv(main_results, csv_dir / f"P_ex_vs_T_L{L}{task_suffix}.csv")
    if conv_results:
        write_csv(conv_results, csv_dir / f"dt_convergence_L{L}{task_suffix}.csv",
                  fields=DT_CONVERGENCE_FIELDS)
    write_metadata(csv_dir, cfg)

    elapsed = time.perf_counter() - t_total
    print(f"\n{'=' * 64}")
    print(f"Summary ({elapsed:.1f}s) [{task_tag}]:")
    for r in main_results:
        print(f"  T={r['T']:6.1f}  P_ex={r['P_ex']:.8f}  "
              f"norm_err={r['max_norm_error']:.2e}  conv={r['converged']}")
    print(f"\nResults: {csv_dir}/")
    print("Done.")


if __name__ == "__main__":
    main()
