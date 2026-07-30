import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
JULIA_PROJECT = PROJECT_ROOT / "julia" / "Project.toml"


def test_julia_project_declares_required_dependencies() -> None:
    project = tomllib.loads(JULIA_PROJECT.read_text(encoding="utf-8"))
    assert {"UniformTEMPO", "OrdinaryDiffEq", "JSON3", "KrylovKit"} <= project[
        "deps"
    ].keys()
    assert project["compat"]["julia"] == "1.12"


def test_julia_runner_rejects_missing_input(tmp_path: Path) -> None:
    julia = shutil.which("julia")
    if julia is None:
        pytest.skip("Julia is not installed")
    completed = subprocess.run(
        [
            julia,
            f"--project={PROJECT_ROOT / 'julia'}",
            str(PROJECT_ROOT / "julia" / "run_uniform_tempo.jl"),
            str(tmp_path / "missing.json"),
            str(tmp_path / "out.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "input" in completed.stderr.lower()
