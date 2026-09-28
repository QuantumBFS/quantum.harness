#!/usr/bin/env python3
"""Transactionally advance the registered two-mode analysis on SCNet."""

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
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[2]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from src.research_dataset import file_sha256
from src.two_mode_analysis_gate import (
    AnalysisPaths,
    prepare_analysis_plan,
    validate_aggregate,
    validate_cv_artifacts,
    validate_validation_summary,
)

DEFAULT_TEAM_ROOT = Path(
    "/work/share/giggleliu/cfys01/kharkov_burgers_20260729"
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
    "OUT_OF_MEMORY",
}
POLICY_MARKERS = (
    "AssocGrpSubmitJobsLimit",
    "QOSMaxSubmitJobPerUserLimit",
    "MaxSubmitJobs",
    "job violates accounting/QOS policy",
)
MAX_ATTEMPTS = 4
STAGE_ORDER = ("cross_validation", "aggregate", "validation")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    os.replace(temporary, path)


def _load_record(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"analysis submission record is invalid: {path}"
        ) from error
    if not isinstance(payload, dict):
        raise TypeError("analysis submission record must be an object")
    return dict(payload)


def _parse_slurm_id(stdout: str) -> str | None:
    matches = []
    for line in stdout.splitlines():
        match = re.fullmatch(
            r"(\d+)(?:;[^\s;]+)?",
            line.strip(),
        )
        if match:
            matches.append(match.group(1))
    return matches[0] if len(matches) == 1 else None


def _default_run(
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )


def _default_query_job(slurm_id: str) -> str:
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
    values = queue.stdout.strip().splitlines()
    return values[0] if values else "UNKNOWN"


def _default_query_array(slurm_id: str) -> dict[int, str]:
    result = subprocess.run(
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
    states: dict[int, str] = {}
    pattern = re.compile(rf"^{re.escape(slurm_id)}_(\d+)$")
    for line in result.stdout.splitlines():
        fields = line.split("|")
        if len(fields) < 2:
            continue
        match = pattern.fullmatch(fields[0])
        if match:
            states[int(match.group(1))] = fields[1].split("+", 1)[0]
    return states


def _validate_plan(plan: Mapping[str, Any]) -> None:
    if (
        plan.get("status") != "ready"
        or _canonical_sha256(plan.get("identity"))
        != plan.get("plan_sha256")
    ):
        raise ValueError("two-mode analysis plan hash is invalid")
    tasks = list(plan.get("tasks", []))
    if (
        len(tasks) != 27
        or {int(task["task_index"]) for task in tasks} != set(range(27))
    ):
        raise ValueError("two-mode analysis task set is not exact")
    for stage in STAGE_ORDER:
        script = Path(str(plan["scripts"][stage]))
        if (
            not script.is_file()
            or file_sha256(script)
            != plan["script_sha256"][stage]
        ):
            raise ValueError(f"analysis script is stale: {stage}")


def _record_from_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "status": "ready",
        "plan_sha256": str(plan["plan_sha256"]),
        "identity": dict(plan["identity"]),
        "stages": {
            stage: {
                "status": "ready",
                "script": str(plan["scripts"][stage]),
                "script_sha256": str(
                    plan["script_sha256"][stage]
                ),
                "resource": dict(plan["resources"][stage]),
                "attempts": [],
            }
            for stage in STAGE_ORDER
        },
    }


