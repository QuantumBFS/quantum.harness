#!/usr/bin/env python3
"""Run the complete pre-unblinding research workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def _run(arguments: list[str]) -> None:
    print("+", " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-moment-bootstrap",
        action="store_true",
        help="Use 100 pilot replicates for a quick infrastructure check.",
    )
    args = parser.parse_args()
    python = sys.executable
    manifest = "results_research_program/manifest.json"

    _run([python, "scripts/build_research_manifest.py"])
    _run([python, "scripts/validate_research_datasets.py"])
    _run([python, "scripts/run_convergence_audit.py"])
    moment = [
        python,
        "scripts/run_moment_bridge_audit.py",
        "--manifest",
        manifest,
    ]
    if args.skip_moment_bootstrap:
        moment.extend(["--bootstrap-replicates", "100"])
    _run(moment)
    _run(
        [
            python,
            "scripts/build_research_verdict.py",
            "--expect-phase0",
        ]
    )
    _run(
        [
            python,
            "scripts/run_cross_condition_audit.py",
            "--manifest",
            manifest,
        ]
    )
    _run(
        [
            python,
            "scripts/run_two_mode_comparison.py",
            "--manifest",
            manifest,
            "--seed",
            "20260729",
        ]
    )
    delta2 = ROOT / "data" / "kharkov_highT_delta2.npz"
    if delta2.exists():
        _run([python, "scripts/run_environment_control_comparison.py"])
    _run([python, "scripts/build_program_report.py"])
    print(
        "Pre-unblinding workflow complete. Production-B data remain blinded.",
        flush=True,
    )


if __name__ == "__main__":
    main()
