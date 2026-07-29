from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


SOLUTION = Path(__file__).resolve().parents[1]
WRAPPER = SOLUTION / "scripts" / "pilot_array_slurm.sh"


def _run(tmp_path: Path, task_id: str, *, cpus: str = "1") -> subprocess.CompletedProcess[str]:
    repo = tmp_path / "repo"
    script = repo / "tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "import os,sys\n"
        "print(sys.executable)\n"
        "print(os.environ['NUMBA_CACHE_DIR'])\n"
        "print('ARGS=' + ' '.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text("{}\n", encoding="utf-8")
    local_tmp = tmp_path / "node"
    local_tmp.mkdir()
    env = {
        **os.environ,
        "CHALLENGE_194_REPO_ROOT": str(repo),
        "CHALLENGE_194_PYTHON": os.path.realpath(os.sys.executable),
        "HARNESS_RUN_SPEC": str(run_spec),
        "SLURM_ARRAY_TASK_ID": task_id,
        "SLURM_ARRAY_JOB_ID": "991",
        "SLURM_CPUS_PER_TASK": cpus,
        "SLURM_TMPDIR": str(local_tmp),
        "PYTHONPATH": "/hostile/path",
    }
    return subprocess.run(
        ["bash", str(WRAPPER)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(("task_id", "index"), (("1", "0"), ("96", "95")))
def test_array_boundaries_map_one_based_to_zero_based(
    tmp_path: Path, task_id: str, index: str
):
    result = _run(tmp_path, task_id)
    assert result.returncode == 0, result.stderr
    assert f"--cell-index {index}" in result.stdout
    assert os.path.realpath(os.sys.executable) in result.stdout
    assert f"challenge-194-pilot-991-{task_id}" in result.stdout


@pytest.mark.parametrize("task_id", ("0", "97", "-1", "x"))
def test_array_rejects_out_of_range_ids(tmp_path: Path, task_id: str):
    result = _run(tmp_path, task_id)
    assert result.returncode == 64


def test_array_requires_exactly_one_cpu(tmp_path: Path):
    assert _run(tmp_path, "1", cpus="2").returncode == 64


def test_wrapper_preserves_venv_launcher_and_cleans_pythonpath(tmp_path: Path):
    result = _run(tmp_path, "1")
    assert result.returncode == 0
    assert "/hostile/path" not in result.stdout
    assert "PYTHONPATH" not in result.stderr
