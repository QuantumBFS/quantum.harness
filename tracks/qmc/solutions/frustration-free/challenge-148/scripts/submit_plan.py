#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


PARTITION = "ihicnormal"
ACCOUNT = "chenkun2025"
QOS = "user_student090"
CPUS_PER_TASK = 2
MEMORY = "6000M"
CALIBRATION_ARRAY = "0"
PRODUCTION_ARRAY = "0-71%16"
METADATA_SCHEMA = "challenge148-slurm-job-v1"
_JOB_ID = re.compile(r"^[1-9][0-9]*$")
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: object) -> bytes:
    return _canonical_body(value) + b"\n"


def _canonical_body(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _read_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read valid plan JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("plan must be a JSON object")
    plan_sha256 = value.get("plan_sha256")
    if not isinstance(plan_sha256, str) or not _HEX_SHA256.fullmatch(plan_sha256):
        raise ValueError("plan_sha256 must be 64 lowercase hexadecimal characters")
    hash_material = dict(value)
    del hash_material["plan_sha256"]
    if hashlib.sha256(_canonical_body(hash_material)).hexdigest() != plan_sha256:
        raise ValueError("plan_sha256 does not match plan content")
    if value.get("allocation") != {
        "cores_per_cell": CPUS_PER_TASK,
        "memory_mb_per_cell": 6000,
        "max_concurrency": 16,
    }:
        raise ValueError("plan allocation must be exactly 2 CPU, 6000 MB, and 16")
    cells = value.get("cells")
    if not isinstance(cells, list) or len(cells) != 72:
        raise ValueError("plan must contain exactly 72 cells")
    return value


def _regular_file(path: Path, label: str, *, executable: bool = False) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"{label} must be a regular file: {resolved}")
    if executable and not os.access(resolved, os.X_OK):
        raise ValueError(f"{label} must be executable: {resolved}")
    return resolved


def _directory(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"{label} must be a directory: {resolved}")
    return resolved


def _job_environment(plan: Path, solution: Path, binary: Path) -> dict[str, str]:
    return {
        "CH148_PLAN": str(plan),
        "CH148_SOLUTION_DIR": str(solution),
        "CH148_QMC_SSE": str(binary),
    }


def _base_command(
    *,
    wrapper: Path,
    logs: Path,
    plan_sha256: str,
    kind: str,
    array: str,
    dependency: str | None = None,
) -> list[str]:
    command = [
        "sbatch",
        "--parsable",
        f"--partition={PARTITION}",
        f"--account={ACCOUNT}",
        f"--qos={QOS}",
        f"--cpus-per-task={CPUS_PER_TASK}",
        f"--mem={MEMORY}",
        "--ntasks=1",
        f"--array={array}",
        f"--job-name=ch148-{kind}-{plan_sha256[:12]}",
        f"--output={logs}/{kind}-%A_%a.out",
        "--export=ALL,CH148_PLAN,CH148_SOLUTION_DIR,CH148_QMC_SSE",
    ]
    if dependency is not None:
        command.extend(
            [f"--dependency={dependency}", "--kill-on-invalid-dep=yes"]
        )
    command.append(str(wrapper))
    return command


def _display_command(command: list[str], environment: dict[str, str]) -> str:
    assignments = [f"{name}={value}" for name, value in environment.items()]
    return shlex.join(["env", *assignments, *command])


def _parse_job_id(output: str, *, test_only: bool) -> str:
    stripped = output.strip()
    candidate = stripped.split(";", 1)[0]
    if _JOB_ID.fullmatch(candidate):
        return candidate
    if test_only:
        match = re.search(r"\bJob\s+([1-9][0-9]*)\b", stripped)
        if match is not None:
            return match.group(1)
    raise RuntimeError(f"sbatch did not return a valid job ID: {stripped!r}")


def _run_sbatch(
    command: list[str],
    environment: dict[str, str],
    *,
    test_only: bool,
) -> str:
    invoked = [*command]
    if test_only:
        invoked.insert(1, "--test-only")
    process_environment = os.environ.copy()
    process_environment.update(environment)
    completed = subprocess.run(
        invoked,
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"sbatch exited with status {completed.returncode}: {detail}"
        )
    return _parse_job_id(completed.stdout or completed.stderr, test_only=test_only)


def _metadata_value(
    *,
    kind: str,
    job_id: str,
    array: str,
    plan_sha256: str,
    plan: Path,
    solution: Path,
    binary: Path,
    dependency: str | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": METADATA_SCHEMA,
        "kind": kind,
        "job_id": job_id,
        "array": array,
        "plan_sha256": plan_sha256,
        "plan_path": str(plan),
        "solution_root": str(solution),
        "qmc_sse": str(binary),
        "account": ACCOUNT,
        "qos": QOS,
        "cpus_per_task": CPUS_PER_TASK,
        "memory": MEMORY,
    }
    if dependency is not None:
        value["dependency"] = dependency
    return value


