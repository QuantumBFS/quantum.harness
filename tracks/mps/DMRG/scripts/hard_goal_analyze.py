#!/usr/bin/env python3
"""Run hash-bound Stage 8 finite-size analysis as a standalone delegate."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys


TRACK_ROOT = Path(__file__).resolve().parents[1]
SRC = TRACK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spinglass3d.analysis import (  # noqa: E402
    load_production_summary,
    run_stage8_analysis,
    write_stage8_analysis,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _output_file(path: Path) -> Path:
    return path if path.suffix.lower() == ".json" else path / "analysis.json"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = _output_file(args.output)
    try:
        source = load_production_summary(args.production_summary)
        result = run_stage8_analysis(source)
        write_stage8_analysis(result, output)
    except (
        FileExistsError,
        FileNotFoundError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        print(f"Stage 8 analysis failed closed: {error}", file=sys.stderr, flush=True)
        return 2
    joint = result.fit_table["joint"]
    interval = joint.statistical_intervals["tc"]
    print(
        f"stage8 protocol_sha256={result.protocol_sha256} "
        f"joint_tc={joint.fit.tc:.12g} "
        f"bootstrap_95=[{interval.lower:.12g},{interval.upper:.12g}] "
        f"output={output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
