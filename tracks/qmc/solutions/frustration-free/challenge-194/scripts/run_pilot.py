#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from long_range_percolation.pilot import (
    RUN_SPEC_NAME,
    build_pilot_run_spec,
    merge_pilot_progress,
    pending_pilot_cells,
    run_pilot_cell,
    verify_pilot_download,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build, run, merge, and verify Challenge 194 Pilot P0 cells."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build-spec")
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--run-spec", type=Path, required=True)
    build.add_argument("--validation-report", type=Path, required=True)

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
        elif arguments.command == "run-cell":
            print(f"pilot cell {arguments.cell_index} started", flush=True)
            result = {
                "status": "success",
                **run_pilot_cell(
                    arguments.run_spec.resolve(), arguments.cell_index
                ),
            }
        elif arguments.command == "merge":
            document = merge_pilot_progress(
                arguments.run_spec.resolve(),
                arguments.output.resolve() if arguments.output else None,
            )
            result = {
                "status": "success",
                "cells": document["cell_count"],
                "trajectories": document["trajectory_count"],
            }
        elif arguments.command == "verify":
            document = verify_pilot_download(arguments.run_spec.resolve())
            result = {
                "status": "verified",
                "cells": document["cell_count"],
                "trajectories": document["trajectory_count"],
            }
        else:
            cells = pending_pilot_cells(arguments.run_spec.resolve())
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
