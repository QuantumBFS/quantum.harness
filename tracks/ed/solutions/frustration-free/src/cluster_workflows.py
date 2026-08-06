"""Per-key cluster workflows with validated, restartable result files."""

from __future__ import annotations

import csv
import json
from math import comb
import os
from pathlib import Path
from typing import Sequence
import uuid

import numpy as np

from .batch import (
    ParameterPoint,
    RealtimePoint,
    atomic_savez_exclusive,
    load_chern_checkpoint,
    pair_checkpoint_name,
    realtime_result_name,
    save_chern_checkpoint,
    static_result_name,
)
from .diagonalization import EDEngine
from .dynamics import converge_time_steps
from .model import ModelParameters, RiceMeleHubbardModel
from .topology import compute_adiabatic_charge, scan_chern


STATIC_SCHEMA_VERSION = 1
REALTIME_SCHEMA_VERSION = 1


def _engine(
    point: ParameterPoint,
    *,
    L: int,
    delta0: float,
    Delta0: float,
    delta_center: float = 0.0,
    Delta_center: float = 0.0,
) -> EDEngine:
    return EDEngine(
        RiceMeleHubbardModel(
            ModelParameters(
                L=L,
                t=point.t,
                delta0=delta0,
                Delta0=Delta0,
                delta_center=delta_center,
                Delta_center=Delta_center,
                U=point.U,
                N_up=L // 2,
                N_down=L // 2,
            )
        )
    )


def _find_checkpoint(
    point: ParameterPoint,
    *,
    grid_size: int,
    chern_dir: Path,
    resume_dirs: Sequence[Path | str],
) -> Path | None:
    name = pair_checkpoint_name(point, grid_size)
    for directory in (chern_dir, *(Path(value) for value in resume_dirs)):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def run_static_point(
    point: ParameterPoint,
    *,
    L: int,
    delta0: float,
    Delta0: float,
    delta_center: float = 0.0,
    Delta_center: float = 0.0,
    chern_sizes: Sequence[int],
    polarization_points: int,
    chern_dir: Path | str,
    static_dir: Path | str,
    resume_dirs: Sequence[Path | str] = (),
) -> Path:
    """Compute or reuse Chern/gap data and add the adiabatic charge."""
    if not chern_sizes:
        raise ValueError("at least one Chern grid size is required")
    sizes = tuple(int(value) for value in chern_sizes)
    for coarse, fine in zip(sizes, sizes[1:]):
        if fine <= coarse or fine % coarse:
            raise ValueError("Chern grids must be increasing nested multiples")
    chern_directory = Path(chern_dir)
    static_directory = Path(static_dir)
    output = static_directory / static_result_name(point)
    if output.exists():
        validate_static_result(output, expected_point=point, expected_L=L)
        return output

    engine = _engine(
        point,
        L=L,
        delta0=delta0,
        Delta0=Delta0,
        delta_center=delta_center,
        Delta_center=Delta_center,
    )
    max_size = sizes[-1]
    checkpoint = _find_checkpoint(
        point,
        grid_size=max_size,
        chern_dir=chern_directory,
        resume_dirs=resume_dirs,
    )
    reused = checkpoint is not None
    if checkpoint is None:
        results = tuple(
            scan_chern(engine, n_theta=size, n_phi=size) for size in sizes
        )
        checkpoint = chern_directory / pair_checkpoint_name(point, max_size)
        save_chern_checkpoint(
            checkpoint,
            engine,
            point=point,
            results=results,
        )
        chern_summary = results[-1].as_dict()
    else:
        loaded = load_chern_checkpoint(
            checkpoint,
            engine,
            point=point,
            grid_size=max_size,
        )
        chern_summary = dict(loaded.metadata["summary"])

    adiabatic = compute_adiabatic_charge(
        engine,
        n_phi=int(polarization_points),
    )
    summary = {
        "index": point.index,
        "L": L,
        "U": point.U,
        "t": point.t,
        "delta0": float(delta0),
        "Delta0": float(Delta0),
        "delta_center": float(delta_center),
        "Delta_center": float(Delta_center),
        "C_MB": float(chern_summary["C_raw"]),
        "C_MB_integer": int(chern_summary["C_rounded"]),
        "Delta_min": float(chern_summary["gap_min"]),
        "Q_adiabatic": float(adiabatic.charge),
        "minimum_link_overlap": float(chern_summary["min_link_overlap"]),
        "maximum_abs_berry_flux": float(
            chern_summary["max_abs_berry_curvature"]
        ),
        "minimum_resta_modulus": float(adiabatic.minimum_resta_modulus),
        "polarization_points_used": int(adiabatic.n_phi),
        "adiabatic_refinements": int(adiabatic.refinement_count),
        "adiabatic_convergence_error": float(
            adiabatic.charge_convergence_error
        ),
        "maximum_solver_residual": float(
            max(
                float(chern_summary["solver_residual"]),
                adiabatic.maximum_residual,
            )
        ),
        "chern_grid": max_size,
        "chern_checkpoint": str(checkpoint.resolve()),
        "chern_checkpoint_reused": reused,
    }
    metadata = {
        "schema_version": STATIC_SCHEMA_VERSION,
        "complete": True,
        "summary": summary,
    }
    atomic_savez_exclusive(
        output,
        {
            "schema_version": np.asarray(STATIC_SCHEMA_VERSION),
            "metadata_json": json.dumps(metadata, sort_keys=True),
            "phi": adiabatic.phi,
            "resta_values": adiabatic.resta_values,
            "polarization": adiabatic.polarization,
        },
    )
    validate_static_result(output, expected_point=point, expected_L=L)
    return output


