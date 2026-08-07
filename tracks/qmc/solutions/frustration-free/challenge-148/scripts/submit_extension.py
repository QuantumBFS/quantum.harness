#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import submit_plan as shared


CALIBRATION_ARRAY = "0"
PRODUCTION_ARRAY = "0-23%16"
METADATA_SCHEMA = "challenge148-extension-slurm-job-v1"


def _read_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read valid plan JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("plan must be a JSON object")
    if value.get("schema_version") != "challenge148-directed-extension-plan-v1":
        raise ValueError("plan must use the directed extension schema_version")
    plan_sha256 = value.get("plan_sha256")
    if (
        not isinstance(plan_sha256, str)
        or not shared._HEX_SHA256.fullmatch(plan_sha256)
    ):
        raise ValueError("plan_sha256 must be 64 lowercase hexadecimal characters")
    hash_material = dict(value)
    del hash_material["plan_sha256"]
    if hashlib.sha256(shared._canonical_body(hash_material)).hexdigest() != plan_sha256:
        raise ValueError("plan_sha256 does not match plan content")
    if value.get("allocation") != {
        "adapter_timeout_seconds": 1800,
        "cores_per_cell": shared.CPUS_PER_TASK,
        "memory_mb_per_cell": 6000,
        "max_concurrency": 16,
    }:
        raise ValueError(
            "extension allocation must be exactly 1800 seconds, 2 CPU, "
            "6000 MB, and 16"
        )
    cells = value.get("cells")
    if not isinstance(cells, list) or len(cells) != 24:
        raise ValueError("extension plan must contain exactly 24 cells")
    return value


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
    value = shared._metadata_value(
        kind=kind,
        job_id=job_id,
        array=array,
        plan_sha256=plan_sha256,
        plan=plan,
        solution=solution,
        binary=binary,
        dependency=dependency,
    )
    value["schema_version"] = METADATA_SCHEMA
    return value


def _load_metadata(path: Path, **expected: object) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = path.read_bytes()
        value = json.loads(payload)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid existing job metadata: {path}") from exc
    if not isinstance(value, dict) or payload != shared._canonical_json(value):
        raise ValueError(f"existing job metadata is not canonical: {path}")
    job_id = value.get("job_id")
    if not isinstance(job_id, str) or not shared._JOB_ID.fullmatch(job_id):
        raise ValueError(f"existing job metadata has invalid job ID: {path}")
    wanted = _metadata_value(job_id=job_id, **expected)
    if value != wanted:
        raise ValueError(f"existing job metadata does not match submission: {path}")
    return value


def submit(arguments: argparse.Namespace) -> dict[str, object] | None:
    solution = shared._directory(arguments.solution_root, "solution root")
    plan_path = shared._regular_file(arguments.plan, "plan")
    binary = shared._regular_file(
        arguments.qmc_sse, "QMC_SSE binary", executable=True
    )
    wrapper = shared._regular_file(
        solution / "scripts" / "slurm_extension.sh",
        "extension Slurm wrapper",
        executable=True,
    )
    shared._regular_file(solution / "scripts" / "run_cell.py", "cell runner")
    plan = _read_plan(plan_path)
    plan_sha256 = plan["plan_sha256"]
    assert isinstance(plan_sha256, str)
    metadata_dir = arguments.metadata_dir.expanduser().resolve()
    if any(
        (metadata_dir / name).exists()
        for name in ("calibration-job.json", "array-job.json")
    ):
        raise ValueError("refusing to use base scan metadata directory")
    logs = metadata_dir / "logs"
    environment = shared._job_environment(plan_path, solution, binary)
    calibration_command = shared._base_command(
        wrapper=wrapper,
        logs=logs,
        plan_sha256=plan_sha256,
        kind="extension-calibration",
        array=CALIBRATION_ARRAY,
    )
    if arguments.dry_run:
        production_command = shared._base_command(
            wrapper=wrapper,
            logs=logs,
            plan_sha256=plan_sha256,
            kind="extension-array",
            array=PRODUCTION_ARRAY,
            dependency="afterok:<calibration-job-id>",
        )
        print(shared._display_command(calibration_command, environment))
        print(shared._display_command(production_command, environment))
        return None

    shared._prepare_submission_directories(metadata_dir, logs)
    if arguments.test_only:
        calibration_job_id = shared._run_sbatch(
            calibration_command, environment, test_only=True
        )
        production_command = shared._base_command(
            wrapper=wrapper,
            logs=logs,
            plan_sha256=plan_sha256,
            kind="extension-array",
            array=PRODUCTION_ARRAY,
        )
        shared._run_sbatch(production_command, environment, test_only=True)
        return {
            "mode": "test-only",
            "calibration_estimated_job_id": calibration_job_id,
            "dependency": "validated during real submission",
        }

    common = {
        "plan_sha256": plan_sha256,
        "plan": plan_path,
        "solution": solution,
        "binary": binary,
    }
    calibration_path = metadata_dir / "extension-calibration-job.json"
    calibration = _load_metadata(
        calibration_path,
        kind="extension-calibration",
        array=CALIBRATION_ARRAY,
        **common,
    )
    if calibration is None:
        calibration_job_id = shared._run_sbatch(
            calibration_command, environment, test_only=False
        )
        calibration = _metadata_value(
            kind="extension-calibration",
            job_id=calibration_job_id,
            array=CALIBRATION_ARRAY,
            **common,
        )
        shared._publish_metadata(calibration_path, calibration)
    calibration_job_id = calibration["job_id"]
    assert isinstance(calibration_job_id, str)
    dependency = f"afterok:{calibration_job_id}"
    production_path = metadata_dir / "extension-array-job.json"
    production = _load_metadata(
        production_path,
        kind="extension-array",
        array=PRODUCTION_ARRAY,
        dependency=dependency,
        **common,
    )
    if production is None:
        production_command = shared._base_command(
            wrapper=wrapper,
            logs=logs,
            plan_sha256=plan_sha256,
            kind="extension-array",
            array=PRODUCTION_ARRAY,
            dependency=dependency,
        )
        production_job_id = shared._run_sbatch(
            production_command, environment, test_only=False
        )
        production = _metadata_value(
            kind="extension-array",
            job_id=production_job_id,
            array=PRODUCTION_ARRAY,
            dependency=dependency,
            **common,
        )
        shared._publish_metadata(production_path, production)
    return {
        "mode": "submitted",
        "calibration_job_id": calibration["job_id"],
        "array_job_id": production["job_id"],
        "dependency": production["dependency"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Submit the gated Challenge 148 directed extension."
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
        print(f"submit_extension.py: {exc}", file=sys.stderr)
        return 1
    if result is not None:
        print(shared._canonical_json(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
