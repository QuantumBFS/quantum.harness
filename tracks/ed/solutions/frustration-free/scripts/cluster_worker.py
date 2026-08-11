#!/usr/bin/env python3
"""Manifest-strict worker and aggregation CLI for the L=8 cluster scan."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.batch import (  # noqa: E402
    ParameterPoint,
    RealtimePoint,
    pair_checkpoint_name,
    parameter_points,
    realtime_points,
    static_result_name,
)
from src.cluster_workflows import (  # noqa: E402
    aggregate_complete_results,
    missing_refinement_points,
    missing_realtime_points,
    missing_static_points,
    run_realtime_point,
    run_refinement_point,
    run_static_point,
    select_refinement_indices_from_summaries,
    validate_static_result,
)


def _point_record(point: ParameterPoint) -> dict:
    return {"index": point.index, "U": point.U, "t": point.t}


def _realtime_record(point: RealtimePoint) -> dict:
    return {
        "index": point.index,
        "pair_index": point.pair.index,
        "U": point.pair.U,
        "t": point.pair.t,
        "period": point.period,
    }


def _emit(records) -> None:
    for record in records:
        print(json.dumps(record, sort_keys=True))


def _read_records(path: Path) -> list[dict]:
    records = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON on {path}:{line_number}") from error
        if not isinstance(record, dict):
            raise ValueError(f"task record on {path}:{line_number} is not an object")
        records.append(record)
    return records


def _parameter_from_record(record: dict) -> ParameterPoint:
    index = int(record.get("index", -1))
    manifest = parameter_points()
    if index < 0 or index >= len(manifest):
        raise ValueError(f"parameter index is outside the canonical manifest: {index}")
    point = manifest[index]
    if record != _point_record(point):
        raise ValueError(f"parameter record does not match canonical index {index}")
    return point


def _realtime_from_record(record: dict) -> RealtimePoint:
    index = int(record.get("index", -1))
    manifest = realtime_points()
    if index < 0 or index >= len(manifest):
        raise ValueError(f"real-time index is outside the canonical manifest: {index}")
    point = manifest[index]
    if record != _realtime_record(point):
        raise ValueError(f"real-time record does not match canonical index {index}")
    return point


def _task_record(args: argparse.Namespace) -> dict:
    records = _read_records(args.task_map)
    if args.task_id < 0 or args.task_id >= len(records):
        raise IndexError(f"task id {args.task_id} is outside the task map")
    return records[args.task_id]


def _add_model_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--L", type=int, default=8)
    parser.add_argument("--delta0", type=float, default=0.9)
    parser.add_argument("--Delta0", type=float, default=3.0)


def _add_task_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-map", type=Path, required=True)
    parser.add_argument("--task-id", type=int, required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    manifest = commands.add_parser("manifest")
    manifest.add_argument("--kind", choices=("static", "realtime"), required=True)

    missing = commands.add_parser("missing")
    missing.add_argument(
        "--kind",
        choices=("static", "refine", "realtime"),
        required=True,
    )
    missing.add_argument("--result-dir", type=Path, required=True)
    missing.add_argument("--L", type=int, default=8)
    missing.add_argument("--manifest", type=Path)
    missing.add_argument("--static-dir", type=Path)
    missing.add_argument("--target-grid", type=int, default=20)

    static = commands.add_parser("static")
    _add_task_arguments(static)
    _add_model_arguments(static)
    static.add_argument("--chern-sizes", type=int, nargs="+", default=(5, 10))
    static.add_argument("--polarization-points", type=int, default=10)
    static.add_argument("--chern-dir", type=Path, required=True)
    static.add_argument("--static-dir", type=Path, required=True)
    static.add_argument("--resume-dir", type=Path, action="append", default=[])

    refine = commands.add_parser("refine")
    _add_task_arguments(refine)
    refine.add_argument("--static-dir", type=Path, required=True)
    refine.add_argument("--refined-dir", type=Path, required=True)
    refine.add_argument("--target-grid", type=int, default=20)

    realtime = commands.add_parser("realtime")
    _add_task_arguments(realtime)
    realtime.add_argument("--static-dir", type=Path, required=True)
    realtime.add_argument("--realtime-dir", type=Path, required=True)
    realtime.add_argument("--initial-time-step", type=float, default=0.05)
    realtime.add_argument("--charge-tolerance", type=float, default=5e-3)
    realtime.add_argument("--max-refinements", type=int, default=3)

    select = commands.add_parser("select")
    select.add_argument("--static-dir", type=Path, required=True)
    select.add_argument("--L", type=int, default=8)

    aggregate = commands.add_parser("aggregate")
    aggregate.add_argument("--static-dir", type=Path, required=True)
    aggregate.add_argument("--realtime-dir", type=Path, required=True)
    aggregate.add_argument("--refined-dir", type=Path, required=True)
    aggregate.add_argument("--output-dir", type=Path, required=True)
    aggregate.add_argument("--refinement-manifest", type=Path, required=True)
    aggregate.add_argument("--refined-grid", type=int, default=20)
    aggregate.add_argument("--L", type=int, default=8)
    return parser


def _run(args: argparse.Namespace) -> None:
    if args.command == "manifest":
        records = (
            (_point_record(point) for point in parameter_points())
            if args.kind == "static"
            else (_realtime_record(point) for point in realtime_points())
        )
        _emit(records)
        return
    if args.command == "missing":
        if args.kind == "static":
            missing = missing_static_points(
                args.result_dir,
                parameter_points(),
                L=args.L,
            )
            _emit(_point_record(point) for point in missing)
        elif args.kind == "realtime":
            missing = missing_realtime_points(
                args.result_dir,
                realtime_points(),
                L=args.L,
            )
            _emit(_realtime_record(point) for point in missing)
        else:
            if args.manifest is None or args.static_dir is None:
                raise ValueError("refine missing requires --manifest and --static-dir")
            selected = tuple(
                _parameter_from_record(record)
                for record in _read_records(args.manifest)
            )
            missing = missing_refinement_points(
                args.result_dir,
                selected,
                static_dir=args.static_dir,
                target_grid=args.target_grid,
                L=args.L,
            )
            _emit(_point_record(point) for point in missing)
        return
    if args.command == "static":
        point = _parameter_from_record(_task_record(args))
        output = run_static_point(
            point,
            L=args.L,
            delta0=args.delta0,
            Delta0=args.Delta0,
            chern_sizes=args.chern_sizes,
            polarization_points=args.polarization_points,
            chern_dir=args.chern_dir,
            static_dir=args.static_dir,
            resume_dirs=args.resume_dir,
        )
        print(json.dumps({"kind": "static", "index": point.index, "output": str(output.resolve())}))
        return
    if args.command == "refine":
        point = _parameter_from_record(_task_record(args))
        output = run_refinement_point(
            point,
            static_path=args.static_dir / static_result_name(point),
            refined_dir=args.refined_dir,
            target_grid=args.target_grid,
        )
        print(json.dumps({"kind": "refine", "index": point.index, "output": str(output.resolve())}))
        return
    if args.command == "realtime":
        point = _realtime_from_record(_task_record(args))
        if args.initial_time_step <= 0.0:
            raise ValueError("initial-time-step must be positive")
        initial_steps = max(2, math.ceil(point.period / args.initial_time_step))
        output = run_realtime_point(
            point,
            static_path=args.static_dir / static_result_name(point.pair),
            realtime_dir=args.realtime_dir,
            initial_steps=initial_steps,
            charge_tolerance=args.charge_tolerance,
            max_refinements=args.max_refinements,
        )
        print(json.dumps({"kind": "realtime", "index": point.index, "output": str(output.resolve())}))
        return
    if args.command == "select":
        points = parameter_points()
        missing = missing_static_points(args.static_dir, points, L=args.L)
        if missing:
            raise ValueError("cannot select refinements before static manifest is complete")
        rows = [
            validate_static_result(
                args.static_dir / static_result_name(point),
                expected_point=point,
                expected_L=args.L,
            )
            for point in points
        ]
        indices = select_refinement_indices_from_summaries(rows)
        _emit(_point_record(points[index]) for index in indices)
        return
    records = _read_records(args.refinement_manifest)
    refinement_indices = tuple(
        _parameter_from_record(record).index for record in records
    )
    output = aggregate_complete_results(
        static_dir=args.static_dir,
        realtime_dir=args.realtime_dir,
        refined_dir=args.refined_dir,
        output_dir=args.output_dir,
        points=parameter_points(),
        dynamics=realtime_points(),
        refinement_indices=refinement_indices,
        L=args.L,
        refined_grid=args.refined_grid,
    )
    print(json.dumps({"kind": "aggregate", "output": str(output.resolve())}))


def main() -> None:
    _run(_parser().parse_args())


if __name__ == "__main__":
    main()
