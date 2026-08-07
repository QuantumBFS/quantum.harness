#!/usr/bin/env python3
"""Freeze a Stage 6 pilot manifest into a production-candidate contract."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence


TRACK_ROOT = Path(__file__).resolve().parents[1]
SRC = TRACK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spinglass3d.workflow import freeze_production_candidate  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        candidate = freeze_production_candidate(args.pilot, args.output)
    except (FileExistsError, FileNotFoundError, KeyError, TypeError, ValueError) as error:
        print(f"production candidate freeze failed closed: {error}", file=sys.stderr, flush=True)
        return 2
    print(
        f"classification={candidate['classification']} output={args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
