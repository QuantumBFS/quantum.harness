#!/usr/bin/python3
"""Run or verify the CPMC important-path pattern analysis."""

from __future__ import annotations

import argparse
import pathlib

from pattern_analysis.pipeline import (
    AnalysisConfig,
    run_analysis,
    verify_analysis,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--m6-results", type=pathlib.Path, required=True)
    parser.add_argument("--m4-results", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument(
        "--cpmc-audit",
        type=pathlib.Path,
        dest="executable",
        required=True,
    )
    parser.add_argument(
        "--trials", default="rhf_x,rhf_y,uhf"
    )
    parser.add_argument("--fraction", type=float, default=0.01)
    parser.add_argument("--progress-updates", type=int, default=20)
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = AnalysisConfig(
        m6_results=args.m6_results,
        m4_results=args.m4_results,
        output=args.output,
        executable=args.executable,
        trials=tuple(
            trial for trial in args.trials.split(",") if trial
        ),
        fraction=args.fraction,
        progress_updates=args.progress_updates,
    )
    if args.verify_only:
        result = verify_analysis(config)
        if result["valid"]:
            print("PASS: pattern analysis verification")
            return 0
        for error in result["errors"]:
            print(f"ERROR: {error}")
        return 1
    run_analysis(config)
    result = verify_analysis(config)
    if not result["valid"]:
        for error in result["errors"]:
            print(f"ERROR: {error}")
        return 1
    print("PASS: pattern analysis complete and verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
