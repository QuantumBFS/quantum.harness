#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from long_range_percolation.validation import ValidationProtocol
from long_range_percolation.validation_shards import (
    merge_validation_shards,
    run_validation_cell,
    run_validation_global_checks,
    write_validation_run_spec,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and execute immutable Challenge 194 validation shards."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build-spec")
    build.add_argument("--protocol", choices=("production-v1",), required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--run-spec", type=Path, required=True)

    global_checks = commands.add_parser("run-global")
    global_checks.add_argument("--run-spec", type=Path, required=True)

    cell = commands.add_parser("run-cell")
    cell.add_argument("--run-spec", type=Path, required=True)
    cell.add_argument("--case-index", type=int, required=True)

    merge = commands.add_parser("merge")
    merge.add_argument("--run-spec", type=Path, required=True)
    merge.add_argument("--output", type=Path, required=True)
    return parser


def _production_protocol() -> ValidationProtocol:
    protocol = ValidationProtocol.production_v1()
    protocol.require_production()
    return protocol


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "build-spec":
            if arguments.run_spec.parent.resolve() != (
                arguments.output_root.resolve()
            ):
                raise ValueError("--run-spec must be directly under --output-root")
            document = write_validation_run_spec(
                _production_protocol(),
                arguments.output_root,
                arguments.run_spec,
            )
            result = {
                "status": "ready",
                "cells": len(document["cells"]),
                "run_spec": str(arguments.run_spec),
                "run_spec_sha256": document["run_spec_sha256"],
            }
        elif arguments.command == "run-global":
            manifest = run_validation_global_checks(arguments.run_spec)
            result = {
                "status": "success",
                "artifact": manifest["artifact_path"],
                "sha256": manifest["artifact_sha256"],
            }
        elif arguments.command == "run-cell":
            print(
                f"validation cell {arguments.case_index} started",
                flush=True,
            )
            result = {
                "status": "success",
                **run_validation_cell(
                    arguments.run_spec, arguments.case_index
                ),
            }
        else:
            report = merge_validation_shards(
                arguments.run_spec, arguments.output
            )
            result = {
                "status": "success" if report["passed"] else "scientific-failure",
                "passed": report["passed"],
                "families": report["family_count"],
                "minimum_margin": report["minimum_margin"],
                "output": str(arguments.output),
            }
            print(json.dumps(result, sort_keys=True), flush=True)
            return 0 if report["passed"] else 2
    except Exception as error:
        print(
            f"validation shard infrastructure failure: "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
