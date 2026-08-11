"""I/O utilities for spinon-holon pump experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def save_defect_result(
    out_path: Path,
    L: int,
    antiperiodic: bool,
    dt: float,
    T: float,
    U: float,
    R_delta: float,
    phi_0: float,
    k0: float,
    sigma: float,
    protocol: str,
    defect,
    wall_time_s: float,
    extra: dict | None = None,
) -> None:
    """Save DefectResult as compressed .npz with metadata."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = json.dumps({
        "L": L,
        "antiperiodic": antiperiodic,
        "dt": dt,
        "T": T,
        "U": U,
        "R_delta": R_delta,
        "phi_0": phi_0,
        "k0": k0,
        "sigma": sigma,
        "protocol": protocol,
        "wall_time_s": wall_time_s,
    })

    save_dict = {
        "tau": defect.tau,
        "h_j": defect.h_j,
        "s_j": defect.s_j,
        "h_bar": defect.h_bar,
        "s_bar": defect.s_bar,
        "X_h": defect.X_h,
        "X_s": defect.X_s,
        "Z_h": defect.Z_h,
        "Z_s": defect.Z_s,
        "width_h": defect.width_h,
        "width_s": defect.width_s,
        "peak_h": defect.peak_h,
        "peak_s": defect.peak_s,
        "sum_h": defect.sum_h,
        "sum_s": defect.sum_s,
        "n_ref": defect.n_ref,
        "Sz_ref": defect.Sz_ref,
        "n_hole": defect.n_hole,
        "Sz_hole": defect.Sz_hole,
        "metadata": metadata,
    }

    if extra:
        for key, value in extra.items():
            save_dict[key] = value

    np.savez_compressed(out_path, **save_dict)


def load_defect_result(path: Path) -> dict:
    """Load a saved DefectResult .npz file."""
    data = np.load(path, allow_pickle=True)
    result = {key: data[key] for key in data.files}
    data.close()
    return result


def save_pump_result(
    out_path: Path,
    L: int,
    antiperiodic: bool,
    dt: float,
    T: float,
    U: float,
    R_delta: float,
    k0: float,
    sigma: float,
    direction: str,
    defect_ext,
    pump_odd,
    wall_time_s: float,
    extra: dict | None = None,
) -> None:
    """Save ExtendedDefectResult + PumpOddResult as compressed .npz."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = json.dumps({
        "L": L,
        "antiperiodic": antiperiodic,
        "dt": dt,
        "T": T,
        "U": U,
        "R_delta": R_delta,
        "k0": k0,
        "sigma": sigma,
        "direction": direction,
        "wall_time_s": wall_time_s,
    })

    d = defect_ext
    po = pump_odd

    save_dict: dict = {
        "tau": d.tau,
        # Hole sector
        "h_j": d.hole.h_j,
        "s_j": d.hole.s_j,
        "h_bar": d.hole.h_bar,
        "s_bar": d.hole.s_bar,
        "X_h": d.hole.X_h,
        "X_s": d.hole.X_s,
        "sum_h": d.hole.sum_h,
        "sum_s": d.hole.sum_s,
        # Particle sector
        "p_j": d.p_j,
        "s_j_plus": d.s_j_plus,
        "p_bar": d.p_bar,
        "s_plus_bar": d.s_plus_bar,
        "X_p": d.X_p,
        "X_s_plus": d.X_s_plus,
        "sum_p": d.sum_p,
        "sum_s_plus": d.sum_s_plus,
        # Pump-odd
        "dX_h_odd": po.dX_h_odd,
        "dX_p_odd": po.dX_p_odd,
        "dX_s_minus_odd": po.dX_s_minus_odd,
        "dX_s_plus_odd": po.dX_s_plus_odd,
        "X_h_frozen": po.X_h_frozen,
        "X_p_frozen": po.X_p_frozen,
        "hole_vs_particle_diff": po.hole_vs_particle_diff,
        "hole_charge_vs_spin_diff": po.hole_charge_vs_spin_diff,
        "particle_charge_vs_spin_diff": po.particle_charge_vs_spin_diff,
        # Metadata
        "metadata": metadata,
    }

    if extra:
        for key, value in extra.items():
            save_dict[key] = value

    np.savez_compressed(out_path, **save_dict)


def save_deconfinement_result(
    out_path: Path,
    L: int,
    antiperiodic: bool,
    dt: float,
    T: float,
    U: float,
    R_delta: float,
    k0: float,
    sigma: float,
    deconf,
    wall_time_s: float,
    extra: dict | None = None,
) -> None:
    """Save DeconfinementResult + per-protocol metrics as .npz."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = json.dumps({
        "L": L,
        "antiperiodic": antiperiodic,
        "dt": dt,
        "T": T,
        "U": U,
        "R_delta": R_delta,
        "k0": k0,
        "sigma": sigma,
        "wall_time_s": wall_time_s,
    })

    def _pack_rm(r):
        return {
            "O_hs": r.O_hs,
            "D_hs": r.D_hs,
            "xi_hs": r.xi_hs,
            "xi_hs_signed": r.xi_hs_signed,
            "P_hs": r.P_hs,
            "delta_D_hs": r.delta_D_hs if r.delta_D_hs is not None else np.array([]),
            "delta_xi_hs": r.delta_xi_hs if r.delta_xi_hs is not None else np.array([]),
        }

    save_dict: dict = {
        "tau": deconf.tau,
        "cw": _pack_rm(deconf.cw),
        "ccw": _pack_rm(deconf.ccw),
        "frozen": _pack_rm(deconf.frozen),
        "D_hs_odd": deconf.D_hs_odd,
        "xi_hs_odd": deconf.xi_hs_odd,
        "O_hs_odd": deconf.O_hs_odd,
        "metadata": metadata,
    }

    if extra:
        for key, value in extra.items():
            save_dict[key] = value

    np.savez_compressed(out_path, **save_dict)


def load_deconfinement_result(path: Path) -> dict:
    """Load a saved DeconfinementResult .npz file."""
    data = np.load(path, allow_pickle=True)
    result = {key: data[key] for key in data.files}
    data.close()
    return result
