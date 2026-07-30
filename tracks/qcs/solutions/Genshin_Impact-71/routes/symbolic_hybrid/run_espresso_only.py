#!/usr/bin/env python3
"""Run standalone Berkeley Espresso on incomplete PLAs and audit its circuits."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

import routes
from run_experiments import abc_map, convert_and_audit, run_logged


def run_one(name: str, work: Path, abc: Path, espresso: Path) -> dict[str, object]:
    directory = work / name
    source = directory / "train-incomplete.pla"
    minimized = directory / "espresso-minimized.pla"
    run_logged(
        (str(espresso), "-o", "f", str(source)),
        directory / "espresso.log",
        stdout_path=minimized,
    )

    mapped = directory / "espresso-incomplete-k2.blif"
    abc_map(abc, minimized, mapped, directory / "abc-espresso-incomplete.log")
    challenge = directory / "espresso-incomplete.txt"
    audit_path = directory / "espresso-incomplete-audit.json"
    audit = convert_and_audit(
        directory / "discovery.json",
        mapped,
        challenge,
        audit_path,
        require_exact=False,
    )
    result = {
        "instance": name,
        "input_pla": str(source),
        "minimized_pla": str(minimized),
        "mapped_blif": str(mapped),
        "challenge": str(challenge),
        "audit": str(audit_path),
        "result": audit,
    }
    routes.atomic_json(directory / "espresso-flow-summary.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True)
    parser.add_argument("--abc", required=True)
    parser.add_argument("--espresso", required=True)
    args = parser.parse_args()
    work = Path(args.work).resolve()
    abc = Path(args.abc).resolve()
    espresso = Path(args.espresso).resolve()
    for executable in (abc, espresso):
        if not os.access(executable, os.X_OK):
            raise ValueError(f"executable missing: {executable}")

    espresso_help = subprocess.run(
        (str(espresso), "-h"),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    ).stdout
    abc_version = subprocess.run(
        (str(abc), "-c", "version; quit"),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    ).stdout
    summary: dict[str, object] = {
        "schema": "occam71-standalone-berkeley-espresso-incomplete-v1",
        "root_seed": routes.ROOT_SEED,
        "abc": str(abc),
        "abc_sha256": routes.sha256_file(abc),
        "abc_version_output": abc_version,
        "espresso": str(espresso),
        "espresso_sha256": routes.sha256_file(espresso),
        "espresso_help_output": espresso_help,
        "instances": {},
    }
    for name in routes.INSTANCE_NAMES:
        summary["instances"][name] = run_one(name, work, abc, espresso)
    routes.atomic_json(work / "espresso-flow-summary.json", summary)
    (work / "ESPRESSO_FLOW_COMPLETE").write_text(
        "success\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
