from __future__ import annotations

import json
from pathlib import Path

from scripts.build_production_v2_bundle import (
    DEFAULT_SOURCE_PREFLIGHT,
    _status,
    build_bundle,
    production_resource_spec,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads(
    (ROOT / "results_research_program" / "production_manifest_v2.json").read_text()
)


def _all_pass() -> dict[str, dict[str, str]]:
    return {
        "convergence": {"status": "accepted"},
        "source_preflight": {"status": "pass"},
        "j2": {"status": "pass"},
        "unblinding": {"status": "opened"},
    }


def test_default_source_preflight_matches_compute_evidence_name() -> None:
    assert DEFAULT_SOURCE_PREFLIGHT.name == "production_v2_validation_20260730.json"


def test_boolean_convergence_audit_is_recognized_as_accepted() -> None:
    assert _status({"accepted": True, "records": []}) == "accepted"
    assert _status({"accepted": False, "records": []}) == "missing"


def test_bundle_never_materializes_scripts_for_reuse_rows(tmp_path: Path) -> None:
    gates = _all_pass()
    reuse = {
        job["job_id"]: {"status": "accepted"}
        for job in MANIFEST["jobs"]
        if job["execution_mode"] == "reuse"
    }
    result = build_bundle(
        MANIFEST,
        outdir=tmp_path,
        cluster_root=Path("/cluster/project"),
        python="python3",
        gates=gates,
        reuse_attestations=reuse,
    )
    assert result.reuse_count == 2
    assert len(result.script_paths) == 66
    assert all("amp_mu005_up__production_a" not in path.name for path in result.script_paths)
    assert all("amp_mu005_down__production_a" not in path.name for path in result.script_paths)
    assert result.submission_performed is False


def test_convergence_not_accepted_blocks_every_execute_row(tmp_path: Path) -> None:
    gates = _all_pass()
    gates["convergence"] = {"status": "pending"}
    result = build_bundle(
        MANIFEST,
        outdir=tmp_path,
        cluster_root=Path("/cluster/project"),
        python="python3",
        gates=gates,
    )
    assert result.ready_count == 0
    assert result.submission_performed is False
    matrix = json.loads(result.matrix_path.read_text())
    assert matrix["summary"]["submission_performed"] is False
    assert {
        "convergence_gate_not_accepted"
    } <= set(matrix["records"][0]["block_reasons"])


def test_fcs_scripts_use_exact_registered_grid(tmp_path: Path) -> None:
    result = build_bundle(
        MANIFEST,
        outdir=tmp_path,
        cluster_root=Path("/cluster/project"),
        python="python3",
        gates=_all_pass(),
        reuse_attestations={
            job["job_id"]: {"status": "accepted"}
            for job in MANIFEST["jobs"]
            if job["execution_mode"] == "reuse"
        },
    )
    fcs_script = next(
        path for path in result.script_paths if "amp_mu002_up__production_a" in path.name
    )
    text = fcs_script.read_text()
    assert "--fcs-gamma '-0.6,-0.4,-0.2,0,0.2,0.4,0.6'" in text or (
        "--fcs-gamma -0.6,-0.4,-0.2,0,0.2,0.4,0.6" in text
    )
    assert "scripts/run_tenpy_production_job.py" in text
    assert "#SBATCH --cpus-per-task=32" in text
    assert "#SBATCH --mem=120G" in text


def test_cluster_script_separates_source_and_public_data_roots(
    tmp_path: Path,
) -> None:
    result = build_bundle(
        MANIFEST,
        outdir=tmp_path,
        cluster_root=Path("/public/team/kharkov"),
        source_root=Path("/public/team/kharkov/source"),
        python="/public/team/kharkov/env/tenpy-py311/bin/python",
        gates=_all_pass(),
        reuse_attestations={
            job["job_id"]: {"status": "accepted"}
            for job in MANIFEST["jobs"]
            if job["execution_mode"] == "reuse"
        },
    )
    script = next(
        path
        for path in result.script_paths
        if "amp_mu002_up__production_a" in path.name
    ).read_text()
    assert "cd /public/team/kharkov/source" in script
    assert (
        "--manifest "
        "/public/team/kharkov/source/results_research_program/"
        "production_manifest_v2.json"
    ) in script
    assert (
        "--output /public/team/kharkov/data/research/raw/production_a/"
        "amp_mu002_up__production_a__v2.npz"
    ) in script
    assert "/public/team/kharkov/scripts/run_tenpy_production_job.py" not in script


def test_non_fcs_resource_matches_accepted_fine_pilot_ratio() -> None:
    job = next(
        job
        for job in MANIFEST["jobs"]
        if job["stage"] == "production_a"
        and job["execution_mode"] == "execute"
        and "fcs_logZ" not in job["observables"]
    )
    assert production_resource_spec(job) == {
        "cpus": 16,
        "memory": "60G",
        "walltime": "7-00:00:00",
        "fcs": False,
        "resource_pilot_job_id": "23009308",
    }


def test_generated_batch_submitter_is_permanently_disabled(
    tmp_path: Path,
) -> None:
    build_bundle(
        MANIFEST,
        outdir=tmp_path,
        cluster_root=Path("/cluster/project"),
        python="python3",
        gates=_all_pass(),
        reuse_attestations={
            job["job_id"]: {"status": "accepted"}
            for job in MANIFEST["jobs"]
            if job["execution_mode"] == "reuse"
        },
    )
    text = (tmp_path / "submit_ready.sh").read_text()
    assert "submit_production_a.py" in text
    assert "\nsbatch " not in text
    assert "exit 2" in text


def test_production_b_remains_blocked_without_unblinding(tmp_path: Path) -> None:
    gates = _all_pass()
    gates["unblinding"] = None
    result = build_bundle(
        MANIFEST,
        outdir=tmp_path,
        cluster_root=Path("/cluster/project"),
        python="python3",
        gates=gates,
        reuse_attestations={
            job["job_id"]: {"status": "accepted"}
            for job in MANIFEST["jobs"]
            if job["execution_mode"] == "reuse"
        },
    )
    matrix = json.loads(result.matrix_path.read_text())
    assert all(
        "blinded_until_registered_unblinding" in row["block_reasons"]
        for row in matrix["records"]
        if row["stage"] == "production_b"
    )
