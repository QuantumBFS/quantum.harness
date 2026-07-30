#!/usr/bin/env python3
"""Restartable worker CLI for the L=8 transport-visualization study."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.batch import (  # noqa: E402
    ParameterPoint,
    RealtimePoint,
    pair_checkpoint_name,
    realtime_result_name,
    static_result_name,
)
from src.cluster_workflows import (  # noqa: E402
    run_realtime_point,
    run_refinement_point,
    run_static_point,
    validate_realtime_result,
    validate_static_result,
)
from src.transport_study import (  # noqa: E402
    TransportCase,
    TransportRealtimeCase,
    realtime_cases,
    select_refinement_cases,
    static_cases,
)


def _pair(case: TransportCase) -> ParameterPoint:
    return ParameterPoint(index=case.index, U=case.U, t=case.t)


def _realtime(case: TransportRealtimeCase) -> RealtimePoint:
    return RealtimePoint(index=case.index, pair=_pair(case.static_case), period=case.period)


def _static_path(directory: Path, case: TransportCase) -> Path:
    return directory / static_result_name(_pair(case))


def _realtime_path(directory: Path, case: TransportRealtimeCase) -> Path:
    return directory / realtime_result_name(_realtime(case))


def _refined_path(directory: Path, case: TransportCase) -> Path:
    return directory / pair_checkpoint_name(_pair(case), 20)


def _validate_case_summary(summary: dict, case: TransportCase) -> None:
    expected = {
        "U": case.U,
        "t": case.t,
        "delta0": case.delta0,
        "Delta0": case.Delta0,
        "delta_center": case.delta_center,
        "Delta_center": case.Delta_center,
    }
    if any(float(summary.get(key, math.nan)) != value for key, value in expected.items()):
        raise ValueError(f"result parameters do not match transport case {case.key}")


def _validate_static(path: Path, case: TransportCase, L: int) -> dict:
    summary = validate_static_result(path, expected_point=_pair(case), expected_L=L)
    _validate_case_summary(summary, case)
    return summary


def _validate_realtime(path: Path, case: TransportRealtimeCase, L: int) -> dict:
    summary = validate_realtime_result(
        path, expected_point=_realtime(case), expected_L=L
    )
    _validate_case_summary(summary, case.static_case)
    return summary


def _read_task(path: Path, index: int, *, realtime: bool):
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    if index < 0 or index >= len(lines):
        raise IndexError("task id is outside the task map")
    record = json.loads(lines[index])
    return (
        TransportRealtimeCase.from_dict(record)
        if realtime
        else TransportCase.from_dict(record)
    )


def _emit(cases) -> None:
    for case in cases:
        print(json.dumps(case.as_dict(), sort_keys=True))


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    manifest = commands.add_parser("manifest")
    manifest.add_argument("--kind", choices=("static", "realtime"), required=True)
    missing = commands.add_parser("missing")
    missing.add_argument("--kind", choices=("static", "refine", "realtime"), required=True)
    missing.add_argument("--result-dir", type=Path, required=True)
    missing.add_argument("--static-dir", type=Path)
    missing.add_argument("--manifest", type=Path)
    missing.add_argument("--L", type=int, default=8)
    for name in ("static", "refine", "realtime"):
        worker = commands.add_parser(name)
        worker.add_argument("--task-map", type=Path, required=True)
        worker.add_argument("--task-id", type=int, required=True)
        worker.add_argument("--L", type=int, default=8)
        worker.add_argument("--static-dir", type=Path, required=True)
        worker.add_argument("--realtime-dir", type=Path, required=True)
        worker.add_argument("--chern-dir", type=Path, required=True)
        worker.add_argument("--refined-dir", type=Path, required=True)
    select = commands.add_parser("select")
    select.add_argument("--static-dir", type=Path, required=True)
    select.add_argument("--L", type=int, default=8)
    aggregate = commands.add_parser("aggregate")
    aggregate.add_argument("--static-dir", type=Path, required=True)
    aggregate.add_argument("--realtime-dir", type=Path, required=True)
    aggregate.add_argument("--refined-dir", type=Path, required=True)
    aggregate.add_argument("--refinement-manifest", type=Path, required=True)
    aggregate.add_argument("--output-dir", type=Path, required=True)
    aggregate.add_argument("--L", type=int, default=8)
    return parser


def _run(args: argparse.Namespace) -> None:
    if args.command == "manifest":
        _emit(static_cases() if args.kind == "static" else realtime_cases())
        return
    if args.command == "missing":
        if args.kind == "refine":
            if args.manifest is None or args.static_dir is None:
                raise ValueError("refine missing requires --manifest and --static-dir")
            cases = tuple(
                TransportCase.from_dict(json.loads(line))
                for line in args.manifest.read_text().splitlines()
                if line.strip()
            )
        else:
            cases = static_cases() if args.kind == "static" else realtime_cases()
        missing = []
        for case in cases:
            path = (
                _static_path(args.result_dir, case)
                if args.kind == "static"
                else _realtime_path(args.result_dir, case)
                if args.kind == "realtime"
                else _refined_path(args.result_dir, case)
            )
            if not path.is_file():
                missing.append(case)
            elif args.kind == "static":
                _validate_static(path, case, args.L)
            elif args.kind == "realtime":
                _validate_realtime(path, case, args.L)
            else:
                run_refinement_point(
                    _pair(case),
                    static_path=_static_path(args.static_dir, case),
                    refined_dir=args.result_dir,
                    target_grid=20,
                )
        _emit(missing)
        return
    if args.command == "select":
        cases = static_cases()
        summaries = {
            case.index: _validate_static(_static_path(args.static_dir, case), case, args.L)
            for case in cases
        }
        _emit(select_refinement_cases(cases, summaries))
        return
    if args.command == "static":
        case = _read_task(args.task_map, args.task_id, realtime=False)
        output = run_static_point(
            _pair(case),
            L=args.L,
            delta0=case.delta0,
            Delta0=case.Delta0,
            delta_center=case.delta_center,
            Delta_center=case.Delta_center,
            chern_sizes=(5, 10),
            polarization_points=10,
            chern_dir=args.chern_dir,
            static_dir=args.static_dir,
        )
        _validate_static(output, case, args.L)
        print(output)
        return
    if args.command == "refine":
        case = _read_task(args.task_map, args.task_id, realtime=False)
        output = run_refinement_point(
            _pair(case),
            static_path=_static_path(args.static_dir, case),
            refined_dir=args.refined_dir,
            target_grid=20,
        )
        print(output)
        return
    if args.command == "realtime":
        case = _read_task(args.task_map, args.task_id, realtime=True)
        static_path = _static_path(args.static_dir, case.static_case)
        _validate_static(static_path, case.static_case, args.L)
        output = run_realtime_point(
            _realtime(case),
            static_path=static_path,
            realtime_dir=args.realtime_dir,
            initial_steps=max(2, math.ceil(case.period / 0.05)),
            charge_tolerance=5e-3,
            max_refinements=3,
        )
        _validate_realtime(output, case, args.L)
        print(output)
        return
    refined_cases = tuple(
        TransportCase.from_dict(json.loads(line))
        for line in args.refinement_manifest.read_text().splitlines()
        if line.strip()
    )
    refined_by_index = {}
    for case in refined_cases:
        path = run_refinement_point(
            _pair(case),
            static_path=_static_path(args.static_dir, case),
            refined_dir=args.refined_dir,
            target_grid=20,
        )
        with np.load(path, allow_pickle=False) as data:
            metadata = json.loads(str(data["metadata_json"]))
        refined_by_index[case.index] = metadata["summary"]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    static_rows = []
    for case in static_cases():
        row = {**case.as_dict(), **_validate_static(_static_path(args.static_dir, case), case, args.L)}
        if case.index in refined_by_index:
            refined = refined_by_index[case.index]
            row.update(
                C_MB=float(refined["C_raw"]),
                C_MB_integer=int(refined["C_rounded"]),
                Delta_min=float(refined["gap_min"]),
                minimum_link_overlap=float(refined["min_link_overlap"]),
                maximum_abs_berry_flux=float(refined["max_abs_berry_curvature"]),
                chern_grid=20,
                chern_checkpoint=str(_refined_path(args.refined_dir, case).resolve()),
                refined=True,
            )
        else:
            row["refined"] = False
        row["efficiency_adiabatic"] = float(row["Q_adiabatic"]) / 2.0
        static_rows.append(row)
    final_static = {int(row["index"]): row for row in static_rows}
    realtime_rows = []
    for case in realtime_cases():
        row = {**case.static_case.as_dict(), **_validate_realtime(_realtime_path(args.realtime_dir, case), case, args.L)}
        static_row = final_static[case.static_case.index]
        row.update(
            C_MB=static_row["C_MB"],
            Delta_min=static_row["Delta_min"],
            Q_adiabatic=static_row["Q_adiabatic"],
            chern_grid=static_row["chern_grid"],
            refined=static_row["refined"],
        )
        row["efficiency"] = float(row["Q_real_time"]) / 2.0
        realtime_rows.append(row)
    _write_csv(args.output_dir / "static_summary.csv", static_rows)
    _write_csv(args.output_dir / "realtime_summary.csv", realtime_rows)
    (args.output_dir / "complete.json").write_text(
        json.dumps({"complete": True, "static": len(static_rows), "realtime": len(realtime_rows)}, indent=2) + "\n"
    )


if __name__ == "__main__":
    _run(_parser().parse_args())
