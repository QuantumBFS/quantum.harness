from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "skills/using-slurm/profiles/scnet.toml"
SBATCH = ROOT / "tracks/mps/solutions/issue-86/run_full.sbatch"
CALIBRATION_SBATCH = (
    ROOT / "tracks/mps/solutions/issue-86/run_calibration.sbatch"
)
PACKED_WORKER = ROOT / "tracks/mps/solutions/issue-86/packed_worker.sh"
GENERATE_SPEC = ROOT / "tracks/mps/solutions/issue-86/generate_run_spec.jl"
RUN_CELL = ROOT / "tracks/mps/solutions/issue-86/run_cell.jl"
COLLECT = ROOT / "tracks/mps/solutions/issue-86/collect.jl"
FORMAL_ANALYSIS = ROOT / "tracks/mps/solutions/issue-86/analyze_formal.jl"


def test_scnet_profile_targets_xhacnormalb_cpu_node():
    profile = PROFILE.read_text()

    assert 'default_partition = "xhacnormalb"' in profile
    assert 'name = "xhacnormalb"' in profile
    assert 'class = "cpu"' in profile
    assert "cores = 128" in profile
    assert 'memory = "512000M"' in profile
    assert 'gpu = ' not in profile


def test_issue86_sbatch_packs_a_full_cpu_node():
    script = SBATCH.read_text()

    assert "#SBATCH --partition=xhacnormalb" in script
    assert "#SBATCH --nodes=1" in script
    assert "#SBATCH --cpus-per-task=128" in script
    assert "#SBATCH --mem=480G" in script
    assert "packed_worker.sh" in script
    assert "HARNESS_RUN_SPEC" in script


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(textwrap.dedent(contents).lstrip())
    path.chmod(0o755)


