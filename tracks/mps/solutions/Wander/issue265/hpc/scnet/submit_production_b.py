#!/usr/bin/env python3
"""Prepare, submit, or safely resume the gated Production-B program."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[2]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from hpc.scnet.submit_production_a import (
    ACTIVE_STATES,
    MAX_ATTEMPTS,
    POLICY_MARKERS,
    RECOVERABLE_STATES,
    _adapt_oom_resource,
    _atomic_write,
    _canonical_sha256,
    _default_run,
    _default_state_query,
    _load_json,
    _now,
    _parse_slurm_id,
)
from scripts.build_production_v2_bundle import (
    build_bundle,
    production_resource_spec,
)
from src.production_b_gate import (
    ProductionBGatePaths,
    remote_gate_paths,
    validate_unblinding_record,
)
from src.production_output_validation import validate_production_output
from src.research_dataset import file_sha256

DEFAULT_TEAM_ROOT = Path(
    "/work/share/giggleliu/cfys01/kharkov_burgers_20260729"
)
SOURCE_CLOSURE = (
    "hpc/scnet/submit_production_b.py",
    "hpc/scnet/submit_production_a.py",
    "scripts/build_production_v2_bundle.py",
    "scripts/run_tenpy_production_job.py",
    "scripts/run_tenpy_research_job.py",
    "scripts/unblind_research_test.py",
    "src/production_b_gate.py",
    "src/production_b_policy.py",
    "src/production_initial_conditions.py",
    "src/production_output_validation.py",
    "src/tenpy_research_backend.py",
)


@dataclass(frozen=True)
class ProductionBLaunchPaths:
    """Registered paths for the Production-B controller."""

    gate: ProductionBGatePaths
    bundle_root: Path
    record_path: Path
    cluster_root: Path
    python: str
    partition: str
    account: str


def _source_hashes(source_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in SOURCE_CLOSURE:
        path = source_root / relative
        if not path.is_file():
            raise ValueError(f"Production-B source is missing: {relative}")
        hashes[relative] = file_sha256(path)
    return hashes


def _validate_materialized_bundle(
    bundle_dir: Path,
    *,
    expected_ids: list[str],
) -> dict[str, Path]:
    if not bundle_dir.is_dir():
        raise ValueError("immutable bundle directory is missing")
    scripts = {path.stem: path for path in bundle_dir.glob("*.sbatch")}
    if set(scripts) != set(expected_ids):
        raise ValueError("immutable bundle script set changed")
    matrix_path = bundle_dir / "execution_matrix.json"
    matrix = _load_json(matrix_path, label="Production-B execution matrix")
    summary = dict(matrix.get("summary", {}))
    records = [
        dict(record)
        for record in matrix.get("records", [])
        if isinstance(record, Mapping)
    ]
    if (
        summary.get("ready_execute_rows") != 34
        or summary.get("reuse_rows") != 0
        or summary.get("blocked_rows") != 0
        or summary.get("submission_performed") is not False
        or len(records) != 34
        or {str(record.get("job_id")) for record in records}
        != set(expected_ids)
        or any(
            record.get("stage") != "production_b"
            or record.get("status") != "ready"
            or record.get("script")
            != str(bundle_dir / f"{record.get('job_id')}.sbatch")
            for record in records
        )
    ):
        raise ValueError("immutable bundle execution matrix changed")
    submit_guard = bundle_dir / "submit_ready.sh"
    if not submit_guard.is_file():
        raise ValueError("immutable bundle submission guard is missing")
    return scripts


def _materialize_immutable_bundle(
    manifest: Mapping[str, Any],
    *,
    bundle_dir: Path,
    expected_ids: list[str],
    paths: ProductionBLaunchPaths,
    unblinding: Mapping[str, Any],
) -> dict[str, Path]:
    bundle_dir.parent.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{bundle_dir.name}.staging-",
            dir=bundle_dir.parent,
        )
    )
    try:
        result = build_bundle(
            manifest,
            outdir=stage_dir,
            cluster_root=paths.cluster_root,
            source_root=paths.gate.source_root,
            python=paths.python,
            gates={
                "convergence": {"status": "accepted"},
                "source_preflight": {"status": "pass"},
                "j2": {"status": "pass"},
                "unblinding": unblinding,
            },
            reuse_attestations={},
            partition=paths.partition,
            account=paths.account,
        )
        if (
            result.ready_count != 34
            or result.reuse_count != 0
            or result.blocked_count != 0
            or result.submission_performed
        ):
            raise ValueError(
                "staged bundle does not match the frozen Production-B "
                "launch counts"
            )
        staged_scripts = {
            path.stem: path for path in result.script_paths
        }
        if set(staged_scripts) != set(expected_ids):
            raise ValueError(
                "staged Production-B scripts differ from registered rows"
            )

        if bundle_dir.exists():
            final_scripts = _validate_materialized_bundle(
                bundle_dir,
                expected_ids=expected_ids,
            )
            changed = [
                job_id
                for job_id in expected_ids
                if file_sha256(final_scripts[job_id])
                != file_sha256(staged_scripts[job_id])
            ]
            if (
                changed
                or file_sha256(bundle_dir / "submit_ready.sh")
                != file_sha256(stage_dir / "submit_ready.sh")
            ):
                raise ValueError(
                    "immutable bundle content changed: "
                    + ", ".join(changed or ["submit_ready.sh"])
                )
            return final_scripts

        matrix = _load_json(
            result.matrix_path,
            label="staged Production-B execution matrix",
        )
        for record in matrix.get("records", []):
            if record.get("script") is not None:
                record["script"] = str(
                    bundle_dir / Path(str(record["script"])).name
                )
        result.matrix_path.write_text(
            json.dumps(matrix, indent=2, ensure_ascii=False) + "\n"
        )
        os.replace(stage_dir, bundle_dir)
        return _validate_materialized_bundle(
            bundle_dir,
            expected_ids=expected_ids,
        )
    finally:
        if stage_dir.exists():
            shutil.rmtree(stage_dir)


def prepare_launch_plan(
    paths: ProductionBLaunchPaths,
    *,
    bundle_root_override: Path | None = None,
) -> dict[str, Any]:
    """Freeze the exact 34-job plan without invoking Slurm."""

    unblinding = validate_unblinding_record(paths.gate)
    manifest = _load_json(
        paths.gate.manifest,
        label="production-v2 manifest",
    )
    rows = [
        dict(job)
        for job in manifest.get("jobs", [])
        if job.get("stage") == "production_b"
    ]
    fcs_count = sum(job.get("fcs_gamma") is not None for job in rows)
    if (
        len(rows) != 34
        or fcs_count != 3
        or any(job.get("execution_mode") != "execute" for job in rows)
        or any(job.get("blinded") is not True for job in rows)
    ):
        raise ValueError(
            "Production-B launch set must be exactly 34 execute rows "
            "including exactly 3 FCS rows"
        )
    source_sha256 = _source_hashes(paths.gate.source_root)
    evidence_sha256 = {
        "unblinding_record": file_sha256(
            paths.gate.unblinding_record
        ),
        **{
            f"unblinding_bound_{key}": str(value)
            for key, value in dict(
                unblinding.get("evidence_sha256", {})
            ).items()
        },
    }
    identity = {
        "schema_version": 1,
        "stage": "production_b",
        "execute_rows": [
            {
                "job_id": str(job["job_id"]),
                "resource": production_resource_spec(job),
                "depends_on": list(job.get("depends_on", [])),
            }
            for job in rows
        ],
        "runtime": {
            "cluster_root": str(paths.cluster_root.resolve()),
            "python": paths.python,
            "partition": paths.partition,
            "account": paths.account,
        },
        "source_sha256": source_sha256,
        "evidence_sha256": evidence_sha256,
        "selection_sha256": unblinding["selection_sha256"],
        "analysis_sha256": unblinding["analysis_sha256"],
        "validation_status": unblinding["validation_status"],
    }
    plan_sha256 = _canonical_sha256(identity)
    bundle_parent = bundle_root_override or paths.bundle_root
    bundle_dir = Path(bundle_parent) / plan_sha256
    filtered_manifest = {
        "summary": dict(manifest.get("summary", {})),
        "jobs": rows,
    }
    expected_ids = [str(job["job_id"]) for job in rows]
    scripts = _materialize_immutable_bundle(
        filtered_manifest,
        bundle_dir=bundle_dir,
        expected_ids=expected_ids,
        paths=paths,
        unblinding=unblinding,
    )
    by_id = {str(job["job_id"]): job for job in rows}
    jobs: list[dict[str, Any]] = []
    for job_id in expected_ids:
        script = scripts[job_id]
        job = by_id[job_id]
        jobs.append(
            {
                "job_id": job_id,
                "condition_id": str(job["condition_id"]),
                "stage": "production_b",
                "script": str(script.resolve()),
                "script_sha256": file_sha256(script),
                "job": dict(job),
                "resource": production_resource_spec(job),
                "output": str(
                    (
                        paths.cluster_root
                        / "data"
                        / "research"
                        / "raw"
                        / "production_b"
                        / f"{job_id}.npz"
                    ).resolve()
                ),
            }
        )
    return {
        "schema_version": 1,
        "status": "ready",
        "plan_sha256": plan_sha256,
        "identity": identity,
        "bundle_dir": str(bundle_dir.resolve()),
        "execute_count": 34,
        "fcs_count": fcs_count,
        "production_a_script_count": 0,
        "jobs": jobs,
    }


def _record_from_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "status": "submitting",
        "stage": "production_b",
        "plan_sha256": str(plan["plan_sha256"]),
        "identity": dict(plan["identity"]),
        "bundle_dir": str(plan["bundle_dir"]),
        "execute_count": int(plan["execute_count"]),
        "fcs_count": int(plan["fcs_count"]),
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
            "Production-B submission record and launch plan hash differ"
        )
    if [row["job_id"] for row in record.get("jobs", [])] != [
        row["job_id"] for row in plan["jobs"]
    ]:
        raise ValueError("Production-B submission record job set changed")
    for recorded, current in zip(
        record["jobs"],
        plan["jobs"],
        strict=True,
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
                    "Production-B submission source closure changed for "
                    f"{recorded['job_id']}"
                )


def _validate_plan(plan: Mapping[str, Any]) -> None:
    if (
        _canonical_sha256(dict(plan["identity"]))
        != str(plan.get("plan_sha256"))
        or len(plan.get("jobs", [])) != 34
        or int(plan.get("execute_count", -1)) != 34
        or int(plan.get("fcs_count", -1)) != 3
        or int(plan.get("production_a_script_count", -1)) != 0
    ):
        raise ValueError("Production-B launch plan identity is invalid")
    for row in plan["jobs"]:
        script = Path(str(row["script"]))
        job = row.get("job")
        if (
            row.get("stage") != "production_b"
            or not isinstance(job, Mapping)
            or job.get("job_id") != row.get("job_id")
            or job.get("stage") != "production_b"
            or job.get("execution_mode") != "execute"
            or not script.is_file()
            or file_sha256(script) != str(row.get("script_sha256"))
        ):
            raise ValueError(
                "Production-B launch script is missing or stale: "
                + str(row.get("job_id"))
            )


def _set_record_status(record: dict[str, Any]) -> None:
    record["submission_complete"] = all(
        bool(row.get("attempts")) for row in record["jobs"]
    )
    record["all_complete"] = all(
        row.get("status") == "complete" for row in record["jobs"]
    )
    statuses = {str(row.get("status")) for row in record["jobs"]}
    if "needs_attention" in statuses or statuses & {
        "submission_in_flight",
        "resubmission_in_flight",
    }:
        record["status"] = "needs_attention"
    elif record["all_complete"]:
        record["status"] = "complete"
    elif "policy_deferred" in statuses:
        record["status"] = "policy_deferred"
    elif record["submission_complete"]:
        record["status"] = "submitted"
    else:
        record["status"] = "needs_attention"
    record["updated_at"] = _now()


def submit_plan(
    plan: Mapping[str, Any],
    *,
    record_path: str | Path,
    run_command: Callable[
        [list[str]], subprocess.CompletedProcess[str]
    ] = _default_run,
    resume: bool = False,
) -> dict[str, Any]:
    """Submit each never-attempted row once with an atomic intent record."""

    _validate_plan(plan)
    destination = Path(record_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if destination.exists():
            if not resume:
                raise FileExistsError(
                    "Production-B submission record exists; use --resume"
                )
            record = _load_json(
                destination,
                label="Production-B submission record",
            )
            _record_matches_plan(record, plan)
        else:
            if resume:
                raise FileNotFoundError(
                    "Production-B submission record is missing"
                )
            record = _record_from_plan(plan)
            _atomic_write(destination, record)

        known_ids = {
            str(attempt["slurm_job_id"])
            for row in record["jobs"]
            for attempt in row.get("attempts", [])
        }
        for row in record["jobs"]:
            if row.get("status") in {
                "submission_in_flight",
                "resubmission_in_flight",
            }:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    "external submission may have occurred after a "
                    "controller interruption; reconcile Slurm manually"
                )
                _atomic_write(destination, record)
                continue
            if row.get("attempts"):
                continue
            if row.get("status") not in {"planned", "policy_deferred"}:
                continue
            row["status"] = "submission_in_flight"
            row["submission_intent_at"] = _now()
            record["updated_at"] = _now()
            _atomic_write(destination, record)
            result = run_command(
                ["sbatch", "--parsable", str(row["script"])]
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
                _set_record_status(record)
                _atomic_write(destination, record)
                return record
            slurm_id = _parse_slurm_id(str(result.stdout or ""))
            if slurm_id is None or slurm_id in known_ids:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    "sbatch returned no unique numeric Slurm ID"
                )
                _set_record_status(record)
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
            row.pop("submission_intent_at", None)
            known_ids.add(slurm_id)
            record["updated_at"] = _now()
            _atomic_write(destination, record)

        _set_record_status(record)
        _atomic_write(destination, record)
        return record


def refresh_submitted_jobs(
    plan: Mapping[str, Any],
    *,
    record_path: str | Path,
    query_state: Callable[[str], str] = _default_state_query,
    run_command: Callable[
        [list[str]], subprocess.CompletedProcess[str]
    ] = _default_run,
) -> dict[str, Any]:
    """Validate completed rows and resume only registered recoveries."""

    _validate_plan(plan)
    destination = Path(record_path)
    if not destination.is_file():
        raise FileNotFoundError(
            "Production-B submission record is missing"
        )
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        record = _load_json(
            destination,
            label="Production-B submission record",
        )
        _record_matches_plan(record, plan)
        known_ids = {
            str(attempt["slurm_job_id"])
            for row in record["jobs"]
            for attempt in row.get("attempts", [])
        }
        for row in record["jobs"]:
            if row.get("status") in {
                "submission_in_flight",
                "resubmission_in_flight",
            }:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    "external submission may have occurred after a "
                    "controller interruption; reconcile Slurm manually"
                )
                _atomic_write(destination, record)
                continue
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
                _atomic_write(destination, record)
                continue
            if state in ACTIVE_STATES:
                row["status"] = "submitted"
                _atomic_write(destination, record)
                continue
            if state == "COMPLETED":
                row["status"] = "needs_attention"
                row["validation"] = validation
                row["last_submission_error"] = (
                    "completed output validation failed: "
                    + ", ".join(map(str, validation.get("errors", [])))
                )
                _atomic_write(destination, record)
                continue
            if state == "OUT_OF_MEMORY":
                resource = _adapt_oom_resource(current["resource"])
                if resource is None:
                    row["status"] = "needs_attention"
                    row["last_submission_error"] = (
                        "OOM at maximum safe SCNet resource"
                    )
                    _atomic_write(destination, record)
                    continue
            elif state in RECOVERABLE_STATES:
                resource = dict(current["resource"])
            else:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    f"nonrecoverable terminal state: {state}"
                )
                _atomic_write(destination, record)
                continue
            checkpoint = Path(str(row["output"]) + ".checkpoint.h5")
            if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    f"no usable checkpoint after {state}"
                )
                _atomic_write(destination, record)
                continue
            if len(attempts) >= MAX_ATTEMPTS:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    "maximum continuation attempts reached"
                )
                _atomic_write(destination, record)
                continue
            row["status"] = "resubmission_in_flight"
            row["resubmission_intent"] = {
                "at": _now(),
                "previous_terminal_state": state,
                "resource": resource,
                "checkpoint": str(checkpoint),
            }
            _atomic_write(destination, record)
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
                row.pop("resubmission_intent", None)
                _atomic_write(destination, record)
                continue
            next_id = _parse_slurm_id(str(result.stdout or ""))
            if next_id is None or next_id in known_ids:
                row["status"] = "needs_attention"
                row["last_submission_error"] = (
                    "continuation returned no unique numeric Slurm ID"
                )
                row.pop("resubmission_intent", None)
                _atomic_write(destination, record)
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
            row.pop("resubmission_intent", None)
            _atomic_write(destination, record)

        _set_record_status(record)
        _atomic_write(destination, record)
        return record


def remote_launch_paths(team_root: Path) -> ProductionBLaunchPaths:
    source = team_root / "source"
    jobs = team_root / "jobs"
    return ProductionBLaunchPaths(
        gate=remote_gate_paths(team_root),
        bundle_root=jobs / "production_b_bundles",
        record_path=jobs / "production_b_submission.json",
        cluster_root=team_root,
        python=str(team_root / "env" / "tenpy-py311" / "bin" / "python"),
        partition="xhacnormalb",
        account="giggleliu",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--team-root",
        type=Path,
        default=DEFAULT_TEAM_ROOT,
    )
    args = parser.parse_args()
    paths = remote_launch_paths(args.team_root)
    try:
        plan = prepare_launch_plan(paths)
        if not args.submit and not args.resume:
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "execute_rows": plan["execute_count"],
                        "fcs_rows": plan["fcs_count"],
                        "production_a_script_count": plan[
                            "production_a_script_count"
                        ],
                        "validation_status": plan["identity"][
                            "validation_status"
                        ],
                        "submission_performed": False,
                    },
                    sort_keys=True,
                )
            )
            return
        if args.submit and paths.record_path.exists():
            raise FileExistsError(
                "Production-B submission record exists; use --resume"
            )
        if args.resume:
            refreshed = refresh_submitted_jobs(
                plan,
                record_path=paths.record_path,
            )
            if refreshed["status"] == "needs_attention":
                raise ValueError(
                    "Production-B record needs manual attention"
                )
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
                        bool(row["attempts"]) for row in record["jobs"]
                    ),
                    "submission_complete": record[
                        "submission_complete"
                    ],
                    "all_complete": record["all_complete"],
                    "record": str(paths.record_path),
                },
                sort_keys=True,
            )
        )
        if record["status"] not in {
            "submitted",
            "complete",
            "policy_deferred",
        }:
            raise SystemExit(2)
    except (OSError, TypeError, ValueError) as error:
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
