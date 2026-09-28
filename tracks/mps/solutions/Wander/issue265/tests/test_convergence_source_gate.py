from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from scripts.build_convergence_source_amendment import build_amendment
from src.convergence_source_gate import (
    SourceGateError,
    canonical_sha256,
    sha256_file,
    submission_identity,
    validate_source_gate,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _job_id(index: int) -> str:
    return f"condition_{index:02d}__convergence__fine"


def _record() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "submitted_at": "2026-07-29T13:54:13+00:00",
        "cluster": "SCNet xh5",
        "partition": "xhacnormalb",
        "account": "giggleliu",
        "team_root": "/remote/root",
        "source_root": "/remote/root/source",
        "pilot_job_id": "100",
        "pilot_state": "COMPLETED",
        "manifest_sha256": "",
        "runner_sha256": "",
        "jobs": [
            {
                "job_id": _job_id(index),
                "condition_id": f"condition_{index:02d}",
                "resolution_level": "fine",
                "fcs": index < 6,
                "resource": {
                    "cpus": 16,
                    "memory": "60G",
                    "time": "7-00:00:00",
                },
                "slurm_job_id": str(200 + index),
                "output": f"/remote/root/data/{_job_id(index)}.npz",
            }
            for index in range(12)
        ],
        "submission_complete": True,
    }


def _manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "jobs": [
            {
                "job_id": _job_id(index),
                "condition_id": f"condition_{index:02d}",
                "stage": "convergence",
                "resolution_level": "fine",
                "t_max": 200.0,
                "condition": {"j2": 0.0},
                "numerics": {
                    "L": 512,
                    "dt": 0.0125,
                    "chi_max": 1024,
                    "truncation_cutoff": 1e-11,
                },
            }
            for index in range(12)
        ],
    }


def _valid_fixture(tmp_path: Path) -> dict[str, Path]:
    paths = {
        name: tmp_path / name
        for name in (
            "submission.json",
            "manifest.json",
            "amendment.json",
            "runner.py",
            "backend.py",
            "original_runner.py",
            "original_backend.py",
        )
    }
    paths["runner.py"].write_bytes(b"current runner\n")
    paths["backend.py"].write_bytes(b"current backend\n")
    paths["original_runner.py"].write_bytes(b"original runner\n")
    paths["original_backend.py"].write_bytes(b"original backend\n")
    manifest = _manifest()
    _write_json(paths["manifest.json"], manifest)
    record = _record()
    record["manifest_sha256"] = sha256_file(paths["manifest.json"])
    record["runner_sha256"] = sha256_file(paths["original_runner.py"])
    _write_json(paths["submission.json"], record)
    amendment = {
        "schema_version": 1,
        "created_at": "2026-07-30T00:00:00+00:00",
        "status": "pass",
        "submission": {
            "path": "/remote/root/jobs/convergence_submission.json",
            "identity_sha256": canonical_sha256(
                submission_identity(record)
            ),
        },
        "manifest": {
            "path": "results_research_program/manifest.json",
            "sha256": sha256_file(paths["manifest.json"]),
        },
        "original_source": {
            "runner_sha256": sha256_file(paths["original_runner.py"]),
            "backend_sha256": sha256_file(paths["original_backend.py"]),
        },
        "recovered_artifacts": [
            {
                "path": "original_runner.py",
                "sha256": sha256_file(paths["original_runner.py"]),
            },
            {
                "path": "original_backend.py",
                "sha256": sha256_file(paths["original_backend.py"]),
            },
        ],
        "allowed_source_pairs": [
            {
                "pair_id": "first_slice",
                "runner_sha256": sha256_file(paths["original_runner.py"]),
                "backend_sha256": sha256_file(paths["original_backend.py"]),
            },
            {
                "pair_id": "j2_extended_j2zero_validated",
                "runner_sha256": sha256_file(paths["runner.py"]),
                "backend_sha256": sha256_file(paths["backend.py"]),
            },
        ],
        "all_job_equivalence": {
            "status": "pass",
            "expected_job_count": 12,
            "jobs": [
                {
                    "job_id": _job_id(index),
                    "status": "pass",
                    "numerics_exact": True,
                    "time_grid_exact": True,
                    "time_grid_points": 1001,
                    "canonical_job_sha256_exact": True,
                }
                for index in range(12)
            ],
        },
        "cross_version_resume": {
            "status": "pass",
            "interrupted_process_exit_code": 143,
            "maximum_array_difference": 0.0,
            "threshold": 1e-13,
        },
    }
    _write_json(paths["amendment.json"], amendment)
    return paths


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def test_submission_identity_survives_controller_bookkeeping() -> None:
    original = _record()
    mutated = deepcopy(original)
    mutated["active_controller_job_id"] = "999"
    mutated["controllers"] = [{"generation": 2}]
    first = mutated["jobs"][0]
    first["attempts"] = [
        {
            "slice": 1,
            "slurm_job_id": first["slurm_job_id"],
            "resource": deepcopy(first["resource"]),
        },
        {
            "slice": 2,
            "slurm_job_id": "1000",
            "resource": {
                "cpus": 32,
                "memory": "120G",
                "time": "7-00:00:00",
            },
        },
    ]
    first["slurm_job_id"] = "1000"
    first["resource"] = deepcopy(first["attempts"][1]["resource"])
    assert canonical_sha256(
        submission_identity(original)
    ) == canonical_sha256(submission_identity(mutated))


