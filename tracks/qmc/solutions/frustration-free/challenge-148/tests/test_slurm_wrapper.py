from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "slurm_array.sh"
SUBMITTER = ROOT / "scripts" / "submit_plan.py"
EXTENSION_WRAPPER = ROOT / "scripts" / "slurm_extension.sh"
EXTENSION_SUBMITTER = ROOT / "scripts" / "submit_extension.py"


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _submission_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "solution root"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "run_cell.py").write_text("# runner\n", encoding="utf-8")
    wrapper = scripts / "slurm_array.sh"
    wrapper.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    wrapper.chmod(0o755)
    binary = tmp_path / "binary dir" / "qmc sse"
    _write_executable(binary, "#!/bin/sh\nexit 0\n")
    plan = {
        "schema_version": "challenge148-production-plan-v1",
        "allocation": {
            "cores_per_cell": 2,
            "memory_mb_per_cell": 6000,
            "max_concurrency": 16,
        },
        "cells": [{"cell_id": f"cell-{index:02d}"} for index in range(72)],
    }
    plan["plan_sha256"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    plan_path = tmp_path / "plan dir" / "plan.json"
    plan_path.parent.mkdir()
    plan_path.write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    metadata = tmp_path / "job metadata"
    return root, plan_path, binary, metadata


def _extension_submission_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root, plan_path, binary, _ = _submission_fixture(tmp_path)
    scripts = root / "scripts"
    wrapper = scripts / "slurm_extension.sh"
    wrapper.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    wrapper.chmod(0o755)
    plan = json.loads(plan_path.read_text())
    plan["schema_version"] = "challenge148-directed-extension-plan-v1"
    plan["allocation"]["adapter_timeout_seconds"] = 1800
    plan["cells"] = [{"cell_id": f"directed-{index:02d}"} for index in range(24)]
    plan.pop("plan_sha256")
    plan["plan_sha256"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    plan_path.write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return root, plan_path, binary, tmp_path / "extension job metadata"


def _submit_extension(
    root: Path,
    plan: Path,
    binary: Path,
    metadata: Path,
    *mode: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(EXTENSION_SUBMITTER),
            "--plan",
            str(plan),
            "--solution-root",
            str(root),
            "--qmc-sse",
            str(binary),
            "--metadata-dir",
            str(metadata),
            *mode,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _submit(
    root: Path,
    plan: Path,
    binary: Path,
    metadata: Path,
    *mode: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SUBMITTER),
            "--plan",
            str(plan),
            "--solution-root",
            str(root),
            "--qmc-sse",
            str(binary),
            "--metadata-dir",
            str(metadata),
            *mode,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _canonical_payload(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    value = json.loads(payload)
    assert payload == (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    return value


def test_wrapper_is_checkout_neutral_strict_and_requires_environment():
    text = WRAPPER.read_text(encoding="utf-8")

    assert "/home/" not in text
    assert "quantum.harness-challenge-148" not in text
    assert "set -euo pipefail" in text
    assert "umask 077" in text
    for variable in (
        "CH148_PLAN",
        "CH148_SOLUTION_DIR",
        "CH148_QMC_SSE",
        "SLURM_ARRAY_TASK_ID",
    ):
        assert variable in text

    result = subprocess.run(
        ["bash", str(WRAPPER)], check=False, capture_output=True, text=True, env={}
    )
    assert result.returncode != 0
    assert "CH148_PLAN" in result.stderr


def test_spooled_wrapper_preserves_quoted_paths_and_array_index(tmp_path: Path):
    spool = tmp_path / "slurm spool"
    spool.mkdir()
    copied = spool / "job script"
    copied.write_bytes(WRAPPER.read_bytes())
    copied.chmod(0o755)
    solution = tmp_path / "checkout with spaces"
    (solution / "scripts").mkdir(parents=True)
    (solution / "scripts" / "run_cell.py").write_text("# runner\n")
    plan = tmp_path / "plan with spaces.json"
    plan.write_text("{}\n")
    binary = tmp_path / "qmc binary"
    _write_executable(binary, "#!/bin/sh\nexit 0\n")
    capture = tmp_path / "captured args"
    fake_bin = tmp_path / "fake bin"
    fake_python = fake_bin / "python3"
    _write_executable(
        fake_python,
        f"""#!/bin/sh
printf '%s\\n' "$@" > {str(capture)!r}
""",
    )
    environment = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "CH148_PLAN": str(plan),
        "CH148_SOLUTION_DIR": str(solution),
        "CH148_QMC_SSE": str(binary),
        "SLURM_ARRAY_TASK_ID": "17",
    }

    result = subprocess.run(
        ["bash", str(copied)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert capture.read_text().splitlines() == [
        str(solution / "scripts" / "run_cell.py"),
        "--plan",
        str(plan),
        "--cell-index",
        "17",
        "--qmc-sse",
        str(binary),
    ]


@pytest.mark.parametrize("task_id", ["", "-1", "72", "1x"])
def test_wrapper_rejects_invalid_array_task_id(tmp_path: Path, task_id: str):
    solution, plan, binary, _ = _submission_fixture(tmp_path)
    environment = os.environ.copy()
    environment.update(
        {
            "CH148_PLAN": str(plan),
            "CH148_SOLUTION_DIR": str(solution),
            "CH148_QMC_SSE": str(binary),
            "SLURM_ARRAY_TASK_ID": task_id,
        }
    )

    result = subprocess.run(
        ["bash", str(WRAPPER)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode != 0
    assert "SLURM_ARRAY_TASK_ID" in result.stderr


def test_dry_run_quotes_paths_and_emits_exact_lasg02_resources(tmp_path: Path):
    solution, plan, binary, metadata = _submission_fixture(tmp_path)

    result = _submit(solution, plan, binary, metadata, "--dry-run")

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 2
    calibration, production = lines
    for command in lines:
        words = shlex.split(command)
        assert "--partition=ihicnormal" in command
        assert "--account=chenkun2025" in command
        assert "--qos=user_student090" in command
        assert "--cpus-per-task=2" in command
        assert "--mem=6000M" in command
        assert f"CH148_SOLUTION_DIR={solution}" in words
        assert f"CH148_PLAN={plan}" in words
        assert f"CH148_QMC_SSE={binary}" in words
    assert "--array=0" in calibration
    assert "--array=0-71%16" in production
    assert "--dependency=afterok:<calibration-job-id>" in production
    assert not metadata.exists()


def test_test_only_validates_both_job_shapes_without_false_dependency(tmp_path: Path):
    solution, plan, binary, metadata = _submission_fixture(tmp_path)
    fake_bin = tmp_path / "fake-bin"
    log = tmp_path / "sbatch.log"
    _write_executable(
        fake_bin / "sbatch",
        f"""#!/bin/sh
printf '%s\\n' "$*" >> {str(log)!r}
echo 'sbatch: Job 321 to start at 2030-01-01T00:00:00'
""",
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

    result = _submit(
        solution, plan, binary, metadata, "--test-only", env=environment
    )

    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    assert len(calls) == 2
    assert all("--test-only" in call for call in calls)
    assert "--array=0 " in calls[0]
    assert "--array=0-71%16" in calls[1]
    assert "--dependency" not in calls[1]
    assert not list(metadata.glob("*.json"))


def test_real_submission_publishes_durable_metadata_and_restarts_cleanly(
    tmp_path: Path,
):
    solution, plan, binary, metadata = _submission_fixture(tmp_path)
    fake_bin = tmp_path / "fake-bin"
    log = tmp_path / "sbatch.log"
    counter = tmp_path / "counter"
    _write_executable(
        fake_bin / "sbatch",
        f"""#!/bin/sh
printf '%s\\n' "$*" >> {str(log)!r}
count=$(cat {str(counter)!r} 2>/dev/null || echo 500)
count=$((count + 1))
printf '%s' "$count" > {str(counter)!r}
printf '%s;cluster\\n' "$count"
""",
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

    first = _submit(solution, plan, binary, metadata, env=environment)
    second = _submit(solution, plan, binary, metadata, env=environment)

    assert first.returncode == second.returncode == 0
    assert len(log.read_text().splitlines()) == 2
    calibration = _canonical_payload(metadata / "calibration-job.json")
    production = _canonical_payload(metadata / "array-job.json")
    assert calibration["job_id"] == "501"
    assert calibration["array"] == "0"
    assert production["job_id"] == "502"
    assert production["array"] == "0-71%16"
    assert production["dependency"] == "afterok:501"
    expected_plan_sha256 = json.loads(plan.read_text())["plan_sha256"]
    assert (
        calibration["plan_sha256"]
        == production["plan_sha256"]
        == expected_plan_sha256
    )
    assert "501" in second.stdout and "502" in second.stdout


def test_failed_array_submission_retains_calibration_for_restart(tmp_path: Path):
    solution, plan, binary, metadata = _submission_fixture(tmp_path)
    fake_bin = tmp_path / "fake-bin"
    attempts = tmp_path / "attempts"
    _write_executable(
        fake_bin / "sbatch",
        f"""#!/bin/sh
count=$(cat {str(attempts)!r} 2>/dev/null || echo 0)
count=$((count + 1))
printf '%s' "$count" > {str(attempts)!r}
if [ "$count" -eq 1 ]; then echo '701;cluster'; exit 0; fi
if [ "$count" -eq 2 ]; then echo 'array rejected' >&2; exit 9; fi
echo '702;cluster'
""",
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

    failed = _submit(solution, plan, binary, metadata, env=environment)
    restarted = _submit(solution, plan, binary, metadata, env=environment)

    assert failed.returncode != 0
    assert "array rejected" in failed.stderr
    assert _canonical_payload(metadata / "calibration-job.json")["job_id"] == "701"
    assert restarted.returncode == 0, restarted.stderr
    assert attempts.read_text() == "3"
    assert _canonical_payload(metadata / "array-job.json")["job_id"] == "702"


def test_existing_metadata_must_match_current_submission(tmp_path: Path):
    solution, plan, binary, metadata = _submission_fixture(tmp_path)
    metadata.mkdir()
    value = {
        "array": "0",
        "job_id": "91",
        "kind": "calibration",
        "plan_sha256": "b" * 64,
        "schema_version": "challenge148-slurm-job-v1",
    }
    (metadata / "calibration-job.json").write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    )

    result = _submit(solution, plan, binary, metadata)

    assert result.returncode != 0
    assert "metadata" in result.stderr.lower()


def test_extension_wrapper_requires_environment_and_preserves_quoted_paths(
    tmp_path: Path,
):
    text = EXTENSION_WRAPPER.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "/home/" not in text
    missing = subprocess.run(
        ["bash", str(EXTENSION_WRAPPER)],
        check=False,
        capture_output=True,
        text=True,
        env={},
    )
    assert missing.returncode != 0
    assert "CH148_PLAN" in missing.stderr

    spool = tmp_path / "slurm spool"
    spool.mkdir()
    copied = spool / "extension script"
    copied.write_bytes(EXTENSION_WRAPPER.read_bytes())
    solution, plan, binary, _ = _extension_submission_fixture(tmp_path)
    capture = tmp_path / "captured args"
    fake_bin = tmp_path / "fake bin"
    _write_executable(
        fake_bin / "python",
        f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {str(capture)!r}\n",
    )
    environment = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "CH148_PLAN": str(plan),
        "CH148_SOLUTION_DIR": str(solution),
        "CH148_QMC_SSE": str(binary),
        "SLURM_ARRAY_TASK_ID": "23",
    }
    result = subprocess.run(
        ["bash", str(copied)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    assert capture.read_text().splitlines() == [
        str(solution / "scripts" / "run_cell.py"),
        "--plan",
        str(plan),
        "--cell-index",
        "23",
        "--qmc-sse",
        str(binary),
        "--timeout-seconds",
        "1800",
    ]


@pytest.mark.parametrize("task_id", ["", "-1", "24", "1x"])
def test_extension_wrapper_rejects_invalid_array_task_id(
    tmp_path: Path, task_id: str
):
    solution, plan, binary, _ = _extension_submission_fixture(tmp_path)
    environment = os.environ.copy()
    environment.update(
        {
            "CH148_PLAN": str(plan),
            "CH148_SOLUTION_DIR": str(solution),
            "CH148_QMC_SSE": str(binary),
            "SLURM_ARRAY_TASK_ID": task_id,
        }
    )
    result = subprocess.run(
        ["bash", str(EXTENSION_WRAPPER)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode != 0
    assert "SLURM_ARRAY_TASK_ID" in result.stderr


def test_extension_dry_run_emits_exact_resources_dependency_and_array(
    tmp_path: Path,
):
    solution, plan, binary, metadata = _extension_submission_fixture(tmp_path)
    result = _submit_extension(solution, plan, binary, metadata, "--dry-run")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 2
    calibration, production = lines
    for command in lines:
        words = shlex.split(command)
        assert "--partition=ihicnormal" in words
        assert "--account=chenkun2025" in words
        assert "--qos=user_student090" in words
        assert "--ntasks=1" in words
        assert "--cpus-per-task=2" in words
        assert "--mem=6000M" in words
        assert f"CH148_PLAN={plan}" in words
        assert f"CH148_QMC_SSE={binary}" in words
    assert "--array=0" in calibration
    assert "--array=0-23%16" in production
    assert "--dependency=afterok:<calibration-job-id>" in production
    assert "--kill-on-invalid-dep=yes" in production
    assert not metadata.exists()


def test_extension_test_only_and_real_submission_publish_immutable_metadata(
    tmp_path: Path,
):
    solution, plan, binary, metadata = _extension_submission_fixture(tmp_path)
    fake_bin = tmp_path / "fake-bin"
    log = tmp_path / "sbatch.log"
    counter = tmp_path / "counter"
    _write_executable(
        fake_bin / "sbatch",
        f"""#!/bin/sh
printf '%s\n' "$*" >> {str(log)!r}
if [ "$1" = "--test-only" ]; then echo 'sbatch: Job 321 accepted'; exit 0; fi
count=$(cat {str(counter)!r} 2>/dev/null || echo 800)
count=$((count + 1))
printf '%s' "$count" > {str(counter)!r}
printf '%s;cluster\n' "$count"
""",
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

    tested = _submit_extension(
        solution, plan, binary, metadata, "--test-only", env=environment
    )
    assert tested.returncode == 0, tested.stderr
    test_calls = log.read_text().splitlines()
    assert len(test_calls) == 2
    assert all("--test-only" in call for call in test_calls)
    assert "--dependency" not in test_calls[1]
    assert not list(metadata.glob("*.json"))

    submitted = _submit_extension(solution, plan, binary, metadata, env=environment)
    restarted = _submit_extension(solution, plan, binary, metadata, env=environment)
    assert submitted.returncode == restarted.returncode == 0
    assert len(log.read_text().splitlines()) == 4
    calibration = _canonical_payload(metadata / "extension-calibration-job.json")
    production = _canonical_payload(metadata / "extension-array-job.json")
    assert calibration["array"] == "0"
    assert production["array"] == "0-23%16"
    assert production["dependency"] == "afterok:801"
    assert production["schema_version"] == "challenge148-extension-slurm-job-v1"
