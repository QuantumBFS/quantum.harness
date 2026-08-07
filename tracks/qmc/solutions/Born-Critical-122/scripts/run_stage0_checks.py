#!/usr/bin/env python3
"""Run stage-0 tests on a compute node and write an auditable manifest."""

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


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Node-local result directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "unittest.log"
    started_at = utc_now()

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
    print(f"[stage0] source={project_root}", flush=True)
    print(f"[stage0] output={output}", flush=True)
    print(f"[stage0] command={' '.join(command)}", flush=True)

    child_environment = os.environ.copy()
    source_path = str(project_root / "src")
    existing_pythonpath = child_environment.get("PYTHONPATH")
    child_environment["PYTHONPATH"] = (
        source_path
        if not existing_pythonpath
        else source_path + os.pathsep + existing_pythonpath
    )

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

    metrics_path = output / "metrics.json"
    if return_code == 0:
        sys.path.insert(0, source_path)
        try:
            from borncritical.stage0_metrics import collect_stage0_metrics

            atomic_json(metrics_path, collect_stage0_metrics())
            print(f"[stage0] metrics={metrics_path}", flush=True)
        except Exception as error:
            print(
                f"[stage0] metric collection failed: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )
            return_code = 2

    manifest = {
        "schema_version": 1,
        "stage": "stage0",
        "status": "success" if return_code == 0 else "failed",
        "return_code": return_code,
        "started_at": started_at,
        "finished_at": utc_now(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version,
        "packages": {
            "numpy": package_version("numpy"),
        },
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
        },
    }
    atomic_json(output / "manifest.json", manifest)
    print(f"[stage0] status={manifest['status']} return_code={return_code}", flush=True)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
