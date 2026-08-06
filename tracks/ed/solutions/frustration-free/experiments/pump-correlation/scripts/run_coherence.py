#!/usr/bin/env python3
"""Current coherence diagnostics for the Rice-Mele-Hubbard pump.

Computes eigenbasis decomposition, current channel analysis, coherence
metrics, slow-reference comparison, and hold-time interferometry.

Usage:
    python scripts/run_coherence.py --L 6                    # single size
    python scripts/run_coherence.py --L 6 --smoke            # 10-step smoke test
    python scripts/run_coherence.py --all                    # L=6,8,10
    python scripts/run_coherence.py --L 6 --no-hold          # skip hold-time scan
    python scripts/run_coherence.py --L 6 --gauge-check      # run gauge invariance check
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))

from src.model import SplitRMHModel, _is_antiperiodic  # noqa: E402
from src.evolution import compute_ground_state, evolve_midpoint_krylov  # noqa: E402
from src.current import measure_currents  # noqa: E402
from src.coherence import (  # noqa: E402
    CoherenceResult,
    HoldTimeResult,
    compute_coherence,
    run_hold_time_scan,
    check_gauge_invariance,
)

# ---------------------------------------------------------------------------
# Physical parameters (same as run_pump_correlation.py)
# ---------------------------------------------------------------------------
U = 10.0
T_TOTAL = 100.0
T_REF = 200.0  # slow reference period

DELTA_C = U / 2          # = 5.0
R_DELTA = 2.10
R_DELTA_PHASE = 0.88

DT_DEFAULT = 0.1
SAVE_INTERVAL = 0.2

L_DEFAULT_LIST = [6, 8, 10]

RESULTS_DIR = _PROJECT.parent.parent / "results" / "pump-correlation"


# ---------------------------------------------------------------------------
# Pump path functions
# ---------------------------------------------------------------------------

def _make_pump_functions(T):
    """Return (delta_of_tau, Delta_of_tau) for given period T."""
    def theta_of_tau(tau):
        return -2.0 * np.pi * tau / T

    def delta_of_tau(tau):
        return R_DELTA_PHASE * np.cos(theta_of_tau(tau))

    def Delta_of_tau(tau):
        return DELTA_C + R_DELTA * np.sin(theta_of_tau(tau))

    return delta_of_tau, Delta_of_tau


# ---------------------------------------------------------------------------
# N_eig selection
# ---------------------------------------------------------------------------

def get_N_eig(L: int) -> int:
    """Return recommended N_eig for given system size."""
    return {6: 30, 8: 20, 10: 15}.get(L, 20)


# ---------------------------------------------------------------------------
# Main: single L
# ---------------------------------------------------------------------------

def run_single_L(L: int, dt: float = DT_DEFAULT, smoke: bool = False,
                 do_hold: bool = True, do_slow_ref: bool = True,
                 do_gauge_check: bool = False) -> dict:
    """Run coherence diagnostics for one system size."""
    anti = _is_antiperiodic(L)
    bc_label = "anti-PBC" if anti else "PBC"
    T_eff = min(T_TOTAL, 10 * dt) if smoke else T_TOTAL
    N_eig = get_N_eig(L)

    print(f"\n{'=' * 64}")
    print(f"L = {L}  ({bc_label})  dim = C({L},{L//2})^2 = {L//2} choose {L//2}")
    print(f"U = {U}  T = {T_eff}  dt = {dt}  N_eig = {N_eig}")
    print(f"{'SMOKE TEST' if smoke else 'PRODUCTION RUN'}")
    print(f"{'=' * 64}")

    # --- Build model ---
    t0 = time.perf_counter()
    model = SplitRMHModel(L=L, U=U)
    print(f"Basis dimension: {model.dim}")
    print(f"Build time: {time.perf_counter() - t0:.1f}s")

    # --- Pump path ---
    delta_of_tau, Delta_of_tau = _make_pump_functions(T_eff)

    # --- Initial ground state ---
    print("\nComputing initial ground state at θ = 0 ...")
    delta_i = delta_of_tau(0.0)
    Delta_i = Delta_of_tau(0.0)
    gs = compute_ground_state(model, delta_i, Delta_i)
    print(f"  E₀ = {gs.energy:.8f}  residual = {gs.residual:.2e}  "
          f"converged = {gs.converged}  {gs.wall_time_s:.1f}s")

    # --- Time evolution ---
    print(f"\nEvolving for T = {T_eff} with dt = {dt} ...")
    ev = evolve_midpoint_krylov(
        model=model, psi0=gs.state, T=T_eff, dt=dt,
        delta_of_tau=delta_of_tau, Delta_of_tau=Delta_of_tau,
        save_interval=SAVE_INTERVAL,
    )
    max_norm_err = max(ev.norm_errors) if ev.norm_errors else 0.0
    print(f"  n_steps = {ev.n_steps}  n_save = {len(ev.times)}  "
          f"max|norm-1| = {max_norm_err:.2e}  {ev.wall_time_s:.1f}s")

    # --- Measure direct currents ---
    print("Measuring direct currents ...")
    currents = measure_currents(model, ev.times, ev.states, delta_of_tau)
    print(f"  Q_cycle = {currents.Q_cycle:.6f}  "
          f"continuity_residual = {currents.continuity_residual:.2e}")

    # --- Coherence computation ---
    print(f"\nComputing eigenbasis decomposition (N_eig = {N_eig}) ...")
    coh = compute_coherence(
        model=model, times=ev.times, states=ev.states,
        delta_of_tau=delta_of_tau, Delta_of_tau=Delta_of_tau,
        N_eig=N_eig, verbose=True,
    )

    # --- Save coherence result ---
    out_path = RESULTS_DIR / f"L{L}" / f"coherence_L{L}_dt{dt}.npz"
    _save_coherence_npz(out_path, L, anti, dt, T_eff, U, ev, currents, coh)
    print(f"Saved: {out_path}")

    result = {
        "L": L,
        "tau": ev.times,
        "tau_over_T": ev.times / T_eff,
        "coherence": coh,
        "currents": currents,
        "evolution": ev,
    }

    # --- Slow reference protocol ---
    if do_slow_ref and not smoke:
        result["slow_ref"] = _run_slow_reference(
            model, gs, L, dt, anti, N_eig,
        )

    # --- Gauge invariance check ---
    if do_gauge_check and not smoke:
        print("\n--- Gauge invariance check ---")
        gcheck = check_gauge_invariance(
            model, ev.times, ev.states,
            delta_of_tau, Delta_of_tau, N_eig=N_eig,
        )
        print("  Max differences under random gauge transform:")
        for key, val in gcheck["max_diffs"].items():
            print(f"    {key}: {val:.2e}")
        result["gauge_check"] = gcheck

    # --- Hold-time interferometry ---
    if do_hold and not smoke:
        result["hold_time"] = _run_hold_time_scans(
            model, gs.state, L, T_eff, dt, delta_of_tau, Delta_of_tau, N_eig,
        )

    total_wall = time.perf_counter() - t0
    print(f"\nTotal wall time: {total_wall:.1f}s")

    return result


# ---------------------------------------------------------------------------
# Slow reference protocol
# ---------------------------------------------------------------------------

def _run_slow_reference(model, gs, L, dt, anti, N_eig):
    """Run with T_ref = 200 for comparison."""
    print(f"\n{'=' * 64}")
    print(f"SLOW REFERENCE: T_ref = {T_REF}")
    print(f"{'=' * 64}")

    delta_s, Delta_s = _make_pump_functions(T_REF)

    t0 = time.perf_counter()
    ev_ref = evolve_midpoint_krylov(
        model=model, psi0=gs.state, T=T_REF, dt=dt,
        delta_of_tau=delta_s, Delta_of_tau=Delta_s,
        save_interval=SAVE_INTERVAL * 2,  # coarser save for longer run
    )
    print(f"  Evolution: {ev_ref.n_steps} steps, {ev_ref.wall_time_s:.1f}s")

    currents_ref = measure_currents(model, ev_ref.times, ev_ref.states, delta_s)
    print(f"  Q_cycle_ref = {currents_ref.Q_cycle:.6f}")

    print(f"Computing coherence (N_eig = {N_eig}) ...")
    coh_ref = compute_coherence(
        model=model, times=ev_ref.times, states=ev_ref.states,
        delta_of_tau=delta_s, Delta_of_tau=Delta_s,
        N_eig=N_eig, verbose=False,
    )

    out_path = RESULTS_DIR / f"L{L}" / f"coherence_slow_L{L}_dt{dt}_T{T_REF}.npz"
    _save_coherence_npz(out_path, L, anti, dt, T_REF, U, ev_ref, currents_ref, coh_ref)
    print(f"Saved: {out_path}")

    return {
        "tau": ev_ref.times,
        "tau_over_T": ev_ref.times / T_REF,
        "coherence": coh_ref,
        "currents": currents_ref,
        "Q_cycle_ref": currents_ref.Q_cycle,
    }


# ---------------------------------------------------------------------------
# Hold-time interferometry
# ---------------------------------------------------------------------------

def _run_hold_time_scans(model, psi0, L, T, dt, delta_of_tau, Delta_of_tau, N_eig):
    """Run hold-time scan at 3 positions."""
    print(f"\n{'=' * 64}")
    print(f"HOLD-TIME INTERFEROMETRY")
    print(f"{'=' * 64}")

    # Determine crossing times from existing data or heuristics
    # For the RMH pump with clockwise path:
    #   τ/T ≈ 0.20-0.25: spin-gapless crossing
    #   τ/T ≈ 0.30-0.35: charge transfer peak
    t_s = _estimate_crossing_time(L, "spin")     # spin-gapless crossing
    t_c = _estimate_crossing_time(L, "charge")    # charge transfer

    print(f"  Estimated crossing times: t_s = {t_s:.1f} (τ/T={t_s/T:.3f})")
    print(f"                            t_c = {t_c:.1f} (τ/T={t_c/T:.3f})")

    # Three hold positions
    t_star_positions = [
        max(0, t_s - 5.0),           # before spin crossing
        (t_s + t_c) / 2,              # between crossings
        min(T - 5.0, t_c + 10.0),    # after charge transfer
    ]
    labels = ["pre-crossing", "between", "post-transfer"]

    # Determine tau_h range: cover at least a few periods of relevant energy differences
    # The smallest relevant gap is ~0.01-0.1, giving periods 2π/ΔE ~ 60-600
    # Scan from 0 to ~200 with ~50 points
    tau_h_values = np.linspace(0, 200, 51)

    all_holds = {}
    for t_star, label in zip(t_star_positions, labels):
        if t_star <= 0 or t_star >= T:
            print(f"  Skipping '{label}' (t_star={t_star:.1f} out of range)")
            continue

        print(f"\n  Hold position: {label} (t_star = {t_star:.1f}, τ/T = {t_star/T:.3f})")
        hold = run_hold_time_scan(
            model=model, psi0=psi0, T=T, dt=dt,
            delta_of_tau=delta_of_tau, Delta_of_tau=Delta_of_tau,
            t_star=t_star, tau_h_values=tau_h_values,
            N_eig=N_eig, save_interval=SAVE_INTERVAL, verbose=True,
        )

        # Save
        out_path = RESULTS_DIR / f"L{L}" / f"hold_time_L{L}_tstar{label}_dt{dt}.npz"
        _save_hold_npz(out_path, L, dt, hold)
        print(f"  Saved: {out_path}")

        all_holds[label] = hold

    return all_holds


def _estimate_crossing_time(L: int, which: str) -> float:
    """Estimate t_s (spin crossing) or t_c (charge transfer) from heuristics.

    For the clockwise RMH pump (U=10, Δ_c=5, R_Δ=2.1, R_δ=0.88):
    - Spin gap closes near θ ≈ -π/2 (Δ ≈ 0), τ/T ≈ 0.25
    - Charge transfer peaks near θ ≈ -π/4 (δ small, Δ ≈ 3-5), τ/T ≈ 0.125...0.25
    - Actually: θ = -2πτ/T (clockwise), so:
      - τ/T = 0: θ=0, δ=R_δ, Δ=Δ_c
      - τ/T = 0.25: θ=-π/2, δ=0, Δ=Δ_c-R_Δ=2.9
      - τ/T = 0.5: θ=-π, δ=-R_δ, Δ=Δ_c
      - τ/T = 0.75: θ=-3π/2, δ=0, Δ=Δ_c+R_Δ=7.1

    The spin-gap closes when Δ ≈ 0 (staggered potential vanishes).
    Δ(τ) = Δ_c + R_Δ sin(-2πτ/T) = 5 - 2.1 sin(2πτ/T)
    Δ = 0 → sin(2πτ/T) = 5/2.1 ≈ 2.38 → no real solution!
    So Δ never crosses zero. The spin gap minimum is at τ/T=0.25 where Δ=2.9.

    The charge transfer is around τ/T ≈ 0.3-0.35.

    These are approximate; refine with actual gap data if available.
    """
    if which == "spin":
        # τ/T ≈ 0.25 (Δ minimum, δ ≈ 0)
        return 0.25 * T_TOTAL
    else:
        # τ/T ≈ 0.33 (peak of charge current)
        return 0.33 * T_TOTAL


# ---------------------------------------------------------------------------
# Save utilities
# ---------------------------------------------------------------------------

def _save_coherence_npz(out_path, L, anti, dt, T, U, ev, currents, coh):
    """Save coherence result as npz."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = json.dumps({
        "L": L, "antiperiodic": anti, "dt": dt, "T": T, "U": U,
        "N_eig": coh.N_eig,
        "min_W_cap": coh.convergence.get("min_W_cap", 0),
        "max_W_cap": coh.convergence.get("max_W_cap", 0),
        "max_reconstruction_error": coh.convergence.get("max_reconstruction_error", 0),
        "Q_cycle": float(currents.Q_cycle),
        "continuity_residual": float(currents.continuity_residual),
    })

    np.savez_compressed(
        out_path,
        L=np.array(L),
        tau=coh.tau,
        tau_over_T=coh.tau_over_T,
        capture_weight=coh.capture_weight,
        weights=coh.weights,
        J_direct=coh.J_direct,
        J_diag=coh.J_diag,
        J_off=coh.J_off,
        J_0e=coh.J_0e,
        J_ee=coh.J_ee,
        A_J=coh.A_J,
        R_J=coh.R_J,
        Phi_J=coh.Phi_J,
        Z_J_real=coh.Z_J_real,
        Z_J_imag=coh.Z_J_imag,
        reconstruction_error=coh.reconstruction_error,
        current_mean=currents.current_mean,
        Q=currents.Q,
        Q_cycle=np.array(currents.Q_cycle),
        metadata=metadata,
    )