def test_submission_identity_changes_if_initial_slice_changes() -> None:
    record = _record()
    changed = deepcopy(record)
    changed["jobs"][0]["slurm_job_id"] = "different"
    assert submission_identity(record) != submission_identity(changed)


def test_valid_source_pair_returns_attestation(tmp_path: Path) -> None:
    paths = _valid_fixture(tmp_path)
    result = validate_source_gate(
        submission_path=paths["submission.json"],
        manifest_path=paths["manifest.json"],
        amendment_path=paths["amendment.json"],
        job_id=_job_id(0),
        runner_path=paths["runner.py"],
        backend_path=paths["backend.py"],
    )
    assert result.job_id == _job_id(0)
    assert result.source_pair_id == "j2_extended_j2zero_validated"
    assert result.runner_sha256 == sha256_file(paths["runner.py"])
    assert result.backend_sha256 == sha256_file(paths["backend.py"])
    assert len(result.evidence_sha256) == 64
    assert result.as_dict()["status"] == "pass"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("evidence_status", "amendment status is not pass"),
        ("submission_incomplete", "submission record is incomplete"),
        ("original_runner", "original runner hash mismatch"),
        ("identity", "submission identity mismatch"),
        ("manifest_hash", "manifest hash mismatch"),
        ("job_count", "expected exactly 12 submitted jobs"),
        ("comparison_count", "comparison job set mismatch"),
        ("comparison_status", "job comparison failed"),
        ("resume_exit", "interruption exit code is not 143"),
        ("resume_threshold", "resume difference is not below threshold"),
        ("unknown_job", "requested job is not in the submission record"),
        ("production_stage", "requested manifest job is not convergence"),
        ("j2", "requested manifest job has nonzero J2"),
        ("artifact", "recovered artifact hash mismatch"),
    ],
)
def test_gate_rejects_invalid_evidence(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    paths = _valid_fixture(tmp_path)
    record = _load(paths["submission.json"])
    manifest = _load(paths["manifest.json"])
    amendment = _load(paths["amendment.json"])
    job_id = _job_id(0)

    if mutation == "evidence_status":
        amendment["status"] = "pending"
    elif mutation == "submission_incomplete":
        record["submission_complete"] = False
        amendment["submission"]["identity_sha256"] = canonical_sha256(
            submission_identity(record)
        )
    elif mutation == "original_runner":
        record["runner_sha256"] = hashlib.sha256(b"unexpected").hexdigest()
        amendment["submission"]["identity_sha256"] = canonical_sha256(
            submission_identity(record)
        )
    elif mutation == "identity":
        amendment["submission"]["identity_sha256"] = "0" * 64
    elif mutation == "manifest_hash":
        amendment["manifest"]["sha256"] = "0" * 64
    elif mutation == "job_count":
        record["jobs"].pop()
        amendment["submission"]["identity_sha256"] = canonical_sha256(
            submission_identity(record)
        )
    elif mutation == "comparison_count":
        amendment["all_job_equivalence"]["jobs"].pop()
    elif mutation == "comparison_status":
        amendment["all_job_equivalence"]["jobs"][0]["status"] = "fail"
    elif mutation == "resume_exit":
        amendment["cross_version_resume"][
            "interrupted_process_exit_code"
        ] = 0
    elif mutation == "resume_threshold":
        amendment["cross_version_resume"]["maximum_array_difference"] = 1e-13
    elif mutation == "unknown_job":
        job_id = "not-registered"
    elif mutation == "production_stage":
        manifest["jobs"][0]["stage"] = "production_a"
        _write_json(paths["manifest.json"], manifest)
        manifest_hash = sha256_file(paths["manifest.json"])
        record["manifest_sha256"] = manifest_hash
        amendment["manifest"]["sha256"] = manifest_hash
        amendment["submission"]["identity_sha256"] = canonical_sha256(
            submission_identity(record)
        )
    elif mutation == "j2":
        manifest["jobs"][0]["condition"]["j2"] = 0.2
        _write_json(paths["manifest.json"], manifest)
        manifest_hash = sha256_file(paths["manifest.json"])
        record["manifest_sha256"] = manifest_hash
        amendment["manifest"]["sha256"] = manifest_hash
        amendment["submission"]["identity_sha256"] = canonical_sha256(
            submission_identity(record)
        )
    elif mutation == "artifact":
        paths["original_backend.py"].write_bytes(b"changed")

    _write_json(paths["submission.json"], record)
    _write_json(paths["amendment.json"], amendment)
    with pytest.raises(SourceGateError, match=message):
        validate_source_gate(
            submission_path=paths["submission.json"],
            manifest_path=paths["manifest.json"],
            amendment_path=paths["amendment.json"],
            job_id=job_id,
            runner_path=paths["runner.py"],
            backend_path=paths["backend.py"],
        )


def test_gate_rejects_unvalidated_hybrid_source_pair(
    tmp_path: Path,
) -> None:
    paths = _valid_fixture(tmp_path)
    with pytest.raises(
        SourceGateError,
        match="current source pair is not allowed",
    ):
        validate_source_gate(
            submission_path=paths["submission.json"],
            manifest_path=paths["manifest.json"],
            amendment_path=paths["amendment.json"],
            job_id=_job_id(0),
            runner_path=paths["original_runner.py"],
            backend_path=paths["backend.py"],
        )


def test_gate_rejects_malformed_json(tmp_path: Path) -> None:
    paths = _valid_fixture(tmp_path)
    paths["amendment.json"].write_text("{not-json")
    with pytest.raises(SourceGateError, match="cannot parse amendment"):
        validate_source_gate(
            submission_path=paths["submission.json"],
            manifest_path=paths["manifest.json"],
            amendment_path=paths["amendment.json"],
            job_id=_job_id(0),
            runner_path=paths["runner.py"],
            backend_path=paths["backend.py"],
        )


def test_amendment_builder_requires_and_freezes_all_twelve_jobs(
    tmp_path: Path,
) -> None:
    paths = _valid_fixture(tmp_path)
    amendment = _load(paths["amendment.json"])
    all_job_path = tmp_path / "all_job.json"
    resume_path = tmp_path / "resume.json"
    source_hashes = {
        "original_runner_sha256": sha256_file(
            paths["original_runner.py"]
        ),
        "original_backend_sha256": sha256_file(
            paths["original_backend.py"]
        ),
        "current_runner_sha256": sha256_file(paths["runner.py"]),
        "current_backend_sha256": sha256_file(paths["backend.py"]),
    }
    _write_json(
        all_job_path,
        {
            "schema_version": 1,
            "status": "pass",
            **source_hashes,
            "jobs": amendment["all_job_equivalence"]["jobs"],
        },
    )
    _write_json(
        resume_path,
        {
            "schema_version": 1,
            "status": "pass",
            **source_hashes,
            "environment": {
                "python": "3.11.14",
                "tenpy": "1.0.6",
            },
            "interrupted_process_exit_code": 143,
            "maximum_array_difference": 0.0,
            "threshold": 1e-13,
        },
    )
    built = build_amendment(
        submission_path=paths["submission.json"],
        manifest_path=paths["manifest.json"],
        original_runner_path=paths["original_runner.py"],
        original_backend_path=paths["original_backend.py"],
        current_runner_path=paths["runner.py"],
        current_backend_path=paths["backend.py"],
        all_job_report_path=all_job_path,
        resume_report_path=resume_path,
        output_path=paths["amendment.json"],
        created_at="2026-07-30T00:00:00+00:00",
    )
    assert built["status"] == "pass"
    assert len(built["all_job_equivalence"]["jobs"]) == 12
    assert len(built["allowed_source_pairs"]) == 2
    assert (
        built["allowed_source_pairs"][0]["runner_sha256"]
        != built["allowed_source_pairs"][1]["runner_sha256"]
    )

    incomplete = _load(all_job_path)
    incomplete["jobs"].pop()
    _write_json(all_job_path, incomplete)
    with pytest.raises(
        SourceGateError,
        match="does not cover exactly 12 jobs",
    ):
        build_amendment(
            submission_path=paths["submission.json"],
            manifest_path=paths["manifest.json"],
            original_runner_path=paths["original_runner.py"],
            original_backend_path=paths["original_backend.py"],
            current_runner_path=paths["runner.py"],
            current_backend_path=paths["backend.py"],
            all_job_report_path=all_job_path,
            resume_report_path=resume_path,
            output_path=paths["amendment.json"],
        )


def _run_cli(paths: dict[str, Path], *, backend: Path) -> subprocess.CompletedProcess[str]:
    script = (
        Path(__file__).resolve().parents[1]
        / "hpc"
        / "scnet"
        / "check_convergence_source.py"
    )
    return subprocess.run(
        [
            sys.executable,
            str(script),
            "--job-id",
            _job_id(0),
            "--submission",
            str(paths["submission.json"]),
            "--manifest",
            str(paths["manifest.json"]),
            "--amendment",
            str(paths["amendment.json"]),
            "--runner",
            str(paths["runner.py"]),
            "--backend",
            str(backend),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_source_gate_cli_emits_compact_attestation(
    tmp_path: Path,
) -> None:
    paths = _valid_fixture(tmp_path)
    result = _run_cli(paths, backend=paths["backend.py"])
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["job_id"] == _job_id(0)


def test_source_gate_cli_fails_without_running_unvalidated_pair(
    tmp_path: Path,
) -> None:
    paths = _valid_fixture(tmp_path)
    changed_backend = tmp_path / "changed_backend.py"
    changed_backend.write_bytes(b"not validated\n")
    result = _run_cli(paths, backend=changed_backend)
    assert result.returncode != 0
    assert result.stdout == ""
    assert "source_gate: current source pair is not allowed" in result.stderr
