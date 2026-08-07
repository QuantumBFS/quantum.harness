#!/usr/bin/env python3
"""Entry point for fail-closed Hard Goal workflow stages."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
from pathlib import Path
import subprocess
import sys
from typing import Sequence


TRACK_ROOT = Path(__file__).resolve().parents[1]
SRC = TRACK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spinglass3d.workflow import (
    CORRECTNESS_FAILURE,
    prepare_pilot_run,
    run_stage4,
    run_stage5,
)
from spinglass3d.production import preview_slurm, run_cell  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Hard Goal workflow gates")
    subcommands = parser.add_subparsers(dest="stage", required=True)
    stage4 = subcommands.add_parser(
        "stage4", description="Run the two-dimensional MPS regression gate"
    )
    stage4.add_argument("--config", type=Path, required=True)
    stage4.add_argument("--output", type=Path, required=True)
    validate = subcommands.add_parser(
        "validate", description="Run the exact and small-3D Stage 5 gate"
    )
    validate.add_argument("--config", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    pilot_plan = subcommands.add_parser(
        "pilot-plan",
        description="Build an immutable Stage 6 launch package",
    )
    pilot_plan.add_argument("--config", type=Path, required=True)
    pilot_plan.add_argument("--backend-evidence", type=Path, required=True)
    pilot_plan.add_argument("--output", type=Path, required=True)
    preview = subcommands.add_parser(
        "preview-slurm",
        description="Run Stage 7 precheck, queue probe, and scheduler test-only",
    )
    preview.add_argument("--candidate", type=Path, required=True)
    preview.add_argument("--run-spec", type=Path, required=True)
    preview.add_argument("--script", type=Path, required=True)
    preview.add_argument("--profile-from-candidate", action="store_true", required=True)
    cell = subcommands.add_parser(
        "cell",
        description="Validate one approved Stage 7 cell without fabricating compute",
    )
    cell.add_argument("--run-spec", type=Path, required=True)
    cell.add_argument("--selector", required=True)
    cell.add_argument("--approved-run-spec-sha256", required=True)
    cell.add_argument("--resume", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    command_runner: Callable[..., object] = subprocess.run,
) -> int:
    args = build_parser().parse_args(argv)
    if args.stage == "preview-slurm":
        try:
            preview = preview_slurm(
                args.candidate,
                args.run_spec,
                args.script,
                command_runner=command_runner,
            )
        except (FileNotFoundError, RuntimeError, TypeError, ValueError) as error:
            print(f"preview-slurm failed closed: {error}", file=sys.stderr, flush=True)
            return 2
        print(json.dumps(preview.to_dict(), sort_keys=True), flush=True)
        return 0
    if args.stage == "cell":
        try:
            manifest = run_cell(
                args.run_spec,
                args.selector,
                approved_run_spec_sha256=args.approved_run_spec_sha256,
            )
        except (
            FileExistsError,
            FileNotFoundError,
            KeyError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            print(f"cell failed closed: {error}", file=sys.stderr, flush=True)
            return 2
        if not manifest.terminal:
            print(
                "cell failed closed: Stage 7 compute backend is not frozen; "
                "refusing to fabricate output",
                file=sys.stderr,
                flush=True,
            )
            return 2
        print(
            f"cell_id={manifest.cell_id} classification={manifest.classification}",
            flush=True,
        )
        return manifest.exit_code
    if args.stage == "pilot-plan":
        try:
            launch = prepare_pilot_run(
                args.config,
                args.backend_evidence,
                args.output,
            )
        except (
            FileExistsError,
            FileNotFoundError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            print(f"pilot-plan failed closed: {error}", file=sys.stderr, flush=True)
            return 2
        print(
            f"classification={launch['classification']} "
            f"cells={launch['cell_count']} output={args.output}",
            flush=True,
        )
        return 0
    runner = run_stage4 if args.stage == "stage4" else run_stage5
    try:
        manifest = runner(args.config, args.output)
    except (FileExistsError, FileNotFoundError, RuntimeError, TypeError, ValueError) as error:
        print(f"{args.stage} failed closed: {error}", file=sys.stderr, flush=True)
        return 2
    if args.stage == "stage4":
        print(
            f"classification={manifest.classification} "
            "regression-only; not 3D Hard Goal evidence",
            flush=True,
        )
    else:
        print(f"classification={manifest.classification}", flush=True)
    return 2 if manifest.classification == CORRECTNESS_FAILURE else 0


if __name__ == "__main__":
    raise SystemExit(main())
