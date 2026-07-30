#!/usr/bin/env python3
"""Create one immutable, provenance-bound direct N=6 smoke run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any


DIRECT = Path(__file__).absolute().parent
PROFILE = DIRECT / "qdeshell_profile.json"
BATCH = DIRECT / "n6_train_qdeshell.sbatch"
RUNNER = DIRECT / "run_task.py"
SEEDS = (0, 1, 2, 3, 4)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(path: Path) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {value}")
        ),
        object_pairs_hook=pairs,
    )


def envelope(schema: str, payload: dict[str, Any]) -> bytes:
    document = {
        "payload": payload,
        "payload_sha256": sha256_bytes(canonical(payload)),
        "schema": schema,
    }
    return canonical(document) + b"\n"


def require_absolute_real_file(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if current.is_symlink():
            raise ValueError(f"{label} contains a symlink: {current}")
    if not path.is_file():
        raise ValueError(f"{label} must be a regular file: {path}")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"{label} must be a regular file: {path}")
    return path


def require_absolute_real_dir(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if current.is_symlink():
            raise ValueError(f"{label} contains a symlink: {current}")
    if not path.is_dir():
        raise ValueError(f"{label} must be a real directory: {path}")
    return path


def require_real_parent(path: Path, label: str) -> None:
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    require_absolute_real_dir(probe, f"{label} existing parent")


def git(source: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=source,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


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
        raise ValueError("interpreter identity query failed")
    identity = json.loads(result.stdout)
    if not isinstance(identity, dict):
        raise ValueError("interpreter identity is invalid")
    return identity, sha256_bytes(canonical(identity))


def create_only(path: Path, encoded: bytes, mode: int = 0o444) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    path.chmod(mode)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--source-root", required=True, type=Path)
    result.add_argument("--config", required=True, type=Path)
    result.add_argument("--config-sha256")
    result.add_argument("--interpreter", required=True, type=Path)
    result.add_argument("--run-dir", required=True, type=Path)
    result.add_argument("--output-root", required=True, type=Path)
    result.add_argument("--particles", type=int, default=6)
    result.add_argument("--rank", type=int, default=1)
    result.add_argument("--seeds", default="0,1,2,3,4")
    result.add_argument("--steps", type=int, default=1)
    return result


def prepare(arguments: argparse.Namespace) -> Path:
    source = require_absolute_real_dir(arguments.source_root, "source root")
    config_path = require_absolute_real_file(arguments.config, "config")
    interpreter = require_absolute_real_file(arguments.interpreter, "interpreter")
    run_dir: Path = arguments.run_dir
    output_root: Path = arguments.output_root
    require_real_parent(run_dir, "run directory")
    require_real_parent(output_root, "output root")
    if run_dir.exists() or run_dir.is_symlink():
        raise ValueError(f"run directory already exists: {run_dir}")
    if arguments.particles != 6 or arguments.rank != 1:
        raise ValueError("direct smoke is fixed to N=6 and rank=1")
    seeds = tuple(int(item) for item in arguments.seeds.split(","))
    if seeds != SEEDS:
        raise ValueError("direct smoke requires exactly seeds 0,1,2,3,4")
    if not 1 <= arguments.steps <= 100:
        raise ValueError("direct smoke steps must be between 1 and 100")
    try:
        config_path.relative_to(source)
    except ValueError as exc:
        raise ValueError("config path must be inside source root") from exc

    commit = git(source, "rev-parse", "--verify", "HEAD")
    if git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("prepare requires clean committed source")
    if not git(source, "ls-files", "--error-unmatch", str(config_path.relative_to(source))):
        raise ValueError("config must be committed source")
    python_path = source / "src" if (source / "src" / "challenge15").is_dir() else source
    if not (python_path / "challenge15").is_dir():
        raise ValueError("source root does not contain the challenge15 package")

    config = strict_json(config_path)
    if not isinstance(config, dict):
        raise ValueError("config must contain one JSON object")
    config_canonical_sha = sha256_bytes(canonical(config))
    if (
        arguments.config_sha256 is not None
        and arguments.config_sha256 != config_canonical_sha
    ):
        raise ValueError("config SHA256 mismatch")
    identity, identity_sha = runtime_identity(interpreter)
    profile = require_absolute_real_file(PROFILE, "direct profile")
    batch = require_absolute_real_file(BATCH, "batch script")
    runner = require_absolute_real_file(RUNNER, "task runner")

    output_root = output_root.absolute()
    run_id_payload = {
        "commit": commit,
        "config_sha256": config_canonical_sha,
        "interpreter_sha256": sha256_file(interpreter),
        "particles": 6,
        "rank": 1,
        "seeds": list(SEEDS),
        "steps": arguments.steps,
    }
    run_id = sha256_bytes(canonical(run_id_payload))
    command_template = [
        str(interpreter),
        "-m",
        "challenge15.cli",
        "train",
        "--config",
        str(config_path),
        "--particles",
        "6",
        "--ranks",
        "1",
        "--seeds",
        "{seed}",
        "--steps",
        str(arguments.steps),
        "--output",
        "{output_dir}",
        "{resume}",
    ]

    run_dir.mkdir(mode=0o700)
    tasks_dir = run_dir / "tasks"
    tasks_dir.mkdir(mode=0o700)
    task_entries = []
    common = {
        "config_canonical_sha256": config_canonical_sha,
        "config_file_sha256": sha256_file(config_path),
        "interpreter_sha256": sha256_file(interpreter),
        "manifest_run_id": run_id,
        "particles": 6,
        "rank": 1,
        "runtime_identity_sha256": identity_sha,
        "source_commit": commit,
        "steps": arguments.steps,
    }
    try:
        for task_id, seed in enumerate(SEEDS):
            task_payload = {
                **common,
                "output_dir": str(output_root / f"seed-{seed}"),
                "seed": seed,
                "task_id": task_id,
            }
            encoded = envelope("challenge15.direct-seed-task.v1", task_payload)
            relative = f"tasks/seed-{seed}.json"
            path = run_dir / relative
            create_only(path, encoded)
            task_document = json.loads(encoded)
            task_entries.append(
                {
                    "payload_sha256": task_document["payload_sha256"],
                    "relative_path": relative,
                    "sha256": sha256_bytes(encoded),
                    "task_id": task_id,
                }
            )

        manifest_payload = {
            "batch": {"path": str(batch), "sha256": sha256_file(batch)},
            "command_template": command_template,
            "config": {
                "canonical_sha256": config_canonical_sha,
                "file_sha256": sha256_file(config_path),
                "path": str(config_path),
            },
            "output_root": str(output_root),
            "particles": 6,
            "profile": {"path": str(profile), "sha256": sha256_file(profile)},
            "rank": 1,
            "run_id": run_id,
            "runner": {"path": str(runner), "sha256": sha256_file(runner)},
            "runtime": {
                "identity": identity,
                "identity_sha256": identity_sha,
                "interpreter": str(interpreter),
                "interpreter_sha256": sha256_file(interpreter),
            },
            "seeds": list(SEEDS),
            "source": {
                "commit": commit,
                "python_path": str(python_path),
                "root": str(source),
            },
            "steps": arguments.steps,
            "tasks": task_entries,
        }
        manifest_path = run_dir / "run.json"
        create_only(
            manifest_path,
            envelope("challenge15.direct-run-manifest.v1", manifest_payload),
        )
        os.sync()
        return manifest_path
    except BaseException:
        # A failed prepare is intentionally not reusable. Retain any partial
        # directory as operator-visible evidence instead of filling it later.
        raise


def main() -> int:
    try:
        path = prepare(parser().parse_args())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
