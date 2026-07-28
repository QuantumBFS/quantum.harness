import json
import pathlib
import subprocess
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
import device
import hardware_adapter
import pulses
import systems


def _one_qubit_true_system(seed=21):
    model = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(model, "small", seed=seed)
    return model, true_system


def test_attempt_004_dry_run_batch_backend_counts_jobs_shots_and_counts():
    model, true_system = _one_qubit_true_system()
    shots = 128
    candidates = [
        hardware_adapter.HardwareCandidate(
            "center",
            pulses.initial_pulse(config.ONE_QUBIT_X, seed=1),
        ),
        hardware_adapter.HardwareCandidate(
            "offset",
            pulses.initial_pulse(config.ONE_QUBIT_X, seed=2),
            metadata={"basis": "test"},
        ),
    ]
    backend = hardware_adapter.DryRunBatchBackend(true_system, seed=22)

    jobs = backend.submit_batch(candidates, shots=shots, metadata={"system": model.config.name})
    results = backend.collect_results([job.job_id for job in jobs])
    evaluations = [hardware_adapter.evaluate_result(result) for result in results]

    assert backend.query_count == 2
    assert backend.shot_count == 2 * shots
    assert len(jobs) == 2
    assert len(results) == 2
    assert {job.candidate_id for job in jobs} == {"center", "offset"}
    assert all(result.shots == shots for result in results)
    assert all(sum(result.counts.values()) == shots for result in results)
    assert all(0.0 <= evaluation.objective <= 1.0 for evaluation in evaluations)


def test_attempt_004_batch_bundle_and_results_round_trip(tmp_path):
    shots = 64
    candidates = [
        hardware_adapter.HardwareCandidate(
            "candidate-a",
            np.array([0.1, -0.2, 0.3], dtype=float),
            metadata={"direction": "center"},
        ),
        hardware_adapter.HardwareCandidate(
            "candidate-b",
            np.array([-0.1, 0.2, -0.3], dtype=float),
            metadata={"direction": "plus"},
        ),
    ]
    out_dir = tmp_path / "batch"

    paths = hardware_adapter.write_batch_bundle(
        candidates,
        out_dir,
        shots=shots,
        metadata={"backend": "dry-run"},
    )

    assert paths["manifest"] == out_dir / "batch_manifest.json"
    assert paths["candidates"] == out_dir / "candidates.csv"
    assert paths["pulse_payloads"] == out_dir / "pulse_payloads.jsonl"
    assert paths["manifest"].exists()
    assert paths["candidates"].exists()
    assert paths["pulse_payloads"].exists()

    manifest = json.loads(paths["manifest"].read_text())
    assert manifest["candidate_count"] == 2
    assert manifest["shots_per_candidate"] == 64
    assert manifest["total_planned_shots"] == 128
    assert manifest["objective_proxy"] == "success_probability_infidelity"

    results_path = out_dir / "hardware_results.jsonl"
    hardware_adapter.write_results_jsonl(
        [
            hardware_adapter.HardwareResult(
                "job-1",
                "candidate-a",
                64,
                {"target": 50, "other": 14},
                {"round": 0},
            ),
            hardware_adapter.HardwareResult(
                "job-2",
                "candidate-b",
                64,
                {"target": 48, "other": 16},
                {"round": 0},
            ),
        ],
        results_path,
    )
    round_tripped = hardware_adapter.read_results_jsonl(results_path)
    evaluations = [hardware_adapter.evaluate_result(result) for result in round_tripped]
    summary = hardware_adapter.summarize_evaluations(evaluations)

    assert [result.candidate_id for result in round_tripped] == ["candidate-a", "candidate-b"]
    assert round_tripped[0].candidate_id == "candidate-a"
    assert round_tripped[0].counts == {"target": 50, "other": 14}
    assert round_tripped[1].candidate_id == "candidate-b"
    assert round_tripped[1].counts == {"target": 48, "other": 16}
    assert summary["candidate_count"] == 2
    assert summary["total_shots"] == 128
    assert summary["best_candidate_id"] == "candidate-a"


def test_attempt_004_evaluate_result_rejects_malformed_counts():
    malformed = hardware_adapter.HardwareResult(
        "job-bad",
        "candidate-bad",
        64,
        {"target": 65, "other": -1},
        {},
    )

    try:
        hardware_adapter.evaluate_result(malformed)
    except ValueError as exc:
        assert "counts must be non-negative" in str(exc)
    else:
        raise AssertionError("malformed hardware counts were accepted")


def test_attempt_004_hardware_dry_run_script_emits_batch_artifacts(tmp_path):
    out_dir = tmp_path / "hardware"

    result = subprocess.run(
        [
            sys.executable,
            str(ATTEMPT / "run_hardware_dry_run.py"),
            "--out",
            str(out_dir),
            "--shots",
            "128",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (out_dir / "batch_manifest.json").exists()
    assert (out_dir / "candidates.csv").exists()
    assert (out_dir / "pulse_payloads.jsonl").exists()
    assert (out_dir / "hardware_results.jsonl").exists()
    assert (out_dir / "hardware_summary.json").exists()

    summary = json.loads((out_dir / "hardware_summary.json").read_text())
    assert summary["candidate_count"] == 7
    assert summary["query_count"] == 7
    assert summary["shot_count"] == 7 * 128
    assert summary["total_shots"] == 7 * 128
    assert summary["best_candidate_id"]
    assert summary["real_hardware"] is False
