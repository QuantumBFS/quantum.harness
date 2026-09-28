from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.production_b_gate import (
    ProductionBGatePaths,
    build_unblinding_record,
    canonical_sha256,
    validate_unblinding_prerequisites,
    validate_unblinding_record,
)
from src.production_reuse_gate import ALLOWED_REUSE

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (dict, list)):
        path.write_text(json.dumps(payload, indent=2) + "\n")
    else:
        path.write_text(str(payload))
    return path


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _selection(
    *,
    status: str = "scalar_surrogate_not_rejected",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "status": "frozen",
        "validation_status": status,
        "production_b_eligible": status
        in {
            "scalar_surrogate_not_rejected",
            "independent_two_burgers_supported",
            "coupled_two_mode_supported",
        },
        "terminal_negative": status == "memory_or_more_modes_required",
        "analysis_sha256": "a" * 64,
        "parameters_refit_on_blind_data": False,
        "source_summary_path": "/unused/summary.json",
        "source_summary_sha256": "b" * 64,
        "aggregate_path": "/unused/aggregate.json",
        "aggregate_sha256": "c" * 64,
        "analysis_submission_record_sha256": "d" * 64,
        "plan_sha256": "e" * 64,
        "validation_summary": {"status": status},
    }
    payload["selection_sha256"] = canonical_sha256(payload)
    return payload


def _gate_paths(
    tmp_path: Path,
    *,
    selection_status: str = "scalar_surrogate_not_rejected",
) -> ProductionBGatePaths:
    evidence = tmp_path / "evidence"
    manifest = json.loads(
        (
            ROOT
            / "results_research_program"
            / "production_manifest_v2.json"
        ).read_text()
    )
    manifest_path = _write(evidence / "manifest.json", manifest)
    convergence = _write(
        evidence / "convergence.json",
        {
            "accepted": True,
            "records": [
                {"condition_id": "fixture", "accepted": True},
            ],
        },
    )
    source_file = ROOT / "src" / "production_b_policy.py"
    source_preflight = _write(
        evidence / "preflight.json",
        {
            "status": "pass",
            "source_closure": {
                "files": {
                    "src/production_b_policy.py": _file_sha256(
                        source_file
                    ),
                }
            },
        },
    )
    j2 = _write(
        evidence / "j2.json",
        {
            "status": "pass",
            "source_sha256": {
                "src/production_b_policy.py": _file_sha256(source_file),
            },
        },
    )

    a_jobs: list[dict[str, object]] = []
    for job in manifest["jobs"]:
        if (
            job["stage"] != "production_a"
            or job["execution_mode"] != "execute"
        ):
            continue
        output = _write(
            tmp_path / "data" / f"{job['job_id']}.npz",
            f"dataset:{job['job_id']}",
        )
        summary = _write(
            output.with_suffix(".run.json"),
            {"job_id": job["job_id"], "status": "complete"},
        )
        a_jobs.append(
            {
                "job_id": job["job_id"],
                "status": "complete",
                "output": str(output),
                "validation": {
                    "status": "valid",
                    "dataset_sha256": _file_sha256(output),
                    "run_summary_sha256": _file_sha256(summary),
                },
            }
        )
    production_a = _write(
        evidence / "production_a_submission.json",
        {
            "schema_version": 1,
            "stage": "production_a",
            "status": "complete",
            "submission_complete": True,
            "all_complete": True,
            "reuse_count": 2,
            "plan_sha256": "f" * 64,
            "jobs": a_jobs,
        },
    )

    reuse: dict[str, object] = {}
    for target, source in ALLOWED_REUSE.items():
        dataset = _write(
            tmp_path / "reuse" / f"{target}.npz",
            f"reuse:{target}",
        )
        summary = _write(
            dataset.with_suffix(".run.json"),
            {"job_id": source, "status": "complete"},
        )
        reuse[target] = {
            "status": "accepted",
            "source_job_id": source,
            "dataset_path": str(dataset),
            "dataset_sha256": _file_sha256(dataset),
            "run_summary_sha256": _file_sha256(summary),
        }
    reuse_path = _write(evidence / "reuse.json", reuse)

    selection_payload = _selection(status=selection_status)
    selection_path = _write(evidence / "selection.json", selection_payload)
    analysis_path = _write(
        evidence / "two_mode_analysis_submission.json",
        {
            "schema_version": 1,
            "stage": "two_mode_validation",
            "status": "decision_frozen",
            "plan_sha256": "e" * 64,
            "selection": {
                "path": str(selection_path),
                "selection_sha256": selection_payload["selection_sha256"],
                "validation_status": selection_status,
                "production_b_eligible": selection_payload[
                    "production_b_eligible"
                ],
            },
        },
    )
    rules = _write(evidence / "rules.json", {"schema_version": 1})
    analysis_rules = _write(
        evidence / "analysis_rules.json",
        {
            "bootstrap": {"seed": 20260730},
            "optimization": {"seed": 20260730},
        },
    )
    return ProductionBGatePaths(
        team_root=tmp_path / "team",
        source_root=ROOT,
        manifest=manifest_path,
        rules=rules,
        convergence_audit=convergence,
        source_preflight=source_preflight,
        j2_validation=j2,
        production_a_record=production_a,
        reuse_attestations=reuse_path,
        analysis_record=analysis_path,
        selection_record=selection_path,
        unblinding_record=tmp_path / "team" / "jobs" / "unblinding.json",
        analysis_rules=analysis_rules,
    )


