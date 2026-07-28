import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import pytest

from long_range_percolation import runtime
from long_range_percolation.runtime import runtime_capability, runtime_provenance


CAPABILITY_KEYS = {
    "schema_version",
    "python",
    "implementation",
    "platform",
    "machine",
    "numpy",
    "scipy",
    "h5py",
    "numba",
    "llvmlite",
    "cpu_name",
    "cpu_features",
    "threading_layer",
    "numba_disable_jit",
    "fastmath",
    "boundscheck",
}


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _commit(repository: Path, message: str) -> None:
    _git(repository, "add", "uv.lock")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Runtime Test",
            "-c",
            "user.email=runtime-test@local",
            "commit",
            "-m",
            message,
        ],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init")
    (repository / "uv.lock").write_bytes(b"version = 1\n")
    _commit(repository, "initial")
    return repository


def test_numba_is_exactly_pinned_and_imports_in_fresh_python():
    declared = open("pyproject.toml", encoding="utf-8").read()
    version = importlib.metadata.version("numba")
    assert f'"numba=={version}"' in declared
    smoke = """
import numba

@numba.njit
def add_one(value):
    return value + 1

assert add_one(41) == 42
assert add_one.nopython_signatures
print(numba.__version__)
"""
    completed = subprocess.run(
        [sys.executable, "-c", smoke],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == version


def test_runtime_capability_is_complete_and_json_stable():
    first = runtime_capability()
    second = runtime_capability()
    assert first == second
    assert set(first) == CAPABILITY_KEYS
    assert first["schema_version"] == "challenge-194-runtime-v1"
    assert first["fastmath"] is False
    assert first["boundscheck"] is True
    assert json.loads(json.dumps(first, sort_keys=True)) == first


def test_runtime_provenance_is_deterministic_and_tracks_each_input(
    tmp_path, monkeypatch
):
    repository = _repository(tmp_path)
    first = runtime_provenance(repository)
    assert first == runtime_provenance(repository)
    assert set(first) == {
        "schema_version",
        "source_revision",
        "uv_lock_sha256",
        "runtime_capability_sha256",
    }
    assert first["schema_version"] == "challenge-194-runtime-provenance-v1"
    assert first["source_revision"] == _git(repository, "rev-parse", "HEAD")
    assert len(first["source_revision"]) == 40
    int(first["source_revision"], 16)
    for key in ("uv_lock_sha256", "runtime_capability_sha256"):
        assert len(first[key]) == 64
        int(first[key], 16)
    assert first["uv_lock_sha256"] == hashlib.sha256(
        (repository / "uv.lock").read_bytes()
    ).hexdigest()
    capability_bytes = json.dumps(
        runtime_capability(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    assert first["runtime_capability_sha256"] == hashlib.sha256(
        capability_bytes
    ).hexdigest()

    (repository / "revision-input").write_text("changed\n", encoding="utf-8")
    _git(repository, "add", "revision-input")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Runtime Test",
            "-c",
            "user.email=runtime-test@local",
            "commit",
            "-m",
            "change revision",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    revision_changed = runtime_provenance(repository)
    assert revision_changed["source_revision"] != first["source_revision"]
    assert revision_changed["uv_lock_sha256"] == first["uv_lock_sha256"]
    assert (
        revision_changed["runtime_capability_sha256"]
        == first["runtime_capability_sha256"]
    )

    (repository / "uv.lock").write_bytes(b"version = 2\n")
    _commit(repository, "change lock")
    lock_changed = runtime_provenance(repository)
    assert lock_changed["uv_lock_sha256"] != revision_changed["uv_lock_sha256"]

    changed_capability = runtime_capability() | {"threading_layer": "workqueue"}
    monkeypatch.setattr(runtime, "runtime_capability", lambda: changed_capability)
    capability_changed = runtime_provenance(repository)
    assert (
        capability_changed["runtime_capability_sha256"]
        != lock_changed["runtime_capability_sha256"]
    )


def test_runtime_provenance_rejects_dirty_repository(tmp_path):
    repository = _repository(tmp_path)
    (repository / "untracked").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="repository is dirty"):
        runtime_provenance(repository)


@pytest.mark.parametrize("lock_kind", ["missing", "directory", "symlink"])
def test_runtime_provenance_rejects_invalid_lockfile(tmp_path, lock_kind):
    repository = _repository(tmp_path)
    lockfile = repository / "uv.lock"
    lockfile.unlink()
    if lock_kind == "directory":
        lockfile.mkdir()
    elif lock_kind == "symlink":
        target = repository / "target.lock"
        target.write_bytes(b"replacement\n")
        lockfile.symlink_to(target)
    with pytest.raises(RuntimeError, match="uv.lock must be a regular non-symlink"):
        runtime_provenance(repository)


def test_runtime_provenance_rejects_malformed_revision(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    real_run = runtime.subprocess.run

    def malformed_revision(command, **kwargs):
        if command == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, "not-a-revision\n", "")
        return real_run(command, **kwargs)

    monkeypatch.setattr(runtime.subprocess, "run", malformed_revision)
    with pytest.raises(RuntimeError, match="malformed Git revision"):
        runtime_provenance(repository)


def test_runtime_provenance_reports_git_failures(tmp_path):
    repository = tmp_path / "not-a-repository"
    repository.mkdir()
    (repository / "uv.lock").write_bytes(b"version = 1\n")
    with pytest.raises(RuntimeError, match="git status --porcelain failed"):
        runtime_provenance(repository)


def test_runtime_provenance_reports_git_execution_failures(tmp_path, monkeypatch):
    repository = _repository(tmp_path)

    def unavailable_git(*args, **kwargs):
        raise FileNotFoundError("git unavailable")

    monkeypatch.setattr(runtime.subprocess, "run", unavailable_git)
    with pytest.raises(
        RuntimeError, match="unable to execute git status --porcelain"
    ):
        runtime_provenance(repository)


@pytest.mark.parametrize(
    "invalid_value",
    [{1, 2}, ("not", "canonical")],
)
def test_runtime_provenance_rejects_noncanonical_capability(
    tmp_path, monkeypatch, invalid_value
):
    repository = _repository(tmp_path)
    capability = runtime_capability() | {"cpu_features": invalid_value}
    monkeypatch.setattr(runtime, "runtime_capability", lambda: capability)
    with pytest.raises(RuntimeError, match="canonical JSON"):
        runtime_provenance(repository)
