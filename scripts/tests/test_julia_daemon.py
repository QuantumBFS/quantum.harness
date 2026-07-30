from __future__ import annotations

import os
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "julia-daemon.sh"
JULIA_BIN = os.environ.get("JULIA_REAL_BIN")
CONFIGURED_TOOL_ENV = os.environ.get("JULIA_DAEMON_TOOL_ENV")


def daemon_tool_environment() -> str | None:
    if not JULIA_BIN:
        return None
    command = [JULIA_BIN, "--startup-file=no"]
    if CONFIGURED_TOOL_ENV:
        command.append(f"--project={CONFIGURED_TOOL_ENV}")
    command.extend(
        [
            "-e",
            'using DaemonMode; print(dirname(Base.active_project()))',
        ]
    )
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


DAEMON_TOOL_ENV = daemon_tool_environment()
requires_daemonmode = pytest.mark.skipif(
    not DAEMON_TOOL_ENV,
    reason="set JULIA_REAL_BIN to a real Julia with DaemonMode.jl installed",
)


def unused_port() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return str(sock.getsockname()[1])


def run_runner(
    home: Path,
    *args: str,
    check: bool = True,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "XDG_CACHE_HOME": str(home / "cache"),
            "JULIA_REAL_BIN": JULIA_BIN or "/missing/real/julia",
            "JULIA_DAEMON_TOOL_ENV": DAEMON_TOOL_ENV or "/missing/daemon/tool/environment",
        }
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(RUNNER), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=check,
        timeout=120,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    path = tmp_path / "project"
    path.mkdir()
    (path / "Project.toml").write_text("[deps]\n", encoding="utf-8")
    return path


def test_help_describes_isolation_and_security_boundary(tmp_path: Path) -> None:
    result = run_runner(tmp_path, "help")
    assert "dedicated cache environment" in result.stdout
    assert "target compute" in result.stdout
    assert "project is not modified" in result.stdout
    assert "do not use it on" in result.stdout
    assert "shared login or compute nodes" in result.stdout
    assert "not another wrapper" in result.stdout
    assert "install-shim" in result.stdout
    assert "eval" in result.stdout
    assert "out-of-memory (OOM)" in result.stdout
    assert "retains compiled code" in result.stdout
    assert "state left by an earlier call" in result.stdout
    assert "stop [--port N]" in result.stdout
    assert "restart after dependency" in result.stdout


@requires_daemonmode
def test_run_reuses_server_without_modifying_project(tmp_path: Path, project: Path) -> None:
    port = unused_port()
    project_before = (project / "Project.toml").read_bytes()
    manifest = project / "Manifest.toml"
    try:
        first = run_runner(
            tmp_path,
            "run",
            "--port",
            port,
            "--project",
            str(project),
            "-e",
            'println("pid=", getpid()); println("first")',
        )
        second = run_runner(
            tmp_path,
            "run",
            "--port",
            port,
            "--project",
            str(project),
            "-e",
            'println("pid=", getpid()); println("second")',
        )
        assert first.stdout.splitlines()[0] == second.stdout.splitlines()[0]
        assert "first" in first.stdout
        assert "second" in second.stdout
        assert (project / "Project.toml").read_bytes() == project_before
        assert not manifest.exists()
    finally:
        run_runner(tmp_path, "stop", "--port", port, check=False)


@requires_daemonmode
def test_whitespace_in_script_argument_is_rejected(tmp_path: Path, project: Path) -> None:
    port = unused_port()
    script = tmp_path / "args.jl"
    script.write_text("println(repr(ARGS))\n", encoding="utf-8")
    result = run_runner(
        tmp_path,
        "run",
        "--port",
        port,
        "--project",
        str(project),
        str(script),
        "two words",
        check=False,
    )
    assert result.returncode != 0
    assert "arguments containing whitespace" in result.stderr


@requires_daemonmode
def test_port_rejects_a_different_project(tmp_path: Path, project: Path) -> None:
    port = unused_port()
    other = tmp_path / "other"
    other.mkdir()
    (other / "Project.toml").write_text("[deps]\n", encoding="utf-8")
    try:
        run_runner(tmp_path, "start", "--port", port, "--project", str(project))
        result = run_runner(
            tmp_path,
            "start",
            "--port",
            port,
            "--project",
            str(other),
            check=False,
        )
        assert result.returncode != 0
        assert "already serves" in result.stderr
    finally:
        run_runner(tmp_path, "stop", "--port", port, check=False)


@requires_daemonmode
def test_concurrent_starts_manage_one_server(tmp_path: Path, project: Path) -> None:
    port = unused_port()
    command = ("start", "--port", port, "--project", str(project))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: run_runner(tmp_path, *command), range(2)))
        assert all(result.returncode == 0 for result in results)
        status = run_runner(tmp_path, "status", "--port", port)
        assert "running pid=" in status.stdout
    finally:
        run_runner(tmp_path, "stop", "--port", port, check=False)


