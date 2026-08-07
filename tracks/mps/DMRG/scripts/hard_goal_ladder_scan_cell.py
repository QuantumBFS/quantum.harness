#!/usr/bin/env python3
"""Run one immutable adaptive temperature-ladder scan cell."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence


TRACK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(
    os.environ.get("HARNESS_REPO_ROOT", str(TRACK_ROOT.parents[2]))
).resolve()
SRC = TRACK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spinglass3d.ladder_scan import (  # noqa: E402
    load_ladder_scan_cell,
    run_ladder_scan_cell,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--require-platform", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--checkpoint-every", type=int, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.dry_run:
            spec, output = load_ladder_scan_cell(
                args.run_spec,
                args.selector,
                track_root=TRACK_ROOT,
                repo_root=REPO_ROOT,
            )
            print(
                json.dumps(
                    {
                        "cell_id": spec.cell_id,
                        "length": spec.length,
                        "temperature_count": len(spec.temperatures),
                        "chain_pairs": spec.chain_pairs,
                        "calibration_sweeps": spec.calibration_sweeps,
                        "spec_sha256": spec.sha256,
                        "output": str(output),
                        "predicted_only": True,
                        "measured_success": False,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            return 0
        manifest = run_ladder_scan_cell(
            args.run_spec,
            args.selector,
            required_platform=args.require_platform,
            checkpoint_every=args.checkpoint_every,
            resume=args.resume,
            track_root=TRACK_ROOT,
            repo_root=REPO_ROOT,
        )
    except (
        FileExistsError,
        FileNotFoundError,
        KeyError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        print(f"ladder-scan cell failed closed: {error}", file=sys.stderr, flush=True)
        return 2
    print(
        f"cell_id={manifest['cell_id']} "
        f"classification={manifest['classification']} "
        f"ladder_decision={manifest['parallel_tempering']['ladder_decision']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
