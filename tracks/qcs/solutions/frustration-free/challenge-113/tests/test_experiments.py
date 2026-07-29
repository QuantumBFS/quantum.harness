from __future__ import annotations

from dataclasses import replace
import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import qcontrol.artifacts as artifacts_module
import qcontrol.experiments as experiments_module
from qcontrol.artifacts import ArtifactConflict, ArtifactStore
from qcontrol.closed_loop import make_model_hessian_space
from qcontrol.config import DeviceConfig, ExperimentConfig, SearchConfig, SystemConfig
from qcontrol.device import Observation
from qcontrol.experiments import (
    SweepStatus,
    TrialResult,
    TrialSpec,
    default_sweep_configs,
    generate_paired_trials,
    run_sweep,
    run_trial,
    validate_sweep,
)
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system, perturb_system


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


@pytest.mark.parametrize("identity", ("", "../trial", "trial/path", "UPPER", "a b"))
def test_trial_spec_rejects_unsafe_identity_tokens(identity) -> None:
    config = _config("random", 1)
    with pytest.raises(ValueError, match="token"):
        TrialSpec(identity, "device-1", "stream-1", config)
    with pytest.raises(ValueError, match="token"):
        TrialSpec("trial-1", identity, "stream-1", config)
    with pytest.raises(ValueError, match="token"):
        TrialSpec("trial-1", "device-1", identity, config)


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
    derived = {
        "exact_infidelity": {
            "best_successful_audited_infidelity": None,
            "cumulative_best_by_optimizer_query": [0.5, 0.5],
            "initial_infidelity": 0.5,
        },
        "geometry": {
            "model_effective_ranks": [1, 1, 1],
            "model_top_subspace_sha256": "3" * 64,
            "principal_angles_radians": [0.0] * spec.config.search.dimension,
            "rank_thresholds": [1e-6, 1e-8, 1e-10],
            "signed_leading_eigenvalue_gaps": [0.0]
            * spec.config.search.dimension,
            "truth_effective_ranks": [1, 1, 1],
            "truth_top_subspace_sha256": "4" * 64,
        },
        "restricted_noiseless_optimization": {
            "attained_infidelity_upper_bound": 0.5,
            "attained_infidelity_source": "restricted_solver",
            "best_successful_audited_exact_infidelity": None,
            "cached_solver_attained_infidelity_upper_bound": 0.5,
            "cached_solver_starting_infidelity_upper_bound": 0.5,
            "certified": True,
            "consistency_tolerance": 1e-10,
            "gradient_tolerance": 1e-9,
            "max_evaluations": 1_000,
            "max_iterations": 100,
            "nfev": 1,
            "nit": 0,
            "solver": "L-BFGS-B",
            "solver_message_code": "convergence",
            "solver_output_finite": True,
            "solver_status": 0,
            "solver_success": True,
            "initial_exact_infidelity": 0.5,
            "termination": "converged",
        },
    }
    result_payload = {
        "schema_version": 3 if spec.config.run_kind == "production" else 2,
        "search": {
            "basis_sha256": "1" * 64,
            "dimension": spec.config.search.dimension,
            "method": spec.config.search.method,
            "origin_sha256": "2" * 64,
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
    }
    if spec.config.run_kind == "production":
        result_payload["derived_metrics"] = derived
    return TrialResult(
        trial_id=spec.trial_id,
        device_id=spec.device_id,
        observation_stream_id=spec.observation_stream_id,
        config=spec.config.canonical_dict(),
        result=result_payload,
        ledger={
            "optimizer_queries": 2,
            "optimizer_shots": 2_000,
            "validation_queries": 0,
            "validation_shots": 0,
            "total_queries": 2,
            "total_shots": 2_000,
        },
        attempts=(
            {
                "attempt_index": index,
                "charged_shots": 1_000,
                "error_category": "sampling_failure",
                "estimate": None,
                "observation_seed": index,
                "optimizer_query_index": index,
                "requested_shots": 1_000,
                "seed_digest": f"{index:064x}",
                "status": "failed",
                "validation": False,
            }
            for index in (1, 2)
        ),
        execution=execution,
    )


def _result_with_two_validations(spec) -> TrialResult:
    def observation(
        attempt_index: int,
        optimizer_query_index: int,
        estimate: float,
        *,
        validation: bool,
        shots: int,
    ) -> dict[str, object]:
        return {
            "attempt_index": attempt_index,
            "estimate": estimate,
            "observation_seed": attempt_index,
            "optimizer_query_index": optimizer_query_index,
            "seed_digest": f"{attempt_index:064x}",
            "shots": shots,
            "validation": validation,
        }

    optimizer_one = observation(1, 1, 0.9991, validation=False, shots=1_000)
    validation_one = observation(2, 1, 0.998, validation=True, shots=100_000)
    optimizer_two = observation(3, 2, 0.9992, validation=False, shots=1_000)
    validation_two = observation(4, 2, 1.0, validation=True, shots=100_000)
    attempts = tuple(
        {
            "attempt_index": item["attempt_index"],
            "charged_shots": item["shots"],
            "error_category": None,
            "estimate": item["estimate"],
            "observation_seed": item["observation_seed"],
            "optimizer_query_index": item["optimizer_query_index"],
            "requested_shots": item["shots"],
            "seed_digest": item["seed_digest"],
            "status": "succeeded",
            "validation": item["validation"],
        }
        for item in (
            optimizer_one,
            validation_one,
            optimizer_two,
            validation_two,
        )
    )
    pulse = [0.0] * 6
    validation_attempts = [
        {
            "best_observation": optimizer_one,
            "certified": False,
            "device_attempt_index": 2,
            "failure_category": None,
            "optimizer_query_index": 1,
            "pulse": pulse,
            "status": "rejected",
            "validation_observation": validation_one,
        },
        {
            "best_observation": optimizer_two,
            "certified": True,
            "device_attempt_index": 4,
            "failure_category": None,
            "optimizer_query_index": 2,
            "pulse": pulse,
            "status": "certified",
            "validation_observation": validation_two,
        },
    ]
    return TrialResult(
        trial_id=spec.trial_id,
        device_id=spec.device_id,
        observation_stream_id=spec.observation_stream_id,
        config=spec.config.canonical_dict(),
        result={
            "best_observation": optimizer_two,
            "best_pulse": pulse,
            "budget": 200,
            "budget_exhausted": False,
            "certified": True,
            "evaluations": 2,
            "first_certified_query": 2,
            "observations": [optimizer_one, optimizer_two],
            "provisional_crossings": [1, 2],
            "schema_version": 2,
            "search": {
                "basis_sha256": "1" * 64,
                "dimension": 1,
                "method": "random",
                "origin_sha256": "2" * 64,
            },
            "stop_reason": "certified",
            "validation_attempts": validation_attempts,
            "validation_result": validation_two,
        },
        ledger={
            "optimizer_queries": 2,
            "optimizer_shots": 2_000,
            "validation_queries": 2,
            "validation_shots": 200_000,
            "total_queries": 4,
            "total_shots": 202_000,
        },
        attempts=attempts,
        execution=1,
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


def test_crash_after_trial_publish_adopts_without_rerunning_physics(
    tmp_path,
    monkeypatch,
) -> None:
    spec = generate_paired_trials([_config("random", 1)])[0]
    store = ArtifactStore(tmp_path)
    calls = 0
    real_update = store._update_index_locked

    def execute(item) -> TrialResult:
        nonlocal calls
        calls += 1
        return _result(item, calls)

    def crash_before_index(*_args, **_kwargs) -> None:
        raise KeyboardInterrupt()

    monkeypatch.setattr(store, "_update_index_locked", crash_before_index)
    with pytest.raises(KeyboardInterrupt):
        run_sweep([spec], store, executor=execute)
    assert calls == 1
    assert (tmp_path / "trials" / f"{spec.trial_id}.json").is_file()
    assert spec.trial_id not in store.trial_hashes()

    monkeypatch.setattr(store, "_update_index_locked", real_update)
    status = run_sweep([spec], store, executor=execute)

    assert status == SweepStatus(expected=1, completed=1, pending=0)
    assert calls == 1
    assert spec.trial_id in store.trial_hashes()


@pytest.mark.parametrize(
    ("variant", "message"),
    (
        ("whitespace", "noncanonical"),
        ("alternate-number", "noncanonical"),
        ("bom", "noncanonical"),
        ("trailing", "noncanonical"),
        ("duplicate-known", "duplicate"),
        ("duplicate-private", "duplicate"),
    ),
)
def test_orphan_adoption_rejects_noncanonical_or_duplicate_json(
    tmp_path,
    variant,
    message,
) -> None:
    spec = generate_paired_trials([_config("random", 1)])[0]
    store = ArtifactStore(tmp_path)
    run_sweep([spec], store, executor=lambda item: _result(item, 1), stop_after=0)
    payload = _result(spec, 1).canonical_dict()
    canonical = artifacts_module.canonical_json_bytes(payload)
    if variant == "whitespace":
        raw = canonical.replace(b'{"attempts"', b'{ "attempts"', 1)
    elif variant == "alternate-number":
        raw = canonical.replace(b'"charged_shots":1000', b'"charged_shots":1e3', 1)
    elif variant == "bom":
        raw = b"\xef\xbb\xbf" + canonical
    elif variant == "trailing":
        raw = canonical + b"trailing"
    elif variant == "duplicate-known":
        raw = canonical[:-2] + (
            f',"trial_id":"{spec.trial_id}"'.encode("ascii")
        ) + b"}\n"
    else:
        raw = (
            b'{"private_basis":[1],"private_basis":[2],'
            + canonical[1:]
        )
    trial_path = tmp_path / "trials" / f"{spec.trial_id}.json"
    trial_path.parent.mkdir(exist_ok=True)
    trial_path.write_bytes(raw)
    calls = 0

    def execute(item) -> TrialResult:
        nonlocal calls
        calls += 1
        return _result(item, calls)

    with pytest.raises(ArtifactConflict, match=message):
        run_sweep([spec], store, executor=execute)

    assert calls == 0
    assert trial_path.read_bytes() == raw
    assert spec.trial_id not in store.trial_hashes()


def test_source_change_during_trial_aborts_before_publication(
    tmp_path,
    monkeypatch,
) -> None:
    spec = generate_paired_trials([_config("random", 1)])[0]
    store = ArtifactStore(tmp_path)
    calls = 0
    real_collect = artifacts_module._collect_provenance
    collections = 0

    def changing_provenance(payload):
        nonlocal collections
        collections += 1
        provenance = real_collect(payload)
        if collections > 1:
            provenance["source_hashes"] = {
                **provenance["source_hashes"],
                "src/qcontrol/changed.py": "0" * 64,
            }
        return provenance

    monkeypatch.setattr(
        artifacts_module,
        "_collect_provenance",
        changing_provenance,
    )

    def execute(item) -> TrialResult:
        nonlocal calls
        calls += 1
        return _result(item, calls)

    with pytest.raises(ArtifactConflict, match="provenance"):
        run_sweep([spec], store, executor=execute)

    assert calls == 1
    assert not (tmp_path / "trials" / f"{spec.trial_id}.json").exists()


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


@pytest.mark.parametrize("method", ("model_hessian", "random", "oracle"))
def test_trial_artifact_structurally_excludes_numeric_search_bases(
    tmp_path,
    method,
) -> None:
    spec = generate_paired_trials([_config(method, 1)])[0]
    store = ArtifactStore(tmp_path)
    run_sweep([spec], store, executor=lambda item: _result(item, 1))
    payload = json.loads(
        (tmp_path / "trials" / f"{spec.trial_id}.json").read_text()
    )

    keys = set(_walk_keys(payload))
    assert "basis" not in keys
    assert "origin" not in keys
    assert "drift_direction" not in keys
    assert "control_gain_deltas" not in keys
    assert "unmodeled_direction" not in keys
    assert payload["result"]["search"] == {
        "basis_sha256": "1" * 64,
        "dimension": 1,
        "method": method,
        "origin_sha256": "2" * 64,
    }


@pytest.mark.integration
def test_real_trial_uses_public_search_identity_without_numeric_basis(
    tmp_path,
    monkeypatch,
) -> None:
    config = ExperimentConfig(
        run_kind="development",
        system=SystemConfig("one_qubit", 6, 4.0),
        device=DeviceConfig(gap=0.0, shots=None, perturbation_seed=5),
        search=SearchConfig("random", 3, 200),
        trial_seed=5,
    )

    geometry_calls = 0
    restricted_calls = 0
    real_geometry = experiments_module.compute_geometry_diagnostics
    real_restricted = experiments_module.optimize_restricted_noiseless_upper_bound

    def counted_geometry(*args, **kwargs):
        nonlocal geometry_calls
        geometry_calls += 1
        return real_geometry(*args, **kwargs)

    def counted_restricted(*args, **kwargs):
        nonlocal restricted_calls
        restricted_calls += 1
        return real_restricted(*args, **kwargs)

    experiments_module._DERIVED_STATIC_CACHE.clear()
    monkeypatch.setattr(
        experiments_module,
        "compute_geometry_diagnostics",
        counted_geometry,
    )
    monkeypatch.setattr(
        experiments_module,
        "optimize_restricted_noiseless_upper_bound",
        counted_restricted,
    )
    result = run_trial(config, ArtifactStore(tmp_path))
    run_trial(config, ArtifactStore(tmp_path / "replay"))
    payload = result.canonical_dict()

    assert geometry_calls == restricted_calls == 1

    assert "space" not in payload["result"]
    assert "basis" not in set(_walk_keys(payload))
    assert payload["result"]["search"]["method"] == "random"
    assert len(payload["result"]["search"]["basis_sha256"]) == 64
    assert len(payload["attempts"]) == payload["ledger"]["total_queries"]
    assert payload["schema_version"] == 3
    assert payload["result"]["schema_version"] == 3

    derived = payload["result"]["derived_metrics"]
    exact = derived["exact_infidelity"]
    trajectory = exact["cumulative_best_by_optimizer_query"]
    assert len(trajectory) == payload["ledger"]["optimizer_queries"]
    assert all(np.isfinite([exact["initial_infidelity"], *trajectory]))
    assert all(current <= previous for previous, current in zip(trajectory, trajectory[1:]))

    restricted = derived["restricted_noiseless_optimization"]
    assert restricted["attained_infidelity_upper_bound"] <= min(
        exact["initial_infidelity"],
        *trajectory,
    ) + restricted["consistency_tolerance"]
    assert restricted["max_iterations"] > 0
    assert restricted["gradient_tolerance"] > 0.0

    geometry = derived["geometry"]
    assert geometry["rank_thresholds"] == [1e-06, 1e-08, 1e-10]
    assert geometry["model_effective_ranks"] == geometry["truth_effective_ranks"]
    assert np.max(np.abs(geometry["signed_leading_eigenvalue_gaps"])) < 1e-10
    assert np.max(np.abs(geometry["principal_angles_radians"])) < 1e-7
    assert all(np.isfinite(value) for value in geometry["principal_angles_radians"])

    private_keys = {
        "basis",
        "origin",
        "truth",
        "hamiltonian",
        "drift_direction",
        "control_gain_deltas",
        "unmodeled_direction",
        "pulse_history",
        "pulses",
    }
    assert not (private_keys & set(_walk_keys(payload)))

    before = dict(payload["ledger"])
    TrialResult.from_canonical_dict(payload)
    assert payload["ledger"] == before


def test_derived_caches_follow_scientific_dependencies(monkeypatch) -> None:
    base = _config("model_hessian", 1, seed=3)
    shot_variant = replace(
        base,
        device=replace(base.device, shots=10_000),
    )
    k_variant = replace(
        shot_variant,
        search=replace(shot_variant.search, dimension=2),
    )
    device_variant = replace(
        base,
        device=replace(base.device, gap=0.05),
    )
    model = make_system(base.system)
    pulse_space = PulseSpace.from_system(model, base.system.segments)
    origin = np.zeros(pulse_space.parameter_count)
    basis = np.eye(pulse_space.parameter_count)
    spaces = {
        1: make_model_hessian_space(origin, basis, dimension=1),
        2: make_model_hessian_space(origin, basis, dimension=2),
    }
    observation = Observation(0.5, 1_000, 1, False, 1)
    audited = ((origin.copy(), observation),)
    counts = {"exact": 0, "geometry": 0, "restricted": 0}
    real_exact = experiments_module.cumulative_best_exact_infidelity
    real_geometry = experiments_module.compute_geometry_diagnostics
    real_restricted = experiments_module.optimize_restricted_noiseless_upper_bound

    def counted_exact(*args, **kwargs):
        counts["exact"] += 1
        return real_exact(*args, **kwargs)

    def counted_geometry(*args, **kwargs):
        counts["geometry"] += 1
        return real_geometry(*args, **kwargs)

    def counted_restricted(*args, **kwargs):
        counts["restricted"] += 1
        return real_restricted(*args, **kwargs)

    experiments_module._DERIVED_STATIC_CACHE.clear()
    monkeypatch.setattr(
        experiments_module,
        "cumulative_best_exact_infidelity",
        counted_exact,
    )
    monkeypatch.setattr(
        experiments_module,
        "compute_geometry_diagnostics",
        counted_geometry,
    )
    monkeypatch.setattr(
        experiments_module,
        "optimize_restricted_noiseless_upper_bound",
        counted_restricted,
    )
    base_restricted = None
    for config in (base, shot_variant, k_variant, device_variant):
        truth = perturb_system(
            model,
            config.device.gap,
            config.device.perturbation_seed,
        )
        _, _, restricted = experiments_module._cached_derived_metrics(
            config,
            model,
            truth,
            pulse_space,
            spaces[config.search.dimension],
            audited,
        )
        if config is base:
            base_restricted = restricted

    altered_audit = ((origin.copy() + 0.1, observation),)
    truth = perturb_system(model, base.device.gap, base.device.perturbation_seed)
    _, _, altered_restricted = experiments_module._cached_derived_metrics(
        base,
        model,
        truth,
        pulse_space,
        spaces[base.search.dimension],
        altered_audit,
    )

    assert counts == {"exact": 3, "geometry": 2, "restricted": 3}
    assert altered_restricted is base_restricted


def test_old_production_trial_schema_and_orphan_are_rejected(tmp_path) -> None:
    spec = generate_paired_trials([_config("random", 1, kind="production")])[0]
    legacy = _result(spec, 1).canonical_dict()
    legacy["schema_version"] = 2
    legacy["result"]["schema_version"] = 2
    del legacy["result"]["derived_metrics"]

    with pytest.raises(ValueError, match="production.*schema|schema.*production"):
        TrialResult.from_canonical_dict(legacy)

    store = ArtifactStore(tmp_path)
    trial_path = tmp_path / "trials" / f"{spec.trial_id}.json"
    trial_path.parent.mkdir()
    trial_path.write_bytes(artifacts_module.canonical_json_bytes(legacy))
    with pytest.raises(ArtifactConflict, match="invalid strict schema"):
        run_sweep([spec], store, executor=lambda _: _result(spec, 2))


def test_audited_candidate_bound_serializes_with_cached_solver_provenance() -> None:
    spec = generate_paired_trials([_config("random", 1, kind="production")])[0]
    payload = _result(spec, 1).canonical_dict()
    derived = payload["result"]["derived_metrics"]
    derived["exact_infidelity"].update(
        {
            "best_successful_audited_infidelity": 0.1,
            "cumulative_best_by_optimizer_query": [0.5, 0.1],
        }
    )
    derived["restricted_noiseless_optimization"].update(
        {
            "attained_infidelity_upper_bound": 0.1,
            "attained_infidelity_source": "audited_candidate",
            "best_successful_audited_exact_infidelity": 0.1,
            "cached_solver_attained_infidelity_upper_bound": 0.4,
        }
    )
    payload["attempts"][1].update(
        {
            "error_category": None,
            "estimate": 0.9,
            "status": "succeeded",
        }
    )
    payload["result"]["observations"] = [
        {
            "attempt_index": 2,
            "estimate": 0.9,
            "observation_seed": 2,
            "optimizer_query_index": 2,
            "seed_digest": f"{2:064x}",
            "shots": 1_000,
            "validation": False,
        }
    ]

    replayed = TrialResult.from_canonical_dict(payload)

    restricted = replayed.result["derived_metrics"][
        "restricted_noiseless_optimization"
    ]
    assert restricted["attained_infidelity_source"] == "audited_candidate"
    assert restricted["cached_solver_attained_infidelity_upper_bound"] == 0.4


@pytest.mark.parametrize(
    "mutation",
    (
        {
            "certified": False,
            "solver_success": False,
            "termination": "solver_failure",
        },
        {
            "certified": False,
            "solver_message_code": "numerical_failure",
            "solver_output_finite": True,
            "solver_status": 2,
            "solver_success": False,
            "termination": "numerical_failure",
        },
        {
            "certified": False,
            "nit": 0,
            "solver_message_code": "iteration_limit",
            "solver_status": 1,
            "solver_success": False,
            "termination": "iteration_limit",
        },
        {"certified": False, "termination": "solver_failure"},
        {
            "certified": False,
            "solver_message_code": "line_search_failure",
            "solver_status": 1,
            "solver_success": False,
            "termination": "line_search_failure",
        },
    ),
)
def test_restricted_termination_rejects_tampered_raw_facts(mutation) -> None:
    spec = generate_paired_trials([_config("random", 1, kind="production")])[0]
    payload = _result(spec, 1).canonical_dict()
    restricted = payload["result"]["derived_metrics"][
        "restricted_noiseless_optimization"
    ]
    restricted.update(mutation)
    with pytest.raises(ValueError, match="solver|termination|restricted"):
        TrialResult.from_canonical_dict(payload)


def test_production_matrix_has_exact_design_coverage() -> None:
    specs = generate_paired_trials(default_sweep_configs("production"))

    assert len(specs) == 9_500
    by_system = {
        name: [spec for spec in specs if spec.config.system.name == name]
        for name in ("one_qubit", "two_qubit")
    }
    assert len(by_system["two_qubit"]) == 5_700
    assert len(by_system["one_qubit"]) == 3_800

    for name, dimensions, shots in (
        ("two_qubit", {5, 10, 15, 20, 30, 80}, {None, 1_000, 10_000}),
        ("one_qubit", {1, 2, 3, 4, 6, 24}, {None, 1_000}),
    ):
        subset = by_system[name]
        assert {spec.config.device.gap for spec in subset} == {
            0.0,
            0.02,
            0.05,
            0.10,
            0.20,
        }
        assert {spec.config.device.shots for spec in subset} == shots
        assert {spec.config.trial_seed for spec in subset} == set(range(20))
        assert {
            spec.config.search.dimension
            for spec in subset
            if spec.config.search.method != "full"
        } == dimensions
        full = [spec for spec in subset if spec.config.search.method == "full"]
        assert len(full) == 5 * len(shots) * 20


@pytest.mark.parametrize("invalid", (True, 1.0, "1"))
def test_trial_result_rejects_coerced_ledger_integers(invalid) -> None:
    spec = generate_paired_trials([_config("random", 1)])[0]
    payload = _result(spec, 1).canonical_dict()
    payload["ledger"]["optimizer_queries"] = invalid

    with pytest.raises(ValueError, match="invalid trial-result"):
        TrialResult.from_canonical_dict(payload)


def test_trial_result_rejects_missing_extra_and_duplicate_attempts() -> None:
    spec = generate_paired_trials([_config("random", 1)])[0]
    canonical = _result(spec, 1).canonical_dict()
    mutations = []

    missing = copy.deepcopy(canonical)
    del missing["ledger"]["total_queries"]
    mutations.append(missing)

    extra = copy.deepcopy(canonical)
    extra["ledger"]["extra"] = 0
    mutations.append(extra)

    extra_result = copy.deepcopy(canonical)
    extra_result["result"]["private_basis"] = [[1.0]]
    mutations.append(extra_result)

    missing_attempt_field = copy.deepcopy(canonical)
    del missing_attempt_field["attempts"][0]["requested_shots"]
    mutations.append(missing_attempt_field)

    duplicate = copy.deepcopy(canonical)
    duplicate["attempts"][1]["attempt_index"] = 1
    mutations.append(duplicate)

    inconsistent = copy.deepcopy(canonical)
    inconsistent["attempts"][0]["validation"] = True
    mutations.append(inconsistent)

    wrong_requested = copy.deepcopy(canonical)
    wrong_requested["attempts"][0]["requested_shots"] = 999
    mutations.append(wrong_requested)

    false_success = copy.deepcopy(canonical)
    false_success["attempts"][0]["status"] = "succeeded"
    mutations.append(false_success)

    for payload in mutations:
        with pytest.raises(ValueError):
            TrialResult.from_canonical_dict(payload)


def test_trial_result_rejects_decreasing_validation_crossings() -> None:
    spec = generate_paired_trials([_config("random", 1)])[0]
    payload = _result_with_two_validations(spec).canonical_dict()
    payload["result"]["validation_attempts"].reverse()
    payload["result"]["provisional_crossings"] = [2, 1]

    with pytest.raises(ValueError, match="increasing"):
        TrialResult.from_canonical_dict(payload)


def test_trial_result_requires_certified_attempt_to_be_final() -> None:
    spec = generate_paired_trials([_config("random", 1)])[0]
    payload = _result_with_two_validations(spec).canonical_dict()
    first, second = payload["result"]["validation_attempts"]
    first["certified"] = True
    first["status"] = "certified"
    second["certified"] = False
    second["status"] = "rejected"
    payload["result"]["first_certified_query"] = 1

    with pytest.raises(ValueError, match="final"):
        TrialResult.from_canonical_dict(payload)