def _save_hold_npz(out_path, L, dt, hold):
    """Save hold-time result as npz."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        out_path,
        L=np.array(L),
        dt=np.array(dt),
        t_star=np.array(hold.t_star),
        t_star_over_T=np.array(hold.t_star_over_T),
        tau_h=hold.tau_h,
        Q_post=hold.Q_post,
        A_J_hold=hold.A_J_hold,
        R_J_hold=hold.R_J_hold,
        Phi_J_hold=hold.Phi_J_hold,
        cos_Phi_hold=hold.cos_Phi_hold,
        weights_hold=hold.weights_hold,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="RMH pump current coherence diagnostics"
    )
    parser.add_argument("--L", type=int, default=None,
                        help="Single system size to run")
    parser.add_argument("--all", action="store_true",
                        help="Run all L = 6, 8, 10")
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke test (10 steps only)")
    parser.add_argument("--dt", type=float, default=DT_DEFAULT,
                        help=f"Time step (default: {DT_DEFAULT})")
    parser.add_argument("--no-hold", action="store_true",
                        help="Skip hold-time interferometry scan")
    parser.add_argument("--no-slow-ref", action="store_true",
                        help="Skip slow reference protocol")
    parser.add_argument("--gauge-check", action="store_true",
                        help="Run gauge invariance verification")
    args = parser.parse_args()

    if args.all:
        L_list = L_DEFAULT_LIST
    elif args.L is not None:
        L_list = [args.L]
    else:
        print("Specify --L or --all")
        sys.exit(1)

    for L in L_list:
        run_single_L(
            L, dt=args.dt, smoke=args.smoke,
            do_hold=not args.no_hold,
            do_slow_ref=not args.no_slow_ref,
            do_gauge_check=args.gauge_check,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
