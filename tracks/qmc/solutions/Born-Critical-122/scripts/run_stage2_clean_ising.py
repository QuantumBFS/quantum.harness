#!/usr/bin/env python3
"""Run stage-2 clean-Ising tests and finite-size analysis on a compute node."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_digest(root: Path) -> str:
    digest = hashlib.sha256()
    included_suffixes = {".json", ".md", ".py", ".toml", ".yml"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in included_suffixes:
            continue
        if any(part in {"__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        payload = path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "unittest.log"
    metrics_path = output / "metrics.json"
    fits_path = output / "fits.json"
    size_path = output / "size-data.csv"
    explicit_path = output / "explicit-crosscheck.csv"
    plot_path = output / "ising-casimir.svg"
    started_at = utc_now()
    source_path = str(project_root / "src")

    command = [
        sys.executable,
        "-u",
        "-m",
        "unittest",
        "discover",
        "-s",
        str(project_root / "tests"),
        "-v",
    ]
    child_environment = os.environ.copy()
    existing_pythonpath = child_environment.get("PYTHONPATH")
    child_environment["PYTHONPATH"] = (
        source_path
        if not existing_pythonpath
        else source_path + os.pathsep + existing_pythonpath
    )
    print(f"[stage2] source={project_root}", flush=True)
    print(f"[stage2] output={output}", flush=True)
    print(f"[stage2] command={' '.join(command)}", flush=True)

    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=project_root,
            env=child_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        return_code = process.wait()

    if return_code == 0:
        sys.path.insert(0, source_path)
        try:
            from borncritical.stage2_metrics import (
                collect_stage2_evidence,
                write_csv,
                write_stage2_svg,
            )

            metrics, size_rows, explicit_rows, fit_records = (
                collect_stage2_evidence()
            )
            atomic_json(metrics_path, metrics)
            atomic_json(fits_path, fit_records)
            write_csv(size_path, size_rows)
            write_csv(explicit_path, explicit_rows)
            write_stage2_svg(plot_path, size_rows, fit_records)
            print(f"[stage2] metrics={metrics_path}", flush=True)
            print(f"[stage2] fits={fits_path}", flush=True)
            print(f"[stage2] plot={plot_path}", flush=True)
            if not metrics["all_gates_passed"]:
                failed = [
                    name
                    for name, passed in metrics["gates"].items()
                    if not passed
                ]
                print(f"[stage2] failed gates={failed}", flush=True)
                return_code = 3
        except Exception as error:
            print(
                f"[stage2] evidence collection failed: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )
            return_code = 2

    manifest = {
        "schema_version": 1,
        "stage": "stage2-clean-ising",
        "status": "success" if return_code == 0 else "failed",
        "return_code": return_code,
        "started_at": started_at,
        "finished_at": utc_now(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version,
        "packages": {"numpy": package_version("numpy")},
        "slurm": {
            "job_id": os.environ.get("SLURM_JOB_ID"),
            "array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
            "cpus_per_task": os.environ.get("SLURM_CPUS_PER_TASK"),
            "job_nodelist": os.environ.get("SLURM_JOB_NODELIST"),
        },
        "source_sha256": source_digest(project_root),
        "command": command,
        "artifacts": {
            "unittest_log": log_path.name,
            "metrics": metrics_path.name if metrics_path.exists() else None,
            "fits": fits_path.name if fits_path.exists() else None,
            "size_data": size_path.name if size_path.exists() else None,
            "explicit_crosscheck": (
                explicit_path.name if explicit_path.exists() else None
            ),
            "stability_plot": plot_path.name if plot_path.exists() else None,
        },
    }
    atomic_json(output / "manifest.json", manifest)
    print(f"[stage2] status={manifest['status']} return_code={return_code}", flush=True)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
