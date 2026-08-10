#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

from analysis.data_io import sha256_file, write_json_atomic
from analysis.report_builder import build_report_document


def finalize(run_dir: Path, elapsed_s: float, renderer: Path) -> bool:
    manifest_path = run_dir / "manifest.json"
    summary_path = run_dir / "processed/summary.json"
    manifest = json.loads(manifest_path.read_text())
    summary = json.loads(summary_path.read_text())
    manifest["total_elapsed_s"] = elapsed_s
    summary["runtime_s"] = elapsed_s
    write_json_atomic(summary_path, summary)
    manifest["artifact_sha256"]["summary"] = sha256_file(summary_path)
    write_json_atomic(manifest_path, manifest)
    report_path = run_dir / "report.json"
    write_json_atomic(report_path, build_report_document(summary, manifest))
    subprocess.run(
        [sys.executable, str(renderer.resolve()), str(run_dir.resolve())],
        check=True,
    )
    manifest["artifact_sha256"]["report-json"] = sha256_file(report_path)
    manifest["artifact_sha256"]["report-html"] = sha256_file(run_dir / "report.html")
    write_json_atomic(manifest_path, manifest)
    return bool(summary["gates"]["all_required_pass"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("elapsed_s", type=float)
    parser.add_argument("--renderer", type=Path, required=True)
    arguments = parser.parse_args()
    passed = finalize(arguments.run_dir.resolve(), arguments.elapsed_s, arguments.renderer)
    print(f"report: {arguments.run_dir.resolve() / 'report.html'}", flush=True)
    manifest = json.loads((arguments.run_dir / "manifest.json").read_text())
    return 0 if passed or not manifest["config"]["production_gates"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
