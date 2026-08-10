#!/usr/bin/env python3
"""Validate and execute exactly one immutable direct smoke seed task."""

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


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json_bytes(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(
        raw.decode("utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {value}")
        ),
        object_pairs_hook=pairs,
    )


def real_file(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label} contains a symlink")
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"{label} must be a regular file")
    return path


def real_directory(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label} contains a symlink")
    if not path.is_dir():
        raise ValueError(f"{label} must be a real directory")
    return path


def load_envelope(path: Path, schema: str) -> tuple[dict[str, Any], bytes]:
    real_file(path, schema)
    raw = path.read_bytes()
    document = strict_json_bytes(raw)
    if raw != canonical(document) + b"\n":
        raise ValueError(f"{schema} is not canonical JSON")
    if (
        not isinstance(document, dict)
        or set(document) != {"payload", "payload_sha256", "schema"}
        or document.get("schema") != schema
        or not isinstance(document.get("payload"), dict)
    ):
        raise ValueError(f"invalid {schema}")
    if sha_bytes(canonical(document["payload"])) != document.get("payload_sha256"):
        raise ValueError(f"{schema} payload SHA256 mismatch")
    return document, raw


def runtime_identity(interpreter: Path) -> tuple[dict[str, str], str]:
    program = (
        "import json,platform,sys;"
        "print(json.dumps({"
        "'cache_tag':sys.implementation.cache_tag,"
        "'implementation':sys.implementation.name,"
        "'platform':platform.platform(),"
        "'version':platform.python_version()"
        "},sort_keys=True,separators=(',',':')))"
    )
    result = subprocess.run(
        [str(interpreter), "-c", program],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError("runtime identity query failed")
    identity = strict_json_bytes(result.stdout.encode())
    return identity, sha_bytes(canonical(identity))


def validate_profile(path: Path, expected_sha: str) -> None:
    document, raw = load_envelope(
        path, "challenge15.direct-qdeshell-profile.v1"
    )
    if sha_bytes(raw) != expected_sha:
        raise ValueError("profile file SHA256 mismatch")
    if document["payload"] != EXPECTED_PROFILE:
        raise ValueError("Qdeshell resource profile mismatch")


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


def validate_done(
    done_path: Path,
    *,
    manifest_sha: str,
    task_sha: str,
    task: dict[str, Any],
) -> None:
    document, _ = load_envelope(done_path, "challenge15.direct-done.v1")
    payload = document["payload"]
    expected = {
        "config_canonical_sha256": task["config_canonical_sha256"],
        "interpreter_sha256": task["interpreter_sha256"],
        "manifest_sha256": manifest_sha,
        "runtime_identity_sha256": task["runtime_identity_sha256"],
        "seed": task["seed"],
        "source_commit": task["source_commit"],
        "task_sha256": task_sha,
    }
    if {key: payload.get(key) for key in expected} != expected:
        raise ValueError("DONE provenance hash mismatch")
    outputs = payload.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("DONE output inventory is invalid")
    output_dir = done_path.parent
    expected_names = set()
    for item in outputs:
        if not isinstance(item, dict) or set(item) != {
            "relative_path",
            "sha256",
            "size_bytes",
        }:
            raise ValueError("DONE output inventory is invalid")
        name = item["relative_path"]
        if name not in {"checkpoint.json", "result.json"}:
            raise ValueError("DONE output path is invalid")
        expected_names.add(name)
        path = real_file(output_dir / name, "DONE output")
        if path.stat().st_size != item["size_bytes"] or sha_file(path) != item["sha256"]:
            raise ValueError("DONE output SHA256 mismatch")
    actual_names = {path.name for path in output_dir.iterdir()}
    if actual_names != expected_names | {"DONE.json"}:
        raise ValueError("DONE directory contains ambiguous output")


def publish_done(
    output_dir: Path,
    *,
    manifest_sha: str,
    task_sha: str,
    task: dict[str, Any],
) -> None:
    outputs = []
    for name in ("checkpoint.json", "result.json"):
        path = real_file(output_dir / name, "training output")
        outputs.append(
            {
                "relative_path": name,
                "sha256": sha_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    payload = {
        "config_canonical_sha256": task["config_canonical_sha256"],
        "interpreter_sha256": task["interpreter_sha256"],
        "manifest_sha256": manifest_sha,
        "outputs": outputs,
        "runtime_identity_sha256": task["runtime_identity_sha256"],
        "seed": task["seed"],
        "source_commit": task["source_commit"],
        "task_sha256": task_sha,
    }
    document = {
        "payload": payload,
        "payload_sha256": sha_bytes(canonical(payload)),
        "schema": "challenge15.direct-done.v1",
    }
    encoded = canonical(document) + b"\n"
    partial = output_dir / f".DONE.json.partial.{os.getpid()}"
    descriptor = os.open(
        partial,
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
    try:
        os.link(partial, output_dir / "DONE.json", follow_symlinks=False)
        os.fsync(os.open(output_dir, os.O_RDONLY | os.O_DIRECTORY))
    finally:
        partial.unlink(missing_ok=True)


def execute(manifest_path: Path, task_id: int, batch_path: Path) -> int:
    if task_id not in range(5):
        raise ValueError("seed task ID must be 0 through 4")
    manifest_document, manifest_raw = load_envelope(
        manifest_path, "challenge15.direct-run-manifest.v1"
    )
    manifest = manifest_document["payload"]
    manifest_sha = sha_bytes(manifest_raw)
    if (
        manifest.get("particles") != 6
        or manifest.get("rank") != 1
        or manifest.get("seeds") != [0, 1, 2, 3, 4]
        or not 1 <= manifest.get("steps", 0) <= 100
    ):
        raise ValueError("manifest is not a bounded N=6 rank-1 smoke")

    real_file(batch_path, "batch script")
    if batch_path != Path(manifest["batch"]["path"]):
        raise ValueError("batch script path mismatch")
    if sha_file(batch_path) != manifest["batch"]["sha256"]:
        raise ValueError("batch script SHA256 mismatch")
    runner = real_file(Path(manifest["runner"]["path"]), "task runner")
    if runner != Path(__file__).absolute() or sha_file(runner) != manifest["runner"]["sha256"]:
        raise ValueError("task runner SHA256 mismatch")
    validate_profile(
        Path(manifest["profile"]["path"]), manifest["profile"]["sha256"]
    )

    source = real_directory(Path(manifest["source"]["root"]), "source root")
    if git(source, "rev-parse", "--verify", "HEAD") != manifest["source"]["commit"]:
        raise ValueError("source commit mismatch")
    if git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("source checkout is not clean")
    python_path = real_directory(
        Path(manifest["source"]["python_path"]), "source Python path"
    )
    if python_path not in {source, source / "src"}:
        raise ValueError("source Python path mismatch")

    config = real_file(Path(manifest["config"]["path"]), "config")
    if sha_file(config) != manifest["config"]["file_sha256"]:
        raise ValueError("config file SHA256 mismatch")
    config_value = strict_json_bytes(config.read_bytes())
    if sha_bytes(canonical(config_value)) != manifest["config"]["canonical_sha256"]:
        raise ValueError("canonical config SHA256 mismatch")

    interpreter = real_file(
        Path(manifest["runtime"]["interpreter"]), "portable interpreter"
    )
    if sha_file(interpreter) != manifest["runtime"]["interpreter_sha256"]:
        raise ValueError("interpreter SHA256 mismatch")
    identity, identity_sha = runtime_identity(interpreter)
    if (
        identity != manifest["runtime"]["identity"]
        or identity_sha != manifest["runtime"]["identity_sha256"]
    ):
        raise ValueError("runtime identity SHA256 mismatch")

    entry = manifest["tasks"][task_id]
    if entry["task_id"] != task_id:
        raise ValueError("task index mismatch")
    relative = Path(entry["relative_path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("task path traversal rejected")
    task_path = manifest_path.parent / relative
    task_document, task_raw = load_envelope(
        task_path, "challenge15.direct-seed-task.v1"
    )
    if (
        sha_bytes(task_raw) != entry["sha256"]
        or task_document["payload_sha256"] != entry["payload_sha256"]
    ):
        raise ValueError("task document SHA256 mismatch")
    task = task_document["payload"]
    expected_task = {
        "config_canonical_sha256": manifest["config"]["canonical_sha256"],
        "config_file_sha256": manifest["config"]["file_sha256"],
        "interpreter_sha256": manifest["runtime"]["interpreter_sha256"],
        "manifest_run_id": manifest["run_id"],
        "particles": 6,
        "rank": 1,
        "runtime_identity_sha256": manifest["runtime"]["identity_sha256"],
        "seed": manifest["seeds"][task_id],
        "source_commit": manifest["source"]["commit"],
        "steps": manifest["steps"],
        "task_id": task_id,
    }
    if {key: task.get(key) for key in expected_task} != expected_task:
        raise ValueError("task and manifest hashes mismatch")
    output_dir = Path(task["output_dir"])
    if output_dir != Path(manifest["output_root"]) / f"seed-{task['seed']}":
        raise ValueError("task output path mismatch")

    done_path = output_dir / "DONE.json"
    task_sha = sha_bytes(task_raw)
    if done_path.exists() or done_path.is_symlink():
        validate_done(
            done_path,
            manifest_sha=manifest_sha,
            task_sha=task_sha,
            task=task,
        )
        return 0

    resume = False
    if output_dir.exists() or output_dir.is_symlink():
        real_directory(output_dir, "seed output directory")
        names = {path.name for path in output_dir.iterdir()}
        if names == {"checkpoint.json"}:
            real_file(output_dir / "checkpoint.json", "checkpoint")
            resume = True
        elif names:
            raise ValueError("ambiguous or mismatched seed output")
    else:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        real_directory(output_dir.parent, "output root")
        output_dir.mkdir(mode=0o700)

    command = [
        str(interpreter),
        "-m",
        "challenge15.cli",
        "train",
        "--config",
        str(config),
        "--particles",
        "6",
        "--ranks",
        "1",
        "--seeds",
        str(task["seed"]),
        "--steps",
        str(task["steps"]),
        "--output",
        str(output_dir),
    ]
    template = [*command[:-1], "{output_dir}", "{resume}"]
    template[-3] = "{output_dir}"
    # Compare directly to avoid accepting a command assembled from mutable input.
    expected_template = [
        str(interpreter),
        "-m",
        "challenge15.cli",
        "train",
        "--config",
        str(config),
        "--particles",
        "6",
        "--ranks",
        "1",
        "--seeds",
        "{seed}",
        "--steps",
        str(task["steps"]),
        "--output",
        "{output_dir}",
        "{resume}",
    ]
    if manifest["command_template"] != expected_template:
        raise ValueError("exact command template mismatch")
    if resume:
        command.append("--resume")
    environment = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join(
            filter(None, (str(python_path), os.environ.get("PYTHONPATH")))
        ),
    }
    result = subprocess.run(command, env=environment)
    if result.returncode:
        return result.returncode
    names = {path.name for path in output_dir.iterdir()}
    if names != {"checkpoint.json", "result.json"}:
        raise ValueError("successful train produced ambiguous output")
    publish_done(
        output_dir,
        manifest_sha=manifest_sha,
        task_sha=task_sha,
        task=task,
    )
    validate_done(
        done_path,
        manifest_sha=manifest_sha,
        task_sha=task_sha,
        task=task,
    )
    return 0


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: run_task.py MANIFEST TASK_ID BATCH_SCRIPT", file=sys.stderr)
        return 2
    try:
        return execute(Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3]))
    except (KeyError, OSError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
