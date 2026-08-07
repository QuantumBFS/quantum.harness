#!/usr/bin/env python3
"""Capture immutable per-cell Slurm accounting records from sacct stdin."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys


JOB_ID_RE = re.compile(r"^[1-9][0-9]*$")
CELL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def classify(state: str, exit_code: str) -> str:
    if state == "COMPLETED" and exit_code == "0:0":
        return "success"
    if state.startswith(("OUT_OF_ME", "OOM")):
        return "oom"
    if state == "TIMEOUT":
        return "walltime"
    if state == "FAILED":
        return "logic-failure" if exit_code == "0:0" else "nonzero-exit"
    if state.startswith("CANCELLED"):
        return "cancelled"
    if state in {"RUNNING", "PENDING", "REQUEUED"}:
        return "in-progress"
    return f"unknown:{state}"


def memory_bytes(text: str) -> int | None:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([KMGTPE]?)", text)
    if match is None or not text:
        return None
    powers = {"": 0, "K": 1, "M": 2, "G": 3, "T": 4, "P": 5, "E": 6}
    return int(float(match.group(1)) * (1024 ** powers[match.group(2)]))


def write_immutable(path: Path, payload: dict) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"refusing to replace accounting record: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8")


def capture(run_spec_path: Path, job_id: str, rows) -> dict:
    if JOB_ID_RE.fullmatch(job_id) is None:
        raise ValueError("job id must be a positive integer")
    run_spec = json.loads(run_spec_path.read_text(encoding="utf-8"))
    run_directory = Path(run_spec["run_dir"])
    if not run_directory.is_absolute():
        run_directory = Path.cwd() / run_directory
    cells = run_spec["cells"]

    grouped: dict[int, list[dict[str, str]]] = {}
    row_pattern = re.compile(
        rf"^{re.escape(job_id)}_([1-9][0-9]*)(?:\.[A-Za-z0-9_-]+)?$"
    )
    for row in rows:
        match = row_pattern.fullmatch(row.get("JobID", ""))
        if match is not None:
            grouped.setdefault(int(match.group(1)), []).append(row)

    recorded = []
    promoted = []
    for task_id, task_rows in sorted(grouped.items()):
        if not 1 <= task_id <= len(cells):
            raise ValueError(f"array task {task_id} is outside the run spec")
        parent_id = f"{job_id}_{task_id}"
        parents = [row for row in task_rows if row["JobID"] == parent_id]
        if len(parents) != 1:
            raise ValueError(f"expected one parent sacct row for {parent_id}")
        parent = parents[0]
        cell = cells[task_id - 1]
        cell_id = cell["cell_id"]
        if CELL_ID_RE.fullmatch(cell_id) is None:
            raise ValueError(f"unsafe cell id: {cell_id}")

        rss_candidates = []
        for row in task_rows:
            text = row.get("MaxRSS", "")
            value = memory_bytes(text)
            if value is not None:
                rss_candidates.append((value, text))
        max_rss_bytes, max_rss = (
            max(rss_candidates) if rss_candidates else (None, "")
        )
        allocated_cpus_text = parent.get("AllocCPUS", "")
        record = {
            "schema_version": 1,
            "purpose": "slurm-array-task-accounting",
            "accounting_source": "sacct",
            "sacct_units": "K",
            "cell_id": cell_id,
            "cell_index": task_id,
            "job_id": job_id,
            "array_task_id": task_id,
            "state": parent.get("State", ""),
            "exit_code": parent.get("ExitCode", ""),
            "classification": classify(
                parent.get("State", ""),
                parent.get("ExitCode", ""),
            ),
            "elapsed": parent.get("Elapsed", ""),
            "max_rss": max_rss,
            "max_rss_bytes": max_rss_bytes,
            "allocated_cpus": (
                int(allocated_cpus_text)
                if allocated_cpus_text.isdigit()
                else None
            ),
            "requested_memory": parent.get("ReqMem", ""),
            "partition": parent.get("Partition", ""),
            "node_list": parent.get("NodeList", ""),
        }
        cell_directory = run_directory / "cells" / cell_id
        attempt_path = (
            cell_directory
            / "slurm-attempts"
            / f"job-{job_id}-task-{task_id}.json"
        )
        write_immutable(attempt_path, record)
        recorded.append(cell_id)
        if record["classification"] == "success":
            write_immutable(
                cell_directory / "slurm-task-record.json",
                record,
            )
            promoted.append(cell_id)

    if not recorded:
        raise ValueError(f"sacct input contains no tasks for job {job_id}")
    return {
        "job_id": job_id,
        "attempts_recorded": recorded,
        "success_records_promoted": promoted,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", required=True, type=Path)
    parser.add_argument("--job-id", required=True)
    arguments = parser.parse_args()
    rows = csv.DictReader(sys.stdin, delimiter="|")
    summary = capture(arguments.run_spec, arguments.job_id, rows)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
