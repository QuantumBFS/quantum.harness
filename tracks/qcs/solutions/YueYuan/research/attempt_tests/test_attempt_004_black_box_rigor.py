import csv
import json
import os
import pathlib
import subprocess
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
import device
import pulses
import run_black_box_holdout
import sealed_black_box
import systems


def test_attempt_004_pulse_distortion_changes_pulse_and_counts_queries():
    system = systems.build_system(config.ONE_QUBIT_X)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=501)

    distorted = device.distort_pulse_parameters(
        theta,
        config.ONE_QUBIT_X,
        smoothing=0.2,
        memory=0.15,
    )

    assert distorted.shape == theta.shape
    assert not np.allclose(distorted, theta)
    assert np.max(np.abs(distorted)) <= config.ONE_QUBIT_X.max_amplitude

    oracle = device.build_query_device(system, "pulse_distortion", seed=502, query_seed=503)
    value = oracle.query(theta, shots=64)

    assert 0.0 <= value <= 1.0
    assert oracle.query_count == 1
    assert oracle.shot_count == 64


class PoisonedOracle:
    def __init__(self):
        self.query_count = 0
        self.shot_count = 0

    def query(self, pulse_parameters, shots: int, seed=None) -> float:
        self.query_count += 1
        self.shot_count += int(shots)
        return 0.5

    def exact_infidelity(self, pulse_parameters):
        raise AssertionError("optimizer touched exact true-device scoring")


def test_attempt_004_sealed_optimizer_uses_only_query_api():
    system = systems.build_system(config.ONE_QUBIT_X)
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=511)
    oracle = sealed_black_box.RecordingQueryOracle(PoisonedOracle())
    cfg = config.ClosedLoopConfig(query_budget=7, target_infidelity=1e-3, initial_step=0.04)

    result = sealed_black_box.run_sealed_subspace_method(
        "full_space_nelder_mead",
        system,
        oracle,
        start,
        np.eye(config.ONE_QUBIT_X.raw_dim),
        k=2,
        shots=32,
        seed=512,
        cfg=cfg,
    )

    assert result.query_count <= cfg.query_budget
    assert result.shot_count == result.query_count * 32
    assert len(result.transcript) == result.query_count
    assert not hasattr(oracle, "exact_infidelity")


def test_attempt_004_sealed_result_is_scored_after_optimization():
    system = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(system, "small", seed=521)
    oracle = sealed_black_box.RecordingQueryOracle(
        device.QueryOnlyDevice(true_system, seed=522)
    )
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=523)
    cfg = config.ClosedLoopConfig(query_budget=8, target_infidelity=1e-3, initial_step=0.04)

    sealed = sealed_black_box.run_sealed_subspace_method(
        "hessian_subspace_nelder_mead",
        system,
        oracle,
        start,
        np.eye(config.ONE_QUBIT_X.raw_dim),
        k=3,
        shots=32,
        seed=524,
        cfg=cfg,
    )
    record = sealed_black_box.score_sealed_run(
        system,
        sealed,
        true_system,
        shots=32,
        query_budget=cfg.query_budget,
        seed=524,
        target_infidelity=cfg.target_infidelity,
        mismatch="small",
    )

    assert record.query_count == sealed.query_count
    assert record.total_shots == sealed.shot_count
    assert 0.0 <= record.final_infidelity <= 1.0


def test_attempt_004_sealed_scoring_can_apply_hidden_pulse_transform():
    system = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(system, "pulse_distortion", seed=531)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=532)
    sealed = sealed_black_box.SealedRunResult(
        method="model_only",
        final_theta=theta,
        k=0,
        query_count=1,
        shot_count=64,
        transcript=(
            sealed_black_box.QueryTranscriptEntry(
                query_index=1,
                shots=64,
                total_shots=64,
                pulse_parameters=theta,
                noisy_infidelity=0.5,
            ),
        ),
        metadata={},
    )
    transform = lambda pulse: device.distort_pulse_parameters(
        pulse,
        config.ONE_QUBIT_X,
        smoothing=0.2,
        memory=0.15,
    )

    raw = sealed_black_box.score_sealed_run(
        system,
        sealed,
        true_system,
        shots=64,
        query_budget=1,
        seed=533,
        target_infidelity=1e-3,
        mismatch="pulse_distortion",
    )
    transformed = sealed_black_box.score_sealed_run(
        system,
        sealed,
        true_system,
        shots=64,
        query_budget=1,
        seed=533,
        target_infidelity=1e-3,
        mismatch="pulse_distortion",
        pulse_transform=transform,
    )

    assert raw.final_infidelity != transformed.final_infidelity


def test_attempt_004_black_box_holdout_runner_emits_dev_and_holdout(tmp_path):
    out_dir = tmp_path / "black_box_holdout"
    result = subprocess.run(
        [
            sys.executable,
            str(ATTEMPT / "run_black_box_holdout.py"),
            "--out",
            str(out_dir),
            "--fast",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in (out_dir / "runs.jsonl").read_text().splitlines()]
    assert {"dev", "holdout"} <= {row["split"] for row in rows}
    assert "device_informed_adaptive_hessian_nelder_mead" in {row["method"] for row in rows}
    assert "pulse_distortion" in {row["true_device_variant"] for row in rows}
    summary_rows = list(
        csv.DictReader((out_dir / "summary_tables" / "black_box_holdout_summary.csv").open())
    )
    assert summary_rows
    assert (out_dir / "figures" / "black_box_holdout_success.png").exists()


def test_attempt_004_black_box_holdout_combine_rejects_partial_task_set(tmp_path):
    out_dir = tmp_path / "black_box_holdout"
    tasks_dir = out_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "runs_000.jsonl").write_text("")

    try:
        run_black_box_holdout.combine_tasks(out_dir)
    except ValueError as exc:
        assert "expected 48 task files" in str(exc)
    else:
        raise AssertionError("partial Slurm task set was combined without an error")


def test_attempt_004_black_box_holdout_combine_survives_missing_matplotlib(tmp_path):
    out_dir = tmp_path / "black_box_holdout"
    tasks_dir = out_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    row = {
        "split": "holdout",
        "true_device_variant": "pulse_distortion",
        "system": "one_qubit_x",
        "shots_per_query": 2048,
        "method": "device_informed_adaptive_hessian_nelder_mead",
        "success": True,
        "query_count": 8,
        "total_shots": 16384,
        "final_infidelity": 3.2e-4,
    }
    for index in range(len(run_black_box_holdout.work_items(False))):
        (tasks_dir / f"runs_{index:03d}.jsonl").write_text(json.dumps(row) + "\n")

    fake_modules = tmp_path / "fake_modules"
    fake_modules.mkdir()
    (fake_modules / "matplotlib.py").write_text("raise ImportError('no plotting here')\n")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(fake_modules) + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [
            sys.executable,
            str(ATTEMPT / "run_black_box_holdout.py"),
            "--out",
            str(out_dir),
            "--combine-tasks",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert (out_dir / "summary_tables" / "black_box_holdout_summary.csv").exists()
    assert (out_dir / "figures" / "black_box_holdout_success.skipped.txt").exists()
