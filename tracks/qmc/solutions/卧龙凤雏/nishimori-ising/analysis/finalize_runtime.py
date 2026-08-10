#!/usr/bin/env python3
"""Finalize end-to-end runtime, rerender the report, and enforce required gates."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from analysis.data_io import sha256_file, write_json_atomic
from analysis.report_builder import build_report_document


def finalize(run_dir: Path, elapsed_s: float, renderer: Path) -> bool:
    manifest_path = run_dir / "manifest.json"
    summary_path = run_dir / "processed" / "summary.json"
    gates_path = run_dir / "processed" / "gates.json"
    manifest = json.loads(manifest_path.read_text())
    summary = json.loads(summary_path.read_text())
    gates = summary["gates"]

    runtime_gate = next(
        gate for gate in gates["gates"] if gate["name"] == "runtime"
    )
    runtime_gate["value"] = elapsed_s
    runtime_gate["passed"] = elapsed_s < 600.0
    gates["all_required_pass"] = all(
        gate["passed"] for gate in gates["gates"] if gate["required"]
    )
    summary["runtime_s"] = elapsed_s
    summary["gates"] = gates
    manifest["total_elapsed_s"] = elapsed_s
    write_json_atomic(summary_path, summary)
    write_json_atomic(gates_path, gates)
    manifest["artifact_sha256"]["summary"] = sha256_file(summary_path)
    manifest["artifact_sha256"]["gates"] = sha256_file(gates_path)
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
    return gates["all_required_pass"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("elapsed_s", type=float)
    parser.add_argument("--renderer", type=Path, required=True)
    arguments = parser.parse_args()
    passed = finalize(
        arguments.run_dir.resolve(),
        arguments.elapsed_s,
        arguments.renderer,
    )
    print(f"report: {arguments.run_dir.resolve() / 'report.html'}", flush=True)
    manifest = json.loads((arguments.run_dir / "manifest.json").read_text())
    required = bool(manifest["config"]["production_gates"])
    return 0 if passed or not required else 2


if __name__ == "__main__":
    raise SystemExit(main())