def validate_static_result(
    path: Path | str,
    *,
    expected_point: ParameterPoint,
    expected_L: int,
) -> dict:
    output = Path(path)
    with np.load(output, allow_pickle=False) as data:
        if int(data["schema_version"]) != STATIC_SCHEMA_VERSION:
            raise ValueError("static result schema version is unsupported")
        metadata = json.loads(str(data["metadata_json"]))
        phi = np.asarray(data["phi"], dtype=np.float64)
        resta = np.asarray(data["resta_values"], dtype=np.complex128)
        polarization = np.asarray(data["polarization"], dtype=np.float64)
    if metadata.get("schema_version") != STATIC_SCHEMA_VERSION or not metadata.get(
        "complete"
    ):
        raise ValueError("static result is incomplete")
    summary = dict(metadata.get("summary", {}))
    expected = {
        "index": expected_point.index,
        "L": int(expected_L),
        "U": expected_point.U,
        "t": expected_point.t,
    }
    if any(summary.get(key) != value for key, value in expected.items()):
        raise ValueError("static result parameters do not match")
    if phi.ndim != 1 or resta.shape != phi.shape or polarization.shape != phi.shape:
        raise ValueError("static polarization arrays have inconsistent shapes")
    if phi.size < 3 or not all(
        np.all(np.isfinite(array)) for array in (phi, resta, polarization)
    ):
        raise ValueError("static polarization arrays are invalid")
    charge = float(polarization[-1] - polarization[0])
    if not np.isclose(charge, float(summary.get("Q_adiabatic", np.nan)), atol=1e-10):
        raise ValueError("static adiabatic charge is inconsistent")
    if not np.isclose(
        np.min(np.abs(resta)),
        float(summary.get("minimum_resta_modulus", np.nan)),
        atol=1e-10,
    ):
        raise ValueError("static Resta diagnostic is inconsistent")
    for key in ("C_MB", "Delta_min", "maximum_solver_residual"):
        if not np.isfinite(float(summary.get(key, np.nan))):
            raise ValueError(f"static summary field {key} is invalid")
    checkpoint = Path(str(summary.get("chern_checkpoint", "")))
    if not checkpoint.is_file():
        raise ValueError("referenced Chern checkpoint is missing")
    return summary


