#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

SOLUTION_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = SOLUTION_DIR / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from challenge148.paper_fss import (  # noqa: E402
    analyze_paper_root,
    write_paper_analysis,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fit the validated 140-cell paper-aligned production root."
    )
    parser.add_argument("--production-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        analysis = analyze_paper_root(arguments.production_root.resolve())
        output = arguments.output.resolve()
        write_paper_analysis(output, analysis)
    except (OSError, ValueError) as exc:
        print(f"analyze_paper.py: {exc}", file=sys.stderr)
        return 1
    print(f"stage: {analysis['stage']}")
    print(f"analysis_sha256: {analysis['analysis_sha256']}")
    print(f"artifact: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
