from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "slurm_paper.sh"
SUBMITTER = ROOT / "scripts" / "submit_paper.py"
RUNNER = ROOT / "scripts" / "run_cell.py"


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    solution = tmp_path / "solution root"
    scripts = solution / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "run_cell.py").write_text("# runner\n", encoding="utf-8")
    (scripts / "slurm_paper.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (scripts / "slurm_paper.sh").chmod(0o755)
    binary = tmp_path / "binary dir" / "qmc sse"
    _write_executable(binary, "#!/bin/sh\nexit 0\n")
    plan = {
        "schema_version": "challenge148-paper-scan-plan-v1",
        "allocation": {
            "adapter_timeout_seconds": 3600,
            "cores_per_cell": 2,
            "memory_mb_per_cell": 6000,
            "max_concurrency": 16,
        },
        "cells": [{"cell_id": f"paper-{index:03d}"} for index in range(140)],
    }
    plan["plan_sha256"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    plan_path = tmp_path / "plan dir" / "plan.json"
    plan_path.parent.mkdir()
    plan_path.write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return solution, plan_path, binary, tmp_path / "paper metadata"


def _submit(
    solution: Path,
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
            str(solution),
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


def test_runner_dispatches_only_exact_paper_schema(monkeypatch):
    specification = importlib.util.spec_from_file_location("paper_runner", RUNNER)
    assert specification is not None and specification.loader is not None
    runner = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(runner)
    seen = []
    monkeypatch.setattr(runner, "validate_paper_scan_plan", seen.append)
    plan = {"schema_version": "challenge148-paper-scan-plan-v1"}
    runner._validate_plan_schema(plan)
    assert seen == [plan]


def test_paper_wrapper_preserves_paths_index_and_timeout(tmp_path: Path):
    copied = tmp_path / "slurm spool" / "paper wrapper"
    copied.parent.mkdir()
    copied.write_bytes(WRAPPER.read_bytes())
    solution, plan, binary, _ = _fixture(tmp_path)
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
        "SLURM_ARRAY_TASK_ID": "139",
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
        "139",
        "--qmc-sse",
        str(binary),
        "--timeout-seconds",
        "3600",
    ]


@pytest.mark.parametrize("task_id", ["", "-1", "140", "1x"])
def test_paper_wrapper_rejects_invalid_index(tmp_path: Path, task_id: str):
    solution, plan, binary, _ = _fixture(tmp_path)
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


def test_paper_dry_run_has_exact_array_resources_and_dependency(tmp_path: Path):
    solution, plan, binary, metadata = _fixture(tmp_path)
    result = _submit(solution, plan, binary, metadata, "--dry-run")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 2
    calibration, production = lines
    for line in lines:
        words = shlex.split(line)
        assert "--partition=ihicnormal" in words
        assert "--account=chenkun2025" in words
        assert "--qos=user_student090" in words
        assert "--cpus-per-task=2" in words
        assert "--mem=6000M" in words
        assert f"CH148_PLAN={plan}" in words
    assert "--array=0" in calibration
    assert "--array=0-139%16" in production
    assert "--dependency=afterok:<calibration-job-id>" in production
    assert "--kill-on-invalid-dep=yes" in production
    assert not metadata.exists()


def test_paper_test_only_and_metadata_are_namespaced(tmp_path: Path):
    solution, plan, binary, metadata = _fixture(tmp_path)
    fake_bin = tmp_path / "fake-bin"
    log = tmp_path / "sbatch.log"
    _write_executable(
        fake_bin / "sbatch",
        f"""#!/bin/sh
printf '%s\n' "$*" >> {str(log)!r}
echo 'sbatch: Job 321 accepted'
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
    assert "--dependency" not in calls[1]
    assert not list(metadata.glob("*.json"))
