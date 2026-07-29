#!/usr/bin/env python3
"""Validate the Route D+ runtime and write its Phase 1 manifest.

This program is an evidence-producing remote smoke test. It must be executed
with the same interpreter and inside the same compute allocation that will run
the Route D+ workload.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = "challenge-15-route-d-plus-environment-v1"
REQUIRED_PYTHON = (3, 11)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def require_clean_commit(repo_root: Path) -> tuple[str, bool]:
    commit = git_output(repo_root, "rev-parse", "HEAD")
    dirty = bool(git_output(repo_root, "status", "--porcelain"))
    if len(commit) != 40:
        raise RuntimeError(f"expected a full Git commit SHA, received {commit!r}")
    if dirty:
        raise RuntimeError(
            "Route D+ Phase 1 requires a clean committed source revision"
        )
    return commit, dirty


def collect_manifest(
    *,
    repo_root: Path,
    lock_file: Path,
    requested_platform: str,
) -> dict[str, Any]:
    if sys.version_info[:2] != REQUIRED_PYTHON:
        raise RuntimeError(
            "Route D+ requires Python 3.11; "
            f"received {platform.python_version()}"
        )
    if not lock_file.is_file():
        raise RuntimeError(f"dependency lock does not exist: {lock_file}")

    import jax
    import jaxlib

    jax.config.update("jax_enable_x64", True)
    if not bool(jax.config.read("jax_enable_x64")):
        raise RuntimeError("JAX x64 could not be enabled")

    devices = list(jax.devices())
    if not devices:
        raise RuntimeError("JAX reported no devices")
    device_platforms = [str(device.platform) for device in devices]
    if requested_platform not in device_platforms:
        raise RuntimeError(
            f"requested JAX platform {requested_platform!r}, "
            f"available platforms are {device_platforms!r}"
        )

    commit, dirty = require_clean_commit(repo_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "python_executable": str(Path(sys.executable).resolve()),
        "jax_version": str(jax.__version__),
        "jaxlib_version": str(jaxlib.__version__),
        "jax_enable_x64": True,
        "requested_platform": requested_platform,
        "device_platforms": device_platforms,
        "device_kinds": [str(device.device_kind) for device in devices],
        "device_count": len(devices),
        "git_commit": commit,
        "git_dirty": dirty,
        "requirements_lock_sha256": sha256_file(lock_file),
        "requirements_lock_path": str(lock_file.resolve()),
        "hostname": platform.node(),
        "machine": platform.machine(),
        "system": platform.system(),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_cluster_name": os.environ.get("SLURM_CLUSTER_NAME"),
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def validate_manifest(payload: dict[str, Any]) -> None:
    import jsonschema

    schema_path = Path(__file__).with_name("manifest.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    validator.validate(payload)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--lock-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--require-platform",
        choices=("cpu", "gpu"),
        required=True,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = collect_manifest(
        repo_root=args.repo_root.resolve(),
        lock_file=args.lock_file.resolve(),
        requested_platform=args.require_platform,
    )
    validate_manifest(manifest)
    write_json_atomic(args.output.resolve(), manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
