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
GUARDRAIL = REPO / "scripts" / "cluster_guardrail.py"


def run(args, *, env=None, cwd=REPO):
    full = {**os.environ, "HARNESS_LOGIN_SHELL": "0", **(env or {})}
    return subprocess.run(
        [str(SCRIPT), *args], capture_output=True, text=True, env=full, cwd=str(cwd)
    )


def run_guardrail(args):
    return subprocess.run(["python3", str(GUARDRAIL), *args], capture_output=True, text=True)


@pytest.fixture
def fake_ssh(tmp_path):
    """Put a fake `ssh` on PATH that prints $FAKE_OUT regardless of arguments."""
    bind = tmp_path / "bin"
    bind.mkdir()
    ssh = bind / "ssh"
    ssh.write_text("#!/bin/bash\nprintf '%s\\n' \"${FAKE_OUT:-}\"\n")
    ssh.chmod(0o755)
    return {"PATH": f"{bind}:{os.environ['PATH']}"}


def write_profile(tmp_path):
    profile = tmp_path / "cluster.toml"
    profile.write_text(
        """
[identity]
name = "test"

[connection]
repo_path_remote = "~/repo"

[connection.ssh]
alias = "test-cluster"

[scheduler]
type = "slurm"
default_partition = "default-gpu"

[[partitions]]
name = "default-gpu"
required_gres = "gpu:default:1"

[[partitions]]
name = "explicit-gpu"
required_gres = "gpu:explicit:2"

[[partitions]]
name = "other-gpu"
required_gres = "gpu:other:1"
"""
    )
    return profile


def write_job_script(tmp_path, text=""):
    script = tmp_path / "job.sbatch"
    script.write_text(text)
    return script


# --------------------------------------------------------------------------- #
# cluster_guardrail option parser
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ("--partition=explicit-gpu", "explicit-gpu"),
        ("--partition explicit-gpu", "explicit-gpu"),
        ("-p explicit-gpu", "explicit-gpu"),
        ("-pexplicit-gpu", "explicit-gpu"),
        ("--partition=default-gpu --partition=explicit-gpu", "explicit-gpu"),
    ],
)
def test_guardrail_option_reads_last_partition_from_extra(extra, expected):
    r = run_guardrail(["option", "--field", "partition", "--", extra])
    assert r.returncode == 0
    assert r.stdout.strip() == expected


def test_guardrail_option_reports_absent_field():
    r = run_guardrail(["option", "--field", "partition", "--", "--time=01:00:00"])
    assert r.returncode == 1
    assert r.stdout == ""


def test_guardrail_option_fails_closed_on_malformed_extra():
    r = run_guardrail(["option", "--field", "partition", "--", "--partition='unterminated"])
    assert r.returncode == 2
    assert "malformed --extra" in r.stderr


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


