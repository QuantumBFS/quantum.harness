from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


TRACK = Path(__file__).resolve().parents[1]
REPO = TRACK.parents[2]
RUNNER = TRACK / "scripts" / "issue28_cluster_cell.py"
GUARDRAIL = REPO / "scripts" / "cluster_guardrail.py"
CLUSTER_REQUIREMENTS = TRACK / "config" / "issue28_cluster_requirements_v1.txt"
CLUSTER_WHEEL_HASHES = TRACK / "config" / "issue28_cluster_wheels_v1.sha256"
JOBS = (
    TRACK / "jobs" / "issue28_smoke.slurm",
    TRACK / "jobs" / "issue28_n3.slurm",
    TRACK / "jobs" / "issue28_n4.slurm",
)
N5_JOB = TRACK / "jobs" / "issue28_n5.slurm"


def test_python38_cluster_contract_includes_numba_backport_dependencies() -> None:
    requirements = {
        line.split("==", 1)[0].lower(): line.split("==", 1)[1]
        for line in CLUSTER_REQUIREMENTS.read_text(encoding="ascii").splitlines()
        if line.strip()
    }
    assert requirements["importlib-metadata"] == "6.8.0"
    assert requirements["zipp"] == "3.17.0"
    hashed_wheels = {
        line.split(maxsplit=1)[1]
        for line in CLUSTER_WHEEL_HASHES.read_text(encoding="ascii").splitlines()
        if line.strip()
    }
    assert "importlib_metadata-6.8.0-py3-none-any.whl" in hashed_wheels
    assert "zipp-3.17.0-py3-none-any.whl" in hashed_wheels


