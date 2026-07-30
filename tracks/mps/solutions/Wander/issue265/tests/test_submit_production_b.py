from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import hpc.scnet.submit_production_b as launcher
from hpc.scnet.submit_production_b import (
    ProductionBLaunchPaths,
    prepare_launch_plan,
    refresh_submitted_jobs,
    submit_plan,
)
from src.production_b_gate import ProductionBGatePaths

ROOT = Path(__file__).resolve().parents[1]


def _gate_paths(tmp_path: Path) -> ProductionBGatePaths:
    placeholder = tmp_path / "unused.json"
    placeholder.write_text('{"status":"opened"}\n')
    return ProductionBGatePaths(
        team_root=tmp_path / "team",
        source_root=ROOT,
        manifest=ROOT
        / "results_research_program"
        / "production_manifest_v2.json",
        rules=placeholder,
        convergence_audit=placeholder,
        source_preflight=placeholder,
        j2_validation=placeholder,
        production_a_record=placeholder,
        reuse_attestations=placeholder,
        analysis_record=placeholder,
        selection_record=placeholder,
        unblinding_record=placeholder,
    )


def _paths(tmp_path: Path) -> ProductionBLaunchPaths:
    return ProductionBLaunchPaths(
        gate=_gate_paths(tmp_path),
        bundle_root=tmp_path / "bundles",
        record_path=tmp_path / "jobs" / "production_b_submission.json",
        cluster_root=tmp_path / "team",
        python="/cluster/python",
        partition="xhacnormalb",
        account="giggleliu",
    )


def _eligible_unblinding() -> dict[str, object]:
    return {
        "schema_version": 2,
        "status": "opened",
        "protocol_version": "1.2",
        "validation_status": "scalar_surrogate_not_rejected",
        "selection_sha256": "a" * 64,
        "analysis_sha256": "b" * 64,
        "source_tree_sha256": "c" * 64,
        "evidence_sha256": {"selection": "d" * 64},
    }


@pytest.fixture(autouse=True)
def _valid_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        launcher,
        "validate_unblinding_record",
        lambda paths: _eligible_unblinding(),
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


def test_plan_is_exact_registered_production_b_set(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    plan = prepare_launch_plan(paths)
    assert plan["status"] == "ready"
    assert plan["execute_count"] == 34
    assert plan["fcs_count"] == 3
    assert plan["production_a_script_count"] == 0
    assert len(plan["jobs"]) == 34
    assert all(row["stage"] == "production_b" for row in plan["jobs"])
    assert all(
        "__production_a" not in Path(row["script"]).name
        for row in plan["jobs"]
    )
    assert all(
        row["job"]["job_id"] == row["job_id"] for row in plan["jobs"]
    )
    assert not paths.record_path.exists()


def test_bundle_is_atomically_reused_and_never_repaired_in_place(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    first = prepare_launch_plan(paths)
    bundle = Path(first["bundle_dir"])
    matrix = json.loads((bundle / "execution_matrix.json").read_text())
    assert all(
        str(record["script"]).startswith(str(bundle))
        for record in matrix["records"]
        if record["script"] is not None
    )
    second = prepare_launch_plan(paths)
    assert second["plan_sha256"] == first["plan_sha256"]
    assert not list(paths.bundle_root.glob(".*.staging-*"))

    Path(first["jobs"][0]["script"]).write_text("tampered\n")
    with pytest.raises(ValueError, match="immutable bundle"):
        prepare_launch_plan(paths)


def test_invalid_unblinding_never_materializes_or_submits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def reject(paths):
        raise ValueError("unblinding record evidence no longer matches")

    monkeypatch.setattr(launcher, "validate_unblinding_record", reject)
    paths = _paths(tmp_path)
    with pytest.raises(ValueError, match="unblinding"):
        plan = prepare_launch_plan(paths)
        submit_plan(
            plan,
            record_path=paths.record_path,
            run_command=lambda command: calls.append(command),
        )
    assert calls == []
    assert not paths.bundle_root.exists()
    assert not paths.record_path.exists()


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
            stderr="sbatch: error: AssocGrpSubmitJobsLimit",
        )

    partial = submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=first_wave,
    )
    assert partial["status"] == "policy_deferred"
    assert [row["attempts"][0]["slurm_job_id"] for row in partial["jobs"][:2]] == [
        "9101",
        "9102",
    ]

    resumed_calls: list[str] = []

    def resumed_wave(command: list[str]):
        resumed_calls.append(command[-1])
        return _completed(0, f"{9200 + len(resumed_calls)}\n")

    resumed = submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=resumed_wave,
        resume=True,
    )
    assert resumed["status"] == "submitted"
    assert resumed["submission_complete"] is True
    assert len(resumed_calls) == 32
    assert set(resumed_calls).isdisjoint(first_calls[:2])


