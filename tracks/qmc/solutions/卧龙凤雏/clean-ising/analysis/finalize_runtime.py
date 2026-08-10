#!/usr/bin/env python3
"""Finalize total runtime in manifest/report and enforce the production budget."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("elapsed_s", type=float)
    parser.add_argument("--renderer", type=Path, required=True)
    arguments = parser.parse_args()
    run_dir = arguments.run_dir.resolve()
    passed = arguments.elapsed_s < 600.0

    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["total_elapsed_s"] = arguments.elapsed_s
    _write_json_atomic(manifest_path, manifest)

    metadata_path = run_dir / "processed" / "analysis_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["gates"]["runtime"] = passed
    _write_json_atomic(metadata_path, metadata)

    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for section in report["sections"]:
        if section["title"] != "Verification":
            continue
        for block in section["blocks"]:
            if block["kind"] == "verdict" and "Runtime:" in block.get("why", ""):
                block["status"] = "good" if passed else "bad"
                block["label"] = "PASS" if passed else "FAIL"
            if block["kind"] == "table" and block.get("columns") == ["Stage", "Seconds"]:
                for row in block["rows"]:
                    if row[0] == "Total":
                        row[1] = f"{arguments.elapsed_s:.3f}"
    if not passed:
        report["lede"] = report["lede"].replace(
            "Overall verification: PASS", "Overall verification: FAIL"
        )
    _write_json_atomic(report_path, report)
    subprocess.run(
        [sys.executable, str(arguments.renderer.resolve()), str(run_dir)],
        check=True,
    )
    print(f"report: {run_dir / 'report.html'}", flush=True)
    production = bool(manifest["config"]["production_gates"])
    return 0 if passed or not production else 2


def _write_json_atomic(path: Path, value) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
