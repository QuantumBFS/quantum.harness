import hashlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

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
    declared = Path("pyproject.toml").read_text(encoding="utf-8")
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
    assert (
        first["uv_lock_sha256"]
        == hashlib.sha256((repository / "uv.lock").read_bytes()).hexdigest()
    )
    capability_bytes = json.dumps(
        runtime_capability(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    assert (
        first["runtime_capability_sha256"]
        == hashlib.sha256(capability_bytes).hexdigest()
    )

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
    with pytest.raises(RuntimeError, match="unable to execute git status --porcelain"):
        runtime_provenance(repository)


def test_readme_documents_exact_p0_p1_collaborator_boundary():
    readme = Path("README.md").read_text(encoding="utf-8")
    required = (
        "scripts/download_pilot.sh",
        "scripts/run_pilot.py verify --run-spec",
        "scripts/analyze_pilot.py analyze --run-spec",
        "--output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json",
        "scripts/analyze_pilot.py build-p1 --analysis",
        "--output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p1_protocol.json",
        "scripts/analyze_pilot.py verify --analysis",
        "--p1-protocol",
        "sha256sum",
        "e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8",
        "44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b",
        "P0 extension required before P1 publication: 0.9, 1.0",
        "scripts/analyze_pilot.py build-p0-extension",
        "scripts/run_pilot.py build-extension-spec",
        "scripts/pilot_extension_build_slurm.sh",
        "scripts/pilot_extension_array_slurm.sh",
        "No P0 extension data exist yet",
        "p1_protocol.json does not exist",
        "P1 has not been published or executed",
        "verified-existing",
    )
    for text in required:
        assert text in readme
    assert "P1 was executed" not in readme
    assert "P1 was published" not in readme


def test_pilot_plan_freezes_selector_and_exploratory_boundary():
    plan = Path("PILOT_PLAN.md").read_text(encoding="utf-8")
    required = (
        "Use the two largest P0 sizes",
        "sign change",
        "[0.25, 0.75]",
        "narrowest",
        "lower coupling",
        "maximum absolute",
        "sigma `1.1`",
        "P0 extension",
        "P0 and P1 remain exploratory",
        "confirmatory",
        "challenge-194-p0-extension-protocol-v1",
        "challenge-194-p0-extension-run-spec-v1",
        "challenge-194-p0-extension-progress-v1",
        "76dc7e07639ed085873a8f291cc2aaee0e8942ddac8efce3982743dd67491071",
        "d40b4a2afac533d74965513513fff1870918831000b2e040063ca2a0e29ad091",
        "40-minute",
        "canonical decimal IDs",
        "three submission batches",
        "six acceptance checks",
    )
    for text in required:
        assert text in plan


def test_extension_build_wrapper_freezes_resources_paths_and_environment():
    wrapper = Path("scripts/pilot_extension_build_slurm.sh").read_text(encoding="utf-8")
    required = (
        "#SBATCH --cpus-per-task=1",
        "#SBATCH --mem=1800M",
        "#SBATCH --time=00:10:00",
        'P0_ANALYSIS_PATH="${HARNESS_RUN_SPEC}"',
        'RESULTS_ROOT="$(dirname "${P0_ANALYSIS_PATH}")"',
        'EXTENSION_PROTOCOL_PATH="${RESULTS_ROOT}/p0_extension_v1_protocol.json"',
        'VALIDATION_REPORT_PATH="${RESULTS_ROOT}/validation-prod-877ab93/report/report.json"',
        'EXTENSION_ROOT="${RESULTS_ROOT}/pilot-p0-extension-v1"',
        "44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b",
        "unset PYTHONHOME PYTHONUSERBASE PYTHONPATH",
        "scripts/analyze_pilot.py build-p0-extension",
        "scripts/run_pilot.py build-extension-spec",
    )
    for text in required:
        assert text in wrapper


def test_extension_operational_contract_matches_approval_registry():
    approval = json.loads(
        Path("pilot_correctness_approval.json").read_text(encoding="utf-8")
    )
    package = f"validation-prod-{approval['approval_revision'][:7]}"
    validation_path = f"{package}/report/report.json"
    wrapper = Path("scripts/pilot_extension_build_slurm.sh").read_text(encoding="utf-8")
    pilot_plan = Path("PILOT_PLAN.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    implementation_plan = (
        Path(__file__).resolve().parents[6]
        / "docs/superpowers/plans/2026-07-30-challenge-194-p0-extension.md"
    ).read_text(encoding="utf-8")

    for document in (wrapper, pilot_plan, readme, implementation_plan):
        assert validation_path in document
        assert "validation-prod-fd0aa31-compute" not in document
    for field in (
        "approval_revision",
        "report_sha256",
        "run_spec_sha256",
        "protocol_sha256",
        "check_registry_sha256",
        "scientific_engine_sha256",
    ):
        assert approval[field] in pilot_plan
        assert approval[field] in readme

    remote_root_python = (
        "/work/share/giggleliu/jiangweiqi/"
        "quantum.harness-challenge-194/.venv/bin/python"
    )
    for document in (pilot_plan, readme, implementation_plan):
        assert remote_root_python in document
    assert approval["report_sha256"] in implementation_plan
    assert (
        "quantum.harness-challenge-194/tracks/qmc/solutions/"
        "frustration-free/challenge-194/.venv/bin/python" not in implementation_plan
    )
    assert "quantum.harness-p0-extension-v2" in implementation_plan
    assert "challenge-194-p0-extension-v2.bundle" in implementation_plan
    assert (
        'REMOTE_ROOT="${REMOTE_RESULTS}/pilot-p0-extension-v1"' in implementation_plan
    )
    assert (
        'REMOTE_PROTOCOL="${REMOTE_RESULTS}/p0_extension_v1_protocol.json"'
        in implementation_plan
    )


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
