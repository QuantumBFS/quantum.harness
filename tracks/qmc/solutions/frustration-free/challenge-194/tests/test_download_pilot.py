from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest


SOLUTION = Path(__file__).resolve().parents[1]
SCRIPT = SOLUTION / "scripts" / "download_pilot.sh"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _run(
    tmp_path: Path,
    *,
    remote_root: str | None = None,
    local_root: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    calls = tmp_path / "calls"
    calls.mkdir(exist_ok=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    _write_executable(
        fake_bin / "rsync",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"${CALLS}/rsync\"\n",
    )
    python = tmp_path / "python"
    _write_executable(
        python,
        "#!/bin/bash\n"
        "python3 - \"$@\" <<'PY'\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['CALLS'], 'verify').write_text(json.dumps({\n"
        "    'argv': sys.argv[1:],\n"
        "    'cwd': os.getcwd(),\n"
        "    'pythonpath': os.environ.get('PYTHONPATH'),\n"
        "}))\n"
        "print('{\"cells\": 96, \"status\": \"verified\", \"trajectories\": 96}')\n"
        "PY\n",
    )
    remote = remote_root or "/remote/pilot-p0"
    local = local_root or str(tmp_path / "pilot-p0")
    result = subprocess.run(
        ["bash", str(SCRIPT), "cluster", remote, local, str(python)],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}", "CALLS": str(calls)},
        capture_output=True,
        text=True,
    )
    return result, calls, Path(local)


@pytest.mark.parametrize(
    ("remote_root", "local_root"),
    (("relative/remote", None), (None, "relative/local")),
)
def test_requires_absolute_source_and_destination(
    tmp_path: Path, remote_root: str | None, local_root: str | None
):
    result, calls, _ = _run(
        tmp_path, remote_root=remote_root, local_root=local_root
    )
    assert result.returncode == 64
    assert not (calls / "rsync").exists()


def test_transfers_with_checksum_and_partial_safe_archive_flags_then_verifies(
    tmp_path: Path,
):
    result, calls, local_root = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (calls / "rsync").read_text(encoding="utf-8").splitlines() == [
        "--archive",
        "--checksum",
        "--partial",
        "--itemize-changes",
        "cluster:/remote/pilot-p0/",
        f"{local_root}/",
    ]
    verify = json.loads((calls / "verify").read_text(encoding="utf-8"))
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


def test_refuses_unmarked_nonempty_destination(tmp_path: Path):
    local_root = tmp_path / "pilot-p0"
    local_root.mkdir()
    (local_root / "unexpected").write_text("keep", encoding="utf-8")
    result, calls, _ = _run(tmp_path, local_root=str(local_root))
    assert result.returncode == 73
    assert not (calls / "rsync").exists()
    assert (local_root / "unexpected").read_text(encoding="utf-8") == "keep"


def test_allows_same_marked_root_to_resume(tmp_path: Path):
    first, _, local_root = _run(tmp_path)
    assert first.returncode == 0, first.stderr
    (local_root / "partial-data").write_text("partial", encoding="utf-8")
    (tmp_path / "calls" / "rsync").unlink()
    second, calls, _ = _run(tmp_path, local_root=str(local_root))
    assert second.returncode == 0, second.stderr
    assert (calls / "rsync").exists()
    assert (local_root / "partial-data").read_text(encoding="utf-8") == "partial"


def test_refuses_nonempty_destination_marked_for_different_remote(tmp_path: Path):
    first, _, local_root = _run(tmp_path)
    assert first.returncode == 0, first.stderr
    (local_root / "partial-data").write_text("partial", encoding="utf-8")
    (tmp_path / "calls" / "rsync").unlink()
    second, calls, _ = _run(
        tmp_path,
        remote_root="/remote/other-pilot",
        local_root=str(local_root),
    )
    assert second.returncode == 73
    assert not (calls / "rsync").exists()


def test_keeps_transfer_state_and_logs_outside_downloaded_root(tmp_path: Path):
    result, _, local_root = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert not any(
        entry.name.endswith((".download-source", ".transfer.log"))
        for entry in local_root.iterdir()
    )
    assert Path(f"{local_root}.download-source").is_file()
    assert Path(f"{local_root}.transfer.log").is_file()
