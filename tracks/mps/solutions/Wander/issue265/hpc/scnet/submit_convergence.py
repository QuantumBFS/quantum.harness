#!/usr/bin/env python3
"""Submit the twelve preregistered convergence jobs exactly once on SCNet."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path("/work/share/giggleliu/cfys01/kharkov_burgers_20260729")
SOURCE = ROOT / "source"
MANIFEST = SOURCE / "results_research_program" / "manifest.json"
ENTRYPOINT = SOURCE / "hpc" / "scnet" / "run_convergence.sbatch"
SUBMISSION_RECORD = ROOT / "jobs" / "convergence_submission.json"

# xhacnormalb has 128 cores and about 500 GiB per node, with an effective
# per-core memory ceiling close to 3.9 GiB.  The registered coarse/FCS pilot
# (SCNet job 23009308) reached chi=136 at L=256 with 339 MiB MaxRSS.  Scaling
# that measurement as L*chi^2 predicts about 39 GiB for fine/FCS at chi=1024.
# The requests below leave at least a factor-three memory margin while avoiding
# the cost and queue penalty of whole-node allocations.  FCS jobs evolve three
# counting branches plus the physical branch; non-FCS jobs evolve only the
# physical branch.
RESOURCES: dict[tuple[str, bool], dict[str, str | int]] = {
    ("coarse", False): {"cpus": 4, "memory": "12G", "time": "7-00:00:00"},
    ("coarse", True): {"cpus": 8, "memory": "24G", "time": "7-00:00:00"},
    ("medium", False): {"cpus": 8, "memory": "30G", "time": "7-00:00:00"},
    ("medium", True): {"cpus": 16, "memory": "60G", "time": "7-00:00:00"},
    ("fine", False): {"cpus": 16, "memory": "60G", "time": "7-00:00:00"},
    ("fine", True): {"cpus": 32, "memory": "120G", "time": "7-00:00:00"},
}


def _run(command: list[str]) -> str:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pilot_state(job_id: str) -> str:
    output = _run(
        [
            "sacct",
            "-j",
            job_id,
            "--starttime",
            "2026-07-29",
            "--format=JobIDRaw,State",
            "-n",
            "-P",
        ]
    )
    states = [
        line.split("|", 1)[1].split("+", 1)[0]
        for line in output.splitlines()
        if line.startswith(job_id + "|")
    ]
    if not states:
        raise RuntimeError(f"pilot job {job_id} was not found by sacct")
    return states[0]


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pilot-job-id",
        required=True,
        help="Completed registered-resolution resource pilot required by gate.",
    )
    args = parser.parse_args()

    if SUBMISSION_RECORD.exists():
        raise SystemExit(
            f"refusing duplicate submission; record exists: {SUBMISSION_RECORD}"
        )
    if not MANIFEST.is_file() or not ENTRYPOINT.is_file():
        raise SystemExit("deployed manifest or SCNet entry point is missing")
    state = _pilot_state(args.pilot_job_id)
    if state != "COMPLETED":
        raise SystemExit(
            f"resource pilot {args.pilot_job_id} is {state}, not COMPLETED"
        )

    manifest = json.loads(MANIFEST.read_text())
    jobs = [job for job in manifest["jobs"] if job["stage"] == "convergence"]
    if len(jobs) != 12:
        raise SystemExit(f"expected 12 convergence jobs, found {len(jobs)}")

    record: dict[str, Any] = {
        "schema_version": 1,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "cluster": "SCNet xh5",
        "partition": "xhacnormalb",
        "account": "giggleliu",
        "team_root": str(ROOT),
        "source_root": str(SOURCE),
        "pilot_job_id": args.pilot_job_id,
        "pilot_state": state,
        "manifest_sha256": _sha256(MANIFEST),
        "runner_sha256": _sha256(
            SOURCE / "scripts" / "run_tenpy_research_job.py"
        ),
        "jobs": [],
        "submission_complete": False,
    }
    _atomic_write(SUBMISSION_RECORD, record)

    try:
        for job in jobs:
            job_id = str(job["job_id"])
            level = str(job["resolution_level"])
            fcs = "fcs_logZ" in job.get("observables", [])
            resource = dict(RESOURCES[(level, fcs)])
            log_stem = ROOT / "logs" / job_id
            slurm_id = _run(
                [
                    "sbatch",
                    "--parsable",
                    f"--job-name=kh_{job_id}"[:128],
                    f"--cpus-per-task={resource['cpus']}",
                    f"--mem={resource['memory']}",
                    f"--time={resource['time']}",
                    f"--output={log_stem}.%j.out",
                    f"--error={log_stem}.%j.err",
                    "--requeue",
                    f"--export=ALL,KH_JOB_ID={job_id}",
                    str(ENTRYPOINT),
                ]
            ).split(";", 1)[0]
            record["jobs"].append(
                {
                    "job_id": job_id,
                    "condition_id": job["condition_id"],
                    "resolution_level": level,
                    "fcs": fcs,
                    "resource": resource,
                    "slurm_job_id": slurm_id,
                    "output": str(
                        ROOT / "data" / "convergence" / f"{job_id}.npz"
                    ),
                }
            )
            _atomic_write(SUBMISSION_RECORD, record)
    except Exception as error:
        record["submission_error"] = f"{type(error).__name__}: {error}"
        _atomic_write(SUBMISSION_RECORD, record)
        raise

    record["submission_complete"] = True
    _atomic_write(SUBMISSION_RECORD, record)
    print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        raise
