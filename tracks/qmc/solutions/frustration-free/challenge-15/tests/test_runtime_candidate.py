from __future__ import annotations

import hashlib
import importlib.util
import inspect
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "production" / "runtime"
PUBLISHER = RUNTIME / "publish_noreplace.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "challenge15_verify_wheelhouse", RUNTIME / "verify_wheelhouse.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_publisher():
    assert PUBLISHER.is_file(), "atomic no-replace publisher is missing"
    spec = importlib.util.spec_from_file_location(
        "challenge15_publish_noreplace", PUBLISHER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=("cpu", "cuda12"))
def candidate(request):
    return _load_verifier().load_candidate(request.param, RUNTIME)


@pytest.fixture
def cuda_lock():
    return _load_verifier().load_candidate("cuda12", RUNTIME)


def test_candidate_is_cp312_manylinux2014_and_binary_only(candidate):
    assert candidate.python_version == "3.12"
    assert candidate.abis == ("cp312", "abi3")
    assert candidate.platform == "manylinux2014_x86_64"
    assert candidate.only_binary
    assert candidate.packages["jax"] == "0.4.38"
    assert candidate.packages["jaxlib"] == "0.4.38"
    assert not candidate.sdists


def test_cuda_lock_contains_bundled_runtime(cuda_lock):
    assert cuda_lock.requested == {"jax-cuda12-plugin[with-cuda]": "0.4.38"}
    assert "jax-cuda12-plugin" in cuda_lock.projects
    assert "jax-cuda12-pjrt" in cuda_lock.projects
    assert cuda_lock.nvidia_projects
    assert all(cuda_lock.hashes[name] for name in cuda_lock.nvidia_projects)


def test_candidate_inputs_are_exact_and_cuda_adds_one_requirement():
    cpu = (RUNTIME / "cpu" / "requirements.in").read_text().splitlines()
    cuda = (RUNTIME / "cuda12" / "requirements.in").read_text().splitlines()
    assert cuda == [*cpu, "jax-cuda12-plugin[with-cuda]==0.4.38"]
    assert cpu == [
        "jax==0.4.38",
        "jaxlib==0.4.38",
        "flax==0.10.2",
        "optax==0.2.4",
        "numpy==1.26.4",
        "scipy==1.12.0",
        "sympy==1.13.3",
        "h5py==3.10.0",
        "pytest==8.3.4",
    ]


def test_builder_and_installer_are_constrained_and_offline():
    builder = (RUNTIME / "build_candidate_wheelhouses.sh").read_text()
    for option in (
        "--require-hashes",
        "--platform manylinux2014_x86_64",
        "--implementation cp",
        "--python-version 312",
        "--abi cp312",
        "--abi abi3",
        "--only-binary=:all:",
    ):
        assert builder.count(option) == 2

    installer = (RUNTIME / "install_candidate.sh").read_text()
    for option in ("--no-index", "--require-hashes", "--only-binary=:all:"):
        assert option in installer


def _fake_wheel(
    root: Path,
    filename: str,
    project: str,
    version: str,
    *,
    tags: tuple[str, ...] = ("py3-none-any",),
) -> Path:
    wheel = root / filename
    dist_info = f"{project.replace('-', '_')}-{version}.dist-info"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {project}\nVersion: {version}\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\n"
            + "".join(f"Tag: {tag}\n" for tag in tags),
        )
    return wheel


def _candidate_fixture(tmp_path: Path) -> tuple[Path, Path]:
    runtime = tmp_path / "runtime"
    profile_root = runtime / "cpu"
    wheelhouse = tmp_path / "wheelhouse"
    profile_root.mkdir(parents=True)
    wheelhouse.mkdir()
    shutil.copy(RUNTIME / "cpu" / "requirements.in", profile_root / "requirements.in")

    entries = []
    for line in (profile_root / "requirements.in").read_text().splitlines():
        project, version = line.split("==", 1)
        wheel = _fake_wheel(
            wheelhouse,
            f"{project.replace('-', '_')}-{version}-py3-none-any.whl",
            project,
            version,
        )
        with wheel.open("rb") as wheel_file:
            digest = hashlib.file_digest(wheel_file, "sha256").hexdigest()
        entries.append(
            f"{project}=={version} \\\n"
            f"    --hash=sha256:{digest}"
        )
    (profile_root / "requirements.txt").write_text(
        "--only-binary :all:\n\n" + "\n".join(entries) + "\n"
    )
    return runtime, wheelhouse


