from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from scripts.hard_goal import build_parser as build_hard_goal_parser
from scripts.hard_goal import main as hard_goal_main
from spinglass3d.production import build_production_run_spec, preview_slurm
from test_hg3d_production import _write_candidate, _write_run_spec
from vmcrg_ref.artifacts import sha256_file


TRACK = Path(__file__).resolve().parents[1]
JOB = TRACK / "jobs" / "hard_goal_array.slurm"


def test_stage7_wrapper_is_profile_neutral_and_requires_opaque_inputs() -> None:
    source = JOB.read_text(encoding="ascii")
    assert "HARNESS_RUN_SPEC" in source
    assert "HARNESS_APPROVED_RUN_SPEC_SHA256" in source
    assert "SLURM_ARRAY_TASK_ID" in source
    assert "HARNESS_PYTHON" in source
    assert "scripts/hard_goal.py" in source
    assert "\n  cell\n" in source
    assert "\n  -u\n" in source
    for forbidden in (
        "--partition",
        "--gres",
        "--mem",
        "--time",
        "A800",
        "/home/",
        "/scratch/",
    ):
        assert forbidden not in source


def test_stage7_wrapper_fails_closed_and_propagates_cell_exit(
    tmp_path: Path,
) -> None:
    missing = subprocess.run(
        ["bash", str(JOB)],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env={**os.environ, "HARNESS_PYTHON": "/bin/true"},
    )
    assert missing.returncode != 0
    assert "HARNESS_RUN_SPEC" in missing.stderr

    log = tmp_path / "arguments.json"
    fake_python = tmp_path / "python"
    fake_python.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ARGUMENT_LOG\"\nexit 7\n",
        encoding="ascii",
    )
    fake_python.chmod(0o755)
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text("{}\n", encoding="ascii")
    approved = sha256_file(run_spec)
    result = subprocess.run(
        ["bash", str(JOB)],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HARNESS_RUN_SPEC": str(run_spec),
            "HARNESS_APPROVED_RUN_SPEC_SHA256": approved,
            "SLURM_ARRAY_TASK_ID": "3",
            "HARNESS_PYTHON": str(fake_python),
            "ARGUMENT_LOG": str(log),
        },
    )
    assert result.returncode == 7
    arguments = log.read_text(encoding="ascii").splitlines()
    assert arguments == [
        "-u",
        "scripts/hard_goal.py",
        "cell",
        "--run-spec",
        str(run_spec),
        "--selector",
        "3",
        "--approved-run-spec-sha256",
        approved,
    ]


def test_slurm_preview_executes_only_precheck_probe_and_test_only(
    tmp_path: Path,
) -> None:
    candidate = _write_candidate(tmp_path)
    spec = build_production_run_spec(candidate, "preview-run")
    run_spec = tmp_path / "run-spec.json"
    _write_run_spec(run_spec, spec)
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_runner(args, **kwargs):
        command = [str(value) for value in args]
        calls.append((command, kwargs))
        action = command[1]
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=f"raw-{action}-stdout\n",
            stderr=f"raw-{action}-stderr\n",
        )

    preview = preview_slurm(
        candidate,
        run_spec,
        JOB,
        command_runner=fake_runner,
    )
    payload = preview.to_dict()
    assert payload["execution_performed"] is True
    assert payload["submission_authorized"] is False
    assert payload["array_count"] == len(spec["cells"])
    assert payload["resources"] == {
        "profile": "test-profile",
        "partition_candidates": ["profile-selected", "profile-fallback"],
        "cpus": 8,
        "accelerator": "profile-accelerator:1",
        "accelerator_count": 1,
        "memory_bytes": 16 * 1024**3,
        "wall_seconds": 24 * 3600,
    }
    assert payload["hashes"]["script_sha256"] == sha256_file(JOB)
    assert payload["hashes"]["candidate_sha256"] == sha256_file(candidate)
    assert payload["recovery"]["incomplete_cells"] == (
        "resume_latest_complete_checkpoint"
    )
    assert set(payload["temperature_counts_by_length"].values()) == {4}
    assert payload["j_counts_by_length"]["45"] == 128
    assert [call[0][1] for call in calls] == [
        "precheck",
        "probe-partitions",
        "submit",
    ]
    submit = calls[2][0]
    assert "--test-only" in submit
    assert submit[submit.index("--array") + 1] == str(len(spec["cells"]))
    assert submit[submit.index("--run-spec") + 1] == str(run_spec)
    assert submit[submit.index("--partition") + 1] == "profile-selected"
    assert submit[submit.index("--cpus") + 1] == "8"
    assert submit[submit.index("--time") + 1] == "24:00:00"
    assert all(
        call[1]["env"]["HARNESS_CLUSTER_PROFILE"] == "test-profile"
        for call in calls
    )
    assert payload["checks"]["precheck"]["stdout"] == "raw-precheck-stdout\n"
    assert payload["checks"]["probe_partitions"]["stderr"] == (
        "raw-probe-partitions-stderr\n"
    )
    assert payload["checks"]["test_only"]["returncode"] == 0