# --------------------------------------------------------------------------- #
# profile-driven submit feasibility
# --------------------------------------------------------------------------- #
def test_submit_uses_profile_default_partition_and_required_gres(tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path)
    r = run(
        [
            "--dry-run",
            "submit",
            "--test-only",
            "--script",
            str(script),
        ],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode == 0
    assert "sbatch --test-only" in r.stderr
    assert "--partition=default-gpu" in r.stderr
    assert "--gres=gpu:default:1" in r.stderr


def test_submit_extra_partition_overrides_profile_default_for_required_gres(tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path)
    r = run(
        [
            "--dry-run",
            "submit",
            "--test-only",
            "--script",
            str(script),
            "--extra",
            "--partition=explicit-gpu",
        ],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode == 0
    assert "--partition=default-gpu" not in r.stderr
    assert "--gres=gpu:explicit:2" in r.stderr
    assert "--partition=explicit-gpu" in r.stderr


@pytest.mark.parametrize("extra", ["--partition explicit-gpu", "-p explicit-gpu", "-pexplicit-gpu"])
def test_submit_extra_partition_space_and_short_forms_select_required_gres(tmp_path, extra):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path)
    r = run(
        ["--dry-run", "submit", "--script", str(script), "--extra", extra],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode == 0
    assert "--partition=default-gpu" not in r.stderr
    assert "--gres=gpu:explicit:2" in r.stderr


def test_submit_last_extra_partition_wins_for_required_gres(tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path)
    r = run(
        [
            "--dry-run",
            "submit",
            "--script",
            str(script),
            "--extra",
            "--partition=explicit-gpu --partition=other-gpu",
        ],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode == 0
    assert "--gres=gpu:other:1" in r.stderr
    assert "--gres=gpu:explicit:2" not in r.stderr


def test_submit_uses_explicit_partition_required_gres(tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path, "#SBATCH --partition=default-gpu\n")
    r = run(
        [
            "--dry-run",
            "submit",
            "--script",
            str(script),
            "--partition",
            "explicit-gpu",
        ],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode == 0
    assert "--partition=explicit-gpu" in r.stderr
    assert "--partition=default-gpu" not in r.stderr
    assert "--gres=gpu:explicit:2" in r.stderr


def test_submit_preserves_caller_gres_in_extra(tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path, "#SBATCH --gres=gpu:script:4\n")
    r = run(
        [
            "--dry-run",
            "submit",
            "--script",
            str(script),
            "--extra",
            "--gres=gpu:caller:3",
        ],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode == 0
    assert "--gres=gpu:caller:3" in r.stderr
    assert "--gres=gpu:default:1" not in r.stderr


def test_submit_combines_profile_default_partition_with_script_gres(tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path, "#SBATCH --gres=gpu:script:4\n")

    r = run(
        ["--dry-run", "submit", "--script", str(script)],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode == 0
    assert "--partition=default-gpu" in r.stderr
    assert "--gres=gpu:default:1" not in r.stderr


def test_submit_preserves_script_partition_and_gres(tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(
        tmp_path,
        "#SBATCH --partition=explicit-gpu\n"
        "#SBATCH --gres=gpu:script:4\n"
    )

    r = run(
        ["--dry-run", "submit", "--script", str(script)],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode == 0
    assert "--partition=default-gpu" not in r.stderr
    assert "--gres=gpu:default:1" not in r.stderr
    assert " --partition=" not in r.stderr
    assert " --gres=" not in r.stderr


def test_submit_adds_required_gres_for_script_partition_without_gres(tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path, "#SBATCH --partition=explicit-gpu\n")

    r = run(
        ["--dry-run", "submit", "--script", str(script)],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode == 0
    assert " --partition=" not in r.stderr
    assert "--gres=gpu:explicit:2" in r.stderr


def test_submit_malformed_extra_stops_before_sbatch(tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path)
    r = run(
        [
            "--dry-run",
            "submit",
            "--test-only",
            "--script",
            str(script),
            "--extra",
            "--partition='unterminated",
        ],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode != 0
    assert "malformed --extra" in r.stderr
    assert "DRYRUN ssh" not in r.stderr


def test_submit_missing_local_script_stops_before_sbatch(tmp_path):
    profile = write_profile(tmp_path)
    missing = tmp_path / "missing.sbatch"
    r = run(
        ["--dry-run", "submit", "--test-only", "--script", str(missing)],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )

    assert r.returncode != 0
    assert "locally readable" in r.stderr
    assert "DRYRUN ssh" not in r.stderr


def test_submit_test_only_prints_scheduler_output_without_job_id_parsing(
    fake_ssh, tmp_path
):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path)
    scheduler_output = "sbatch: Job 42 to start at 2026-08-31T12:00:00"
    r = run(
        ["submit", "--test-only", "--script", str(script)],
        env={
            **fake_ssh,
            "FAKE_OUT": scheduler_output,
            "HARNESS_PROFILE_FILE": str(profile),
        },
    )

    assert r.returncode == 0
    assert r.stdout.strip() == scheduler_output
    assert "could not parse a job id" not in r.stderr
    assert "job_id:" not in r.stdout


def test_submit_real_mode_still_parses_job_id(fake_ssh, tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path)
    r = run(
        ["submit", "--script", str(script)],
        env={
            **fake_ssh,
            "FAKE_OUT": "Submitted batch job 12345",
            "HARNESS_PROFILE_FILE": str(profile),
        },
    )

    assert r.returncode == 0
    assert "job_id:    12345" in r.stdout
    assert "partition: default-gpu" in r.stdout
