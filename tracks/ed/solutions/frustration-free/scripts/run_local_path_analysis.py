#!/usr/bin/env python3
"""Compute selected L=8 translated-path observables on the local machine."""

from __future__ import annotations

import argparse
import csv
from fractions import Fraction
import json
from pathlib import Path
import sys
import time

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.diagonalization import EDEngine  # noqa: E402
from src.dynamics import converge_time_steps  # noqa: E402
from src.model import ModelParameters, RiceMeleHubbardModel  # noqa: E402
from src.topology import (  # noqa: E402
    converge_fixed_twist_adiabatic_charge,
    scan_chern,
    wilson_loop_polarization,
)


U_VALUES = (-32.0, -16.0, -8.0, -4.0, 0.0, 2.0, 4.0, 5.0, 5.5, 6.0, 6.5, 7.0, 7.25, 7.5, 8.0, 10.0, 16.0, 32.0)
TYPICAL_U = (0.0, 7.25, 7.5, 16.0)
PATHS = (
    ("shift-1p5", 1.5, "shifted, enclosing origin"),
    ("near-tangent", 2.85, "near-tangent, enclosing origin"),
    ("outside", 3.6, "translated outside origin"),
)
ALL_PATHS = (("center", 0.0, "centered"),) + PATHS
CRITICAL_POINTS = {
    "center": (
        ("simultaneous", Fraction(1, 4), 7.372348498),
    ),
    "shift-1p5": (
        ("low", Fraction(3, 4), 4.352096694),
        ("high", Fraction(1, 4), 10.354477369),
    ),
    "near-tangent": (
        ("low", Fraction(3, 4), 0.882883835),
        ("high", Fraction(1, 4), 13.039003998),
    ),
    "outside": (
        ("low", Fraction(3, 4), 2.343682390),
        ("high", Fraction(1, 4), 14.531681175),
    ),
}
GAP_OFFSETS = (-1.0, -0.75, -0.5, -0.375, -0.25, -0.125, -0.0625, 0.0, 0.0625, 0.125, 0.25, 0.375, 0.5, 0.75, 1.0)
TORUS_OFFSETS = (-0.5, -0.125, 0.125, 0.5)
DELTA0_VALUES = (1.0, 2.0, 4.0, 5.0)
REALTIME_PATHS = PATHS


def _token(value: float) -> str:
    return f"{value:+.2f}".replace("+", "p").replace("-", "m").replace(".", "d")


def _engine(*, U: float, Delta0: float = 3.0, Delta_center: float = 0.0) -> EDEngine:
    return EDEngine(
        RiceMeleHubbardModel(
            ModelParameters(
                L=8,
                t=1.0,
                delta0=0.9,
                Delta0=Delta0,
                Delta_center=Delta_center,
                U=U,
                N_up=4,
                N_down=4,
            )
        )
    )


