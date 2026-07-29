from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from qcontrol.artifacts import ArtifactConflict, ArtifactStore
from qcontrol.config import DeviceConfig, ExperimentConfig, SearchConfig, SystemConfig
from qcontrol.experiments import (
    SweepStatus,
    TrialResult,
    generate_paired_trials,
    run_sweep,
    validate_sweep,
)


def _config(
    method: str,
    dimension: int,
    *,
    seed: int = 3,
    kind: str = "development",
) -> ExperimentConfig:
    return ExperimentConfig(
        run_kind=kind,
        system=SystemConfig("one_qubit", 3, 4.0),
        device=DeviceConfig(gap=0.02, shots=1_000, perturbation_seed=7),
        search=SearchConfig(method, dimension, 200 if kind == "development" else 2_000),
        trial_seed=seed,
    )


def test_paired_methods_share_device_but_not_observation_stream() -> None:
    specs = generate_paired_trials(
        [
            _config("model_hessian", 1),
            _config("random", 1),
            _config("oracle", 1),
        ]
    )

    assert len({spec.device_id for spec in specs}) == 1
    assert len({spec.observation_stream_id for spec in specs}) == len(specs)
    assert len({spec.trial_id for spec in specs}) == len(specs)


def test_trial_ids_bind_every_pairing_dimension() -> None:
    baseline = generate_paired_trials([_config("random", 1)])[0]
    variants = [
        _config("random", 2),
        replace(_config("random", 1), trial_seed=4),
        replace(
            _config("random", 1),
            device=DeviceConfig(gap=0.05, shots=1_000, perturbation_seed=7),
        ),
        replace(
            _config("random", 1),
            device=DeviceConfig(gap=0.02, shots=10_000, perturbation_seed=7),
        ),
        replace(
            _config("random", 1),
            device=DeviceConfig(gap=0.02, shots=1_000, perturbation_seed=8),
        ),
        replace(
            _config("random", 1),
            system=SystemConfig("one_qubit", 4, 4.0),
        ),
    ]
    assert all(
        generate_paired_trials([variant])[0].trial_id != baseline.trial_id
        for variant in variants
    )


def test_full_space_occurs_once_per_device_shot_seed_not_per_k() -> None:
    configs = []
    for dimension in (1, 2, 3):
        configs.extend(
            [
                _config("full", dimension),
                _config("model_hessian", dimension),
                _config("random", dimension),
            ]
        )

    specs = generate_paired_trials(configs)

    assert sum(spec.config.search.method == "full" for spec in specs) == 1
    full = next(spec for spec in specs if spec.config.search.method == "full")
    assert full.config.search.dimension == full.config.system.parameter_count


def test_development_and_production_cannot_mix() -> None:
    with pytest.raises(ValueError, match="run kinds"):
        generate_paired_trials(
            [_config("random", 1), _config("random", 1, kind="production")]
        )


def _result(spec, execution: int) -> TrialResult:
    return TrialResult(
        trial_id=spec.trial_id,
        device_id=spec.device_id,
        observation_stream_id=spec.observation_stream_id,
        config=spec.config.canonical_dict(),
        result={
            "schema_version": 1,
            "space": {
                "origin": [0.0] * 6,
                "basis": [[1.0], [0.0], [0.0], [0.0], [0.0], [0.0]],
                "lower_bounds": [-1.0],
                "upper_bounds": [1.0],
            },
            "best_pulse": [0.0] * 6,
            "best_observation": None,
            "certified": False,
            "evaluations": 2,
            "budget": spec.config.search.budget,
            "budget_exhausted": False,
            "stop_reason": "optimizer_stopped",
            "observations": [],
            "validation_attempts": [],
            "first_certified_query": None,
            "provisional_crossings": [],
            "validation_result": None,
        },
        ledger={
            "optimizer_queries": 2,
            "optimizer_shots": 2_000,
            "validation_queries": 0,
            "validation_shots": 0,
            "total_queries": 2,
            "total_shots": 2_000,
        },
        execution=execution,
    )


