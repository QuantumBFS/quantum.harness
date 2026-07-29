from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time

import pytest


SOLUTION = Path(__file__).resolve().parents[1]
SCRIPT = SOLUTION / "scripts" / "download_pilot.sh"
VERIFIED = '{"cells": 96, "status": "verified", "trajectories": 96}'


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _prepare(
    tmp_path: Path,
    *,
    remote_root: str = "/remote/pilot-p0",
    local_root: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[list[str], dict[str, str], Path, Path]:
    calls = tmp_path / "calls"
    calls.mkdir(exist_ok=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    _write_executable(
        fake_bin / "rsync",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"${CALLS}/rsync.$$\"\n"
        "if [[ -n \"${BLOCK_RSYNC:-}\" ]]; then\n"
        "  : > \"${CALLS}/ready\"\n"
        "  while [[ ! -e \"${CALLS}/release\" ]]; do sleep 0.01; done\n"
        "fi\n"
        "if [[ -n \"${MUTATE_FILE:-}\" ]]; then\n"
        "  printf 'rsync-ran\\n' >> \"${MUTATE_FILE}\"\n"
        "fi\n",
    )
    python = tmp_path / "python"
    _write_executable(
        python,
        "#!/bin/bash\n"
        "python3 - \"$@\" <<'PY'\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "calls = Path(os.environ['CALLS'])\n"
        "(calls / f'verify.{os.getpid()}').write_text(json.dumps({\n"
        "    'argv': sys.argv[1:],\n"
        "    'cwd': os.getcwd(),\n"
        "    'pythonpath': os.environ.get('PYTHONPATH'),\n"
        "}))\n"
        "print(os.environ.get('VERIFY_OUTPUT', "
        "'{\"cells\": 96, \"status\": \"verified\", \"trajectories\": 96}'))\n"
        "raise SystemExit(int(os.environ.get('VERIFY_EXIT', '0')))\n"
        "PY\n",
    )
    local = local_root or tmp_path / "pilot-p0"
    command = [
        "bash",
        str(SCRIPT),
        "cluster",
        remote_root,
        str(local),
        str(python),
    ]
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "CALLS": str(calls),
        **(extra_env or {}),
    }
    return command, environment, calls, local


def _run(
    tmp_path: Path,
    *,
    remote_root: str = "/remote/pilot-p0",
    local_root: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    command, environment, calls, local = _prepare(
        tmp_path,
        remote_root=remote_root,
        local_root=local_root,
        extra_env=extra_env,
    )
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    return result, calls, local


def _rsync_calls(calls: Path) -> list[Path]:
    return sorted(calls.glob("rsync.*"))


def _verify_calls(calls: Path) -> list[Path]:
    return sorted(calls.glob("verify.*"))


def _state(local_root: Path) -> Path:
    return Path(f"{local_root}.download-state")


@pytest.mark.parametrize(
    ("remote_root", "local_root"),
    (("relative/remote", None), ("/remote/pilot-p0", Path("relative/local"))),
)
def test_requires_absolute_source_and_destination(
    tmp_path: Path, remote_root: str, local_root: Path | None
):
    result, calls, _ = _run(
        tmp_path, remote_root=remote_root, local_root=local_root
    )
    assert result.returncode == 64
    assert not _rsync_calls(calls)


def test_requires_existing_parent_before_atomic_claim(tmp_path: Path):
    local_root = tmp_path / "missing-parent" / "pilot-p0"
    result, calls, _ = _run(tmp_path, local_root=local_root)
    assert result.returncode == 73
    assert not local_root.parent.exists()
    assert not _rsync_calls(calls)


def test_transfers_with_checksum_and_partial_safe_archive_flags_then_verifies(
    tmp_path: Path,
):
    result, calls, local_root = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert _rsync_calls(calls)[0].read_text(encoding="utf-8").splitlines() == [
        "--archive",
        "--checksum",
        "--partial",
        "--itemize-changes",
        "cluster:/remote/pilot-p0/",
        f"{local_root}/",
    ]
    verify = json.loads(_verify_calls(calls)[0].read_text(encoding="utf-8"))
    assert verify == {
        "argv": [
            "scripts/run_pilot.py",
            "verify",
            "--run-spec",
            f"{local_root}/run_spec.json",
        ],
        "cwd": str(SOLUTION),
        "pythonpath": str(SOLUTION / "src"),
    }
    assert (_state(local_root) / "verified").read_text(encoding="utf-8") == (
        f"cluster:/remote/pilot-p0\n{VERIFIED}\n"
    )


def test_completed_root_rerun_verifies_without_rsync_or_root_mutation(
    tmp_path: Path,
):
    first, calls, local_root = _run(tmp_path)
    assert first.returncode == 0, first.stderr
    completion = _state(local_root) / "verified"
    completion_before = completion.stat()
    sentinel = local_root / "immutable"
    sentinel.write_text("original\n", encoding="utf-8")
    before = sentinel.stat()

    second, _, _ = _run(
        tmp_path,
        local_root=local_root,
        extra_env={"MUTATE_FILE": str(sentinel)},
    )

    assert second.returncode == 0, second.stderr
    assert len(_rsync_calls(calls)) == 1
    assert len(_verify_calls(calls)) == 2
    assert sentinel.read_text(encoding="utf-8") == "original\n"
    assert sentinel.stat().st_mtime_ns == before.st_mtime_ns
    assert completion.stat().st_mtime_ns == completion_before.st_mtime_ns
    assert completion.stat().st_mode & 0o777 == 0o444


def test_allows_same_incomplete_root_to_resume(tmp_path: Path):
    first, calls, local_root = _run(tmp_path, extra_env={"VERIFY_EXIT": "1"})
    assert first.returncode != 0
    assert not (_state(local_root) / "verified").exists()
    second, _, _ = _run(tmp_path, local_root=local_root)
    assert second.returncode == 0, second.stderr
    assert len(_rsync_calls(calls)) == 2


def test_refuses_unmarked_nonempty_destination(tmp_path: Path):
    local_root = tmp_path / "pilot-p0"
    local_root.mkdir()
    (local_root / "unexpected").write_text("keep", encoding="utf-8")
    result, calls, _ = _run(tmp_path, local_root=local_root)
    assert result.returncode == 73
    assert not _rsync_calls(calls)
    assert (local_root / "unexpected").read_text(encoding="utf-8") == "keep"


def test_refuses_destination_marked_for_different_remote(tmp_path: Path):
    first, calls, local_root = _run(tmp_path)
    assert first.returncode == 0, first.stderr
    second, _, _ = _run(
        tmp_path,
        remote_root="/remote/other-pilot",
        local_root=local_root,
    )
    assert second.returncode == 73
    assert len(_rsync_calls(calls)) == 1


@pytest.mark.parametrize("second_remote", ("/remote/pilot-p0", "/remote/other"))
def test_concurrent_same_or_different_source_fails_closed(
    tmp_path: Path, second_remote: str
):
    command, environment, calls, local_root = _prepare(
        tmp_path, extra_env={"BLOCK_RSYNC": "1"}
    )
    first = subprocess.Popen(
        command,
        cwd=tmp_path,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 5
    while not (calls / "ready").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert (calls / "ready").exists()

    second, _, _ = _run(
        tmp_path,
        remote_root=second_remote,
        local_root=local_root,
    )

    assert second.returncode == 75
    assert len(_rsync_calls(calls)) == 1
    assert (_state(local_root) / "source").read_text(encoding="utf-8") == (
        "cluster:/remote/pilot-p0\n"
    )
    assert Path(f"{local_root}.download-claim").is_dir()
    (calls / "release").touch()
    stdout, stderr = first.communicate(timeout=5)
    assert first.returncode == 0, (stdout, stderr)
    assert not Path(f"{local_root}.download-claim").exists()


def test_preserves_unexpected_claim_for_diagnosis(tmp_path: Path):
    local_root = tmp_path / "pilot-p0"
    claim = Path(f"{local_root}.download-claim")
    claim.mkdir()
    (claim / "diagnostic").write_text("stale\n", encoding="utf-8")
    result, calls, _ = _run(tmp_path, local_root=local_root)
    assert result.returncode == 75
    assert (claim / "diagnostic").read_text(encoding="utf-8") == "stale\n"
    assert not _rsync_calls(calls)


@pytest.mark.parametrize("target_exists", (False, True))
def test_rejects_state_directory_symlink(tmp_path: Path, target_exists: bool):
    local_root = tmp_path / "pilot-p0"
    target = tmp_path / "state-target"
    if target_exists:
        target.mkdir()
    _state(local_root).symlink_to(target, target_is_directory=True)
    result, calls, _ = _run(tmp_path, local_root=local_root)
    assert result.returncode == 73
    assert not _rsync_calls(calls)


@pytest.mark.parametrize("name", ("source", "verified"))
@pytest.mark.parametrize("target_exists", (False, True))
def test_rejects_state_file_symlink(
    tmp_path: Path, name: str, target_exists: bool
):
    local_root = tmp_path / "pilot-p0"
    state = _state(local_root)
    state.mkdir()
    if name != "source":
        (state / "source").write_text(
            "cluster:/remote/pilot-p0\n", encoding="utf-8"
        )
    (state / "logs").mkdir()
    target = tmp_path / f"{name}-target"
    if target_exists:
        target.write_text("target\n", encoding="utf-8")
    (state / name).symlink_to(target)
    result, calls, _ = _run(tmp_path, local_root=local_root)
    assert result.returncode == 73
    assert not _rsync_calls(calls)


@pytest.mark.parametrize("target_exists", (False, True))
def test_rejects_transfer_log_directory_symlink(
    tmp_path: Path, target_exists: bool
):
    local_root = tmp_path / "pilot-p0"
    state = _state(local_root)
    state.mkdir()
    (state / "source").write_text(
        "cluster:/remote/pilot-p0\n", encoding="utf-8"
    )
    target = tmp_path / "logs-target"
    if target_exists:
        target.mkdir()
    (state / "logs").symlink_to(target, target_is_directory=True)
    result, calls, _ = _run(tmp_path, local_root=local_root)
    assert result.returncode == 73
    assert not _rsync_calls(calls)


@pytest.mark.parametrize("target_exists", (False, True))
def test_rejects_transfer_log_file_symlink(tmp_path: Path, target_exists: bool):
    local_root = tmp_path / "pilot-p0"
    state = _state(local_root)
    logs = state / "logs"
    logs.mkdir(parents=True)
    (state / "source").write_text(
        "cluster:/remote/pilot-p0\n", encoding="utf-8"
    )
    target = tmp_path / "log-target"
    if target_exists:
        target.write_text("target\n", encoding="utf-8")
    (logs / "transfer-hostile.log").symlink_to(target)
    result, calls, _ = _run(tmp_path, local_root=local_root)
    assert result.returncode == 73
    assert not _rsync_calls(calls)


def test_bootstraps_verified_existing_legacy_root_without_transfer(tmp_path: Path):
    local_root = tmp_path / "pilot-p0"
    local_root.mkdir()
    (local_root / "run_spec.json").write_text("{}\n", encoding="utf-8")
    Path(f"{local_root}.download-source").write_text(
        "cluster:/remote/pilot-p0\n", encoding="utf-8"
    )

    result, calls, _ = _run(tmp_path, local_root=local_root)

    assert result.returncode == 0, result.stderr
    assert not _rsync_calls(calls)
    assert len(_verify_calls(calls)) == 1
    assert (_state(local_root) / "verified").is_file()


def test_keeps_claim_state_and_transfer_logs_outside_downloaded_root(
    tmp_path: Path,
):
    result, _, local_root = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    state = _state(local_root)
    assert state.is_dir() and not state.is_symlink()
    assert (state / "source").is_file()
    assert (state / "verified").is_file()
    logs = state / "logs"
    assert logs.is_dir() and not logs.is_symlink()
    assert len(list(logs.glob("transfer-*.log"))) == 1
    assert not Path(f"{local_root}.download-claim").exists()
    assert not any(entry.name.startswith(".download") for entry in local_root.iterdir())