def test_stop_refuses_unverified_pid(tmp_path: Path) -> None:
    port = unused_port()
    state = tmp_path / "cache" / "quantum-harness" / "julia-daemon" / port
    state.mkdir(parents=True)
    sleeper = subprocess.Popen(["sleep", "30"])
    try:
        (state / "server.pid").write_text(f"{sleeper.pid}\n", encoding="utf-8")
        (state / "server.token").write_text("forged-token\n", encoding="utf-8")
        (state / "server.identity").write_text("forged-identity\n", encoding="utf-8")
        result = run_runner(tmp_path, "stop", "--port", port, check=False)
        assert result.returncode == 0
        assert "refusing to signal" in result.stderr
        time.sleep(0.1)
        assert sleeper.poll() is None
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)


@requires_daemonmode
def test_script_failure_is_nonzero(tmp_path: Path, project: Path) -> None:
    port = unused_port()
    try:
        result = run_runner(
            tmp_path,
            "run",
            "--port",
            port,
            "--project",
            str(project),
            "-e",
            'error("intentional")',
            check=False,
        )
        assert result.returncode != 0
    finally:
        run_runner(tmp_path, "stop", "--port", port, check=False)


@requires_daemonmode
def test_transparent_julia_mode_reuses_daemon_and_falls_back(
    tmp_path: Path, project: Path
) -> None:
    cache = tmp_path / "transparent-cache"
    env = {"XDG_CACHE_HOME": str(cache)}
    first = run_runner(
        tmp_path,
        "julia",
        f"--project={project}",
        "-e",
        'println("pid=", getpid())',
        extra_env=env,
    )
    second = run_runner(
        tmp_path,
        "julia",
        f"--project={project}",
        "-e",
        'println("pid=", getpid())',
        extra_env=env,
    )
    version = run_runner(tmp_path, "julia", "--version", extra_env=env)
    assert first.stdout == second.stdout
    assert "pid=" in first.stdout
    assert "julia version" in version.stdout.lower()


@requires_daemonmode
def test_install_shim_and_alias_keep_normal_julia_syntax(tmp_path: Path) -> None:
    shim = tmp_path / "bin" / "julia"
    installed = run_runner(tmp_path, "install-shim", str(shim))
    assert shim.stat().st_mode & 0o111
    assert "Julia shim installed" in installed.stdout
    version = subprocess.run(
        [str(shim), "--version"],
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
        env={
            **os.environ,
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "JULIA_DAEMON_TOOL_ENV": DAEMON_TOOL_ENV or "",
        },
    )
    assert "julia version" in version.stdout.lower()

    alias = run_runner(tmp_path, "alias").stdout.strip()
    result = subprocess.run(
        ["bash", "-c", f"shopt -s expand_aliases\n{alias}\njulia --version"],
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    assert "julia version" in result.stdout.lower()


def test_shim_refuses_to_overwrite_runner_copy(tmp_path: Path) -> None:
    runner_copy = tmp_path / "runner.sh"
    runner_copy.write_bytes(RUNNER.read_bytes())
    runner_copy.chmod(0o755)
    result = subprocess.run(
        [str(runner_copy), "install-shim", str(runner_copy)],
        env={**os.environ, "JULIA_REAL_BIN": JULIA_BIN or "/missing/real/julia"},
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0
    assert "runner itself" in result.stderr
    assert runner_copy.read_bytes() == RUNNER.read_bytes()


@requires_daemonmode
def test_reinstalling_shim_does_not_capture_it_as_real_julia(tmp_path: Path) -> None:
    shim = tmp_path / "bin" / "julia"
    run_runner(tmp_path, "install-shim", str(shim))
    env = {
        **os.environ,
        "PATH": f"{shim.parent}:{os.environ['PATH']}",
        "JULIA_DAEMON_TOOL_ENV": DAEMON_TOOL_ENV or "",
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
    }
    subprocess.run(
        [str(RUNNER), "install-shim", str(shim)],
        env=env,
        text=True,
        capture_output=True,
        check=True,
        timeout=60,
    )
    version = subprocess.run(
        [str(shim), "--version"],
        env=env,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    assert "julia version" in version.stdout.lower()


@requires_daemonmode
def test_ambiguous_project_and_whitespace_args_fall_back(
    tmp_path: Path, project: Path
) -> None:
    version = run_runner(
        tmp_path,
        "julia",
        "--project=/does/not/exist",
        "--version",
    )
    assert "julia version" in version.stdout.lower()

    args = run_runner(
        tmp_path,
        "julia",
        f"--project={project}",
        "-e",
        "println(repr(ARGS))",
        "two words",
    )
    assert '["two words"]' in args.stdout