def _record_matches_plan(
    record: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> None:
    if (
        record.get("plan_sha256") != plan.get("plan_sha256")
        or _canonical_sha256(record.get("identity"))
        != _canonical_sha256(plan.get("identity"))
    ):
        raise ValueError(
            "analysis record and current frozen plan differ"
        )
    for stage in STAGE_ORDER:
        recorded = record.get("stages", {}).get(stage, {})
        if (
            recorded.get("script") != plan["scripts"][stage]
            or recorded.get("script_sha256")
            != plan["script_sha256"][stage]
        ):
            raise ValueError(
                f"analysis stage source changed: {stage}"
            )


def _known_ids(record: Mapping[str, Any]) -> set[str]:
    return {
        str(attempt["slurm_job_id"])
        for stage in record["stages"].values()
        for attempt in stage.get("attempts", [])
    }


def _submission_command(
    plan: Mapping[str, Any],
    stage: str,
    *,
    task_indexes: list[int] | None,
    resource: Mapping[str, Any],
    override: bool,
) -> list[str]:
    command = ["sbatch", "--parsable"]
    if override:
        if stage == "cross_validation" and task_indexes is not None:
            command.append(
                "--array=" + ",".join(map(str, task_indexes))
            )
        command.extend(
            [
                f"--cpus-per-task={resource['cpus']}",
                f"--mem={resource['memory']}",
                f"--time={resource['walltime']}",
            ]
        )
    command.append(str(plan["scripts"][stage]))
    return command


def _submit_stage(
    record: dict[str, Any],
    plan: Mapping[str, Any],
    *,
    stage: str,
    run_command: Callable[
        [list[str]], subprocess.CompletedProcess[str]
    ],
    task_indexes: list[int] | None = None,
    resource: Mapping[str, Any] | None = None,
    previous_state: str | None = None,
    override: bool = False,
) -> None:
    stage_record = record["stages"][stage]
    selected_resource = dict(
        stage_record["resource"] if resource is None else resource
    )
    command = _submission_command(
        plan,
        stage,
        task_indexes=task_indexes,
        resource=selected_resource,
        override=override,
    )
    result = run_command(command)
    combined = "\n".join(
        [str(result.stdout or ""), str(result.stderr or "")]
    )
    if int(result.returncode) != 0:
        stage_record["last_submission_error"] = combined.strip()[-4000:]
        if any(marker in combined for marker in POLICY_MARKERS):
            stage_record["status"] = "policy_deferred"
            record["status"] = "policy_deferred"
        else:
            stage_record["status"] = "needs_attention"
            record["status"] = "needs_attention"
        return
    slurm_id = _parse_slurm_id(str(result.stdout or ""))
    if slurm_id is None or slurm_id in _known_ids(record):
        stage_record["status"] = "needs_attention"
        stage_record["last_submission_error"] = (
            "sbatch returned no unique numeric Slurm ID"
        )
        record["status"] = "needs_attention"
        return
    attempt = {
        "attempt": len(stage_record["attempts"]) + 1,
        "slurm_job_id": slurm_id,
        "submitted_at": _now(),
        "script_sha256": stage_record["script_sha256"],
        "resource": selected_resource,
    }
    if stage == "cross_validation":
        attempt["task_indexes"] = (
            list(range(27))
            if task_indexes is None
            else list(task_indexes)
        )
    if previous_state is not None:
        attempt["previous_terminal_state"] = previous_state
    stage_record["attempts"].append(attempt)
    stage_record["status"] = "submitted"
    record["status"] = (
        "cv_submitted"
        if stage == "cross_validation"
        else f"{stage}_submitted"
    )


def _adapt_oom_resource(
    resource: Mapping[str, Any],
) -> dict[str, Any] | None:
    memory_text = str(resource["memory"])
    if not memory_text.endswith("G"):
        return None
    memory = int(memory_text[:-1])
    if memory >= 480:
        return None
    next_memory = min(480, 2 * memory)
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
        "memory": f"{next_memory}G",
        "cpus": next_cpus,
    }


def retryable_missing_indexes(
    expected: set[int],
    valid: set[int],
    element_states: Mapping[int, str],
) -> list[int]:
    """Return sorted missing indexes only when every state is recoverable."""

    missing = sorted(expected - valid)
    if not missing:
        return []
    nonrecoverable = {
        index: str(element_states.get(index, "UNKNOWN"))
        for index in missing
        if str(element_states.get(index, "UNKNOWN"))
        not in RECOVERABLE_STATES
    }
    if nonrecoverable:
        detail = ", ".join(
            f"{index}:{state}"
            for index, state in sorted(nonrecoverable.items())
        )
        raise ValueError(
            "missing CV indexes are not safely retryable: " + detail
        )
    return missing