def test_verifier_rejects_unlisted_files_and_sdists(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "unlisted.txt").write_text("not a wheel")
    with pytest.raises(ValueError, match="unlisted|wheel"):
        verifier.verify_wheelhouse("cpu", tmp_path, runtime_root=RUNTIME)

    (tmp_path / "unlisted.txt").unlink()
    (tmp_path / "jax-0.4.38.tar.gz").write_bytes(b"sdist")
    with pytest.raises(ValueError, match="sdist"):
        verifier.verify_wheelhouse("cpu", tmp_path, runtime_root=RUNTIME)


@pytest.mark.parametrize(
    "replacement",
    [
        "--only-binary=:all:",
        "--only-binary :all:\n--require-hashes",
        "--only-binary :all:\n--index-url https://example.invalid/simple",
    ],
)
def test_requirements_parser_rejects_noncanonical_global_directives(
    tmp_path, replacement
):
    verifier = _load_verifier()
    runtime, _ = _candidate_fixture(tmp_path)
    lock = runtime / "cpu" / "requirements.txt"
    lock.write_text(
        lock.read_text().replace("--only-binary :all:", replacement, 1)
    )
    with pytest.raises(ValueError, match="directive|binary"):
        verifier.load_candidate("cpu", runtime)


@pytest.mark.parametrize(
    "suffix",
    [
        " --trusted-host example.invalid",
        " garbage",
        " --hash=md5:" + "0" * 32,
    ],
)
def test_requirements_parser_rejects_unknown_trailing_tokens(tmp_path, suffix):
    verifier = _load_verifier()
    runtime, _ = _candidate_fixture(tmp_path)
    lock = runtime / "cpu" / "requirements.txt"
    lock.write_text(
        lock.read_text().replace("\njaxlib==0.4.38", suffix + "\njaxlib==0.4.38", 1)
    )
    with pytest.raises(ValueError, match="lock|requirement|token|directive"):
        verifier.load_candidate("cpu", runtime)


def test_requirements_parser_requires_hashes_and_approved_inputs(tmp_path):
    verifier = _load_verifier()
    runtime, _ = _candidate_fixture(tmp_path)
    lock = runtime / "cpu" / "requirements.txt"
    text = lock.read_text()
    start = text.index("jax==0.4.38")
    end = text.index("\njaxlib==0.4.38")
    lock.write_text(text[:start] + "jax==0.4.38" + text[end:])
    with pytest.raises(ValueError, match="hash|lock"):
        verifier.load_candidate("cpu", runtime)

    runtime, _ = _candidate_fixture(tmp_path / "inputs")
    input_path = runtime / "cpu" / "requirements.in"
    input_path.write_text(input_path.read_text().replace("pytest==8.3.4\n", ""))
    with pytest.raises(ValueError, match="approved|input"):
        verifier.load_candidate("cpu", runtime)


def test_requirements_parser_rejects_duplicates_and_has_no_lock_override(tmp_path):
    verifier = _load_verifier()
    runtime, _ = _candidate_fixture(tmp_path)
    lock = runtime / "cpu" / "requirements.txt"
    jax_entry = lock.read_text().split("\njaxlib==0.4.38", 1)[0].split("\n\n", 1)[1]
    lock.write_text(lock.read_text() + jax_entry + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        verifier.load_candidate("cpu", runtime)
    assert "requirements" not in inspect.signature(
        verifier.verify_wheelhouse
    ).parameters


def test_verifier_streams_hashes_without_path_read_bytes(tmp_path, monkeypatch):
    verifier = _load_verifier()
    runtime, wheelhouse = _candidate_fixture(tmp_path)

    def forbidden_read_bytes(self):
        raise AssertionError(f"whole-file read forbidden: {self}")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read_bytes)
    assert verifier.verify_wheelhouse(
        "cpu", wheelhouse, runtime_root=runtime
    ).wheel_count == 9


def test_verifier_rejects_symlinked_root_and_wheel(tmp_path):
    verifier = _load_verifier()
    runtime, wheelhouse = _candidate_fixture(tmp_path)
    linked_root = tmp_path / "linked-wheelhouse"
    linked_root.symlink_to(wheelhouse, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        verifier.verify_wheelhouse("cpu", linked_root, runtime_root=runtime)

    wheel = next(wheelhouse.glob("jax-*.whl"))
    target = tmp_path / wheel.name
    wheel.rename(target)
    wheel.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        verifier.verify_wheelhouse("cpu", wheelhouse, runtime_root=runtime)


def test_verifier_rejects_internal_wheel_tag_mismatch(tmp_path):
    verifier = _load_verifier()
    runtime, wheelhouse = _candidate_fixture(tmp_path)
    wheel = next(wheelhouse.glob("jax-*.whl"))
    wheel.unlink()
    _fake_wheel(
        wheelhouse,
        wheel.name,
        "jax",
        "0.4.38",
        tags=("cp312-cp312-manylinux_2_28_x86_64",),
    )
    with pytest.raises(ValueError, match="Tag|tag"):
        verifier.verify_wheelhouse("cpu", wheelhouse, runtime_root=runtime)


def _fake_python(bin_dir: Path) -> None:
    executable = bin_dir / "python3.12"
    executable.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == */publish_noreplace.py ]]; then
  if [[ -n ${FAKE_ADVERSARY_DEST:-} ]]; then
    mkdir -- "$FAKE_ADVERSARY_DEST"
    printf '%s' 'competing destination' > "$FAKE_ADVERSARY_DEST/owner"
  fi
  exec "$REAL_PYTHON" "$@"
