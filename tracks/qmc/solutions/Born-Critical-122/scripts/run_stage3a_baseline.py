#!/usr/bin/env python3
"""Run stage-3A tests and pinned-upstream baseline comparisons."""

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
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.suffix not in {".cpp", ".h", ".json", ".md", ".py", ".toml", ".yml"}
            or any(part in {"__pycache__", ".pytest_cache"} for part in path.parts)
        ):
            continue
        relative = path.relative_to(root).as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
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
    parser.add_argument("--upstream-driver", type=Path, required=True)
    parser.add_argument("--upstream-smoke", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "unittest.log"
    metrics_path = output / "metrics.json"
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
    environment = os.environ.copy()
    environment["PYTHONPATH"] = source_path + (
        os.pathsep + environment["PYTHONPATH"]
        if environment.get("PYTHONPATH")
        else ""
    )
    print(f"[stage3a] source={project_root}", flush=True)
    print(f"[stage3a] output={output}", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=project_root,
            env=environment,
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
            from borncritical.stage3_baseline import collect_stage3a_metrics

            metrics = collect_stage3a_metrics(
                args.upstream_driver.resolve(),
                output / "fixed-configs",
                args.upstream_smoke.resolve(),
            )
            atomic_json(metrics_path, metrics)
            if not metrics["all_gates_passed"]:
                return_code = 3
        except Exception as error:
            print(
                f"[stage3a] evidence collection failed: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )
            return_code = 2

    manifest = {
        "schema_version": 1,
        "stage": "stage3a-rbim-baseline",
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
            "cpus_per_task": os.environ.get("SLURM_CPUS_PER_TASK"),
            "job_nodelist": os.environ.get("SLURM_JOB_NODELIST"),
        },
        "source_sha256": source_digest(project_root),
        "upstream": {
            "repository": "Zhouquan-Wan/fermionic-transfer-matrix-rbim",
            "commit": "814c24775b6b46cab77f3b4829c9c3802cab2146",
            "build": "fixed source plus documented single-process compatibility headers",
            "pfapack_observable_excluded": "m_mid only; logZ path retained",
        },
        "artifacts": {
            "unittest_log": log_path.name,
            "metrics": metrics_path.name if metrics_path.exists() else None,
            "build_log": "upstream-build.log",
            "upstream_smoke_log": "upstream-smoke.log",
        },
    }
    atomic_json(output / "manifest.json", manifest)
    print(f"[stage3a] status={manifest['status']} return_code={return_code}", flush=True)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
