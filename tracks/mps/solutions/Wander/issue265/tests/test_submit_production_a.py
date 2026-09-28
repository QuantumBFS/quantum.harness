from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import hpc.scnet.submit_production_a as launcher
from hpc.scnet.submit_production_a import (
    LaunchPaths,
    prepare_launch_plan,
    refresh_submitted_jobs,
    submit_plan,
)
from src.production_reuse_gate import ALLOWED_REUSE

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paths(tmp_path: Path, *, convergence_accepted: bool = True) -> LaunchPaths:
    evidence = tmp_path / "evidence"
    return LaunchPaths(
        team_root=tmp_path / "team",
        source_root=ROOT,
        manifest=ROOT
        / "results_research_program"
        / "production_manifest_v2.json",
        convergence_audit=_write(
            evidence / "convergence.json",
            {
                "accepted": convergence_accepted,
                "records": [
                    {
                        "condition_id": "fixture",
                        "accepted": convergence_accepted,
                    }
                ],
            },
        ),
        source_preflight=_write(
            evidence / "preflight.json",
            {
                "status": "pass",
                "source_closure": {
                    "files": {
                        "scripts/run_tenpy_production_job.py": _sha256(
                            ROOT / "scripts/run_tenpy_production_job.py"
                        )
                    }
                },
            },
        ),
        j2_validation=_write(
            evidence / "j2.json",
            {
                "status": "pass",
                "source_sha256": {
                    "src/tenpy_research_backend.py": _sha256(
                        ROOT / "src/tenpy_research_backend.py"
                    )
                },
            },
        ),
        reuse_attestations=_write(
            evidence / "reuse.json",
            {
                target: {
                    "status": "accepted",
                    "source_job_id": source,
                }
                for target, source in ALLOWED_REUSE.items()
            },
        ),
        bundle_root=tmp_path / "bundles",
        record_path=tmp_path / "jobs" / "production_a_submission.json",
        cluster_root=tmp_path / "team",
        python="/cluster/python",
        partition="xhacnormalb",
        account="giggleliu",
    )