def test_gate_accepts_complete_eligible_frozen_evidence(
    tmp_path: Path,
) -> None:
    paths = _gate_paths(tmp_path)
    evidence = validate_unblinding_prerequisites(paths)
    assert (
        evidence["validation_status"]
        == "scalar_surrogate_not_rejected"
    )
    assert evidence["production_a_execute_count"] == 32
    assert evidence["production_b_logical_count"] == 34
    assert evidence["production_b_fcs_count"] == 3


def test_gate_rejects_selection_hash_tamper(tmp_path: Path) -> None:
    paths = _gate_paths(tmp_path)
    selection = json.loads(paths.selection_record.read_text())
    selection["validation_status"] = "coupled_two_mode_supported"
    paths.selection_record.write_text(json.dumps(selection))
    with pytest.raises(ValueError, match="selection hash"):
        validate_unblinding_prerequisites(paths)


def test_gate_rejects_ineligible_candidate_family_failure(
    tmp_path: Path,
) -> None:
    paths = _gate_paths(
        tmp_path,
        selection_status="memory_or_more_modes_required",
    )
    with pytest.raises(ValueError, match="not eligible"):
        validate_unblinding_prerequisites(paths)


def test_gate_rejects_incomplete_production_a(tmp_path: Path) -> None:
    paths = _gate_paths(tmp_path)
    record = json.loads(paths.production_a_record.read_text())
    record["all_complete"] = False
    paths.production_a_record.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Production-A"):
        validate_unblinding_prerequisites(paths)


def test_gate_rejects_stale_preflight_source(tmp_path: Path) -> None:
    paths = _gate_paths(tmp_path)
    preflight = json.loads(paths.source_preflight.read_text())
    preflight["source_closure"]["files"][
        "src/production_b_policy.py"
    ] = "0" * 64
    paths.source_preflight.write_text(json.dumps(preflight))
    with pytest.raises(ValueError, match="source closure"):
        validate_unblinding_prerequisites(paths)


def test_gate_rejects_analysis_plan_hash_disagreement(
    tmp_path: Path,
) -> None:
    paths = _gate_paths(tmp_path)
    analysis = json.loads(paths.analysis_record.read_text())
    analysis["plan_sha256"] = "9" * 64
    paths.analysis_record.write_text(json.dumps(analysis))
    with pytest.raises(ValueError, match="analysis record disagree"):
        validate_unblinding_prerequisites(paths)


def test_unblinding_record_binds_all_evidence(tmp_path: Path) -> None:
    paths = _gate_paths(tmp_path)
    record = build_unblinding_record(
        paths,
        command="scripts/unblind_research_test.py --confirm-unblind",
        now="2026-07-30T12:00:00+00:00",
    )
    assert record["schema_version"] == 2
    assert record["status"] == "opened"
    assert record["protocol_version"] == "1.2"
    assert len(record["evidence_sha256"]) >= 8
    assert record["random_seeds"] == {
        "analysis_rules": [20260730],
    }
    _write(paths.unblinding_record, record)
    validated = validate_unblinding_record(paths)
    assert validated == record

    paths.rules.write_text('{"changed":true}\n')
    with pytest.raises(ValueError, match="evidence"):
        validate_unblinding_record(paths)