def test_cluster_package_avoids_python39_runtime_builtin_generic_aliases() -> None:
    forbidden = {"dict", "frozenset", "list", "set", "tuple"}
    violations = []
    for path in sorted((TRACK / "src" / "vmcrg_ref").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if (
                isinstance(node, (ast.Assign, ast.AnnAssign))
                and isinstance(node.value, ast.Subscript)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id in forbidden
            ):
                violations.append(f"{path.name}:{node.lineno}")
    assert violations == []


def _run_runner(
    spec: Path,
    stage: str,
    *,
    selector: str = "1",
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(RUNNER),
        "--stage",
        stage,
        "--run-spec",
        str(spec),
        "--selector",
        selector,
    ]
    if dry_run:
        command.append("--dry-run")
    return subprocess.run(
        command,
        cwd=TRACK,
        capture_output=True,
        text=True,
        env={**os.environ, "HARNESS_REPO_ROOT": str(REPO)},
    )


def test_cluster_cell_isolates_numba_cache_by_job_task_and_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.issue28_cluster_cell import _isolate_numba_cache

    base = tmp_path / "numba"
    monkeypatch.setenv("NUMBA_CACHE_DIR", str(base))
    monkeypatch.setenv("SLURM_JOB_ID", "5315107")
    monkeypatch.setenv("SLURM_ARRAY_TASK_ID", "4")
    isolated = _isolate_numba_cache()
    assert isolated.parent == base
    assert isolated.name.startswith("job-5315107-task-4-pid-")
    assert os.environ["NUMBA_CACHE_DIR"] == str(isolated)


@pytest.mark.parametrize("field", ("partition", "gres"))
def test_n5_job_leaves_resources_to_cluster_profile(field: str) -> None:
    assert N5_JOB.is_file()
    result = subprocess.run(
        [
            sys.executable,
            str(GUARDRAIL),
            "directive",
            str(N5_JOB),
            "--field",
            field,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stdout == ""


def test_n5_job_fails_closed_without_complete_n4_root(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(N5_JOB)],
        cwd=REPO,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "SLURM_SUBMIT_DIR": str(REPO),
            "HARNESS_SKIP_MODULES": "1",
            "HARNESS_PYTHON": sys.executable,
            "HARNESS_REPO_ROOT": str(tmp_path),
        },
    )
    assert result.returncode != 0
    assert "N4 cells directory is missing" in result.stderr


@pytest.mark.parametrize("job", JOBS)
@pytest.mark.parametrize("field", ("partition", "gres"))
def test_issue28_jobs_leave_resources_to_cluster_profile(
    job: Path,
    field: str,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(GUARDRAIL),
            "directive",
            str(job),
            "--field",
            field,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stdout == ""


@pytest.mark.parametrize("job", JOBS)
def test_issue28_jobs_fail_closed_without_run_spec(job: Path) -> None:
    result = subprocess.run(
        ["bash", str(job)],
        cwd=REPO,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "SLURM_SUBMIT_DIR": str(REPO),
            "HARNESS_SKIP_MODULES": "1",
            "HARNESS_PYTHON": sys.executable,
        },
    )
    assert result.returncode != 0
    assert "HARNESS_RUN_SPEC" in result.stderr


@pytest.mark.parametrize("job", JOBS)
def test_issue28_jobs_load_profile_with_unset_terminal_variable(
    job: Path, tmp_path: Path
) -> None:
    profile = tmp_path / "profile.sh"
    profile.write_text(
        ': "${COLORTERM}"\nmodule() { :; }\n',
        encoding="ascii",
    )
    fake_python = tmp_path / "python"
    fake_python.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    fake_python.chmod(0o755)
    environment = {
        **os.environ,
        "HARNESS_RUN_SPEC": "unused-run-spec.json",
        "HARNESS_SYSTEM_PROFILE": str(profile),
        "HARNESS_PYTHON": str(fake_python),
        "SLURM_ARRAY_TASK_ID": "1",
        "SLURM_SUBMIT_DIR": str(REPO),
    }
    environment.pop("COLORTERM", None)
    result = subprocess.run(
        ["bash", str(job)],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr


def test_smoke_cell_runs_real_import_and_compiled_identity(tmp_path: Path) -> None:
    output = tmp_path / "cells" / "smoke"
    spec = tmp_path / "run_spec.json"
    spec.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cells": [
                    {
                        "cell_id": "smoke",
                        "params": {
                            "stage": "SMOKE",
                            "output": str(output),
                        },
                    }
                ],
            }
        ),
        encoding="ascii",
    )
    result = _run_runner(spec, "SMOKE")
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text(encoding="ascii"))
    assert manifest["status"] == "ok"
    assert manifest["compiled_trajectory_identity"] is True
    assert set(manifest["versions"]) == {"python", "numpy", "scipy", "numba"}


def test_n4_dry_run_selects_opaque_formal_bundle(tmp_path: Path) -> None:
    spec = tmp_path / "run_spec.json"
    cells = [
        {
            "cell_id": f"formal-{index}",
            "params": {
                "stage": "N4",
                "bundle_id": f"formal-{index}",
                "protocol": "tracks/mps/DMRG/config/issue28_formal_v1.json",
                "output": f"results/issue28-n4/cells/formal-{index}",
            },
        }
        for index in range(1, 6)
    ]
    spec.write_text(
        json.dumps({"schema_version": 1, "cells": cells}), encoding="ascii"
    )
    result = _run_runner(spec, "N4", selector="2", dry_run=True)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["cell_id"] == "formal-2"
    assert plan["bundle_id"] == "formal-2"
    assert plan["stage"] == "N4"
    assert not (REPO / "results" / "issue28-n4").exists()


def test_cluster_runner_rejects_stage_mismatch(tmp_path: Path) -> None:
    spec = tmp_path / "run_spec.json"
    spec.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cells": [
                    {
                        "cell_id": "pilot",
                        "params": {
                            "stage": "N3",
                            "protocol": "tracks/mps/DMRG/config/issue28_easy_v1.json",
                            "output": "results/issue28-n3/cells/pilot",
                        },
                    }
                ],
            }
        ),
        encoding="ascii",
    )
    result = _run_runner(spec, "N4", dry_run=True)
    assert result.returncode != 0
    assert "stage mismatch" in result.stderr
