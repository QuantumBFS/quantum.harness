from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.convergence_source_gate import SourceGateError
from hpc.scnet.continue_convergence import (
    _adapt_oom_resource,
    _normalise_attempts,
    _output_is_complete,
    _submit_gated_slice,
)


def test_oom_resource_scaling_stays_below_partition_ratio() -> None:
    resource = {"cpus": 32, "memory": "120G", "time": "7-00:00:00"}
    scaled = _adapt_oom_resource(resource)
    assert scaled == {
        "cpus": 64,
        "memory": "240G",
        "time": "7-00:00:00",
    }
    assert _adapt_oom_resource(
        {"cpus": 128, "memory": "480G", "time": "7-00:00:00"}
    ) is None


def test_initial_attempt_is_materialised_once() -> None:
    job = {
        "slurm_job_id": "123",
        "resource": {"cpus": 4, "memory": "12G", "time": "01:00:00"},
    }
    first = _normalise_attempts(job, submitted_at="time-zero")
    second = _normalise_attempts(job, submitted_at="different")
    assert first is second
    assert first == [
        {
            "slice": 1,
            "slurm_job_id": "123",
            "submitted_at": "time-zero",
            "resource": {
                "cpus": 4,
                "memory": "12G",
                "time": "01:00:00",
            },
        }
    ]


def test_output_completion_requires_matching_summary(tmp_path: Path) -> None:
    output = tmp_path / "job.npz"
    output.write_bytes(b"npz")
    job = {"job_id": "registered-job", "output": str(output)}
    assert not _output_is_complete(job)

    output.with_suffix(".run.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "job_id": "registered-job",
                "output": str(output),
            }
        )
    )
    assert _output_is_complete(job)

    output.with_suffix(".run.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "job_id": "different-job",
                "output": str(output),
            }
        )
    )
    assert not _output_is_complete(job)


def test_source_gate_failure_prevents_sbatch(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[str] = []

    def fail_gate(job_id: str) -> dict[str, str]:
        raise SourceGateError("source_gate: test mismatch")

    def record_submit(*args: object, **kwargs: object) -> str:
        submitted.append("called")
        return "999"

    monkeypatch.setattr(
        "hpc.scnet.continue_convergence._source_attestation",
        fail_gate,
    )
    monkeypatch.setattr(
        "hpc.scnet.continue_convergence._submit_slice",
        record_submit,
    )
    with pytest.raises(SourceGateError, match="test mismatch"):
        _submit_gated_slice(
            {"job_id": "registered"},
            resource={
                "cpus": 4,
                "memory": "12G",
                "time": "7-00:00:00",
            },
            slice_index=2,
        )
    assert submitted == []


def test_successful_gated_submit_returns_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = {
        "status": "pass",
        "job_id": "registered",
        "source_pair_id": "validated",
    }
    monkeypatch.setattr(
        "hpc.scnet.continue_convergence._source_attestation",
        lambda job_id: attestation,
    )
    monkeypatch.setattr(
        "hpc.scnet.continue_convergence._submit_slice",
        lambda *args, **kwargs: "999",
    )
    slurm_id, observed = _submit_gated_slice(
        {"job_id": "registered"},
        resource={
            "cpus": 4,
            "memory": "12G",
            "time": "7-00:00:00",
        },
        slice_index=2,
    )
    assert slurm_id == "999"
    assert observed == attestation