fi
if [[ ${1:-} == -m && ${2:-} == venv ]]; then
  mkdir -p -- "$3/bin"
  cp -- "$0" "$3/bin/python"
  chmod +x -- "$3/bin/python"
  exit 0
fi
if [[ ${1:-} == -m && ${2:-} == pip ]]; then
  if [[ ${3:-} == install ]]; then
    if [[ -n ${FAKE_INSTALL_MARKER:-} ]]; then
      : > "$FAKE_INSTALL_MARKER"
    fi
    sleep "${FAKE_INSTALL_SLEEP:-0}"
  fi
  exit 0
fi
exit 0
"""
    )
    executable.chmod(0o755)


def _installer_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    wheelhouse = tmp_path / "wheelhouse"
    bin_dir.mkdir()
    wheelhouse.mkdir()
    _fake_python(bin_dir)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["REAL_PYTHON"] = sys.executable
    return env, wheelhouse


def test_installer_exclusive_lock_rejects_competing_publication(tmp_path):
    env, wheelhouse = _installer_env(tmp_path)
    destination = tmp_path / "candidate"
    marker = tmp_path / "install-started"
    env.update(FAKE_INSTALL_MARKER=str(marker), FAKE_INSTALL_SLEEP="1")
    command = [
        "bash",
        str(RUNTIME / "install_candidate.sh"),
        "cpu",
        str(wheelhouse),
        str(destination),
    ]
    first = subprocess.Popen(command, env=env, text=True, stderr=subprocess.PIPE)
    for _ in range(100):
        if marker.exists():
            break
        time.sleep(0.02)
    assert marker.exists()
    second = subprocess.run(command, env=env, text=True, capture_output=True)
    _, first_stderr = first.communicate(timeout=5)
    assert first.returncode == 0, first_stderr
    assert second.returncode != 0
    assert "lock" in second.stderr
    assert destination.is_dir()
    assert not Path(f"{destination}.lock").exists()


def test_installer_preserves_competing_destination_and_recoverable_partial(tmp_path):
    env, wheelhouse = _installer_env(tmp_path)
    destination = tmp_path / "candidate"
    lock = Path(f"{destination}.lock")
    lock.mkdir()
    command = [
        "bash",
        str(RUNTIME / "install_candidate.sh"),
        "cpu",
        str(wheelhouse),
        str(destination),
    ]
    blocked = subprocess.run(command, env=env, text=True, capture_output=True)
    assert blocked.returncode != 0
    assert lock.is_dir()

    lock.rmdir()
    env["FAKE_ADVERSARY_DEST"] = str(destination)
    adversarial = subprocess.run(command, env=env, text=True, capture_output=True)
    assert adversarial.returncode != 0
    assert destination.is_dir()
    owner = destination / "owner"
    assert owner.is_file(), adversarial.stderr
    assert owner.read_bytes() == b"competing destination"
    partials = list(tmp_path.glob("candidate.partial.*"))
    assert len(partials) == 1
    assert (partials[0] / "bin" / "python").is_file()
    assert not lock.exists()


def test_publisher_fails_closed_when_renameat2_is_unsupported(tmp_path, monkeypatch):
    publisher = _load_publisher()
    source = tmp_path / "partial"
    destination = tmp_path / "candidate"
    source.mkdir()
    (source / "payload").write_bytes(b"recoverable")
    monkeypatch.setattr(publisher.platform, "machine", lambda: "unsupported")

    with pytest.raises(OSError, match="unsupported"):
        publisher.rename_noreplace(source, destination)

    assert (source / "payload").read_bytes() == b"recoverable"
    assert not destination.exists()


def test_task_does_not_emit_final_allowed_attestation():
    for path in RUNTIME.rglob("*"):
        if path.is_file():
            assert "challenge15.allowed-runtime.v1" not in path.read_text(
                errors="ignore"
            )
