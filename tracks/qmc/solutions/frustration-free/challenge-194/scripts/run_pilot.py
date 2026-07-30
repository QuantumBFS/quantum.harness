#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from long_range_percolation.pilot import (
    PILOT_RUN_SPEC_MAX_BYTES,
    RUN_SPEC_NAME,
    RUN_SPEC_SCHEMA,
    _read_canonical,
    _registered_schema,
    build_p0_extension_run_spec,
    build_pilot_run_spec,
    merge_p0_extension_progress,
    merge_pilot_progress,
    pending_p0_extension_cells,
    pending_pilot_cells,
    run_p0_extension_cell,
    run_pilot_cell,
    verify_p0_extension_download,
    verify_pilot_download,
)
from long_range_percolation.pilot_extension import EXTENSION_RUN_SPEC_SCHEMA


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build, run, merge, and verify Challenge 194 Pilot P0 cells."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build-spec")
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--run-spec", type=Path, required=True)
    build.add_argument("--validation-report", type=Path, required=True)

    extension = commands.add_parser("build-extension-spec")
    extension.add_argument("--protocol", type=Path, required=True)
    extension.add_argument("--validation-report", type=Path, required=True)
    extension.add_argument("--output-root", type=Path, required=True)
    extension.add_argument("--run-spec", type=Path, required=True)

    cell = commands.add_parser("run-cell")
    cell.add_argument("--run-spec", type=Path, required=True)
    cell.add_argument("--cell-index", type=int, required=True)

    merge = commands.add_parser("merge")
    merge.add_argument("--run-spec", type=Path, required=True)
    merge.add_argument("--output", type=Path)

    verify = commands.add_parser("verify")
    verify.add_argument("--run-spec", type=Path, required=True)

    pending = commands.add_parser("pending")
    pending.add_argument("--run-spec", type=Path, required=True)
    return parser


def _registered_operations(run_spec: Path):
    schema = _registered_schema(run_spec)
    if schema == RUN_SPEC_SCHEMA:
        return (
            run_pilot_cell,
            pending_pilot_cells,
            merge_pilot_progress,
            verify_pilot_download,
        )
    if schema == EXTENSION_RUN_SPEC_SCHEMA:
        return (
            run_p0_extension_cell,
            pending_p0_extension_cells,
            merge_p0_extension_progress,
            verify_p0_extension_download,
        )
    raise RuntimeError("registered Pilot run-spec schema is not supported")


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "build-spec":
            output_root = arguments.output_root.resolve()
            run_spec = arguments.run_spec.resolve()
            if run_spec != output_root / RUN_SPEC_NAME:
                raise RuntimeError("--run-spec must equal <output-root>/run_spec.json")
            document = build_pilot_run_spec(
                output_root, arguments.validation_report.resolve()
            )
            result = {
                "status": "ready",
                "cells": document["cell_count"],
                "run_spec": str(run_spec),
                "run_spec_sha256": document["run_spec_sha256"],
            }
        elif arguments.command == "build-extension-spec":
            output_root = arguments.output_root.resolve()
            run_spec = arguments.run_spec.resolve()
            if run_spec != output_root / RUN_SPEC_NAME:
                raise RuntimeError("--run-spec must equal <output-root>/run_spec.json")
            protocol, _ = _read_canonical(
                arguments.protocol.resolve(),
                "P0 extension protocol",
                maximum_size=PILOT_RUN_SPEC_MAX_BYTES,
            )
            document = build_p0_extension_run_spec(
                output_root,
                arguments.validation_report.resolve(),
                protocol,
            )
            result = {
                "status": "ready",
                "cells": 96,
                "run_spec": str(run_spec),
                "run_spec_sha256": document["run_spec_sha256"],
            }
        elif arguments.command == "run-cell":
            run_cell, _, _, _ = _registered_operations(arguments.run_spec.resolve())
            print(f"pilot cell {arguments.cell_index} started", flush=True)
            result = {
                "status": "success",
                **run_cell(
                    arguments.run_spec.resolve(), arguments.cell_index
                ),
            }
        elif arguments.command == "merge":
            _, _, merge_progress, _ = _registered_operations(
                arguments.run_spec.resolve()
            )
            document = merge_progress(
                arguments.run_spec.resolve(),
                arguments.output.resolve() if arguments.output else None,
            )
            result = {
                "status": "success",
                "cells": document["cell_count"],
                "trajectories": document["trajectory_count"],
            }
        elif arguments.command == "verify":
            _, _, _, verify_download = _registered_operations(
                arguments.run_spec.resolve()
            )
            document = verify_download(arguments.run_spec.resolve())
            result = {
                "status": "verified",
                "cells": document["cell_count"],
                "trajectories": document["trajectory_count"],
            }
        else:
            _, pending_cells, _, _ = _registered_operations(
                arguments.run_spec.resolve()
            )
            cells = pending_cells(arguments.run_spec.resolve())
            result = {
                "status": "pending",
                "count": len(cells),
                "cell_indices": cells,
            }
    except Exception as error:
        print(
            f"pilot infrastructure failure: {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