def test_slurm_preview_is_deeply_frozen_and_counts_accelerators(tmp_path: Path) -> None:
    candidate = _write_candidate(tmp_path, accelerator="A800:2")
    spec = build_production_run_spec(candidate, "preview-frozen")
    run_spec = tmp_path / "run-spec.json"
    _write_run_spec(run_spec, spec)

    def fake_runner(args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok\n", stderr="")

    preview = preview_slurm(candidate, run_spec, JOB, command_runner=fake_runner)
    with pytest.raises(AttributeError):
        preview.resources["partition_candidates"].append("mutated")
    detached = preview.to_dict()
    detached["resources"]["partition_candidates"].append("mutated")
    assert preview.to_dict()["resources"]["partition_candidates"] == [
        "profile-selected",
        "profile-fallback",
    ]
    assert preview.resources["accelerator_count"] == 2
    assert preview.estimated_accelerator_hours_upper_bound == pytest.approx(
        len(spec["cells"]) * 24.0 * 2.0
    )


def test_stage7_cli_exposes_preview_and_fails_closed_without_compute_backend(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate = _write_candidate(tmp_path / "candidate", j_counts={"45": 1})
    spec = build_production_run_spec(candidate, "cli-stage7")
    run_spec = tmp_path / "run-spec.json"
    approved = _write_run_spec(run_spec, spec)
    preview_args = [
        "preview-slurm",
        "--candidate",
        str(candidate),
        "--run-spec",
        str(run_spec),
        "--script",
        str(JOB),
        "--profile-from-candidate",
    ]
    assert build_hard_goal_parser().parse_args(preview_args).stage == "preview-slurm"

    def fake_runner(args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok\n", stderr="")

    assert hard_goal_main(preview_args, command_runner=fake_runner) == 0
    preview_payload = json.loads(capsys.readouterr().out)
    assert preview_payload["submission_authorized"] is False
    assert "--test-only" in preview_payload["checks"]["test_only"]["command"]

    cell_args = [
        "cell",
        "--run-spec",
        str(run_spec),
        "--selector",
        "1",
        "--approved-run-spec-sha256",
        approved,
    ]
    assert build_hard_goal_parser().parse_args(cell_args).stage == "cell"
    assert hard_goal_main(cell_args, command_runner=fake_runner) == 2
    assert "compute backend is not frozen" in capsys.readouterr().err


def test_stage7_wrapper_rejects_wrong_approved_run_spec_hash(tmp_path: Path) -> None:
    marker = tmp_path / "called"
    fake_python = tmp_path / "python"
    fake_python.write_text(
        "#!/bin/sh\ntouch \"$MARKER\"\n",
        encoding="ascii",
    )
    fake_python.chmod(0o755)
    run_spec = tmp_path / "run-spec.json"
    run_spec.write_text("{}\n", encoding="ascii")
    completed = subprocess.run(
        ["bash", str(JOB)],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HARNESS_RUN_SPEC": str(run_spec),
            "HARNESS_APPROVED_RUN_SPEC_SHA256": "0" * 64,
            "SLURM_ARRAY_TASK_ID": "1",
            "HARNESS_PYTHON": str(fake_python),
            "MARKER": str(marker),
        },
    )
    assert completed.returncode != 0
    assert "approved run-spec SHA-256" in completed.stderr
    assert not marker.exists()
