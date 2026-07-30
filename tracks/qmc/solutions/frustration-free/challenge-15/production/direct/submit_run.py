#!/usr/bin/env python3
"""Validate and submit one direct run without blindly resubmitting it."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any


EXPECTED_PROFILE = {
    "account": "giggleliu",
    "cpus_per_task": 64,
    "gres": "gpu:NVIDIAA80080GBPCIeLC:8",
    "memory": "480000M",
    "nodes": 1,
    "ntasks": 1,
    "partition": "dzagnormal",
    "qos": "user_jiangweiqi",
    "wall_time": "24:00:00",
}
DIRECTIVES = (
    "#SBATCH --partition=dzagnormal",
    "#SBATCH --account=giggleliu",
    "#SBATCH --qos=user_jiangweiqi",
    "#SBATCH --nodes=1",
    "#SBATCH --ntasks=1",
    "#SBATCH --cpus-per-task=64",
    "#SBATCH --gres=gpu:NVIDIAA80080GBPCIeLC:8",
    "#SBATCH --mem=480000M",
    "#SBATCH --time=24:00:00",
)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(
        raw.decode(),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {value}")
        ),
        object_pairs_hook=pairs,
    )


def real_file(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError(f"{label} must be an absolute non-symlink file")
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"{label} must be a regular file")
    return path


def load_envelope(path: Path, schema: str) -> tuple[dict[str, Any], bytes]:
    raw = real_file(path, schema).read_bytes()
    document = strict_json(raw)
    if raw != canonical(document) + b"\n":
        raise ValueError(f"{schema} is not canonical JSON")
    if (
        not isinstance(document, dict)
        or set(document) != {"payload", "payload_sha256", "schema"}
        or document.get("schema") != schema
        or not isinstance(document.get("payload"), dict)
        or sha_bytes(canonical(document["payload"])) != document.get("payload_sha256")
    ):
        raise ValueError(f"invalid {schema}")
    return document, raw


def git(source: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=source,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or "git validation failed")
    return result.stdout.strip()


def create_only(path: Path, encoded: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o444,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def validate(manifest_path: Path) -> tuple[dict[str, Any], bytes]:
    document, raw = load_envelope(
        manifest_path, "challenge15.direct-run-manifest.v1"
    )
    manifest = document["payload"]
    if (
        manifest.get("particles") != 6
        or manifest.get("rank") != 1
        or manifest.get("seeds") != [0, 1, 2, 3, 4]
        or len(manifest.get("tasks", [])) != 5
    ):
        raise ValueError("manifest is not the fixed five-seed N=6 run")

    profile_path = real_file(Path(manifest["profile"]["path"]), "profile")
    profile, profile_raw = load_envelope(
        profile_path, "challenge15.direct-qdeshell-profile.v1"
    )
    if (
        sha_bytes(profile_raw) != manifest["profile"]["sha256"]
        or profile["payload"] != EXPECTED_PROFILE
    ):
        raise ValueError("exact Qdeshell resource tuple mismatch")

    batch = real_file(Path(manifest["batch"]["path"]), "batch script")
    if sha_file(batch) != manifest["batch"]["sha256"]:
        raise ValueError("batch script SHA256 mismatch")
    lines = batch.read_text(encoding="utf-8").splitlines()
    if any(lines.count(directive) != 1 for directive in DIRECTIVES):
        raise ValueError("batch resource directive mismatch")
    if any(line.startswith("#SBATCH --array") for line in lines):
        raise ValueError("batch arrays are forbidden")

    runner = real_file(Path(manifest["runner"]["path"]), "task runner")
    if sha_file(runner) != manifest["runner"]["sha256"]:
        raise ValueError("task runner SHA256 mismatch")
    interpreter = real_file(
        Path(manifest["runtime"]["interpreter"]), "portable interpreter"
    )
    if sha_file(interpreter) != manifest["runtime"]["interpreter_sha256"]:
        raise ValueError("portable interpreter SHA256 mismatch")

    source = Path(manifest["source"]["root"])
    if git(source, "rev-parse", "--verify", "HEAD") != manifest["source"]["commit"]:
        raise ValueError("source commit mismatch")
    if git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("source checkout is not clean")

    config = real_file(Path(manifest["config"]["path"]), "config")
    if sha_file(config) != manifest["config"]["file_sha256"]:
        raise ValueError("config file SHA256 mismatch")
    if sha_bytes(canonical(strict_json(config.read_bytes()))) != manifest["config"][
        "canonical_sha256"
    ]:
        raise ValueError("canonical config SHA256 mismatch")

    for task_id, entry in enumerate(manifest["tasks"]):
        relative = Path(entry["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("task path traversal rejected")
        task, task_raw = load_envelope(
            manifest_path.parent / relative, "challenge15.direct-seed-task.v1"
        )
        if (
            sha_bytes(task_raw) != entry["sha256"]
            or task["payload_sha256"] != entry["payload_sha256"]
            or task["payload"].get("task_id") != task_id
            or task["payload"].get("seed") != task_id
        ):
            raise ValueError("task document SHA256 mismatch")
    return manifest, raw


def submit(manifest_path: Path) -> str:
    manifest, manifest_raw = validate(manifest_path)
    manifest_sha = sha_bytes(manifest_raw)
    batch_sha = manifest["batch"]["sha256"]
    profile_sha = manifest["profile"]["sha256"]
    submission = manifest_path.parent / "submission"
    if submission.is_symlink() or (submission.exists() and not submission.is_dir()):
        raise ValueError("submission path is not a real directory")
    submission.mkdir(mode=0o700, exist_ok=True)
    claim = submission / "claim.json"
    receipt = submission / "receipt.json"

    if receipt.exists() or receipt.is_symlink():
        receipt_document, _ = load_envelope(
            receipt, "challenge15.direct-submission-receipt.v1"
        )
        payload = receipt_document["payload"]
        if (
            payload.get("manifest_sha256") != manifest_sha
            or payload.get("batch_sha256") != batch_sha
            or payload.get("profile_sha256") != profile_sha
            or not claim.is_file()
            or claim.is_symlink()
            or payload.get("claim_sha256") != sha_file(claim)
        ):
            raise ValueError("existing receipt provenance mismatch")
        return str(payload["scheduler_job_id"])
    if claim.exists() or claim.is_symlink():
        raise ValueError("submission claim exists without receipt; operator recovery required")

    claim_payload = {
        "batch_sha256": batch_sha,
        "manifest_sha256": manifest_sha,
        "profile_sha256": profile_sha,
    }
    create_only(
        claim,
        canonical(
            {
                "payload": claim_payload,
                "payload_sha256": sha_bytes(canonical(claim_payload)),
                "schema": "challenge15.direct-submission-claim.v1",
            }
        )
        + b"\n",
    )
    claim_sha = sha_file(claim)

    result = subprocess.run(
        ["sbatch", "--parsable", manifest["batch"]["path"], str(manifest_path)],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(
            (result.stderr.strip() or "scheduler submission failed")
            + "; operator recovery required"
        )
    job_id = result.stdout.strip()
    if not job_id or any(character not in "0123456789_;.abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-" for character in job_id):
        raise ValueError("scheduler returned an invalid job ID; operator recovery required")

    receipt_payload = {
        "batch_sha256": batch_sha,
        "claim_sha256": claim_sha,
        "manifest_sha256": manifest_sha,
        "profile_sha256": profile_sha,
        "scheduler_job_id": job_id,
    }
    create_only(
        receipt,
        canonical(
            {
                "payload": receipt_payload,
                "payload_sha256": sha_bytes(canonical(receipt_payload)),
                "schema": "challenge15.direct-submission-receipt.v1",
            }
        )
        + b"\n",
    )
    directory_fd = os.open(submission, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return job_id


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: submit_run.py ABSOLUTE_MANIFEST", file=sys.stderr)
        return 2
    try:
        print(submit(Path(sys.argv[1])))
    except (KeyError, OSError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