def _publish_metadata(path: Path, value: dict[str, object]) -> None:
    payload = _canonical_json(value)
    temporary = path.parent / (
        f".{path.name}.publish-{os.getpid()}-{secrets.token_hex(8)}"
    )
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise ValueError(f"refusing mismatched existing job metadata: {path}")
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _prepare_submission_directories(metadata_dir: Path, logs: Path) -> None:
    metadata_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    logs.mkdir(exist_ok=True, mode=0o700)
    for path in (logs, metadata_dir):
        if not path.is_dir():
            raise ValueError(f"submission path must be a directory: {path}")
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _load_metadata(
    path: Path,
    *,
    kind: str,
    array: str,
    plan_sha256: str,
    plan: Path,
    solution: Path,
    binary: Path,
    dependency: str | None = None,
) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = path.read_bytes()
        value = json.loads(payload)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid existing job metadata: {path}") from exc
    if not isinstance(value, dict) or payload != _canonical_json(value):
        raise ValueError(f"existing job metadata is not canonical: {path}")
    job_id = value.get("job_id")
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        raise ValueError(f"existing job metadata has invalid job ID: {path}")
    expected = _metadata_value(
        kind=kind,
        job_id=job_id,
        array=array,
        plan_sha256=plan_sha256,
        plan=plan,
        solution=solution,
        binary=binary,
        dependency=dependency,
    )
    if value != expected:
        raise ValueError(f"existing job metadata does not match submission: {path}")
    return value


def submit(arguments: argparse.Namespace) -> dict[str, object] | None:
    solution = _directory(arguments.solution_root, "solution root")
    plan_path = _regular_file(arguments.plan, "plan")
    binary = _regular_file(arguments.qmc_sse, "QMC_SSE binary", executable=True)
    wrapper = _regular_file(
        solution / "scripts" / "slurm_array.sh", "Slurm wrapper", executable=True
    )
    _regular_file(solution / "scripts" / "run_cell.py", "cell runner")
    plan = _read_plan(plan_path)
    plan_sha256 = plan["plan_sha256"]
    assert isinstance(plan_sha256, str)
    metadata_dir = arguments.metadata_dir.expanduser().resolve()
    logs = metadata_dir / "logs"
    environment = _job_environment(plan_path, solution, binary)

    calibration_command = _base_command(
        wrapper=wrapper,
        logs=logs,
        plan_sha256=plan_sha256,
        kind="calibration",
        array=CALIBRATION_ARRAY,
    )
    if arguments.dry_run:
        production_command = _base_command(
            wrapper=wrapper,
            logs=logs,
            plan_sha256=plan_sha256,
            kind="array",
            array=PRODUCTION_ARRAY,
            dependency="afterok:<calibration-job-id>",
        )
        print(_display_command(calibration_command, environment))
        print(_display_command(production_command, environment))
        return None

    if arguments.test_only:
        _prepare_submission_directories(metadata_dir, logs)
        calibration_job_id = _run_sbatch(
            calibration_command, environment, test_only=True
        )
        production_command = _base_command(
            wrapper=wrapper,
            logs=logs,
            plan_sha256=plan_sha256,
            kind="array",
            array=PRODUCTION_ARRAY,
        )
        _run_sbatch(production_command, environment, test_only=True)
        return {
            "mode": "test-only",
            "calibration_estimated_job_id": calibration_job_id,
            "dependency": "validated during real submission",
        }

    _prepare_submission_directories(metadata_dir, logs)
    calibration_path = metadata_dir / "calibration-job.json"
    calibration = _load_metadata(
        calibration_path,
        kind="calibration",
        array=CALIBRATION_ARRAY,
        plan_sha256=plan_sha256,
        plan=plan_path,
        solution=solution,
        binary=binary,
    )
    if calibration is None:
        calibration_job_id = _run_sbatch(
            calibration_command, environment, test_only=False
        )
        calibration = _metadata_value(
            kind="calibration",
            job_id=calibration_job_id,
            array=CALIBRATION_ARRAY,
            plan_sha256=plan_sha256,
            plan=plan_path,
            solution=solution,
            binary=binary,
        )
        _publish_metadata(calibration_path, calibration)
    calibration_job_id = calibration["job_id"]
    assert isinstance(calibration_job_id, str)
    dependency = f"afterok:{calibration_job_id}"
    production_path = metadata_dir / "array-job.json"
    production = _load_metadata(
        production_path,
        kind="array",
        array=PRODUCTION_ARRAY,
        plan_sha256=plan_sha256,
        plan=plan_path,
        solution=solution,
        binary=binary,
        dependency=dependency,
    )
    if production is None:
        production_command = _base_command(
            wrapper=wrapper,
            logs=logs,
            plan_sha256=plan_sha256,
            kind="array",
            array=PRODUCTION_ARRAY,
            dependency=dependency,
        )
        production_job_id = _run_sbatch(
            production_command, environment, test_only=False
        )
        production = _metadata_value(
            kind="array",
            job_id=production_job_id,
            array=PRODUCTION_ARRAY,
            plan_sha256=plan_sha256,
            plan=plan_path,
            solution=solution,
            binary=binary,
            dependency=dependency,
        )
        _publish_metadata(production_path, production)
    return {
        "mode": "submitted",
        "calibration_job_id": calibration["job_id"],
        "array_job_id": production["job_id"],
        "dependency": production["dependency"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Submit the gated Challenge 148 Slurm calibration and array."
    )
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--solution-root", required=True, type=Path)
    parser.add_argument("--qmc-sse", required=True, type=Path)
    parser.add_argument("--metadata-dir", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--test-only", action="store_true")
    return parser


def main() -> int:
    try:
        result = submit(_parser().parse_args())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"submit_plan.py: {exc}", file=sys.stderr)
        return 1
    if result is not None:
        print(_canonical_json(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
