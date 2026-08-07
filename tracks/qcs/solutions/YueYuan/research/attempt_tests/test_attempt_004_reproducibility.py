import csv
import importlib.util
import json
import pathlib
import subprocess
import sys

import numpy as np
import pytest


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import baselines
import config
import device
import experiments
import hessian
import open_loop
import pulses
import systems


FAST_METHODS = (
    "full_space_nelder_mead",
    "random_subspace_nelder_mead",
    "hessian_subspace_nelder_mead",
    "adaptive_hessian_subspace_nelder_mead",
    "device_informed_adaptive_hessian_nelder_mead",
)


def _prepared_one_qubit(seed=0):
    system = systems.build_system(config.ONE_QUBIT_X)
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=seed)
    opt = open_loop.optimize_model_pulse(
        system,
        start,
        config.OpenLoopConfig(
            steps=25,
            learning_rate=0.05,
            target_infidelity=1e-2,
            seed_scale=0.0,
        ),
    )
    hess = hessian.dense_hessian(system, opt.theta)
    true_system = device.build_true_system(system, "small", seed=seed)
    return system, true_system, opt, hess


def _load_verify_submission():
    module_path = ATTEMPT / "verify_submission.py"
    assert module_path.exists(), "verify_submission.py must exist"
    spec = importlib.util.spec_from_file_location("verify_submission", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_fake_fast_output(out_dir, records=10):
    (out_dir / "summary_tables").mkdir(parents=True)
    (out_dir / "figures").mkdir()
    (out_dir / "summary.json").write_text(
        json.dumps({"records": records, "groups": 10}) + "\n"
    )
    rows = [
        {
            "split": split,
            "true_device_variant": "pulse_distortion",
            "method": method,
        }
        for split in ("dev", "holdout")
        for method in FAST_METHODS
    ]
    (out_dir / "runs.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows)
    )
    with (out_dir / "summary_tables" / "black_box_holdout_summary.csv").open(
        "w",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("split", "true_device_variant", "method"),
        )
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "figures" / "black_box_holdout_success.png").write_bytes(b"PNG")


def test_attempt_004_random_subspace_is_orthonormal_and_reproducible():
    first = baselines.random_subspace(raw_dim=16, k=3, seed=2)
    second = baselines.random_subspace(raw_dim=16, k=3, seed=2)

    assert np.allclose(first, second)
    assert np.max(np.abs(first.T @ first - np.eye(3))) < 1e-10


def test_attempt_004_model_only_and_hessian_records_are_reproducible():
    system, true_system, opt, hess = _prepared_one_qubit(seed=3)
    closed = config.ClosedLoopConfig(
        query_budget=40,
        target_infidelity=1e-3,
        initial_step=0.08,
    )
    record_a = baselines.run_model_only(
        system,
        true_system,
        opt.theta,
        shots=128,
        seed=4,
    )
    record_b = baselines.run_model_only(
        system,
        true_system,
        opt.theta,
        shots=128,
        seed=4,
    )
    hessian_record = baselines.run_subspace_method(
        method="hessian_subspace_nelder_mead",
        system=system,
        true_system=true_system,
        start_theta=opt.theta,
        hessian_matrix=hess,
        k=3,
        shots=128,
        seed=4,
        cfg=closed,
    )

    assert record_a == record_b
    assert record_a.method == "model_only"
    assert hessian_record.method == "hessian_subspace_nelder_mead"
    assert hessian_record.query_count <= closed.query_budget
    assert hessian_record.total_shots <= closed.query_budget * 128


def test_attempt_004_reported_full_profile_has_1656_records():
    sweep = config.default_full_sweep()

    assert experiments.work_item_count(sweep) == 144
    assert experiments.expected_record_count(sweep, include_adaptive=False) == 1656


def test_attempt_004_reported_adaptive_focus_has_600_records():
    sweep = config.focused_adaptive_sweep()

    assert experiments.work_item_count(sweep) == 48
    assert experiments.expected_record_count(sweep, include_adaptive=True) == 600


def test_attempt_004_full_sweep_combine_rejects_partial_task_set(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "runs_000.jsonl").write_text('{"row": 0}\n')
    (tasks / "open_loop_history_000.jsonl").write_text('{"step": 0}\n')
    (tasks / "hessian_spectra_000.json").write_text('[{"rank": 1}]\n')

    with pytest.raises(ValueError, match="expected 2 complete task shards"):
        experiments.combine_task_outputs(tmp_path, expected_task_files=2)


def test_attempt_004_full_sweep_combine_collects_all_artifacts(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    for index in range(2):
        (tasks / f"runs_{index:03d}.jsonl").write_text(
            json.dumps({"task": index, "kind": "run"}) + "\n"
        )
        (tasks / f"open_loop_history_{index:03d}.jsonl").write_text(
            json.dumps({"task": index, "kind": "history"}) + "\n"
        )
        (tasks / f"hessian_spectra_{index:03d}.json").write_text(
            json.dumps([{"task": index, "kind": "spectrum"}]) + "\n"
        )

    payload = experiments.combine_task_outputs(tmp_path, expected_task_files=2)

    assert payload == {
        "out": str(tmp_path),
        "task_files": 2,
        "task_files_expected": 2,
        "records": 2,
        "open_loop_history_rows": 2,
        "hessian_spectra": 2,
    }
    assert len((tmp_path / "runs.jsonl").read_text().splitlines()) == 2
    assert len((tmp_path / "open_loop_history.jsonl").read_text().splitlines()) == 2
    assert len(json.loads((tmp_path / "hessian_spectra.json").read_text())) == 2


def test_attempt_004_full_sweep_combine_rejects_wrong_record_profile(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    for index in range(2):
        (tasks / f"runs_{index:03d}.jsonl").write_text(
            json.dumps({"task": index}) + "\n"
        )
        (tasks / f"open_loop_history_{index:03d}.jsonl").write_text(
            json.dumps({"task": index}) + "\n"
        )
        (tasks / f"hessian_spectra_{index:03d}.json").write_text(
            json.dumps([{"task": index}]) + "\n"
        )

    with pytest.raises(ValueError, match="expected 3 records, found 2"):
        experiments.combine_task_outputs(
            tmp_path,
            expected_task_files=2,
            expected_records=3,
        )

    assert not (tmp_path / "runs.jsonl").exists()


def test_attempt_004_array_task_writes_only_indexed_shard(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ATTEMPT / "run_full_sweep.py"),
            "--out",
            str(tmp_path),
            "--fast",
            "--task-index",
            "0",
            "--exclude-adaptive",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "tasks" / "runs_000.jsonl").exists()
    assert (tmp_path / "tasks" / "open_loop_history_000.jsonl").exists()
    assert (tmp_path / "tasks" / "hessian_spectra_000.json").exists()
    assert not (tmp_path / "runs.jsonl").exists()
    assert not (tmp_path / "open_loop_history.jsonl").exists()
    assert not (tmp_path / "hessian_spectra.json").exists()


def test_attempt_004_submission_check_accepts_complete_fast_output(tmp_path):
    _write_fake_fast_output(tmp_path)
    verify_submission = _load_verify_submission()

    payload = verify_submission.validate_fast_output(tmp_path)

    assert payload == {
        "records": 10,
        "groups": 10,
        "splits": ["dev", "holdout"],
        "true_device_variants": ["pulse_distortion"],
    }


def test_attempt_004_submission_check_rejects_wrong_record_count(tmp_path):
    _write_fake_fast_output(tmp_path, records=9)
    verify_submission = _load_verify_submission()

    with pytest.raises(RuntimeError, match="expected 10 records"):
        verify_submission.validate_fast_output(tmp_path)
