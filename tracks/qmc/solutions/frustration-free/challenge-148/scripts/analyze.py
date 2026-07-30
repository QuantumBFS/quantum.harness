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

from challenge148.fss import (  # noqa: E402
    analyze_extended_production_roots,
    analyze_production_root,
    write_analysis_artifact,
)


def _bootstrap_replicates(value: str) -> int:
    try:
        replicates = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "bootstrap replicates must be an integer of at least two"
        ) from exc
    if replicates < 2:
        raise argparse.ArgumentTypeError(
            "bootstrap replicates must be an integer of at least two"
        )
    return replicates


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze the validated 72-cell Challenge 148 QMC_SSE coarse "
            "production root and freeze its finite-size refinement window."
        )
    )
    parser.add_argument("--production-root", required=True, type=Path)
    parser.add_argument("--extension-root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--bootstrap-replicates", type=_bootstrap_replicates, default=4096
    )
    parser.add_argument("--bootstrap-seed", type=int, default=148)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        production_root = arguments.production_root.resolve()
        output = arguments.output.resolve()
        if arguments.extension_root is None:
            analysis = analyze_production_root(
                production_root,
                bootstrap_replicates=arguments.bootstrap_replicates,
                bootstrap_seed=arguments.bootstrap_seed,
            )
        else:
            analysis = analyze_extended_production_roots(
                production_root,
                arguments.extension_root.resolve(),
                bootstrap_replicates=arguments.bootstrap_replicates,
                bootstrap_seed=arguments.bootstrap_seed,
            )
        write_analysis_artifact(output, analysis)
    except (OSError, ValueError) as exc:
        print(f"analyze.py: {exc}", file=sys.stderr)
        return 1

    print(f"stage: {analysis['stage']}")
    print(f"analysis_sha256: {analysis['analysis_sha256']}")
    print(f"artifact: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