def test_interrupted_sweep_resumes_without_duplicate_ledgers(tmp_path) -> None:
    specs = generate_paired_trials(
        [
            _config("model_hessian", 1, seed=seed)
            for seed in range(5)
        ]
    )
    store = ArtifactStore(tmp_path)
    calls: list[str] = []

    def execute(spec) -> TrialResult:
        calls.append(spec.trial_id)
        return _result(spec, len(calls))

    first = run_sweep(specs, store, executor=execute, stop_after=2)
    before = store.trial_hashes()
    assert first == SweepStatus(expected=5, completed=2, pending=3)

    calls.clear()
    resumed = run_sweep(specs, store, executor=execute)

    assert resumed == SweepStatus(expected=5, completed=5, pending=0)
    assert len(calls) == 3
    assert {
        trial_id: store.trial_hashes()[trial_id] for trial_id in before
    } == before
    ledgers = [
        json.loads(path.read_text())["ledger"]
        for path in sorted((tmp_path / "trials").glob("*.json"))
    ]
    assert sum(ledger["optimizer_queries"] for ledger in ledgers) == 10


def test_resume_fails_closed_on_plan_or_claim_mismatch(tmp_path) -> None:
    specs = generate_paired_trials([_config("random", 1)])
    store = ArtifactStore(tmp_path)
    run_sweep(specs, store, executor=lambda spec: _result(spec, 1))

    changed = generate_paired_trials([_config("random", 2)])
    with pytest.raises(ArtifactConflict, match="plan"):
        run_sweep(changed, store, executor=lambda spec: _result(spec, 2))


def test_validate_checks_coverage_hashes_ledgers_and_unexpected_files(tmp_path) -> None:
    specs = generate_paired_trials([_config("random", 1)])
    store = ArtifactStore(tmp_path)
    run_sweep(specs, store, executor=lambda spec: _result(spec, 1))

    report = validate_sweep(specs, store)
    assert report.valid
    assert report.status == SweepStatus(expected=1, completed=1, pending=0)

    (tmp_path / "surprise.txt").write_text("unexpected")
    report = validate_sweep(specs, store)
    assert not report.valid
    assert any("unexpected" in error for error in report.errors)


def test_partial_production_validation_fails_but_status_succeeds(tmp_path) -> None:
    specs = generate_paired_trials(
        [_config("random", 1, seed=1, kind="production"), _config("random", 1, seed=2, kind="production")]
    )
    store = ArtifactStore(tmp_path)
    run_sweep(specs, store, executor=lambda spec: _result(spec, 1), stop_after=1)

    report = validate_sweep(specs, store)
    assert not report.valid
    assert report.status.pending == 1


def test_trial_artifact_contains_no_private_truth(tmp_path) -> None:
    spec = generate_paired_trials([_config("random", 1)])[0]
    store = ArtifactStore(tmp_path)
    run_sweep([spec], store, executor=lambda item: _result(item, 1))

    artifact = (tmp_path / "trials" / f"{spec.trial_id}.json").read_text()
    assert "truth" not in artifact.lower()
    assert "hamiltonian" not in artifact.lower()


def test_cli_exposes_strict_modes_and_status_smoke(tmp_path) -> None:
    root = Path(__file__).parents[1]
    help_result = subprocess.run(
        [sys.executable, "run.py", "--help"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0
    assert all(
        command in help_result.stdout
        for command in ("geometry", "trial", "sweep", "validate", "status")
    )

    status_result = subprocess.run(
        [sys.executable, "run.py", "status", "--output", str(tmp_path)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert status_result.returncode == 0
    assert json.loads(status_result.stdout)["completed"] == 0

    invalid = subprocess.run(
        [sys.executable, "run.py", "sweep", "--kind", "debug", "--output", str(tmp_path)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode != 0
