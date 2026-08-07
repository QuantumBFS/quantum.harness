"""Immutable, hash-complete CT-HYB run publication."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import shutil
import stat
import uuid

from artifacts import atomic_write_bytes, canonical_json, sha256_bytes, sha256_file, strict_json_load


CHAIN_FILES = {
    "raw.h5",
    "chain-summary.json",
    "completion.json",
    "stdout.log",
    "stderr.log",
}


def _artifact(payload):
    return {"payload": payload, "sha256": sha256_bytes(canonical_json(payload))}


def _regular(path: Path) -> None:
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError(f"published input is not a regular file: {path}")


def _files(run: Path) -> dict[str, str]:
    result = {}
    for path in sorted(run.rglob("*")):
        relative = path.relative_to(run).as_posix()
        if path.is_symlink():
            raise ValueError(f"published run contains symlink: {relative}")
        if path.is_file() and relative != "completion.json":
            _regular(path)
            result[relative] = sha256_file(path)
        elif not path.is_dir() and not path.is_file():
            raise ValueError(f"published run contains special file: {relative}")
    return result


def validate_published_run(path: Path) -> dict[str, object]:
    completion = strict_json_load(path / "completion.json")
    summary = strict_json_load(path / "cthyb-summary.json")
    if (
        not isinstance(completion, dict)
        or completion.get("sha256") != sha256_bytes(canonical_json(completion.get("payload")))
        or not isinstance(summary, dict)
        or summary.get("sha256") != sha256_bytes(canonical_json(summary.get("payload")))
    ):
        raise ValueError("published artifact hash mismatch")
    payload = completion["payload"]
    if payload.get("summary_sha256") != summary["sha256"] or payload.get("files") != _files(path):
        raise ValueError("published completion manifest mismatch")
    expected = {"cthyb-summary.json", "completion.json", "chains"}
    if {entry.name for entry in path.iterdir()} != expected:
        raise ValueError("published run top-level inventory mismatch")
    return summary


def publish_run(
    output_root: Path,
    summary: object,
    chains: list[Path],
) -> Path:
    if (
        not isinstance(summary, dict)
        or summary.get("sha256") != sha256_bytes(canonical_json(summary.get("payload")))
        or summary["payload"].get("status") != "accepted"
        or len(chains) != 4
    ):
        raise ValueError("only accepted summaries with four chains are publishable")
    output_root.mkdir(parents=True, exist_ok=True)
    runs = output_root / "runs"
    runs.mkdir(exist_ok=True)
    lock = os.open(output_root / ".publish.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        run_id = f"cthyb-{summary['sha256'][:16]}"
        destination = runs / run_id
        if destination.exists():
            if validate_published_run(destination)["sha256"] != summary["sha256"]:
                raise ValueError("immutable run ID collision")
            return destination
        staging = runs / f".staging-{run_id}-{uuid.uuid4().hex}"
        staging.mkdir(mode=0o700)
        atomic_write_bytes(staging / "cthyb-summary.json", canonical_json(summary) + b"\n")
        (staging / ".cthyb-summary.json.lock").unlink()
        chain_root = staging / "chains"
        chain_root.mkdir()
        for index, source in enumerate(chains):
            if {entry.name for entry in source.iterdir()} != CHAIN_FILES:
                raise ValueError("chain bundle inventory mismatch")
            target = chain_root / f"chain-{index:03d}"
            target.mkdir()
            for name in sorted(CHAIN_FILES):
                _regular(source / name)
                shutil.copyfile(source / name, target / name)
        completion = _artifact(
            {
                "artifact_type": "cthyb_completion",
                "schema_version": 2,
                "summary_sha256": summary["sha256"],
                "files": _files(staging),
            }
        )
        atomic_write_bytes(staging / "completion.json", canonical_json(completion) + b"\n")
        (staging / ".completion.json.lock").unlink()
        os.rename(staging, destination)
        validate_published_run(destination)
        atomic_write_bytes(
            output_root / "current.json",
            canonical_json({"relative_path": f"runs/{run_id}", "summary_sha256": summary["sha256"]})
            + b"\n",
        )
        return destination
    finally:
        os.close(lock)
