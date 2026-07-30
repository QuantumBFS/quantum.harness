#!/usr/bin/env python3
"""Validate available research datasets against the frozen manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_dataset import (
    file_sha256,
    load_research_dataset,
    validate_research_dataset,
)
from src.convergence_audit import audit_dataset_convergence
from src.research_protocol import load_decision_rules


def _metadata_matches(job: dict[str, Any], metadata: dict[str, Any]) -> list[str]:
    condition = job["condition"]
    numerics = job["numerics"]
    expected = {
        "delta": condition["delta"],
        "J2": condition["j2"],
        "temperature": condition["temperature"],
        "mu": condition["mu"],
        "orientation": condition["orientation"],
        "profile": condition["profile"],
        "width": condition["width"],
        "background_m": condition["background_m"],
        "L": numerics["L"],
        "time_step": numerics["dt"],
        "chi_max": numerics["chi_max"],
        "truncation_cutoff": numerics["truncation_cutoff"],
    }
    mismatches: list[str] = []
    for key, value in expected.items():
        observed = metadata.get(key)
        if isinstance(value, float):
            try:
                if abs(float(observed) - value) > 1e-12 * max(1.0, abs(value)):
                    mismatches.append(f"{key}: expected {value}, got {observed}")
            except (TypeError, ValueError):
                mismatches.append(f"{key}: expected {value}, got {observed}")
        elif observed != value:
            mismatches.append(f"{key}: expected {value}, got {observed}")
    return mismatches


def validate_manifest(
    manifest_path: Path,
    *,
    include_blinded: bool,
    rules_path: Path = ROOT / "configs" / "burgers_decision_rules.json",
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    records: list[dict[str, Any]] = []
    for job in manifest["jobs"]:
        if job["blinded"] and not include_blinded:
            records.append(
                {
                    "job_id": job["job_id"],
                    "status": "blinded_not_opened",
                    "path": job["output_path"],
                }
            )
            continue
        path = Path(job["output_path"])
        if not path.exists():
            records.append(
                {
                    "job_id": job["job_id"],
                    "status": "missing",
                    "path": str(path),
                }
            )
            continue
        try:
            dataset = load_research_dataset(path)
            validation = validate_research_dataset(dataset)
            mismatches = _metadata_matches(job, dataset.metadata)
            if dataset.condition_id != job["condition_id"]:
                mismatches.append(
                    "condition_id: expected "
                    f"{job['condition_id']}, got {dataset.condition_id}"
                )
            status = "valid" if not mismatches else "metadata_mismatch"
            records.append(
                {
                    "job_id": job["job_id"],
                    "status": status,
                    "path": str(path),
                    "file_sha256": file_sha256(path),
                    "mismatches": mismatches,
                    "validation": validation,
                }
            )
        except Exception as error:
            records.append(
                {
                    "job_id": job["job_id"],
                    "status": "invalid",
                    "path": str(path),
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    counts: dict[str, int] = {}
    for record in records:
        status = str(record["status"])
        counts[status] = counts.get(status, 0) + 1
    attempted = [
        record for record in records if record["status"] != "blinded_not_opened"
    ]
    complete = bool(attempted) and all(
        record["status"] == "valid" for record in attempted
    )
    rules = load_decision_rules(rules_path)
    job_by_id = {str(job["job_id"]): job for job in manifest["jobs"]}
    record_by_id = {str(record["job_id"]): record for record in records}
    condition_ids = sorted(
        {
            str(job["condition_id"])
            for job in manifest["jobs"]
            if job["stage"] == "convergence"
        }
    )
    convergence_records: list[dict[str, Any]] = []
    for condition_id in condition_ids:
        ids = {
            level: f"{condition_id}__convergence__{level}"
            for level in ("coarse", "medium", "fine")
        }
        unavailable = [
            job_id
            for job_id in ids.values()
            if record_by_id.get(job_id, {}).get("status") != "valid"
        ]
        if unavailable:
            convergence_records.append(
                {
                    "condition_id": condition_id,
                    "status": "simulation_missing",
                    "accepted": False,
                    "unavailable_job_ids": unavailable,
                }
            )
            continue
        datasets = {
            level: load_research_dataset(
                Path(job_by_id[job_id]["output_path"])
            )
            for level, job_id in ids.items()
        }
        result = audit_dataset_convergence(
            datasets["coarse"],
            datasets["medium"],
            datasets["fine"],
            profile_max=rules.threshold("profile_convergence_max"),
            width_max=rules.threshold("width_convergence_max"),
        )
        convergence_records.append(
            {"condition_id": condition_id, **result.to_dict()}
        )
    convergence_accepted = bool(convergence_records) and all(
        bool(record["accepted"]) for record in convergence_records
    )

    return {
        "schema_version": 1,
        "manifest_path": str(manifest_path.resolve()),
        "rules_path": str(rules_path.resolve()),
        "include_blinded": include_blinded,
        "complete": complete,
        "counts": counts,
        "convergence": {
            "accepted": convergence_accepted,
            "records": convergence_records,
        },
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "results_research_program" / "manifest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results_research_program" / "dataset_validation.json",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=ROOT / "configs" / "burgers_decision_rules.json",
    )
    parser.add_argument("--include-blinded", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    report = validate_manifest(
        args.manifest,
        include_blinded=args.include_blinded,
        rules_path=args.rules,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(report["counts"], ensure_ascii=False))
    if args.require_complete and not report["complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
