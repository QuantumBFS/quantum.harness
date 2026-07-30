#!/usr/bin/env python3
"""Run one checkpointed scientific Stage 6 pilot cell."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence


TRACK_ROOT = Path(
    os.environ.get("HARNESS_TRACK_ROOT", str(Path(__file__).resolve().parents[1]))
).resolve()
REPO_ROOT = Path(
    os.environ.get("HARNESS_REPO_ROOT", str(TRACK_ROOT.parents[2]))
).resolve()
SRC = TRACK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spinglass3d.science_pilot import (  # noqa: E402
    CALIBRATION_COMPLETE,
    CORRECTNESS_FAILURE,
    PILOT_NEEDS_EXTENSION,
    PILOT_PASS,
    run_science_pilot,
)
from spinglass3d.stage6 import load_stage6_science_cell  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--require-platform", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--checkpoint-every", type=int, required=True)
    parser.add_argument("--measurement-cadence", type=int, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--calibration-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        spec, output = load_stage6_science_cell(
            args.run_spec,
            args.selector,
            track_root=TRACK_ROOT,
            repo_root=REPO_ROOT,
            measurement_cadence=args.measurement_cadence,
        )
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "cell_id": spec.cell_id,
                        "length": spec.length,
                        "temperature_count": len(spec.temperatures),
                        "chain_pairs": spec.chain_pairs,
                        "calibration_sweeps": spec.calibration_sweeps,
                        "equilibration_initial_sweeps": (
                            spec.equilibration_initial_sweeps
                        ),
                        "equilibration_maximum_sweeps": (
                            spec.equilibration_maximum_sweeps
                        ),
                        "measurement_sweeps": spec.measurement_sweeps,
                        "measurement_cadence": spec.measurement_cadence,
                        "spec_sha256": spec.sha256,
                        "output": str(output),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            return 0
        manifest = run_science_pilot(
            spec,
            output,
            required_platform=args.require_platform,
            checkpoint_every=args.checkpoint_every,
            resume=args.resume,
            calibration_only=args.calibration_only,
        )
    except Exception as error:
        print(
            f"Stage 6 science pilot cell failed closed: "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 2

    classification = manifest.get("classification")
    print(
        f"cell_id={manifest.get('cell_id')} classification={classification}",
        flush=True,
    )
    if classification in {CALIBRATION_COMPLETE, PILOT_PASS}:
        return 0
    if classification == PILOT_NEEDS_EXTENSION:
        return 3
    if classification == CORRECTNESS_FAILURE:
        return 2
    print(
        f"Stage 6 science pilot cell failed closed: "
        f"unknown classification {classification!r}",
        file=sys.stderr,
        flush=True,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
