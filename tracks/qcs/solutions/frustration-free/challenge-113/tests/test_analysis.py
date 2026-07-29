from __future__ import annotations

import pytest

from qcontrol.analysis import (
    AnalysisError,
    aggregate_run,
    analyze_trials,
    first_certified_query,
    pair_trials,
    paired_bootstrap_ci,
    success_probability,
)
from qcontrol.artifacts import ArtifactStore
from qcontrol.config import DeviceConfig, ExperimentConfig, SearchConfig, SystemConfig
from qcontrol.experiments import TrialResult, generate_paired_trials, run_sweep


def _config(
    method: str,
    *,
    seed: int,
    gap: float = 0.02,
    perturbation_seed: int = 7,
    shots: int | None = 1_000,
    kind: str = "development",
) -> ExperimentConfig:
    return ExperimentConfig(
        run_kind=kind,
        system=SystemConfig("one_qubit", 3, 4.0),
        device=DeviceConfig(gap, shots, perturbation_seed),
        search=SearchConfig(method, 2, 200 if kind == "development" else 2_000),
        trial_seed=seed,
    )


def _observation(
    attempt_index: int,
    query: int,
    estimate: float,
    *,
    validation: bool,
    shots: int,
) -> dict[str, object]:
    return {
        "attempt_index": attempt_index,
        "estimate": estimate,
        "observation_seed": attempt_index,
        "optimizer_query_index": query,
        "seed_digest": f"{attempt_index:064x}",
        "shots": shots,
        "validation": validation,
    }