def freeze_validation_selection(
    validation: Mapping[str, Any],
    *,
    record: Mapping[str, Any],
    aggregate_path: Path,
    destination: Path,
) -> dict[str, Any]:
    """Write or verify the byte-stable immutable selection record."""

    if validation.get("status") != "valid":
        raise ValueError("validation verdict is not valid")
    aggregate_hash = file_sha256(aggregate_path)
    if aggregate_hash != validation.get("aggregate_sha256"):
        raise ValueError("validation aggregate hash changed")
    summary = dict(validation["summary"])
    payload = {
        "schema_version": 1,
        "status": "frozen",
        "validation_status": validation["validation_status"],
        "production_b_eligible": bool(
            validation["production_b_eligible"]
        ),
        "terminal_negative": bool(validation["terminal_negative"]),
        "analysis_sha256": summary["analysis_sha256"],
        "parameters_refit_on_blind_data": summary[
            "parameters_refit_on_blind_data"
        ],
        "source_summary_path": str(validation["path"]),
        "source_summary_sha256": validation["artifact_sha256"],
        "aggregate_path": str(aggregate_path),
        "aggregate_sha256": aggregate_hash,
        "analysis_submission_record_sha256": _canonical_sha256(record),
        "plan_sha256": record["plan_sha256"],
        "validation_summary": summary,
    }
    payload["selection_sha256"] = _canonical_sha256(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if destination.exists():
            observed = _load_record(destination)
            if observed != payload:
                raise FileExistsError(
                    "a different validation selection is already frozen"
                )
            return observed
        _atomic_write(destination, payload)
    return payload


def _mark_attention(
    record: dict[str, Any],
    *,
    stage: str,
    reason: str,
) -> None:
    record["stages"][stage]["status"] = "needs_attention"
    record["stages"][stage]["last_submission_error"] = reason
    record["status"] = "needs_attention"


def _retry_resource(
    stage_record: Mapping[str, Any],
    state: str,
) -> dict[str, Any] | None:
    current = dict(
        stage_record["attempts"][-1].get(
            "resource",
            stage_record["resource"],
        )
    )
    return (
        _adapt_oom_resource(current)
        if state == "OUT_OF_MEMORY"
        else current
    )


def _resume_cv(
    record: dict[str, Any],
    plan: Mapping[str, Any],
    *,
    run_command: Callable[
        [list[str]], subprocess.CompletedProcess[str]
    ],
    query_job: Callable[[str], str],
    query_array: Callable[[str], Mapping[int, str]],
) -> bool:
    stage = record["stages"]["cross_validation"]
    artifacts = validate_cv_artifacts(plan)
    if artifacts.get("status") == "complete":
        stage["status"] = "complete"
        stage["artifact"] = artifacts
        record["status"] = "cv_complete"
        return True
    if artifacts.get("extra_files") or artifacts.get("invalid"):
        _mark_attention(
            record,
            stage="cross_validation",
            reason="invalid or extra cross-validation shard",
        )
        stage["artifact"] = artifacts
        return False
    if not stage["attempts"]:
        _submit_stage(
            record,
            plan,
            stage="cross_validation",
            run_command=run_command,
        )
        return False
    attempt = stage["attempts"][-1]
    state = str(query_job(str(attempt["slurm_job_id"]))).split(
        "+", 1
    )[0]
    attempt["last_checked_at"] = _now()
    attempt["terminal_state"] = state
    if state in ACTIVE_STATES:
        stage["status"] = "submitted"
        record["status"] = "cv_submitted"
        return False
    if len(stage["attempts"]) >= MAX_ATTEMPTS:
        _mark_attention(
            record,
            stage="cross_validation",
            reason="maximum cross-validation attempts reached",
        )
        return False
    element_states = query_array(str(attempt["slurm_job_id"]))
    try:
        missing = retryable_missing_indexes(
            set(range(27)),
            set(map(int, artifacts.get("valid_indexes", []))),
            element_states,
        )
    except ValueError as error:
        _mark_attention(
            record,
            stage="cross_validation",
            reason=str(error),
        )
        return False
    resource = dict(attempt["resource"])
    missing_states = {
        str(element_states[index]) for index in missing
    }
    previous_state = state
    if "OUT_OF_MEMORY" in missing_states:
        adapted = _adapt_oom_resource(resource)
        if adapted is None:
            _mark_attention(
                record,
                stage="cross_validation",
                reason="OOM exceeds safe SCNet resource envelope",
            )
            return False
        resource = adapted
        previous_state = "OUT_OF_MEMORY"
    _submit_stage(
        record,
        plan,
        stage="cross_validation",
        run_command=run_command,
        task_indexes=missing,
        resource=resource,
        previous_state=previous_state,
        override=True,
    )
    return False


def _resume_single_stage(
    record: dict[str, Any],
    plan: Mapping[str, Any],
    *,
    stage_name: str,
    validation: Mapping[str, Any],
    run_command: Callable[
        [list[str]], subprocess.CompletedProcess[str]
    ],
    query_job: Callable[[str], str],
) -> bool:
    stage = record["stages"][stage_name]
    if validation.get("status") == "valid":
        stage["status"] = "complete"
        stage["artifact"] = dict(validation)
        record["status"] = f"{stage_name}_complete"
        return True
    if not stage["attempts"]:
        _submit_stage(
            record,
            plan,
            stage=stage_name,
            run_command=run_command,
        )
        return False
    attempt = stage["attempts"][-1]
    state = str(query_job(str(attempt["slurm_job_id"]))).split(
        "+", 1
    )[0]
    attempt["last_checked_at"] = _now()
    attempt["terminal_state"] = state
    if state in ACTIVE_STATES:
        stage["status"] = "submitted"
        record["status"] = f"{stage_name}_submitted"
        return False
    if state not in RECOVERABLE_STATES:
        _mark_attention(
            record,
            stage=stage_name,
            reason=(
                f"{stage_name} ended {state} without a valid artifact"
            ),
        )
        stage["artifact"] = dict(validation)
        return False
    if len(stage["attempts"]) >= MAX_ATTEMPTS:
        _mark_attention(
            record,
            stage=stage_name,
            reason=f"maximum {stage_name} attempts reached",
        )
        return False
    resource = _retry_resource(stage, state)
    if resource is None:
        _mark_attention(
            record,
            stage=stage_name,
            reason="OOM exceeds safe SCNet resource envelope",
        )
        return False
    _submit_stage(
        record,
        plan,
        stage=stage_name,
        run_command=run_command,
        resource=resource,
        previous_state=state,
        override=True,
    )
    return False


def submit_or_advance(
    plan: Mapping[str, Any],
    *,
    record_path: Path,
    selection_path: Path,
    submit: bool,
    resume: bool,
    run_command: Callable[
        [list[str]], subprocess.CompletedProcess[str]
    ] = _default_run,
    query_job: Callable[[str], str] = _default_query_job,
    query_array: Callable[
        [str], Mapping[int, str]
    ] = _default_query_array,
) -> dict[str, Any]:
    """Apply one transactional state transition and return the saved record."""

    _validate_plan(plan)
    if submit == resume:
        raise ValueError("choose exactly one of submit or resume")
    record_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = record_path.with_suffix(record_path.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if submit:
            if record_path.exists():
                raise FileExistsError(
                    "analysis submission record exists; use --resume"
                )
            record = _record_from_plan(plan)
            _atomic_write(record_path, record)
            _submit_stage(
                record,
                plan,
                stage="cross_validation",
                run_command=run_command,
            )
            record["updated_at"] = _now()
            _atomic_write(record_path, record)
            return record

        if not record_path.is_file():
            raise FileNotFoundError(
                "analysis submission record is missing"
            )
        record = _load_record(record_path)
        _record_matches_plan(record, plan)
        if record.get("status") == "decision_frozen":
            return record
        if record.get("status") == "needs_attention":
            return record

        cv_complete = _resume_cv(
            record,
            plan,
            run_command=run_command,
            query_job=query_job,
            query_array=query_array,
        )
        if not cv_complete:
            record["updated_at"] = _now()
            _atomic_write(record_path, record)
            return record

        aggregate_stage = record["stages"]["aggregate"]
        if not aggregate_stage["attempts"]:
            _submit_stage(
                record,
                plan,
                stage="aggregate",
                run_command=run_command,
            )
            record["updated_at"] = _now()
            _atomic_write(record_path, record)
            return record
        aggregate_complete = _resume_single_stage(
            record,
            plan,
            stage_name="aggregate",
            validation=validate_aggregate(plan),
            run_command=run_command,
            query_job=query_job,
        )
        if not aggregate_complete:
            record["updated_at"] = _now()
            _atomic_write(record_path, record)
            return record

        validation_stage = record["stages"]["validation"]
        if not validation_stage["attempts"]:
            _submit_stage(
                record,
                plan,
                stage="validation",
                run_command=run_command,
            )
            record["updated_at"] = _now()
            _atomic_write(record_path, record)
            return record
        verdict = validate_validation_summary(plan)
        validation_complete = _resume_single_stage(
            record,
            plan,
            stage_name="validation",
            validation=verdict,
            run_command=run_command,
            query_job=query_job,
        )
        if not validation_complete:
            record["updated_at"] = _now()
            _atomic_write(record_path, record)
            return record

        aggregate_path = Path(str(plan["cv_outdir"])) / "summary.json"
        frozen = freeze_validation_selection(
            verdict,
            record=record,
            aggregate_path=aggregate_path,
            destination=selection_path,
        )
        record["status"] = "decision_frozen"
        record["selection"] = {
            "path": str(selection_path),
            "selection_sha256": frozen["selection_sha256"],
            "validation_status": frozen["validation_status"],
            "production_b_eligible": frozen[
                "production_b_eligible"
            ],
        }
        record["updated_at"] = _now()
        _atomic_write(record_path, record)
        return record


def _remote_paths(team_root: Path) -> AnalysisPaths:
    source = team_root / "source"
    return AnalysisPaths(
        team_root=team_root,
        source_root=source,
        production_record=team_root
        / "jobs"
        / "production_a_submission.json",
        reuse_attestations=team_root
        / "jobs"
        / "production_v2_reuse_attestations.json",
        convergence_audit=team_root / "jobs" / "convergence_audit.json",
        manifest=source
        / "results_research_program"
        / "production_manifest_v2.json",
        base_manifest=source
        / "results_research_program"
        / "manifest.json",
        rules=source
        / "configs"
        / "two_mode_fcs_decision_rules_20260730.json",
        solver_budget=source
        / "results_research_program"
        / "two_mode"
        / "solver_budget.json",
        data_root=team_root / "data" / "research" / "raw",
        analysis_root=team_root / "analysis" / "two_mode",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--resume", action="store_true")
    parser.add_argument("--team-root", type=Path, default=DEFAULT_TEAM_ROOT)
    args = parser.parse_args()
    paths = _remote_paths(args.team_root)
    record_path = (
        args.team_root / "jobs" / "two_mode_analysis_submission.json"
    )
    selection_path = (
        args.team_root / "jobs" / "validation_selection.json"
    )
    try:
        plan = prepare_analysis_plan(paths)
        if not args.submit and not args.resume:
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "task_count": len(plan["tasks"]),
                        "stages": list(STAGE_ORDER),
                        "production_b_script_count": 0,
                        "submission_performed": False,
                    },
                    sort_keys=True,
                )
            )
            return
        record = submit_or_advance(
            plan,
            record_path=record_path,
            selection_path=selection_path,
            submit=args.submit,
            resume=args.resume,
        )
        print(
            json.dumps(
                {
                    "status": record["status"],
                    "record": str(record_path),
                    "selection": record.get("selection"),
                },
                sort_keys=True,
            )
        )
        if record["status"] in {
            "needs_attention",
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
