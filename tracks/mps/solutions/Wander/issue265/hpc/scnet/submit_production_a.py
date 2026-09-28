#!/usr/bin/env python3
"""Prepare or transactionally submit the gated production-A program."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[2]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from scripts.build_production_v2_bundle import (
    _status,
    build_bundle,
    production_resource_spec,
)
from scripts.materialize_production_v2_reuse import (
    materialize_reuse_attestations,
    write_reuse_attestations,
)
from src.production_output_validation import validate_production_output
from src.production_reuse_gate import ALLOWED_REUSE
from src.research_dataset import file_sha256

DEFAULT_TEAM_ROOT = Path(
    "/work/share/giggleliu/cfys01/kharkov_burgers_20260729"
)
SOURCE_CLOSURE = (
    "hpc/scnet/submit_production_a.py",
    "scripts/build_production_v2_bundle.py",
    "scripts/materialize_production_v2_reuse.py",
    "scripts/run_tenpy_production_job.py",
    "scripts/run_tenpy_research_job.py",
    "src/production_initial_conditions.py",
    "src/production_output_validation.py",
    "src/production_reuse_gate.py",
    "src/tenpy_research_backend.py",
)
POLICY_MARKERS = (
    "AssocGrpSubmitJobsLimit",
    "QOSMaxSubmitJobPerUserLimit",
    "MaxSubmitJobs",
    "job violates accounting/QOS policy",
)
ACTIVE_STATES = {
    "PENDING",
    "RUNNING",
    "CONFIGURING",
    "COMPLETING",
    "SUSPENDED",
}
RECOVERABLE_STATES = {
    "TIMEOUT",
    "NODE_FAIL",
    "PREEMPTED",
    "BOOT_FAIL",
}
MAX_ATTEMPTS = 12


@dataclass(frozen=True)
class LaunchPaths:
    team_root: Path
    source_root: Path
    manifest: Path
    convergence_audit: Path
    source_preflight: Path
    j2_validation: Path
    reuse_attestations: Path
    bundle_root: Path
    record_path: Path
    cluster_root: Path
    python: str
    partition: str
    account: str
    base_manifest: Path | None = None
    dataset_validation: Path | None = None
    convergence_data_root: Path | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    try:
        return dict(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is invalid: {path}") from error


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    os.replace(temporary, path)


def _validate_primary_gates(
    paths: LaunchPaths,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    convergence = _load_json(
        paths.convergence_audit,
        label="convergence audit",
    )
    if _status(convergence) != "accepted":
        raise ValueError("convergence gate is not accepted")
    records = list(convergence.get("records", []))
    if not records or not all(
        record.get("accepted") is True for record in records
    ):
        raise ValueError(
            "convergence audit lacks an all-accepted frozen record set"
        )
    source_preflight = _load_json(
        paths.source_preflight,
        label="production-v2 source preflight",
    )
    if _status(source_preflight) != "pass":
        raise ValueError("production-v2 source preflight is not pass")
    source_files = dict(
        source_preflight.get("source_closure", {}).get("files", {})
    )
    if not source_files:
        raise ValueError(
            "production-v2 source preflight lacks a source closure"
        )
    _verify_source_hashes(
        source_files,
        source_root=paths.source_root,
        label="production-v2 source preflight",
    )
    j2 = _load_json(paths.j2_validation, label="J2 validation")
    if _status(j2) != "pass":
        raise ValueError("J2 compute-node validation is not pass")
    j2_files = dict(j2.get("source_sha256", {}))
    if not j2_files:
        raise ValueError("J2 validation lacks a source closure")
    _verify_source_hashes(
        j2_files,
        source_root=paths.source_root,
        label="J2 validation",
    )
    return convergence, source_preflight, j2


def _validate_reuse_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    observed = {
        str(key): dict(value)
        for key, value in payload.items()
        if not str(key).startswith("_") and isinstance(value, Mapping)
    }
    if set(observed) != set(ALLOWED_REUSE):
        raise ValueError(
            "exactly two registered production-A reuse attestations are "
            "required"
        )
    for target, source in ALLOWED_REUSE.items():
        record = observed[target]
        if (
            record.get("status") != "accepted"
            or str(record.get("source_job_id")) != source
        ):
            raise ValueError(f"reuse attestation is not accepted: {target}")
    return {**dict(payload)}


def _source_hashes(source_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in SOURCE_CLOSURE:
        path = source_root / relative
        if not path.is_file():
            raise ValueError(f"production source is missing: {relative}")
        hashes[relative] = file_sha256(path)
    return hashes


def _verify_source_hashes(
    expected: Mapping[str, Any],
    *,
    source_root: Path,
    label: str,
) -> None:
    stale = [
        relative
        for relative, digest in expected.items()
        if not (source_root / relative).is_file()
        or file_sha256(source_root / relative) != str(digest)
    ]
    if stale:
        raise ValueError(
            f"{label} source closure is stale: " + ", ".join(sorted(stale))
        )


def prepare_launch_plan(
    paths: LaunchPaths,
    *,
    reuse_payload: Mapping[str, Any] | None = None,
    bundle_root_override: Path | None = None,
) -> dict[str, Any]:
    """Freeze the exact gated script set without invoking Slurm."""

    convergence, source_preflight, j2 = _validate_primary_gates(paths)
    manifest = _load_json(paths.manifest, label="production-v2 manifest")
    reuse = _validate_reuse_payload(
        reuse_payload
        if reuse_payload is not None
        else _load_json(
            paths.reuse_attestations,
            label="production-v2 reuse attestations",
        )
    )
    execute_rows = [
        dict(job)
        for job in manifest.get("jobs", [])
        if job.get("stage") == "production_a"
        and job.get("execution_mode") == "execute"
    ]
    reuse_rows = [
        dict(job)
        for job in manifest.get("jobs", [])
        if job.get("stage") == "production_a"
        and job.get("execution_mode") == "reuse"
    ]
    production_b = [
        dict(job)
        for job in manifest.get("jobs", [])
        if job.get("stage") == "production_b"
    ]
    if (
        len(execute_rows) != 32
        or len(reuse_rows) != 2
        or len(production_b) != 34
    ):
        raise ValueError(
            "production-v2 launch set must be 32 execute, 2 reuse, and "
            "34 locked production-B rows"
        )
    if {job["job_id"] for job in reuse_rows} != set(ALLOWED_REUSE):
        raise ValueError("production-A reuse row set changed")

    source_hashes = _source_hashes(paths.source_root)
    evidence_hashes = {
        "manifest": file_sha256(paths.manifest),
        "convergence_audit": file_sha256(paths.convergence_audit),
        "source_preflight": file_sha256(paths.source_preflight),
        "j2_validation": file_sha256(paths.j2_validation),
        "reuse_attestations": _canonical_sha256(dict(reuse)),
    }
    identity = {
        "schema_version": 1,
        "stage": "production_a",
        "execute_rows": [
            {
                "job_id": str(job["job_id"]),
                "resource": production_resource_spec(job),
            }
            for job in execute_rows
        ],
        "reuse_rows": sorted(ALLOWED_REUSE),
        "runtime": {
            "cluster_root": str(paths.cluster_root.resolve()),
            "python": paths.python,
            "partition": paths.partition,
            "account": paths.account,
        },
        "source_sha256": source_hashes,
        "evidence_sha256": evidence_hashes,
    }
    plan_hash = _canonical_sha256(identity)
    bundle_parent = bundle_root_override or paths.bundle_root
    bundle_dir = Path(bundle_parent) / plan_hash
    result = build_bundle(
        manifest,
        outdir=bundle_dir,
        cluster_root=paths.cluster_root,
        source_root=paths.source_root,
        python=paths.python,
        gates={
            "convergence": convergence,
            "source_preflight": source_preflight,
            "j2": j2,
            "unblinding": None,
        },
        reuse_attestations=reuse,
        partition=paths.partition,
        account=paths.account,
    )
    if (
        result.ready_count != 32
        or result.reuse_count != 2
        or result.blocked_count != 34
        or result.submission_performed
    ):
        raise ValueError(
            "materialized bundle does not match the frozen production-A "
            "launch counts"
        )
    scripts = {path.stem: path for path in result.script_paths}
    expected_ids = [str(job["job_id"]) for job in execute_rows]
    if set(scripts) != set(expected_ids):
        raise ValueError("materialized scripts differ from execute row set")
    jobs = []
    by_id = {str(job["job_id"]): job for job in execute_rows}
    for job_id in expected_ids:
        script = scripts[job_id]
        jobs.append(
            {
                "job_id": job_id,
                "condition_id": str(by_id[job_id]["condition_id"]),
                "stage": "production_a",
                "script": str(script.resolve()),
                "script_sha256": file_sha256(script),
                "job": dict(by_id[job_id]),
                "resource": production_resource_spec(by_id[job_id]),
                "output": str(
                    (
                        paths.cluster_root
                        / "data"
                        / "research"
                        / "raw"
                        / "production_a"
                        / f"{job_id}.npz"
                    ).resolve()
                ),
            }
        )
    return {
        "schema_version": 1,
        "status": "ready",
        "plan_sha256": plan_hash,
        "identity": identity,
        "bundle_dir": str(bundle_dir.resolve()),
        "reuse_count": len(reuse_rows),
        "production_b_script_count": 0,
        "jobs": jobs,
    }


def _default_run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )


def _parse_slurm_id(stdout: str) -> str | None:
    matches: list[str] = []
    for line in stdout.splitlines():
        parsed = re.fullmatch(r"(\d+)(?:;[^\s;]+)?", line.strip())
        if parsed:
            matches.append(parsed.group(1))
    return matches[0] if len(matches) == 1 else None


def _record_from_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "status": "submitting",
        "stage": "production_a",
        "plan_sha256": str(plan["plan_sha256"]),
        "identity": dict(plan["identity"]),
        "bundle_dir": str(plan["bundle_dir"]),
        "reuse_count": int(plan["reuse_count"]),
        "submission_complete": False,
        "all_complete": False,
        "jobs": [
            {
                **dict(job),
                "status": "planned",
                "attempts": [],
            }
            for job in plan["jobs"]
        ],
    }


def _record_matches_plan(
    record: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> None:
    if record.get("plan_sha256") != plan.get("plan_sha256"):
        raise ValueError(
            "submission record and current launch plan hash differ"
        )
    if [row["job_id"] for row in record.get("jobs", [])] != [
        row["job_id"] for row in plan["jobs"]
    ]:
        raise ValueError("submission record job set changed")
    for recorded, current in zip(
        record["jobs"], plan["jobs"], strict=True
    ):
        for key in (
            "script",
            "script_sha256",
            "job",
            "resource",
            "output",
        ):
            if recorded.get(key) != current.get(key):
                raise ValueError(
                    "submission record source closure changed for "
                    f"{recorded['job_id']}"
                )


def _validate_plan(plan: Mapping[str, Any]) -> None:
    expected = _canonical_sha256(dict(plan["identity"]))
    if expected != str(plan.get("plan_sha256")):
        raise ValueError("launch plan hash is invalid")
    if (
        len(plan.get("jobs", [])) != 32
        or int(plan.get("reuse_count", -1)) != 2
        or int(plan.get("production_b_script_count", -1)) != 0
    ):
        raise ValueError("launch plan row counts are invalid")
    for row in plan["jobs"]:
        path = Path(str(row["script"]))
        job = row.get("job")
        if (
            row.get("stage") != "production_a"
            or not isinstance(job, Mapping)
            or job.get("job_id") != row.get("job_id")
            or job.get("stage") != "production_a"
            or job.get("execution_mode") != "execute"
            or not path.is_file()
            or file_sha256(path) != str(row.get("script_sha256"))
        ):
            raise ValueError(
                f"launch script is missing or stale: {row.get('job_id')}"
            )


def submit_plan(
    plan: Mapping[str, Any],
    *,
    record_path: str | Path,
    run_command: Callable[
        [list[str]], subprocess.CompletedProcess[str]
    ] = _default_run,
    resume: bool = False,
) -> dict[str, Any]:
    """Submit each unrecorded row once and persist every result atomically."""

    _validate_plan(plan)
    destination = Path(record_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if destination.exists():
            if not resume:
                raise FileExistsError(
                    "production-A submission record exists; explicit resume "
                    "is required"
                )
            record = _load_json(
                destination,
                label="production-A submission record",
            )
            _record_matches_plan(record, plan)
        else:
            if resume:
                raise FileNotFoundError(
                    "production-A submission record is missing"
                )
            record = _record_from_plan(plan)
            _atomic_write(destination, record)

        known_ids = {
            str(attempt["slurm_job_id"])
            for row in record["jobs"]
            for attempt in row.get("attempts", [])
        }
        for row in record["jobs"]:
            if row.get("attempts"):
                continue
            if row.get("status") not in {"planned", "policy_deferred"}:
                continue
            result = run_command(
                ["sbatch", "--parsable", str(row["script"])]
            )
            combined = "\n".join(
                [str(result.stdout or ""), str(result.stderr or "")]
            )
            if int(result.returncode) != 0:
                row["last_submission_error"] = combined.strip()[-4000:]
                if any(marker in combined for marker in POLICY_MARKERS):
                    row["status"] = "policy_deferred"
                    record["status"] = "policy_deferred"
                else:
                    row["status"] = "needs_attention"
                    record["status"] = "needs_attention"
                record["updated_at"] = _now()
                _atomic_write(destination, record)
                return record

            slurm_id = _parse_slurm_id(str(result.stdout or ""))
            if slurm_id is None or slurm_id in known_ids:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    "sbatch returned no unique numeric Slurm ID"
                )
                record["status"] = "needs_attention"
                record["updated_at"] = _now()
                _atomic_write(destination, record)
                return record
            row["attempts"].append(
                {
                    "attempt": 1,
                    "slurm_job_id": slurm_id,
                    "submitted_at": _now(),
                    "script_sha256": row["script_sha256"],
                    "resource": dict(row["resource"]),
                }
            )
            row["status"] = "submitted"
            known_ids.add(slurm_id)
            record["updated_at"] = _now()
            _atomic_write(destination, record)

        record["submission_complete"] = all(
            bool(row.get("attempts")) for row in record["jobs"]
        )
        record["all_complete"] = all(
            row.get("status") == "complete" for row in record["jobs"]
        )
        if any(
            row.get("status") == "needs_attention"
            for row in record["jobs"]
        ):
            record["status"] = "needs_attention"
        elif record["all_complete"]:
            record["status"] = "complete"
        elif any(
            row.get("status") == "policy_deferred"
            for row in record["jobs"]
        ):
            record["status"] = "policy_deferred"
        elif record["submission_complete"]:
            record["status"] = "submitted"
        else:
            record["status"] = "needs_attention"
        record["updated_at"] = _now()
        _atomic_write(destination, record)
        return record


def _default_state_query(slurm_id: str) -> str:
    accounting = subprocess.run(
        [
            "sacct",
            "-n",
            "-P",
            "-X",
            "-j",
            slurm_id,
            "--format=JobIDRaw,State",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    for line in accounting.stdout.splitlines():
        fields = line.split("|")
        if len(fields) >= 2 and fields[0] == slurm_id:
            return fields[1].split("+", 1)[0]
    queue = subprocess.run(
        ["squeue", "-h", "-j", slurm_id, "-o", "%T"],
        check=False,
        capture_output=True,
        text=True,
    )
    return queue.stdout.strip().splitlines()[0] if queue.stdout.strip() else "UNKNOWN"


def _adapt_oom_resource(
    resource: Mapping[str, Any],
) -> dict[str, Any] | None:
    memory_text = str(resource["memory"])
    if not memory_text.endswith("G"):
        return None
    memory_gib = int(memory_text[:-1])
    if memory_gib >= 480:
        return None
    next_memory = min(480, 2 * memory_gib)
    next_cpus = min(
        128,
        max(
            int(resource["cpus"]),
            math.ceil(next_memory / 3.75),
        ),
    )
    if next_memory / next_cpus > 3.9:
        return None
    return {
        **dict(resource),
        "cpus": next_cpus,
        "memory": f"{next_memory}G",
    }


def refresh_submitted_jobs(
    plan: Mapping[str, Any],
    *,
    record_path: str | Path,
    query_state: Callable[[str], str] = _default_state_query,
    run_command: Callable[
        [list[str]], subprocess.CompletedProcess[str]
    ] = _default_run,
) -> dict[str, Any]:
    """Refresh terminal rows and continue only recoverable checkpointed work."""

    _validate_plan(plan)
    destination = Path(record_path)
    if not destination.is_file():
        raise FileNotFoundError(
            "production-A submission record is missing"
        )
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        record = _load_json(
            destination,
            label="production-A submission record",
        )
        _record_matches_plan(record, plan)
        known_ids = {
            str(attempt["slurm_job_id"])
            for row in record["jobs"]
            for attempt in row.get("attempts", [])
        }
        for row in record["jobs"]:
            attempts = row.get("attempts", [])
            if not attempts or row.get("status") in {
                "complete",
                "needs_attention",
            }:
                continue
            current = attempts[-1]
            slurm_id = str(current["slurm_job_id"])
            state = str(query_state(slurm_id)).split("+", 1)[0]
            current["last_checked_at"] = _now()
            current["terminal_state"] = state
            job = row.get("job")
            validation = (
                validate_production_output(job, str(row["output"]))
                if isinstance(job, Mapping)
                else {
                    "status": "invalid",
                    "errors": ["launch_record_missing_job_spec"],
                }
            )
            if validation.get("status") == "valid":
                row["status"] = "complete"
                row["completed_at"] = _now()
                row["validation"] = validation
                continue
            if state in ACTIVE_STATES:
                row["status"] = "submitted"
                continue
            if state == "COMPLETED":
                row["status"] = "needs_attention"
                row["validation"] = validation
                row["last_submission_error"] = (
                    "completed output validation failed: "
                    + ", ".join(
                        map(str, validation.get("errors", []))
                    )
                )
                continue
            if state == "OUT_OF_MEMORY":
                resource = _adapt_oom_resource(current["resource"])
                if resource is None:
                    row["status"] = "needs_attention"
                    row["last_submission_error"] = (
                        "OOM at maximum safe SCNet resource"
                    )
                    continue
            elif state in RECOVERABLE_STATES:
                resource = dict(current["resource"])
            else:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    f"nonrecoverable terminal state: {state}"
                )
                continue
            checkpoint = Path(str(row["output"]) + ".checkpoint.h5")
            if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    f"no usable checkpoint after {state}"
                )
                continue
            if len(attempts) >= MAX_ATTEMPTS:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    "maximum continuation attempts reached"
                )
                continue
            result = run_command(
                [
                    "sbatch",
                    "--parsable",
                    f"--cpus-per-task={resource['cpus']}",
                    f"--mem={resource['memory']}",
                    f"--time={resource['walltime']}",
                    str(row["script"]),
                ]
            )
            combined = "\n".join(
                [str(result.stdout or ""), str(result.stderr or "")]
            )
            if int(result.returncode) != 0:
                row["last_submission_error"] = combined.strip()[-4000:]
                row["status"] = (
                    "policy_deferred"
                    if any(marker in combined for marker in POLICY_MARKERS)
                    else "needs_attention"
                )
                continue
            next_id = _parse_slurm_id(str(result.stdout or ""))
            if next_id is None or next_id in known_ids:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    "continuation returned no unique numeric Slurm ID"
                )
                continue
            attempts.append(
                {
                    "attempt": len(attempts) + 1,
                    "slurm_job_id": next_id,
                    "submitted_at": _now(),
                    "script_sha256": row["script_sha256"],
                    "resource": resource,
                    "resumed_from_checkpoint": str(checkpoint),
                    "previous_terminal_state": state,
                }
            )
            known_ids.add(next_id)
            row["status"] = "submitted"

        record["submission_complete"] = all(
            bool(row.get("attempts")) for row in record["jobs"]
        )
        record["all_complete"] = all(
            row.get("status") == "complete" for row in record["jobs"]
        )
        if any(
            row.get("status") == "needs_attention"
            for row in record["jobs"]
        ):
            record["status"] = "needs_attention"
        elif record["all_complete"]:
            record["status"] = "complete"
        elif any(
            row.get("status") == "policy_deferred"
            for row in record["jobs"]
        ):
            record["status"] = "policy_deferred"
        else:
            record["status"] = "submitted"
        record["updated_at"] = _now()
        _atomic_write(destination, record)
        return record


def _remote_paths(team_root: Path) -> LaunchPaths:
    source = team_root / "source"
    return LaunchPaths(
        team_root=team_root,
        source_root=source,
        manifest=source
        / "results_research_program"
        / "production_manifest_v2.json",
        convergence_audit=team_root
        / "jobs"
        / "convergence_audit.json",
        source_preflight=source
        / "results_research_program"
        / "hpc"
        / "production_v2_validation_20260730.json",
        j2_validation=source
        / "results_research_program"
        / "hpc"
        / "j2_validation_20260730.json",
        reuse_attestations=team_root
        / "jobs"
        / "production_v2_reuse_attestations.json",
        bundle_root=team_root / "jobs" / "production_a_bundles",
        record_path=team_root / "jobs" / "production_a_submission.json",
        cluster_root=team_root,
        python=str(team_root / "env" / "tenpy-py311" / "bin" / "python"),
        partition="xhacnormalb",
        account="giggleliu",
        base_manifest=source
        / "results_research_program"
        / "manifest.json",
        dataset_validation=team_root
        / "jobs"
        / "convergence_dataset_validation.json",
        convergence_data_root=team_root / "data" / "convergence",
    )


def _materialize_runtime_reuse(paths: LaunchPaths) -> dict[str, Any]:
    if (
        paths.base_manifest is None
        or paths.dataset_validation is None
        or paths.convergence_data_root is None
    ):
        raise ValueError("runtime reuse paths are incomplete")
    return write_reuse_attestations(
        output=paths.reuse_attestations,
        v2_manifest=paths.manifest,
        base_manifest=paths.base_manifest,
        data_root=paths.convergence_data_root,
        dataset_validation=paths.dataset_validation,
        convergence_audit=paths.convergence_audit,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--resume", action="store_true")
    parser.add_argument("--team-root", type=Path, default=DEFAULT_TEAM_ROOT)
    args = parser.parse_args()
    paths = _remote_paths(args.team_root)
    try:
        _validate_primary_gates(paths)
        if args.submit and paths.record_path.exists():
            raise FileExistsError(
                "production-A submission record exists; use --resume"
            )
        if args.submit or args.resume:
            _materialize_runtime_reuse(paths)
            plan = prepare_launch_plan(paths)
            if args.resume:
                refreshed = refresh_submitted_jobs(
                    plan,
                    record_path=paths.record_path,
                )
                if refreshed["status"] == "needs_attention":
                    print(
                        json.dumps(
                            {
                                "status": "needs_attention",
                                "record": str(paths.record_path),
                                "submission_performed": False,
                            },
                            sort_keys=True,
                        )
                    )
                    raise SystemExit(2)
            record = submit_plan(
                plan,
                record_path=paths.record_path,
                resume=args.resume,
            )
            print(
                json.dumps(
                    {
                        "status": record["status"],
                        "submitted_rows": sum(
                            bool(row["attempts"])
                            for row in record["jobs"]
                        ),
                        "submission_complete": record[
                            "submission_complete"
                        ],
                        "record": str(paths.record_path),
                    },
                    sort_keys=True,
                )
            )
            if record["status"] not in {"submitted", "complete"}:
                raise SystemExit(2)
            return

        if paths.reuse_attestations.is_file():
            reuse = _load_json(
                paths.reuse_attestations,
                label="production-v2 reuse attestations",
            )
        else:
            if (
                paths.base_manifest is None
                or paths.dataset_validation is None
                or paths.convergence_data_root is None
            ):
                raise ValueError("runtime reuse paths are incomplete")
            reuse = materialize_reuse_attestations(
                v2_manifest=paths.manifest,
                base_manifest=paths.base_manifest,
                data_root=paths.convergence_data_root,
                dataset_validation=paths.dataset_validation,
                convergence_audit=paths.convergence_audit,
            )
        with tempfile.TemporaryDirectory(
            prefix="kharkov-production-a-preflight-"
        ) as temporary:
            plan = prepare_launch_plan(
                paths,
                reuse_payload=reuse,
                bundle_root_override=Path(temporary),
            )
        print(
            json.dumps(
                {
                    "status": "ready",
                    "execute_rows": len(plan["jobs"]),
                    "reuse_rows": plan["reuse_count"],
                    "production_b_script_count": plan[
                        "production_b_script_count"
                    ],
                    "submission_performed": False,
                },
                sort_keys=True,
            )
        )
    except (OSError, ValueError) as error:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": str(error),
                    "submission_performed": False,
                },
                sort_keys=True,
            )
        )
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