def _run_fake_packed_worker(tmp_path: Path, *, fail_index: int | None = None):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "julia",
        """\
        #!/bin/bash
        case "$*" in
          *pending_cells.jl*) printf '1\\n2\\n3\\n4\\n5\\n6\\n' ;;
          *collect.jl*) exit 0 ;;
          *) exit 0 ;;
        esac
        """,
    )
    _write_executable(
        fake_bin / "srun",
        """\
        #!/usr/bin/env python3
        import fcntl
        import json
        import os
        import sys
        import time

        path = os.environ["FAKE_SRUN_STATE"]
        lock_path = f"{path}.lock"
        index = int(sys.argv[-2])

        def update(delta):
            with open(lock_path, "a+", encoding="utf-8") as lock_handle:
                fcntl.flock(lock_handle, fcntl.LOCK_EX)
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        raw = handle.read()
                except FileNotFoundError:
                    raw = ""
                state = json.loads(raw) if raw else {
                    "active": 0,
                    "maximum": 0,
                    "memories": [],
                    "seen": [],
                    "arguments": [],
                    "thread_sets": [],
                }
                state["active"] += delta
                state["maximum"] = max(state["maximum"], state["active"])
                if delta > 0:
                    state["memories"].extend(
                        arg.split("=", 1)[1]
                        for arg in sys.argv
                        if arg.startswith("--mem=")
                    )
                    state["seen"].append(index)
                    state["arguments"].append(sys.argv[1:])
                    state["thread_sets"].append([
                        os.environ.get("JULIA_NUM_THREADS"),
                        os.environ.get("OPENBLAS_NUM_THREADS"),
                    ])
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(state, handle)
                    handle.flush()
                fcntl.flock(lock_handle, fcntl.LOCK_UN)

        update(1)
        time.sleep(0.08)
        update(-1)
        if os.environ.get("FAKE_FAIL_INDEX") == str(index):
            raise SystemExit(255)
        """,
    )

    spec = tmp_path / "run_spec.json"
    spec.write_text("{}")
    output = tmp_path / "results"
    state_path = tmp_path / "srun-state.json"
    env = dict(os.environ)
    env.update({
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "SLURM_CPUS_PER_TASK": "8",
        "SLURM_MEM_PER_NODE": "12288",
        "FAKE_SRUN_STATE": str(state_path),
    })
    if fail_index is not None:
        env["FAKE_FAIL_INDEX"] = str(fail_index)
    result = subprocess.run(
        [str(PACKED_WORKER), str(spec), str(output), "A", "32", "4"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert state_path.exists(), result.stderr
    state = json.loads(state_path.read_text())
    return result, state


def test_packed_worker_caps_concurrency_to_allocation_and_splits_memory(tmp_path):
    result, state = _run_fake_packed_worker(tmp_path)

    assert result.returncode == 0, result.stderr
    assert state["maximum"] == 2
    assert set(state["memories"]) == {"6144M"}
    assert sorted(state["seen"]) == [1, 2, 3, 4, 5, 6]
    assert all("--exact" in args for args in state["arguments"])
    assert all("--exclusive" in args for args in state["arguments"])
    assert all("--cpu-bind=cores" in args for args in state["arguments"])
    assert all("--cpus-per-task=4" in args for args in state["arguments"])
    assert state["thread_sets"] == [["4", "4"]] * 6


def test_packed_worker_retains_progress_after_one_cell_fails(tmp_path):
    for attempt in range(20):
        attempt_path = tmp_path / f"attempt-{attempt}"
        attempt_path.mkdir()
        result, state = _run_fake_packed_worker(
            attempt_path, fail_index=3
        )

        assert result.returncode != 0
        assert sorted(state["seen"]) == [1, 2, 3, 4, 5, 6]


def test_calibration_uses_one_worker_with_every_allocated_cpu(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "bash",
        """\
        #!/bin/sh
        env | sort > "$CALIBRATION_CAPTURE.env"
        printf '%s\\n' "$@" > "$CALIBRATION_CAPTURE.args"
        """,
    )

    for threads in ("4", "8"):
        capture = tmp_path / f"capture-{threads}"
        env = dict(os.environ)
        env.update({
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "SLURM_CPUS_PER_TASK": threads,
            "CALIBRATION_CAPTURE": str(capture),
        })
        result = subprocess.run(
            ["/bin/bash", str(CALIBRATION_SBATCH)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        captured_env = dict(
            line.split("=", 1)
            for line in Path(f"{capture}.env").read_text().splitlines()
            if "=" in line
        )
        run_directory = (
            f"tracks/mps/results/issue-86-calibration-{threads}t"
        )
        assert captured_env["ISSUE86_WORKERS"] == "1"
        assert captured_env["ISSUE86_CORES_PER_WORKER"] == threads
        assert captured_env["ISSUE86_STAGE"] == "calibration"
        assert captured_env["RESOURCE_CLASS"] == "A"
        assert captured_env["HARNESS_RUN_SPEC"] == f"{run_directory}/run_spec.json"
        assert captured_env["ISSUE86_OUTPUT_DIR"] == run_directory
        assert Path(f"{capture}.args").read_text().splitlines() == [
            "tracks/mps/solutions/issue-86/run_full.sbatch"
        ]


def _capture_full_run_layout(
    tmp_path: Path, *, resource_class: str, allocated_cpus: int
) -> list[str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "bash",
        """\
        #!/bin/sh
        printf '%s\\n' "$@" > "$CLASS_A_CAPTURE"
        """,
    )
    run_directory = tmp_path / "stage1"
    run_directory.mkdir()
    run_spec = run_directory / "run_spec.json"
    run_spec.write_text('{"cells":[]}')
    capture = tmp_path / "class-a.args"
    env = dict(os.environ)
    env.update({
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "HARNESS_RUN_SPEC": str(run_spec),
        "HARNESS_COMMAND": f"stage1:{resource_class}",
        "SLURM_CPUS_PER_TASK": str(allocated_cpus),
        "CLASS_A_CAPTURE": str(capture),
    })

    result = subprocess.run(
        ["/bin/bash", str(SBATCH)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    return capture.read_text().splitlines()


def test_class_a_uses_the_calibrated_eight_core_layout(tmp_path):
    assert _capture_full_run_layout(
        tmp_path, resource_class="A", allocated_cpus=128
    ) == [
        "tracks/mps/solutions/issue-86/packed_worker.sh",
        str(tmp_path / "stage1" / "run_spec.json"),
        str(tmp_path / "stage1"),
        "A",
        "16",
        "8",
    ]


def test_worker_count_scales_to_a_partial_node_allocation(tmp_path):
    assert _capture_full_run_layout(
        tmp_path / "class-a", resource_class="A", allocated_cpus=64
    )[-3:] == ["A", "8", "8"]
    assert _capture_full_run_layout(
        tmp_path / "class-b", resource_class="B", allocated_cpus=64
    )[-3:] == ["B", "4", "16"]


def test_run_spec_entrypoints_are_separate_from_the_solver():
    assert "build_run_spec" in GENERATE_SPEC.read_text()
    assert "execute_cell" in RUN_CELL.read_text()
    assert "collect_cell_results" in COLLECT.read_text()
    analysis = FORMAL_ANALYSIS.read_text()
    assert "fit_crossing_sequence" in analysis
    assert "conservative_error_budget" in analysis
    assert "adaptive_run_spec.json" in analysis