def run_refinement_point(
    point: ParameterPoint,
    *,
    static_path: Path | str,
    refined_dir: Path | str,
    target_grid: int,
) -> Path:
    """Refine one validated Chern grid by computing inserted vertices only."""
    static_file = Path(static_path)
    with np.load(static_file, allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"]))
    summary = dict(metadata.get("summary", {}))
    L = int(summary.get("L", -1))
    validate_static_result(static_file, expected_point=point, expected_L=L)
    source_grid = int(summary["chern_grid"])
    target_grid = int(target_grid)
    if target_grid <= source_grid or target_grid % source_grid:
        raise ValueError("target grid must be a larger multiple of the source grid")

    engine = _engine(
        point,
        L=L,
        delta0=float(summary["delta0"]),
        Delta0=float(summary["Delta0"]),
        delta_center=float(summary.get("delta_center", 0.0)),
        Delta_center=float(summary.get("Delta_center", 0.0)),
    )
    output = Path(refined_dir) / pair_checkpoint_name(point, target_grid)
    if output.exists():
        load_chern_checkpoint(
            output,
            engine,
            point=point,
            grid_size=target_grid,
        )
        return output
    load_chern_checkpoint(
        summary["chern_checkpoint"],
        engine,
        point=point,
        grid_size=source_grid,
    )
    refined = scan_chern(engine, n_theta=target_grid, n_phi=target_grid)
    save_chern_checkpoint(
        output,
        engine,
        point=point,
        results=(refined,),
    )
    return output


def run_realtime_point(
    point: RealtimePoint,
    *,
    static_path: Path | str,
    realtime_dir: Path | str,
    initial_steps: int,
    charge_tolerance: float,
    max_refinements: int,
) -> Path:
    """Evolve one `(U,t,T)` key from its validated static ground state."""
    static_file = Path(static_path)
    with np.load(static_file, allow_pickle=False) as data:
        static_metadata = json.loads(str(data["metadata_json"]))
    static_summary = dict(static_metadata.get("summary", {}))
    L = int(static_summary.get("L", -1))
    validate_static_result(
        static_file,
        expected_point=point.pair,
        expected_L=L,
    )
    output = Path(realtime_dir) / realtime_result_name(point)
    if output.exists():
        validate_realtime_result(output, expected_point=point, expected_L=L)
        return output

    engine = _engine(
        point.pair,
        L=L,
        delta0=float(static_summary["delta0"]),
        Delta0=float(static_summary["Delta0"]),
        delta_center=float(static_summary.get("delta_center", 0.0)),
        Delta_center=float(static_summary.get("Delta_center", 0.0)),
    )
    load_chern_checkpoint(
        static_summary["chern_checkpoint"],
        engine,
        point=point.pair,
        grid_size=int(static_summary["chern_grid"]),
    )
    convergence = converge_time_steps(
        engine,
        period=point.period,
        initial_steps=int(initial_steps),
        charge_tolerance=float(charge_tolerance),
        max_refinements=int(max_refinements),
    )
    result = convergence.fine
    summary = {
        "index": point.index,
        "pair_index": point.pair.index,
        "L": L,
        "U": point.pair.U,
        "t": point.pair.t,
        "delta0": float(static_summary["delta0"]),
        "Delta0": float(static_summary["Delta0"]),
        "delta_center": float(static_summary.get("delta_center", 0.0)),
        "Delta_center": float(static_summary.get("Delta_center", 0.0)),
        "period": point.period,
        "C_MB": float(static_summary["C_MB"]),
        "Delta_min": float(static_summary["Delta_min"]),
        "Q_adiabatic": float(static_summary["Q_adiabatic"]),
        "Q_real_time": float(result.charge),
        "coarse_charge": float(convergence.coarse.charge),
        "coarse_time_steps": int(convergence.coarse.n_steps),
        "time_steps": int(result.n_steps),
        "time_step_charge_error": float(convergence.charge_difference),
        "charge_tolerance": float(charge_tolerance),
        "time_step_refinements": int(convergence.refinement_count),
        "maximum_norm_error": float(result.maximum_norm_error),
        "final_ground_state_fidelity": float(result.final_ground_state_fidelity),
        "static_result": str(static_file.resolve()),
        "chern_checkpoint": str(static_summary["chern_checkpoint"]),
    }
    metadata = {
        "schema_version": REALTIME_SCHEMA_VERSION,
        "complete": True,
        "summary": summary,
    }
    atomic_savez_exclusive(
        output,
        {
            "schema_version": np.asarray(REALTIME_SCHEMA_VERSION),
            "metadata_json": json.dumps(metadata, sort_keys=True),
            "times": result.times,
            "midpoint_phi": result.midpoint_phi,
            "currents": result.currents,
            "cumulative_charge": result.cumulative_charge,
            "norms": result.norms,
            "final_state": result.final_state,
        },
    )
    validate_realtime_result(output, expected_point=point, expected_L=L)
    return output


def validate_realtime_result(
    path: Path | str,
    *,
    expected_point: RealtimePoint,
    expected_L: int,
) -> dict:
    output = Path(path)
    with np.load(output, allow_pickle=False) as data:
        if int(data["schema_version"]) != REALTIME_SCHEMA_VERSION:
            raise ValueError("real-time result schema version is unsupported")
        metadata = json.loads(str(data["metadata_json"]))
        times = np.asarray(data["times"], dtype=np.float64)
        midpoint_phi = np.asarray(data["midpoint_phi"], dtype=np.float64)
        currents = np.asarray(data["currents"], dtype=np.float64)
        cumulative = np.asarray(data["cumulative_charge"], dtype=np.float64)
        norms = np.asarray(data["norms"], dtype=np.float64)
        final_state = np.asarray(data["final_state"], dtype=np.complex128)
    if metadata.get("schema_version") != REALTIME_SCHEMA_VERSION or not metadata.get(
        "complete"
    ):
        raise ValueError("real-time result is incomplete")
    summary = dict(metadata.get("summary", {}))
    expected = {
        "index": expected_point.index,
        "pair_index": expected_point.pair.index,
        "L": int(expected_L),
        "U": expected_point.pair.U,
        "t": expected_point.pair.t,
        "period": expected_point.period,
    }
    if any(summary.get(key) != value for key, value in expected.items()):
        raise ValueError("real-time result parameters do not match")
    steps = int(summary.get("time_steps", -1))
    if (
        times.shape != (steps + 1,)
        or cumulative.shape != (steps + 1,)
        or norms.shape != (steps + 1,)
        or midpoint_phi.shape != (steps,)
        or currents.shape != (steps,)
    ):
        raise ValueError("real-time trace array shapes are inconsistent")
    dimension = comb(expected_L, expected_L // 2) ** 2
    if final_state.shape != (dimension,):
        raise ValueError("real-time final-state shape is inconsistent")
    arrays = (times, midpoint_phi, currents, cumulative, norms, final_state)
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ValueError("real-time result contains non-finite values")
    if not np.isclose(
        cumulative[-1],
        float(summary.get("Q_real_time", np.nan)),
        atol=1e-10,
    ):
        raise ValueError("real-time charge is inconsistent with its trace")
    if not np.isclose(np.linalg.norm(final_state), norms[-1], atol=1e-10):
        raise ValueError("real-time final-state norm is inconsistent")
    error = float(summary.get("time_step_charge_error", np.nan))
    tolerance = float(summary.get("charge_tolerance", np.nan))
    if not np.isfinite(error) or error > tolerance:
        raise ValueError("real-time time-step convergence is not satisfied")
    if float(summary.get("maximum_norm_error", np.inf)) > 1e-9:
        raise ValueError("real-time norm error exceeds tolerance")
    if not Path(str(summary.get("static_result", ""))).is_file():
        raise ValueError("referenced static result is missing")
    return summary


def missing_static_points(
    directory: Path | str,
    points: Sequence[ParameterPoint],
    *,
    L: int,
) -> tuple[ParameterPoint, ...]:
    root = Path(directory)
    missing: list[ParameterPoint] = []
    for point in points:
        path = root / static_result_name(point)
        if not path.is_file():
            missing.append(point)
        else:
            validate_static_result(path, expected_point=point, expected_L=L)
    return tuple(missing)


def missing_realtime_points(
    directory: Path | str,
    points: Sequence[RealtimePoint],
    *,
    L: int,
) -> tuple[RealtimePoint, ...]:
    root = Path(directory)
    missing: list[RealtimePoint] = []
    for point in points:
        path = root / realtime_result_name(point)
        if not path.is_file():
            missing.append(point)
        else:
            validate_realtime_result(path, expected_point=point, expected_L=L)
    return tuple(missing)


def missing_refinement_points(
    directory: Path | str,
    points: Sequence[ParameterPoint],
    *,
    static_dir: Path | str,
    target_grid: int,
    L: int,
) -> tuple[ParameterPoint, ...]:
    root = Path(directory)
    static_root = Path(static_dir)
    missing: list[ParameterPoint] = []
    for point in points:
        path = root / pair_checkpoint_name(point, target_grid)
        if not path.is_file():
            missing.append(point)
            continue
        static = validate_static_result(
            static_root / static_result_name(point),
            expected_point=point,
            expected_L=L,
        )
        engine = _engine(
            point,
            L=L,
            delta0=float(static["delta0"]),
            Delta0=float(static["Delta0"]),
            delta_center=float(static.get("delta_center", 0.0)),
            Delta_center=float(static.get("Delta_center", 0.0)),
        )
        load_chern_checkpoint(
            path,
            engine,
            point=point,
            grid_size=target_grid,
        )
    return tuple(missing)


def select_refinement_indices_from_summaries(
    rows: Sequence[dict],
    *,
    gap_threshold: float = 0.35,
    overlap_threshold: float = 0.35,
    flux_threshold: float = 0.75,
) -> tuple[int, ...]:
    selected = {
        int(row["index"])
        for row in rows
        if float(row["Delta_min"]) < gap_threshold
        or float(row["minimum_link_overlap"]) < overlap_threshold
        or float(row["maximum_abs_berry_flux"]) > flux_threshold
    }
    for coordinate, fixed in (("U", "t"), ("t", "U")):
        groups: dict[float, list[dict]] = {}
        for row in rows:
            groups.setdefault(float(row[fixed]), []).append(row)
        for group in groups.values():
            ordered = sorted(group, key=lambda row: float(row[coordinate]))
            for first, second in zip(ordered, ordered[1:]):
                if int(first["C_MB_integer"]) != int(second["C_MB_integer"]):
                    selected.update((int(first["index"]), int(second["index"])))
    return tuple(sorted(selected))


def _static_rows(
    directory: Path,
    points: Sequence[ParameterPoint],
    *,
    L: int,
) -> list[dict]:
    return [
        validate_static_result(
            directory / static_result_name(point),
            expected_point=point,
            expected_L=L,
        )
        for point in points
    ]


def _write_rows(path: Path, rows: Sequence[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("x", newline="", encoding="utf-8") as stream:
        if not fields:
            return
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def aggregate_complete_results(
    *,
    static_dir: Path | str,
    realtime_dir: Path | str,
    refined_dir: Path | str,
    output_dir: Path | str,
    points: Sequence[ParameterPoint],
    dynamics: Sequence[RealtimePoint],
    refinement_indices: Sequence[int],
    L: int,
    refined_grid: int,
) -> Path:
    """Publish summaries only after every expected result validates."""
    static_root = Path(static_dir)
    realtime_root = Path(realtime_dir)
    refined_root = Path(refined_dir)
    output = Path(output_dir)
    if output.exists():
        complete = json.loads((output / "run_complete.json").read_text())
        if (
            complete.get("static_count") != len(points)
            or complete.get("realtime_count") != len(dynamics)
            or complete.get("refinement_count") != len(refinement_indices)
        ):
            raise ValueError("existing aggregate does not match the manifest")
        return output

    missing_static = missing_static_points(static_root, points, L=L)
    if missing_static:
        raise ValueError(f"static results are missing: {[p.index for p in missing_static]}")
    missing_realtime = missing_realtime_points(realtime_root, dynamics, L=L)
    if missing_realtime:
        raise ValueError(
            f"real-time results are missing: {[p.index for p in missing_realtime]}"
        )

    point_by_index = {point.index: point for point in points}
    static_by_index = {
        int(row["index"]): row for row in _static_rows(static_root, points, L=L)
    }
    for index in refinement_indices:
        if index not in point_by_index:
            raise ValueError(f"unknown refinement index: {index}")
        point = point_by_index[index]
        static = static_by_index[index]
        engine = _engine(
            point,
            L=L,
            delta0=float(static["delta0"]),
            Delta0=float(static["Delta0"]),
            delta_center=float(static.get("delta_center", 0.0)),
            Delta_center=float(static.get("Delta_center", 0.0)),
        )
        path = refined_root / pair_checkpoint_name(point, refined_grid)
        if not path.is_file():
            raise ValueError(f"refinement result is missing: {index}")
        loaded = load_chern_checkpoint(
            path,
            engine,
            point=point,
            grid_size=refined_grid,
        )
        refined = loaded.metadata["summary"]
        static.update(
            {
                "C_MB": float(refined["C_raw"]),
                "C_MB_integer": int(refined["C_rounded"]),
                "Delta_min": float(refined["gap_min"]),
                "minimum_link_overlap": float(refined["min_link_overlap"]),
                "maximum_abs_berry_flux": float(
                    refined["max_abs_berry_curvature"]
                ),
                "chern_grid": refined_grid,
                "chern_checkpoint": str(path.resolve()),
                "refined": True,
            }
        )
    for row in static_by_index.values():
        row.setdefault("refined", False)

    realtime_rows = [
        validate_realtime_result(
            realtime_root / realtime_result_name(point),
            expected_point=point,
            expected_L=L,
        )
        for point in dynamics
    ]
    for row in realtime_rows:
        final_static = static_by_index[int(row["pair_index"])]
        row["C_MB"] = final_static["C_MB"]
        row["Delta_min"] = final_static["Delta_min"]
        row["Q_adiabatic"] = final_static["Q_adiabatic"]
        row["chern_grid"] = final_static["chern_grid"]

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(
        f".{output.name}.partial.{os.getpid()}.{uuid.uuid4().hex}"
    )
    partial.mkdir()
    static_rows = [static_by_index[point.index] for point in points]
    (partial / "static_summary.json").write_text(
        json.dumps(static_rows, indent=2, sort_keys=True) + "\n"
    )
    (partial / "realtime_summary.json").write_text(
        json.dumps(realtime_rows, indent=2, sort_keys=True) + "\n"
    )
    _write_rows(partial / "static_summary.csv", static_rows)
    _write_rows(partial / "realtime_summary.csv", realtime_rows)
    (partial / "run_complete.json").write_text(
        json.dumps(
            {
                "complete": True,
                "static_count": len(static_rows),
                "realtime_count": len(realtime_rows),
                "refinement_count": len(refinement_indices),
                "refinement_indices": list(refinement_indices),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    os.rename(partial, output)
    return output
