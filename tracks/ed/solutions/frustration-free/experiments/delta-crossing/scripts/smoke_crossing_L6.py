#!/usr/bin/env python3
"""L=6 smoke test: non-adiabatic excitation probability P_ex(T).

Computes P_ex(T) = 1 - |⟨GS_f|ψ(T)⟩|² for T ∈ [1, 2, 5, 10, 20, 50, 100]
with dt=0.02 default, plus dt-convergence checks at T=10, 50.

Usage:
    /opt/anaconda3/bin/python scripts/smoke_crossing_L6.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import yaml

# ---- path setup ----
_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))

# Import from rmh_gap_landscape for ground-state computation
_RMH_SRC = _PROJECT.parent / "rmh_gap_landscape"
sys.path.append(str(_RMH_SRC))  # append — our src/ must come first

from src.model import RiceMeleHubbardModel  # noqa: E402

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
    """Compute GS energy and state vector at given (delta, Delta, U)."""
    model = RiceMeleHubbardModel(
        L=L, t=1.0, delta=delta, Delta=Delta, U=U,
        N_up=L // 2, N_down=L // 2,
    )
    r = solve_ground_state(model, k=1, which="SA")
    return r.energy, r.state, r.residual


def run_single(L: int, U: float, Delta: float, delta0: float,
               T: float, dt: float, out_dir: Path) -> dict:
    """Run one (L, T, dt) evolution and return result dict."""
    cp_path = result_path(out_dir, L, T, dt)

    existing = load_result(cp_path)
    if existing is not None:
        print(f"    [skip] checkpoint exists: {cp_path.name}")
        return existing

    # --- initial ground state at delta = -delta0 ---
    print("    GS_i ... ", end="", flush=True)
    t0 = time.perf_counter()
    E_i, psi_i, res_i = compute_ground_state(L, -delta0, Delta, U)
    t_gs_i = time.perf_counter() - t0

    # --- final ground state at delta = +delta0 ---
    print("GS_f ... ", end="", flush=True)
    t0 = time.perf_counter()
    E_f, psi_f_gs, res_f = compute_ground_state(L, +delta0, Delta, U)
    t_gs_f = time.perf_counter() - t0

    # --- time evolution ---
    print("evolve ... ", end="", flush=True)
    split_model = SplitRMHModel(L=L, Delta=Delta, U=U)
    ev = evolve_midpoint(split_model, psi_i, T=T, dt=dt, delta0=delta0)

    # --- fidelity ---
    overlap = np.vdot(psi_f_gs, ev.psi_final)
    F_GS = float(np.abs(overlap) ** 2)
    P_ex = 1.0 - F_GS

    wall_time = t_gs_i + t_gs_f + ev.wall_time_s
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
    cfg_path = _PROJECT / "configs" / "crossing_L6.yaml"
    with open(cfg_path) as fh:
        cfg = yaml.safe_load(fh)

    L = cfg["L"]
    U = cfg["U"]
    Delta = cfg["Delta"]
    delta0 = cfg["delta0"]
    T_list = cfg["T_list"]
    dt_default = cfg["dt_default"]
    dt_conv = cfg["dt_convergence"]
    dt_conv_T = cfg["dt_convergence_T"]

    out_dir = RESULTS_ROOT / "L6" / "checkpoints"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print(f"L=6 SMOKE TEST  U={U}  Δ={Delta}  δ₀={delta0}")
    print(f"T ∈ {T_list}  dt_default={dt_default}")
    print(f"dt convergence at T ∈ {dt_conv_T}: {dt_conv}")
    print("=" * 64)

    t_total = time.perf_counter()

    # ---- Main scan ----
    main_results: list[dict] = []
    for T in T_list:
        print(f"\nT={T:.1f}  dt={dt_default} … ", end="", flush=True)
        r = run_single(L, U, Delta, delta0, T, dt_default, out_dir)
        main_results.append(r)

    # ---- dt convergence ----
    conv_results: list[dict] = []
    for T in dt_conv_T:
        for dt in dt_conv:
            print(f"\nT={T:.1f}  dt={dt} (convergence) … ", end="", flush=True)
            r = run_single(L, U, Delta, delta0, T, dt, out_dir)
            conv_results.append({
                "L": L, "T": T, "dt": dt,
                "P_ex": r["P_ex"], "max_norm_error": r["max_norm_error"],
                "wall_time_s": r["wall_time_s"], "n_steps": r["n_steps"],
            })

    # ---- Save aggregate CSVs ----
    csv_dir = RESULTS_ROOT / "L6"
    write_csv(main_results, csv_dir / "P_ex_vs_T_L6.csv")
    write_csv(conv_results, csv_dir / "dt_convergence_L6.csv",
              fields=DT_CONVERGENCE_FIELDS)
    write_metadata(csv_dir, cfg)

    elapsed = time.perf_counter() - t_total
    print(f"\n{'=' * 64}")
    print(f"Summary ({elapsed:.1f}s):")
    print(f"{'T':>6s}  {'P_ex':>10s}  {'F_GS':>10s}  {'norm_err':>10s}  {'conv'}")
    for r in main_results:
        print(f"{r['T']:6.1f}  {r['P_ex']:10.6f}  {r['F_GS']:10.6f}  "
              f"{r['max_norm_error']:10.2e}  {r['converged']}")
    print(f"\nResults: {csv_dir}/")
    print("Done.")


if __name__ == "__main__":
    main()
