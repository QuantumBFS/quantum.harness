from __future__ import annotations

import os
import json
from pathlib import Path
import subprocess

import pytest


SOLUTION = Path(__file__).resolve().parents[1]
WRAPPER = SOLUTION / "scripts" / "pilot_array_slurm.sh"


def _run(
    tmp_path: Path,
    task_id: str,
    *,
    cpus: str = "1",
    extra_env: dict[str, str] | None = None,
    cache_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    repo = tmp_path / "repo"
    script = repo / "tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "import json,os,sys\n"
        "print(sys.executable)\n"
        "print(os.environ['NUMBA_CACHE_DIR'])\n"
        "print('ENV=' + json.dumps(dict(os.environ), sort_keys=True))\n"
        "print('ARGS=' + ' '.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text("{}\n", encoding="utf-8")
    local_tmp = tmp_path / "node" if cache_root is None else cache_root
    if cache_root is None:
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
        **(extra_env or {}),
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


def test_wrapper_preserves_venv_launcher_and_sanitizes_hostile_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hostile = {
        "NUMBA_DISABLE_JIT": "1",
        "NUMBA_CPU_NAME": "hostile",
        "NUMBA_CPU_FEATURES": "+hostile",
        "NUMBA_THREADING_LAYER": "hostile",
        "NUMBA_CACHE_DIR": "/hostile/cache",
        "PYTHONHOME": "/hostile/home",
        "PYTHONUSERBASE": "/hostile/user",
        "PYTHONPATH": "/hostile/path",
        "LD_PRELOAD": "/hostile/preload.so",
        "LD_LIBRARY_PATH": "/hostile/lib",
        "LIBRARY_PATH": "/hostile/compiler",
        "OMP_NUM_THREADS": "99",
        "OPENBLAS_NUM_THREADS": "99",
        "MKL_NUM_THREADS": "99",
        "NUMEXPR_NUM_THREADS": "99",
        "VECLIB_MAXIMUM_THREADS": "99",
        "PYTHONHASHSEED": "random",
    }
    for key, value in hostile.items():
        monkeypatch.setenv(key, value)
    result = _run(tmp_path, "1")
    assert result.returncode == 0
    line = next(item for item in result.stdout.splitlines() if item.startswith("ENV="))
    environment = json.loads(line.removeprefix("ENV="))
    assert environment["NUMBA_DISABLE_JIT"] == "0"
    assert environment["NUMBA_NUM_THREADS"] == "1"
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["PYTHONHASHSEED"] == "0"
    assert environment["PYTHONPATH"].endswith("/challenge-194/src")
    for key in (
        "NUMBA_CPU_NAME",
        "NUMBA_CPU_FEATURES",
        "NUMBA_THREADING_LAYER",
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "LIBRARY_PATH",
    ):
        assert key not in environment
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        assert environment[key] == "1"


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("SLURM_ARRAY_JOB_ID", "../bad"),
        ("SLURM_JOB_ID", "x"),
    ),
)
def test_wrapper_rejects_invalid_job_ids(
    tmp_path: Path, name: str, value: str
):
    result = _run(tmp_path, "1", extra_env={name: value})
    assert result.returncode == 64


def test_wrapper_rejects_symlink_cache_root(
    tmp_path: Path,
):
    target = tmp_path / "target"
    target.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(target, target_is_directory=True)
    result = _run(tmp_path, "1", cache_root=linked)
    assert result.returncode == 73


@pytest.mark.parametrize("kind", ("empty", "nonempty", "symlink"))
def test_wrapper_requires_uniquely_created_owned_cache_directory(
    tmp_path: Path, kind: str
):
    cache_root = tmp_path / "node"
    cache_root.mkdir()
    cache = cache_root / "challenge-194-pilot-991-1"
    if kind == "symlink":
        target = tmp_path / "hostile-cache"
        target.mkdir()
        cache.symlink_to(target, target_is_directory=True)
    else:
        cache.mkdir()
        if kind == "nonempty":
            (cache / "hostile").write_text("data", encoding="utf-8")
    result = _run(tmp_path, "1", cache_root=cache_root)
    assert result.returncode == 73