def _metadata(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as data:
        record = json.loads(str(data["metadata_json"]))
    if "phi_curve_error" in record and "phi_charge_error" not in record:
        record["phi_charge_error"] = record["phi_curve_error"]
        record["phi_curve_max_error"] = record.pop("phi_curve_error")
    return record


def _static_case(root: Path, path_id: str, center: float, label: str, U: float) -> dict:
    output = root / "static" / f"{path_id}_U_{_token(U)}.npz"
    if output.exists():
        return _metadata(output)
    started = time.perf_counter()
    engine = _engine(U=U, Delta_center=center)
    grid = 5
    try:
        torus = scan_chern(engine, n_theta=grid, n_phi=grid)
    except ValueError:
        grid = 10
        torus = scan_chern(engine, n_theta=grid, n_phi=grid)
    if (
        grid == 5
        and (
            torus.minimum_gap < 0.35
            or torus.fhs.maximum_absolute_flux > 0.65
            or torus.fhs.minimum_overlap < 0.35
        )
    ):
        grid = 10
        torus = scan_chern(engine, n_theta=grid, n_phi=grid)
    adiabatic = wilson_loop_polarization(torus.states)
    if not np.isclose(
        adiabatic.charge,
        torus.fhs.chern_raw,
        atol=1e-8,
        rtol=0.0,
    ):
        raise RuntimeError(
            f"Chern/polarization mismatch for {path_id}, U={U}: "
            f"{torus.fhs.chern_raw} versus {adiabatic.charge}"
        )
    record = {
        "path_id": path_id,
        "label": label,
        "Delta_center": center,
        "Delta0": 3.0,
        "U": U,
        "C_MB": torus.fhs.chern_raw,
        "C_MB_integer": torus.fhs.chern_integer,
        "Delta_min": torus.minimum_gap,
        "Q_adiabatic": adiabatic.charge,
        "efficiency_adiabatic": adiabatic.charge / 2.0,
        "chern_grid": grid,
        "minimum_overlap": torus.fhs.minimum_overlap,
        "maximum_abs_flux": torus.fhs.maximum_absolute_flux,
        "maximum_residual": torus.maximum_residual,
        "wall_time_s": time.perf_counter() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        np.savez_compressed(
            stream,
            metadata_json=json.dumps(record, sort_keys=True),
            phi=np.linspace(0.0, 2.0 * np.pi, grid + 1),
            polarization=adiabatic.polarization,
            e0=torus.ground_state_energies,
            gap=torus.gaps,
            flux=torus.fhs.flux,
        )
    return record


def _amplitude_case(root: Path, Delta0: float, U: float) -> dict:
    output = root / "amplitude" / f"Delta0_{_token(Delta0)}_U_{_token(U)}.npz"
    if output.exists():
        return _metadata(output)
    started = time.perf_counter()
    engine = _engine(U=U, Delta0=Delta0)
    grid = 5
    try:
        torus = scan_chern(engine, n_theta=grid, n_phi=grid)
    except ValueError:
        grid = 10
        torus = scan_chern(engine, n_theta=grid, n_phi=grid)
    if grid == 5 and torus.fhs.maximum_absolute_flux > 0.65:
        grid = 10
        torus = scan_chern(engine, n_theta=grid, n_phi=grid)
    adiabatic = wilson_loop_polarization(torus.states)
    record = {
        "Delta0": Delta0,
        "U": U,
        "Q_adiabatic": adiabatic.charge,
        "efficiency_adiabatic": adiabatic.charge / 2.0,
        "C_MB": torus.fhs.chern_raw,
        "Delta_min": torus.minimum_gap,
        "minimum_overlap": adiabatic.minimum_overlap,
        "polarization_points": grid,
        "maximum_residual": torus.maximum_residual,
        "wall_time_s": time.perf_counter() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        np.savez_compressed(
            stream,
            metadata_json=json.dumps(record, sort_keys=True),
            phi=np.linspace(0.0, 2.0 * np.pi, grid + 1),
            polarization=adiabatic.polarization,
            e0=torus.ground_state_energies,
            gap=torus.gaps,
            flux=torus.fhs.flux,
        )
    return record


def _realtime_case(root: Path, path_id: str, center: float, U: float, period: float) -> dict:
    output = root / "realtime" / f"{path_id}_U_{_token(U)}_T_{_token(period)}.npz"
    if output.exists():
        return _metadata(output)
    started = time.perf_counter()
    convergence = converge_time_steps(
        _engine(U=U, Delta_center=center),
        period=period,
        initial_steps=max(20, round(period / 0.05)),
        charge_tolerance=5e-3,
        max_refinements=3,
    )
    result = convergence.fine
    record = {
        "path_id": path_id,
        "Delta_center": center,
        "Delta0": 3.0,
        "U": U,
        "period": period,
        "Q_real_time": result.charge,
        "efficiency": result.charge / 2.0,
        "time_steps": result.n_steps,
        "time_step_error": convergence.charge_difference,
        "maximum_norm_error": result.maximum_norm_error,
        "wall_time_s": time.perf_counter() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        np.savez_compressed(
            stream,
            metadata_json=json.dumps(record, sort_keys=True),
            times=result.times,
            cumulative_charge=result.cumulative_charge,
            currents=result.currents,
            norms=result.norms,
        )
    return record


def _critical_gap_case(
    root: Path,
    path_id: str,
    center: float,
    branch: str,
    phi_fraction: Fraction,
    critical_u: float,
    offset: float,
) -> dict:
    U = critical_u + offset
    output = root / "critical_gap" / f"{path_id}_{branch}_U_{_token(U)}.npz"
    if output.exists():
        return _metadata(output)
    started = time.perf_counter()
    vertex = _engine(U=U, Delta_center=center).vertex(Fraction(0), phi_fraction)
    record = {
        "path_id": path_id,
        "Delta_center": center,
        "branch": branch,
        "critical_U": critical_u,
        "U": U,
        "U_offset": offset,
        "phi_fraction": float(phi_fraction),
        "phi_over_pi": 2.0 * float(phi_fraction),
        "Delta_min_line": vertex.gap,
        "E0": vertex.energies[0],
        "E1": vertex.energies[1],
        "maximum_residual": vertex.residual,
        "wall_time_s": time.perf_counter() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        np.savez_compressed(
            stream,
            metadata_json=json.dumps(record, sort_keys=True),
        )
    return record


def _refined_static_case(
    root: Path,
    path_id: str,
    center: float,
    label: str,
    branch: str,
    U: float,
) -> dict:
    output = root / "refined_static" / f"{path_id}_{branch}_U_{_token(U)}.npz"
    if output.exists():
        return _metadata(output)
    started = time.perf_counter()
    engine = _engine(U=U, Delta_center=center)
    torus = scan_chern(engine, n_theta=20, n_phi=20)
    adiabatic = wilson_loop_polarization(torus.states)
    if not np.isclose(adiabatic.charge, torus.fhs.chern_raw, atol=1e-8, rtol=0.0):
        raise RuntimeError(
            f"Chern/Wilson mismatch for {path_id}, U={U}: "
            f"{torus.fhs.chern_raw} versus {adiabatic.charge}"
        )
    record = {
        "path_id": path_id,
        "label": label,
        "Delta_center": center,
        "Delta0": 3.0,
        "branch": branch,
        "U": U,
        "C_MB": torus.fhs.chern_raw,
        "C_MB_integer": torus.fhs.chern_integer,
        "Delta_min": torus.minimum_gap,
        "Q_topological": adiabatic.charge,
        "efficiency_topological": adiabatic.charge / 2.0,
        "chern_grid": 20,
        "minimum_overlap": torus.fhs.minimum_overlap,
        "maximum_abs_flux": torus.fhs.maximum_absolute_flux,
        "maximum_residual": torus.maximum_residual,
        "wall_time_s": time.perf_counter() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        np.savez_compressed(
            stream,
            metadata_json=json.dumps(record, sort_keys=True),
            e0=torus.ground_state_energies,
            gap=torus.gaps,
            flux=torus.fhs.flux,
        )
    return record


def _fixed_adiabatic_case(
    root: Path,
    path_id: str,
    center: float,
    U: float,
) -> dict:
    output = root / "fixed_adiabatic" / f"{path_id}_U_{_token(U)}.npz"
    if output.exists():
        return _metadata(output)
    started = time.perf_counter()
    convergence = converge_fixed_twist_adiabatic_charge(
        _engine(U=U, Delta_center=center),
        n_phi=20,
        theta_fraction=Fraction(1, 64),
        curve_tolerance=2e-2,
        max_refinements=5,
    )
    result = convergence.result
    record = {
        "path_id": path_id,
        "Delta_center": center,
        "Delta0": 3.0,
        "U": U,
        "Q_adiabatic_fixed_theta": result.charge,
        "efficiency_fixed_theta": result.charge / 2.0,
        "n_phi": result.n_phi,
        "theta_fraction": str(result.theta_fraction),
        "theta_width": result.theta_width,
        "phi_charge_error": convergence.phi_charge_error,
        "phi_curve_max_error": convergence.phi_curve_max_error,
        "theta_curve_error": convergence.theta_curve_error,
        "refinement_count": convergence.refinement_count,
        "minimum_overlap": result.minimum_overlap,
        "maximum_abs_flux": result.maximum_absolute_flux,
        "maximum_residual": result.maximum_residual,
        "wall_time_s": time.perf_counter() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        np.savez_compressed(
            stream,
            metadata_json=json.dumps(record, sort_keys=True),
            phi=result.phi,
            cumulative_charge=result.cumulative_charge,
            strip_flux=result.strip_flux,
        )
    return record


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    static_rows = []
    for path_id, center, label in PATHS:
        for U in U_VALUES:
            row = _static_case(args.output, path_id, center, label, U)
            static_rows.append(row)
            print("static", path_id, U, row["C_MB_integer"], f"gap={row['Delta_min']:.4g}", flush=True)
    amplitude_rows = []
    for Delta0 in DELTA0_VALUES:
        for U in U_VALUES:
            row = _amplitude_case(args.output, Delta0, U)
            amplitude_rows.append(row)
            print("amplitude", Delta0, U, f"eta={row['efficiency_adiabatic']:.3g}", flush=True)
    realtime_rows = []
    for path_id, center, _ in REALTIME_PATHS:
        for U in TYPICAL_U:
            for period in (2.0, 10.0):
                row = _realtime_case(args.output, path_id, center, U, period)
                realtime_rows.append(row)
                print("realtime", path_id, U, period, f"Q={row['Q_real_time']:.5g}", flush=True)
    critical_gap_rows = []
    refined_static_rows = []
    path_by_id = {
        path_id: (center, label)
        for path_id, center, label in ALL_PATHS
    }
    for path_id, transitions in CRITICAL_POINTS.items():
        center, label = path_by_id[path_id]
        for branch, phi_fraction, critical_u in transitions:
            for offset in GAP_OFFSETS:
                row = _critical_gap_case(
                    args.output,
                    path_id,
                    center,
                    branch,
                    phi_fraction,
                    critical_u,
                    offset,
                )
                critical_gap_rows.append(row)
                print("critical-gap", path_id, branch, f"U={row['U']:.6f}", f"gap={row['Delta_min_line']:.4g}", flush=True)
            for offset in TORUS_OFFSETS:
                U = critical_u + offset
                row = _refined_static_case(
                    args.output,
                    path_id,
                    center,
                    label,
                    branch,
                    U,
                )
                refined_static_rows.append(row)
                print("refined-static", path_id, branch, f"U={U:.6f}", row["C_MB_integer"], f"gap={row['Delta_min']:.4g}", flush=True)
    fixed_adiabatic_rows = []
    for path_id, center, _ in ALL_PATHS:
        for U in TYPICAL_U:
            row = _fixed_adiabatic_case(args.output, path_id, center, U)
            fixed_adiabatic_rows.append(row)
            print("fixed-adiabatic", path_id, U, f"Q={row['Q_adiabatic_fixed_theta']:.5g}", f"Nphi={row['n_phi']}", flush=True)
    _write_csv(args.output / "static_summary.csv", static_rows)
    _write_csv(args.output / "amplitude_summary.csv", amplitude_rows)
    _write_csv(args.output / "realtime_summary.csv", realtime_rows)
    _write_csv(args.output / "critical_gap_summary.csv", critical_gap_rows)
    _write_csv(args.output / "refined_static_summary.csv", refined_static_rows)
    _write_csv(args.output / "fixed_adiabatic_summary.csv", fixed_adiabatic_rows)
    (args.output / "complete.json").write_text(
        json.dumps(
            {
                "complete": True,
                "static": len(static_rows),
                "amplitude": len(amplitude_rows),
                "realtime": len(realtime_rows),
                "critical_gap": len(critical_gap_rows),
                "refined_static": len(refined_static_rows),
                "fixed_adiabatic": len(fixed_adiabatic_rows),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