def _completed(
    returncode: int,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["sbatch"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_plan_has_exact_production_a_set_and_no_production_b(
    tmp_path: Path,
) -> None:
    plan = prepare_launch_plan(_paths(tmp_path))
    assert plan["status"] == "ready"
    assert len(plan["jobs"]) == 32
    assert plan["reuse_count"] == 2
    assert all(row["stage"] == "production_a" for row in plan["jobs"])
    assert all("__production_b" not in row["script"] for row in plan["jobs"])
    assert all(row["job"]["job_id"] == row["job_id"] for row in plan["jobs"])
    assert all(
        f"cd {ROOT}" in Path(row["script"]).read_text()
        for row in plan["jobs"]
    )
    assert len(plan["plan_sha256"]) == 64


def test_failed_gate_never_reaches_sbatch(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    with pytest.raises(ValueError, match="convergence"):
        plan = prepare_launch_plan(
            _paths(tmp_path, convergence_accepted=False)
        )
        submit_plan(
            plan,
            record_path=tmp_path / "record.json",
            run_command=lambda command: calls.append(command),
        )
    assert calls == []
    assert not (tmp_path / "record.json").exists()


def test_stale_compute_preflight_source_blocks_plan(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    preflight = json.loads(paths.source_preflight.read_text())
    preflight["source_closure"]["files"][
        "scripts/run_tenpy_production_job.py"
    ] = "0" * 64
    paths.source_preflight.write_text(json.dumps(preflight))
    with pytest.raises(ValueError, match="source closure is stale"):
        prepare_launch_plan(paths)


def test_partial_policy_rejection_resumes_without_duplicates(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    plan = prepare_launch_plan(paths)
    first_calls: list[str] = []

    def first_wave(command: list[str]):
        first_calls.append(command[-1])
        if len(first_calls) <= 2:
            return _completed(0, f"{9100 + len(first_calls)}\n")
        return _completed(
            1,
            stderr=(
                "sbatch: error: AssocGrpSubmitJobsLimit\n"
                "sbatch: error: Batch job submission failed"
            ),
        )

    partial = submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=first_wave,
    )
    assert partial["status"] == "policy_deferred"
    assert [
        row["attempts"][0]["slurm_job_id"]
        for row in partial["jobs"][:2]
    ] == ["9101", "9102"]
    assert partial["jobs"][2]["status"] == "policy_deferred"
    assert all(not row["attempts"] for row in partial["jobs"][2:])

    resumed_calls: list[str] = []

    def resumed_wave(command: list[str]):
        resumed_calls.append(command[-1])
        return _completed(0, f"{9200 + len(resumed_calls)}\n")

    completed = submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=resumed_wave,
        resume=True,
    )
    assert completed["status"] == "submitted"
    assert completed["submission_complete"] is True
    assert len(resumed_calls) == 30
    assert set(resumed_calls).isdisjoint(first_calls[:2])
    assert len(
        {
            row["attempts"][0]["slurm_job_id"]
            for row in completed["jobs"]
        }
    ) == 32


def test_warning_only_output_never_creates_fake_id(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    plan = prepare_launch_plan(paths)
    record = submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=lambda command: _completed(
            0,
            stdout="warning: locale unavailable\n",
        ),
    )
    assert record["status"] == "needs_attention"
    assert record["jobs"][0]["status"] == "needs_attention"
    assert record["jobs"][0]["attempts"] == []


def test_existing_record_requires_resume_and_plan_hash_match(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    plan = prepare_launch_plan(paths)
    calls: list[list[str]] = []
    submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=lambda command: _completed(
            1,
            stderr="AssocGrpSubmitJobsLimit",
        ),
    )
    with pytest.raises(FileExistsError, match="resume"):
        submit_plan(
            plan,
            record_path=paths.record_path,
            run_command=lambda command: calls.append(command),
        )
    assert calls == []


def test_timeout_continues_only_from_a_checkpoint(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    plan = prepare_launch_plan(paths)
    submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=lambda command: _completed(0, "9301\n"),
    )
    record = json.loads(paths.record_path.read_text())
    for row in record["jobs"][1:]:
        row["attempts"] = []
        row["status"] = "planned"
    paths.record_path.write_text(json.dumps(record))
    checkpoint = Path(plan["jobs"][0]["output"] + ".checkpoint.h5")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_bytes(b"checkpoint")
    calls: list[list[str]] = []
    refreshed = refresh_submitted_jobs(
        plan,
        record_path=paths.record_path,
        query_state=lambda job_id: "TIMEOUT",
        run_command=lambda command: (
            calls.append(command) or _completed(0, "9302\n")
        ),
    )
    attempts = refreshed["jobs"][0]["attempts"]
    assert [item["slurm_job_id"] for item in attempts] == [
        "9301",
        "9302",
    ]
    assert attempts[-1]["previous_terminal_state"] == "TIMEOUT"
    assert attempts[-1]["resumed_from_checkpoint"] == str(checkpoint)
    assert len(calls) == 1


def test_manual_cancel_is_never_automatically_resubmitted(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    plan = prepare_launch_plan(paths)
    submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=lambda command: _completed(0, "9401\n"),
    )
    record = json.loads(paths.record_path.read_text())
    for row in record["jobs"][1:]:
        row["attempts"] = []
        row["status"] = "planned"
    paths.record_path.write_text(json.dumps(record))
    calls: list[list[str]] = []
    refreshed = refresh_submitted_jobs(
        plan,
        record_path=paths.record_path,
        query_state=lambda job_id: "CANCELLED",
        run_command=lambda command: calls.append(command),
    )
    assert refreshed["status"] == "needs_attention"
    assert refreshed["jobs"][0]["status"] == "needs_attention"
    assert calls == []

    changed = dict(plan)
    changed["plan_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="plan hash"):
        submit_plan(
            changed,
            record_path=paths.record_path,
            run_command=lambda command: calls.append(command),
            resume=True,
        )
    assert calls == []


def test_completed_job_requires_full_dataset_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    plan = prepare_launch_plan(paths)
    submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=lambda command: _completed(0, "9501\n"),
    )
    record = json.loads(paths.record_path.read_text())
    for row in record["jobs"][1:]:
        row["attempts"] = []
        row["status"] = "planned"
    paths.record_path.write_text(json.dumps(record))
    monkeypatch.setattr(
        launcher,
        "validate_production_output",
        lambda job, output: {
            "status": "invalid",
            "errors": ["fcs_conjugacy_failed"],
        },
    )
    calls: list[list[str]] = []
    refreshed = refresh_submitted_jobs(
        plan,
        record_path=paths.record_path,
        query_state=lambda job_id: "COMPLETED",
        run_command=lambda command: calls.append(command),
    )
    row = refreshed["jobs"][0]
    assert refreshed["status"] == "needs_attention"
    assert row["status"] == "needs_attention"
    assert row["validation"]["errors"] == ["fcs_conjugacy_failed"]
    assert "completed output validation failed" in row[
        "last_submission_error"
    ]
    assert calls == []
