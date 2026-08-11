"""I/O utilities for pump correlation experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def save_result(
    out_path: Path,
    L: int,
    antiperiodic: bool,
    dt: float,
    T: float,
    U: float,
    delta_of_tau,
    Delta_of_tau,
    times: np.ndarray,
    C_spin: np.ndarray,
    C_charge: np.ndarray,
    bond_spin: np.ndarray,
    bond_charge: np.ndarray,
    norm_errors: list[float],
    wall_time_s: float,
    current_data: dict | None = None,
) -> None:
    """Save full results as compressed .npz with metadata.

    Parameters
    ----------
    current_data : dict or None
        Output from measure_currents(), serialised to dict with keys:
        bond_current, current_mean, current_even, current_odd,
        scaled_current, scaled_current_even, scaled_current_odd,
        Q, Q_even, Q_odd, Q_cycle, density_by_site, continuity_residual.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # evaluate pump parameters at save times
    delta_vals = np.array([delta_of_tau(t) for t in times])
    Delta_vals = np.array([Delta_of_tau(t) for t in times])

    metadata = json.dumps({
        "L": L,
        "antiperiodic": antiperiodic,
        "dt": dt,
        "T": T,
        "U": U,
        "wall_time_s": wall_time_s,
        "max_norm_error": float(max(norm_errors)) if norm_errors else 0.0,
    })

    save_dict = {
        "L": np.array(L),
        "tau": times,
        "tau_over_T": times / T,
        "delta": delta_vals,
        "Delta": Delta_vals,
        "C_spin": C_spin,
        "C_charge": C_charge,
        "bond_spin": bond_spin,
        "bond_charge": bond_charge,
        "norm_error": np.array(norm_errors),
        "antiperiodic": np.array(antiperiodic),
        "dt": np.array(dt),
        "U": np.array(U),
        "metadata": metadata,
    }

    if current_data is not None:
        save_dict.update({
            "bond_current": current_data["bond_current"],
            "current_mean": current_data["current_mean"],
            "current_even": current_data["current_even"],
            "current_odd": current_data["current_odd"],
            "scaled_current": current_data["scaled_current"],
            "scaled_current_even": current_data["scaled_current_even"],
            "scaled_current_odd": current_data["scaled_current_odd"],
            "Q": current_data["Q"],
            "Q_even": current_data["Q_even"],
            "Q_odd": current_data["Q_odd"],
            "Q_cycle": np.array(current_data["Q_cycle"]),
            "density_by_site": current_data["density_by_site"],
            "continuity_residual": np.array(current_data["continuity_residual"]),
        })

    np.savez_compressed(out_path, **save_dict)


def save_summary_csv(
    out_path: Path,
    results: dict[int, dict],
) -> None:
    """Save a combined CSV with τ/T, C_S, C_n for all L."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Find the union of all τ/T values
    all_tau_T = sorted(set().union(*[
        set(r["tau_over_T"]) for r in results.values()
    ]))

    with open(out_path, "w") as f:
        header = ["tau_over_T"] + [
            f"{key}_L{L}" for L in sorted(results.keys())
            for key in ["C_spin", "C_charge"]
        ]
        f.write(",".join(header) + "\n")

        # For each L, interpolate to common τ/T grid
        for t in all_tau_T:
            row = [f"{t:.6f}"]
            for L in sorted(results.keys()):
                r = results[L]
                # nearest-neighbor lookup
                idx = np.argmin(np.abs(r["tau_over_T"] - t))
                row.append(f"{r['C_spin'][idx]:.10f}")
                row.append(f"{r['C_charge'][idx]:.10f}")
            f.write(",".join(row) + "\n")