def test_recoverable_timeout_resumes_only_with_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    plan = prepare_launch_plan(paths)
    counter = iter(range(10000, 10034))
    submitted = submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=lambda command: _completed(
            0,
            f"{next(counter)}\n",
        ),
    )
    first = submitted["jobs"][0]
    checkpoint = Path(first["output"] + ".checkpoint.h5")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text("checkpoint")
    monkeypatch.setattr(
        launcher,
        "validate_production_output",
        lambda job, path: {"status": "invalid", "errors": ["missing"]},
    )
    calls: list[list[str]] = []

    def resume(command: list[str]):
        calls.append(command)
        return _completed(0, "20000\n")

    refreshed = refresh_submitted_jobs(
        plan,
        record_path=paths.record_path,
        query_state=lambda job_id: (
            "TIMEOUT" if job_id == "10000" else "RUNNING"
        ),
        run_command=resume,
    )
    assert len(calls) == 1
    assert refreshed["jobs"][0]["attempts"][-1][
        "resumed_from_checkpoint"
    ] == str(checkpoint)
    assert all(
        len(row["attempts"]) == 1 for row in refreshed["jobs"][1:]
    )


def test_completed_invalid_output_requires_manual_intervention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    plan = prepare_launch_plan(paths)
    counter = iter(range(30000, 30034))
    submitted = submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=lambda command: _completed(0, f"{next(counter)}\n"),
    )
    monkeypatch.setattr(
        launcher,
        "validate_production_output",
        lambda job, path: {"status": "invalid", "errors": ["bad_hash"]},
    )
    refreshed = refresh_submitted_jobs(
        plan,
        record_path=paths.record_path,
        query_state=lambda job_id: (
            "COMPLETED"
            if job_id == submitted["jobs"][0]["attempts"][0]["slurm_job_id"]
            else "RUNNING"
        ),
        run_command=lambda command: pytest.fail("must not resubmit"),
    )
    assert refreshed["status"] == "needs_attention"
    assert refreshed["jobs"][0]["status"] == "needs_attention"
    assert "bad_hash" in refreshed["jobs"][0]["last_submission_error"]


def test_oom_resume_uses_registered_memory_adaptation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    plan = prepare_launch_plan(paths)
    counter = iter(range(40000, 40034))
    submitted = submit_plan(
        plan,
        record_path=paths.record_path,
        run_command=lambda command: _completed(0, f"{next(counter)}\n"),
    )
    first = submitted["jobs"][0]
    checkpoint = Path(first["output"] + ".checkpoint.h5")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text("checkpoint")
    monkeypatch.setattr(
        launcher,
        "validate_production_output",
        lambda job, path: {"status": "invalid", "errors": ["missing"]},
    )
    calls: list[list[str]] = []

    def resume(command: list[str]):
        calls.append(command)
        return _completed(0, "50000\n")

    refreshed = refresh_submitted_jobs(
        plan,
        record_path=paths.record_path,
        query_state=lambda job_id: (
            "OUT_OF_MEMORY" if job_id == "40000" else "RUNNING"
        ),
        run_command=resume,
    )
    assert len(calls) == 1
    attempt = refreshed["jobs"][0]["attempts"][-1]
    assert attempt["previous_terminal_state"] == "OUT_OF_MEMORY"
    assert attempt["resource"]["memory"] == "120G"
    assert attempt["resource"]["cpus"] == 32