def _trial(
    config: ExperimentConfig,
    *,
    certified_query: int | None,
    provisional_query: int | None = None,
) -> TrialResult:
    spec = generate_paired_trials([config])[0]
    evaluations = certified_query if certified_query is not None else config.search.budget
    optimizer = [
        _observation(index, index, 0.5 + index / 10_000, validation=False, shots=1_000)
        for index in range(1, evaluations + 1)
    ]
    attempts = [
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
            "validation": False,
        }
        for item in optimizer
    ]
    validation_attempts: list[dict[str, object]] = []
    provisional_crossings: list[int] = []
    validation_result = None
    next_attempt = evaluations
    if provisional_query is not None:
        next_attempt += 1
        provisional = _observation(
            next_attempt,
            provisional_query,
            0.99,
            validation=True,
            shots=100_000,
        )
        attempts.append(
            {
                "attempt_index": next_attempt,
                "charged_shots": 100_000,
                "error_category": None,
                "estimate": provisional["estimate"],
                "observation_seed": provisional["observation_seed"],
                "optimizer_query_index": provisional_query,
                "requested_shots": 100_000,
                "seed_digest": provisional["seed_digest"],
                "status": "succeeded",
                "validation": True,
            }
        )
        validation_attempts.append(
            {
                "best_observation": optimizer[provisional_query - 1],
                "certified": False,
                "device_attempt_index": next_attempt,
                "failure_category": None,
                "optimizer_query_index": provisional_query,
                "pulse": [0.0] * 6,
                "status": "rejected",
                "validation_observation": provisional,
            }
        )
        provisional_crossings.append(provisional_query)
        validation_result = provisional
    if certified_query is not None:
        next_attempt += 1
        certified = _observation(
            next_attempt,
            certified_query,
            1.0,
            validation=True,
            shots=100_000,
        )
        attempts.append(
            {
                "attempt_index": next_attempt,
                "charged_shots": 100_000,
                "error_category": None,
                "estimate": certified["estimate"],
                "observation_seed": certified["observation_seed"],
                "optimizer_query_index": certified_query,
                "requested_shots": 100_000,
                "seed_digest": certified["seed_digest"],
                "status": "succeeded",
                "validation": True,
            }
        )
        validation_attempts.append(
            {
                "best_observation": optimizer[certified_query - 1],
                "certified": True,
                "device_attempt_index": next_attempt,
                "failure_category": None,
                "optimizer_query_index": certified_query,
                "pulse": [0.0] * 6,
                "status": "certified",
                "validation_observation": certified,
            }
        )
        provisional_crossings.append(certified_query)
        validation_result = certified
    validation_shots = 100_000 * len(validation_attempts)
    ledger = {
        "optimizer_queries": evaluations,
        "optimizer_shots": evaluations * 1_000,
        "validation_queries": len(validation_attempts),
        "validation_shots": validation_shots,
        "total_queries": evaluations + len(validation_attempts),
        "total_shots": evaluations * 1_000 + validation_shots,
    }
    result_payload = {
        "best_observation": optimizer[-1],
        "best_pulse": [0.0] * 6,
        "budget": config.search.budget,
        "budget_exhausted": certified_query is None,
        "certified": certified_query is not None,
        "evaluations": evaluations,
        "first_certified_query": certified_query,
        "observations": optimizer,
        "provisional_crossings": provisional_crossings,
        "schema_version": 3 if config.run_kind == "production" else 2,
        "search": {
            "basis_sha256": "1" * 64,
            "dimension": config.search.dimension,
            "method": config.search.method,
            "origin_sha256": "2" * 64,
        },
        "stop_reason": "certified" if certified_query is not None else "budget",
        "validation_attempts": validation_attempts,
        "validation_result": validation_result,
    }
    if config.run_kind == "production":
        result_payload["derived_metrics"] = {
            "exact_infidelity": {
                "best_successful_audited_infidelity": 0.5,
                "cumulative_best_by_optimizer_query": [0.5] * evaluations,
                "initial_infidelity": 0.5,
            },
            "geometry": {
                "model_effective_ranks": [1, 1, 1],
                "model_top_subspace_sha256": "3" * 64,
                "principal_angles_radians": [0.0] * config.search.dimension,
                "rank_thresholds": [1e-6, 1e-8, 1e-10],
                "signed_leading_eigenvalue_gaps": [0.0]
                * config.search.dimension,
                "truth_effective_ranks": [1, 1, 1],
                "truth_top_subspace_sha256": "4" * 64,
            },
            "restricted_noiseless_optimization": {
                "attained_infidelity_upper_bound": 0.5,
                "attained_infidelity_source": "restricted_solver",
                "best_successful_audited_exact_infidelity": 0.5,
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
    return TrialResult(
        trial_id=spec.trial_id,
        device_id=spec.device_id,
        observation_stream_id=spec.observation_stream_id,
        config=config.canonical_dict(),
        result=result_payload,
        ledger=ledger,
        attempts=attempts,
    )


def test_first_certified_query_ignores_provisional_crossing() -> None:
    trial = _trial(
        _config("model_hessian", seed=1),
        provisional_query=4,
        certified_query=9,
    )

    assert first_certified_query(trial) == 9


def test_success_probability_keeps_budget_exhaustion_in_denominator() -> None:
    trials = [
        _trial(_config("model_hessian", seed=1), certified_query=7),
        _trial(_config("model_hessian", seed=2), certified_query=None),
        _trial(_config("model_hessian", seed=3), certified_query=12),
    ]

    estimate = success_probability(trials)

    assert estimate.value == pytest.approx(2 / 3)
    assert estimate.numerator == 2
    assert estimate.denominator == 3


def test_hand_computable_censoring_shots_and_conditional_queries() -> None:
    trials = [
        _trial(_config("model_hessian", seed=1), certified_query=4),
        _trial(_config("model_hessian", seed=2), certified_query=None),
        _trial(_config("model_hessian", seed=3), certified_query=9),
    ]

    summary = analyze_trials(trials)

    assert summary.trial_count == 3
    assert summary.success_probability.value == pytest.approx(2 / 3)
    assert summary.conditional_first_certified_queries == (4, 9)
    assert summary.censored_first_certified_queries == (4, 200, 9)
    assert summary.total_shots == 413_000
    assert summary.median_best_exact_infidelity_trajectories == {}
    assert (
        len(summary.median_best_observed_infidelity_trajectories["model_hessian"])
        == 200
    )


def test_pairing_requires_exact_device_orientation_gap_shots_and_seed() -> None:
    model = _trial(_config("model_hessian", seed=1), certified_query=4)
    random = _trial(_config("random", seed=1), certified_query=6)
    pairs = pair_trials([model, random])
    assert [(left.trial_id, right.trial_id) for left, right in pairs["random"]] == [
        (model.trial_id, random.trial_id)
    ]

    mismatched = _trial(
        _config("random", seed=1, perturbation_seed=8),
        certified_query=6,
    )
    with pytest.raises(AnalysisError, match="pair"):
        pair_trials([model, mismatched])


def test_seeded_paired_bootstrap_is_deterministic_and_hand_computable() -> None:
    differences = (1.0, 1.0, 1.0)

    first = paired_bootstrap_ci(differences, seed=17, samples=200)
    second = paired_bootstrap_ci(differences, seed=17, samples=200)

    assert first == second
    assert first.low == first.high == first.estimate == 1.0


def test_strict_noncoercive_and_finite_validation() -> None:
    trial = _trial(_config("model_hessian", seed=1), certified_query=4)
    malformed = trial.canonical_dict()
    malformed["result"]["certified"] = 1
    with pytest.raises(AnalysisError, match="invalid trial"):
        analyze_trials([malformed])
    with pytest.raises(AnalysisError, match="finite"):
        paired_bootstrap_ci([float("nan")], seed=1)


def test_production_aggregation_rejects_missing_and_malformed_coverage(
    tmp_path,
) -> None:
    configs = [
        _config("model_hessian", seed=1, kind="production"),
        _config("random", seed=1, kind="production"),
    ]
    specs = generate_paired_trials(configs)
    store = ArtifactStore(tmp_path)
    run_sweep(
        specs,
        store,
        executor=lambda spec: _trial(spec.config, certified_query=4),
        stop_after=1,
    )

    with pytest.raises(AnalysisError, match="coverage"):
        aggregate_run(store)

    pending = next(spec for spec in specs if spec.trial_id not in store.completed_trial_ids())
    store.publish_trial(pending.trial_id, {"schema_version": 2})
    with pytest.raises(AnalysisError, match="invalid|coverage"):
        aggregate_run(store)


def test_aggregate_run_never_drops_failures(tmp_path) -> None:
    configs = [
        _config("model_hessian", seed=1),
        _config("model_hessian", seed=2),
        _config("model_hessian", seed=3),
    ]
    results = {
        config.trial_seed: _trial(
            config,
            certified_query={1: 4, 2: None, 3: 9}[config.trial_seed],
        )
        for config in configs
    }
    specs = generate_paired_trials(configs)
    store = ArtifactStore(tmp_path)
    run_sweep(specs, store, executor=lambda spec: results[spec.config.trial_seed])

    summary = aggregate_run(store)

    assert summary.trial_count == 3
    assert summary.failure_count == 1
    assert summary.success_probability.denominator == 3
