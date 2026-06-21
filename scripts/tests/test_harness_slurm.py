"""Behavioural tests for the harness_slurm.sh subcommands wait / smoke-test /
smoke-verdict.

No cluster is touched: `wait` is driven by a fake ``ssh`` placed on PATH that
echoes a canned squeue line, `smoke-test` is checked in --dry-run, and
`smoke-verdict` runs against a local manifest file.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "harness_slurm.sh"


def run(args, *, env=None, cwd=REPO):
    full = {**os.environ, "HARNESS_LOGIN_SHELL": "0", **(env or {})}
    return subprocess.run(
        [str(SCRIPT), *args], capture_output=True, text=True, env=full, cwd=str(cwd)
    )


@pytest.fixture
def fake_ssh(tmp_path):
    """Put a fake `ssh` on PATH that prints $FAKE_OUT regardless of arguments."""
    bind = tmp_path / "bin"
    bind.mkdir()
    ssh = bind / "ssh"
    ssh.write_text("#!/bin/bash\nprintf '%s\\n' \"${FAKE_OUT:-}\"\n")
    ssh.chmod(0o755)
    return {"PATH": f"{bind}:{os.environ['PATH']}"}


# --------------------------------------------------------------------------- #
# wait
# --------------------------------------------------------------------------- #
def test_wait_dry_run():
    r = run(["--dry-run", "--alias", "x", "wait", "12345"])
    assert r.returncode == 0
    assert "DRYRUN poll squeue -j 12345" in r.stderr


def test_wait_done_when_queue_empty(fake_ssh):
    # FAKE_OUT empty → squeue returns nothing → job has left the queue.
    r = run(["--alias", "x", "wait", "999", "--interval", "0"], env={**fake_ssh})
    assert r.returncode == 0
    assert "DONE (left queue)" in r.stdout


def test_wait_timeout_when_still_running(fake_ssh):
    r = run(
        ["--alias", "x", "wait", "999", "--interval", "0", "--attempts", "2"],
        env={**fake_ssh, "FAKE_OUT": "RUNNING"},
    )
    assert r.returncode == 2
    assert "TIMEOUT" in r.stdout
    assert r.stdout.count("poll ") == 2  # polled exactly --attempts times


def test_wait_rejects_unknown_flag():
    r = run(["--alias", "x", "wait", "1", "--bogus", "y"])
    assert r.returncode != 0
    assert "unknown flag" in r.stderr


# --------------------------------------------------------------------------- #
# smoke-verdict
# --------------------------------------------------------------------------- #
def test_smoke_verdict_pass(tmp_path):
    run_dir = tmp_path / "results" / "smoke"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text('{"host":"n1","status":"ok"}')
    r = run(["smoke-verdict", "smoke"], cwd=tmp_path)
    assert r.returncode == 0 and "PASS" in r.stdout


def test_smoke_verdict_fail_missing(tmp_path):
    r = run(["smoke-verdict", "smoke"], cwd=tmp_path)
    assert r.returncode == 1 and "no manifest" in r.stdout


def test_smoke_verdict_fail_bad_status(tmp_path):
    run_dir = tmp_path / "results" / "smoke"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text('{"status":"error"}')
    r = run(["smoke-verdict", "smoke"], cwd=tmp_path)
    assert r.returncode == 1 and "status != ok" in r.stdout


# --------------------------------------------------------------------------- #
# smoke-test (dry-run plan only — full path needs a cluster)
# --------------------------------------------------------------------------- #
def test_smoke_test_dry_run_plan():
    r = run(
        [
            "--dry-run",
            "--alias",
            "x",
            "--repo",
            "/remote/repo",
            "smoke-test",
            "--partition",
            "i64m512u",
        ]
    )
    assert r.returncode == 0
    for step in ("1. ship", "2. submit", "3. wait", "4. fetch", "5. smoke-verdict"):
        assert step in r.stdout
    assert "i64m512u" in r.stdout


def test_smoke_test_missing_script(tmp_path):
    # Run from a dir with no scripts/smoke_test.sbatch → hard error.
    r = run(["--dry-run", "--alias", "x", "--repo", "/r", "smoke-test"], cwd=tmp_path)
    assert r.returncode != 0
    assert "missing" in r.stderr
