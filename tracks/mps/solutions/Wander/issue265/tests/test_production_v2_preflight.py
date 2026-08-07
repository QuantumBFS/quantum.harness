from __future__ import annotations

import copy
from pathlib import Path

from scripts.validate_production_v2_preflight import (
    build_preflight_evidence,
    evidence_is_current,
)


ROOT = Path(__file__).resolve().parents[1]


def test_local_evidence_stays_cluster_pending_without_runtime() -> None:
    evidence = build_preflight_evidence(
        manifest_path=ROOT
        / "results_research_program"
        / "production_manifest_v2.json",
        j2_evidence_path=ROOT
        / "results_research_program"
        / "hpc"
        / "j2_validation_20260730.json",
        fcs_summary_path=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "fcs_validation"
        / "summary.json",
        resume_summary_path=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "resume_validation"
        / "summary.json",
        runtime=None,
    )
    assert evidence["status"] == "local_pass_cluster_pending"
    assert evidence["submission_performed"] is False
    assert evidence_is_current(evidence)


def test_evidence_invalidates_when_a_source_hash_changes() -> None:
    evidence = build_preflight_evidence(
        manifest_path=ROOT
        / "results_research_program"
        / "production_manifest_v2.json",
        j2_evidence_path=ROOT
        / "results_research_program"
        / "hpc"
        / "j2_validation_20260730.json",
        fcs_summary_path=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "fcs_validation"
        / "summary.json",
        resume_summary_path=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "resume_validation"
        / "summary.json",
        runtime=None,
    )
    stale = copy.deepcopy(evidence)
    key = next(iter(stale["source_closure"]["files"]))
    stale["source_closure"]["files"][key] = "0" * 64
    assert evidence_is_current(stale) is False
