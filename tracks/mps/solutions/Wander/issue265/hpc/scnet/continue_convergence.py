#!/usr/bin/env python3
"""Continue timed-out SCNet convergence slices and run the frozen gate."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from src.convergence_source_gate import (
    SourceGateError,
    validate_source_gate,
)


ROOT = Path("/work/share/giggleliu/cfys01/kharkov_burgers_20260729")
SOURCE = ROOT / "source"
MANIFEST = SOURCE / "results_research_program" / "manifest.json"
AMENDMENT = (
    SOURCE
    / "results_research_program"
    / "hpc"
    / "convergence_source_20260729"
    / "amendment.json"
)
RUNNER = SOURCE / "scripts" / "run_tenpy_research_job.py"
BACKEND = SOURCE / "src" / "tenpy_research_backend.py"
ENTRYPOINT = SOURCE / "hpc" / "scnet" / "run_convergence.sbatch"
CONTROLLER_ENTRYPOINT = (
    SOURCE / "hpc" / "scnet" / "continuation_controller.sbatch"
)
RECORD_PATH = ROOT / "jobs" / "convergence_submission.json"
CLUSTER_MANIFEST = ROOT / "jobs" / "cluster_manifest.json"
VALIDATION_REPORT = ROOT / "jobs" / "convergence_dataset_validation.json"
CONVERGENCE_REPORT = ROOT / "jobs" / "convergence_audit.json"

RECOVERABLE_STATES = {
    "TIMEOUT",
    "NODE_FAIL",
    "PREEMPTED",
    "BOOT_FAIL",
}
ACTIVE_STATES = {
    "PENDING",
    "RUNNING",
    "CONFIGURING",
    "COMPLETING",
    "SUSPENDED",
}
MAX_ATTEMPTS = 12


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(
    command: list[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        capture_output=True,
        text=True,
    )


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    os.replace(temporary, path)


def _job_state(job_id: str) -> str:
    result = _run(
        [
            "sacct",
            "-j",
            job_id,
            "--starttime",
            "2026-07-29",
            "--format=JobIDRaw,State",
            "-X",
            "-n",
            "-P",
        ]
    )
    for line in result.stdout.splitlines():
        fields = line.split("|")
        if len(fields) >= 2 and fields[0] == job_id:
            return fields[1].split("+", 1)[0]
    queue = _run(["squeue", "-h", "-j", job_id, "-o", "%T"])
    if queue.stdout.strip():
        return queue.stdout.strip().splitlines()[0]
    return "UNKNOWN"


def _output_is_complete(job: dict[str, Any]) -> bool:
    output = Path(str(job["output"]))
    summary = output.with_suffix(".run.json")
    if not output.is_file() or output.stat().st_size == 0:
        return False
    if not summary.is_file() or summary.stat().st_size == 0:
        return False
    try:
        payload = json.loads(summary.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("status") == "complete"
        and payload.get("job_id") == job["job_id"]
        and Path(str(payload.get("output", ""))) == output
    )


def _checkpoint_is_usable(job: dict[str, Any]) -> bool:
    checkpoint = Path(str(job["output"]) + ".checkpoint.h5")
    return checkpoint.is_file() and checkpoint.stat().st_size > 0


def _normalise_attempts(
    job: dict[str, Any],
    *,
    submitted_at: str,
) -> list[dict[str, Any]]:
    attempts = job.setdefault("attempts", [])
    if not attempts:
        attempts.append(
            {
                "slice": 1,
                "slurm_job_id": str(job["slurm_job_id"]),
                "submitted_at": submitted_at,
                "resource": deepcopy(job["resource"]),
            }
        )
    return attempts


def _adapt_oom_resource(resource: dict[str, Any]) -> dict[str, Any] | None:
    memory_text = str(resource["memory"])
    if not memory_text.endswith("G"):
        return None
    memory_gib = int(memory_text[:-1])
    if memory_gib >= 480:
        return None
    next_memory = min(480, 2 * memory_gib)
    # Keep below the observed xhacnormalb ceiling of about 3.9 GiB/core.
    next_cpus = min(128, max(int(resource["cpus"]), math.ceil(next_memory / 3.75)))
    if next_memory / next_cpus > 3.9:
        return None
    return {
        "cpus": next_cpus,
        "memory": f"{next_memory}G",
        "time": str(resource["time"]),
    }


def _submit_slice(
    job: dict[str, Any],
    *,
    resource: dict[str, Any],
    slice_index: int,
) -> str:
    job_id = str(job["job_id"])
    log_stem = ROOT / "logs" / f"{job_id}.slice{slice_index}"
    result = _run(
        [
            "sbatch",
            "--parsable",
            f"--job-name=kh_{job_id}_s{slice_index}"[:128],
            f"--cpus-per-task={resource['cpus']}",
            f"--mem={resource['memory']}",
            f"--time={resource['time']}",
            f"--output={log_stem}.%j.out",
            f"--error={log_stem}.%j.err",
            "--requeue",
            f"--export=ALL,KH_JOB_ID={job_id}",
            str(ENTRYPOINT),
        ]
    )
    return result.stdout.strip().split(";", 1)[0]


def _source_attestation(job_id: str) -> dict[str, Any]:
    """Return the frozen source attestation for one continuation job."""

    return validate_source_gate(
        submission_path=RECORD_PATH,
        manifest_path=MANIFEST,
        amendment_path=AMENDMENT,
        job_id=job_id,
        runner_path=RUNNER,
        backend_path=BACKEND,
    ).as_dict()


def _submit_gated_slice(
    job: dict[str, Any],
    *,
    resource: dict[str, Any],
    slice_index: int,
) -> tuple[str, dict[str, Any]]:
    """Check provenance before calling sbatch for a continuation slice."""

    attestation = _source_attestation(str(job["job_id"]))
    slurm_id = _submit_slice(
        job,
        resource=resource,
        slice_index=slice_index,
    )
    return slurm_id, attestation


def _schedule_controller(
    job_ids: list[str],
    *,
    generation: int,
) -> str:
    dependency = "afterany:" + ":".join(job_ids)
    result = _run(
        [
            "sbatch",
            "--parsable",
            f"--job-name=kh_conv_ctl_g{generation}",
            "--cpus-per-task=2",
            "--mem=6G",
            "--time=00:30:00",
            f"--dependency={dependency}",
            f"--output={ROOT / 'logs' / f'controller-g{generation}.%j.out'}",
            f"--error={ROOT / 'logs' / f'controller-g{generation}.%j.err'}",
            f"--export=ALL,KH_CONTROLLER_GENERATION={generation}",
            str(CONTROLLER_ENTRYPOINT),
        ]
    )
    return result.stdout.strip().split(";", 1)[0]


def _materialise_cluster_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text())
    cluster_manifest = deepcopy(manifest)
    for job in cluster_manifest["jobs"]:
        job["output_path"] = str(
            ROOT
            / "data"
            / str(job["stage"])
            / (str(job["job_id"]) + ".npz")
        )
    _atomic_write(CLUSTER_MANIFEST, cluster_manifest)


def _run_convergence_gate(record: dict[str, Any]) -> bool:
    _materialise_cluster_manifest()
    validation = _run(
        [
            sys.executable,
            str(SOURCE / "scripts" / "validate_research_datasets.py"),
            "--manifest",
            str(CLUSTER_MANIFEST),
            "--output",
            str(VALIDATION_REPORT),
        ],
        check=False,
    )
    audit = _run(
        [
            sys.executable,
            str(SOURCE / "scripts" / "run_convergence_audit.py"),
            "--manifest",
            str(CLUSTER_MANIFEST),
            "--output",
            str(CONVERGENCE_REPORT),
            "--require-accepted",
        ],
        check=False,
    )
    accepted = audit.returncode == 0
    record["convergence_gate"] = {
        "finished_at": _now(),
        "accepted": accepted,
        "validation_returncode": validation.returncode,
        "validation_stdout": validation.stdout.strip(),
        "validation_stderr": validation.stderr.strip(),
        "audit_returncode": audit.returncode,
        "audit_stdout": audit.stdout.strip(),
        "audit_stderr": audit.stderr.strip(),
        "cluster_manifest": str(CLUSTER_MANIFEST),
        "validation_report": str(VALIDATION_REPORT),
        "audit_report": str(CONVERGENCE_REPORT),
    }
    _atomic_write(RECORD_PATH, record)
    return accepted


def _schedule_initial_controller(record: dict[str, Any]) -> None:
    existing = record.get("active_controller_job_id")
    if existing:
        state = _job_state(str(existing))
        if state in ACTIVE_STATES:
            raise SystemExit(
                f"active continuation controller already exists: {existing}"
            )
        raise SystemExit(
            "a controller is already recorded but not active; inspect before "
            f"replacing it: {existing}={state}"
        )
    current_ids = [
        str(job.get("attempts", [{}])[-1].get("slurm_job_id")
            if job.get("attempts")
            else job["slurm_job_id"])
        for job in record["jobs"]
    ]
    controller_id = _schedule_controller(current_ids, generation=1)
    record.setdefault("controllers", []).append(
        {
            "generation": 1,
            "slurm_job_id": controller_id,
            "submitted_at": _now(),
            "dependency_job_ids": current_ids,
        }
    )
    record["active_controller_job_id"] = controller_id
    _atomic_write(RECORD_PATH, record)
    print(
        json.dumps(
            {
                "initial_controller_job_id": controller_id,
                "dependency_job_count": len(current_ids),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schedule-initial",
        action="store_true",
        help="Submit the first afterany controller for the recorded jobs.",
    )
    args = parser.parse_args()
    if not RECORD_PATH.is_file():
        raise SystemExit(f"submission record is missing: {RECORD_PATH}")
    record = json.loads(RECORD_PATH.read_text())
    if args.schedule_initial:
        _schedule_initial_controller(record)
        return
    generation = int(os.environ.get("KH_CONTROLLER_GENERATION", "1"))
    record["continuation_generation"] = generation
    record.setdefault("controllers", [])
    active: list[tuple[str, str]] = []
    for job in record["jobs"]:
        attempts = _normalise_attempts(
            job,
            submitted_at=str(record["submitted_at"]),
        )
        current_id = str(attempts[-1]["slurm_job_id"])
        state = _job_state(current_id)
        attempts[-1]["terminal_state"] = state
        if state in ACTIVE_STATES:
            active.append((str(job["job_id"]), state))
    if active:
        _atomic_write(RECORD_PATH, record)
        raise SystemExit(
            "controller ran before dependencies ended: "
            + ", ".join(f"{job_id}={state}" for job_id, state in active)
        )

    new_ids: list[str] = []
    attention: list[dict[str, str]] = []
    for job in record["jobs"]:
        attempts = job["attempts"]
        state = str(attempts[-1]["terminal_state"])
        if _output_is_complete(job):
            job["status"] = "complete"
            job["completed_at"] = _now()
            continue
        if len(attempts) >= MAX_ATTEMPTS:
            job["status"] = "needs_attention"
            attention.append(
                {
                    "job_id": str(job["job_id"]),
                    "reason": "maximum_attempts_reached",
                }
            )
            continue
        if state == "OUT_OF_MEMORY":
            resource = _adapt_oom_resource(dict(attempts[-1]["resource"]))
            if resource is None:
                job["status"] = "needs_attention"
                attention.append(
                    {
                        "job_id": str(job["job_id"]),
                        "reason": "oom_at_maximum_safe_resource",
                    }
                )
                continue
        elif state in RECOVERABLE_STATES:
            resource = dict(attempts[-1]["resource"])
        else:
            job["status"] = "needs_attention"
            attention.append(
                {
                    "job_id": str(job["job_id"]),
                    "reason": f"nonrecoverable_state:{state}",
                }
            )
            continue
        if not _checkpoint_is_usable(job):
            job["status"] = "needs_attention"
            attention.append(
                {
                    "job_id": str(job["job_id"]),
                    "reason": f"no_usable_checkpoint_after:{state}",
                }
            )
            continue
        slice_index = len(attempts) + 1
        try:
            slurm_id, source_attestation = _submit_gated_slice(
                job,
                resource=resource,
                slice_index=slice_index,
            )
        except SourceGateError as error:
            job["status"] = "needs_attention"
            attention.append(
                {
                    "job_id": str(job["job_id"]),
                    "reason": str(error),
                }
            )
            continue
        attempts.append(
            {
                "slice": slice_index,
                "slurm_job_id": slurm_id,
                "submitted_at": _now(),
                "resource": resource,
                "resumed_from_checkpoint": str(job["output"])
                + ".checkpoint.h5",
                "previous_terminal_state": state,
                "source_attestation": source_attestation,
            }
        )
        job["status"] = "running"
        job["slurm_job_id"] = slurm_id
        job["resource"] = resource
        new_ids.append(slurm_id)
        _atomic_write(RECORD_PATH, record)

    record["needs_attention"] = attention
    complete_count = sum(
        job.get("status") == "complete" for job in record["jobs"]
    )
    record["completed_job_count"] = complete_count
    record["all_complete"] = complete_count == len(record["jobs"])
    _atomic_write(RECORD_PATH, record)

    if attention:
        raise SystemExit(
            "continuation stopped for nonrecoverable jobs: "
            + ", ".join(item["job_id"] for item in attention)
        )
    if record["all_complete"]:
        accepted = _run_convergence_gate(record)
        if not accepted:
            raise SystemExit("all datasets completed but convergence gate failed")
        print(json.dumps({"all_complete": True, "accepted": True}))
        return
    if not new_ids:
        raise SystemExit("incomplete jobs remain but no continuation was submitted")

    next_generation = generation + 1
    controller_id = _schedule_controller(
        new_ids,
        generation=next_generation,
    )
    record["controllers"].append(
        {
            "generation": next_generation,
            "slurm_job_id": controller_id,
            "submitted_at": _now(),
            "dependency_job_ids": new_ids,
        }
    )
    record["active_controller_job_id"] = controller_id
    _atomic_write(RECORD_PATH, record)
    print(
        json.dumps(
            {
                "continued_jobs": len(new_ids),
                "next_controller_job_id": controller_id,
                "generation": next_generation,
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        raise
