from __future__ import annotations

import json

import numpy as np
import pytest

import qcontrol.analysis as analysis_module
from qcontrol.analysis import (
    AnalysisError,
    Summary,
    aggregate_run,
    analyze_trials,
    first_certified_query,
    pair_trials,
    paired_bootstrap_ci,
    success_probability,
)
from qcontrol.artifacts import ArtifactStore, canonical_json_bytes
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
    dimension: int = 2,
    system: str = "one_qubit",
    segments: int | None = None,
) -> ExperimentConfig:
    segment_count = segments if segments is not None else (
        3 if system == "one_qubit" else 10
    )
    return ExperimentConfig(
        run_kind=kind,
        system=SystemConfig(system, segment_count, 4.0),
        device=DeviceConfig(gap, shots, perturbation_seed),
        search=SearchConfig(
            method,
            dimension,
            200 if kind == "development" else 2_000,
        ),
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
    exact_values: tuple[float, ...] | None = None,
    attained_bound: float = 0.5,
    principal_angles: tuple[float, ...] | None = None,
    model_ranks: tuple[int, int, int] = (1, 1, 1),
    truth_ranks: tuple[int, int, int] = (1, 1, 1),
    signed_gaps: tuple[float, ...] | None = None,
) -> TrialResult:
    spec = generate_paired_trials([config])[0]
    evaluations = certified_query if certified_query is not None else config.search.budget
    optimizer_shots = 0 if config.device.shots is None else config.device.shots
    optimizer = [
        _observation(
            index,
            index,
            0.5 + index / 10_000,
            validation=False,
            shots=optimizer_shots,
        )
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
                "pulse": [0.0] * config.system.parameter_count,
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
                "pulse": [0.0] * config.system.parameter_count,
                "status": "certified",
                "validation_observation": certified,
            }
        )
        provisional_crossings.append(certified_query)
        validation_result = certified
    validation_shots = 100_000 * len(validation_attempts)
    ledger = {
        "optimizer_queries": evaluations,
        "optimizer_shots": evaluations * optimizer_shots,
        "validation_queries": len(validation_attempts),
        "validation_shots": validation_shots,
        "total_queries": evaluations + len(validation_attempts),
        "total_shots": evaluations * optimizer_shots + validation_shots,
    }
    result_payload = {
        "best_observation": optimizer[-1],
        "best_pulse": [0.0] * config.system.parameter_count,
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
        exact = (
            exact_values
            if exact_values is not None
            else (0.5,) * evaluations
        )
        if len(exact) != evaluations:
            raise ValueError("test exact trajectory must align with evaluations")
        angles = principal_angles or (0.0,) * config.search.dimension
        gaps = signed_gaps or (0.0,) * config.search.dimension
        best_audited = min(exact)
        final_attained = min(attained_bound, best_audited, 0.5)
        attained_source = (
            "restricted_solver"
            if final_attained == attained_bound
            else "audited_candidate"
        )
        result_payload["derived_metrics"] = {
            "exact_infidelity": {
                "best_successful_audited_infidelity": best_audited,
                "cumulative_best_by_optimizer_query": list(exact),
                "initial_infidelity": 0.5,
            },
            "geometry": {
                "model_effective_ranks": list(model_ranks),
                "model_top_subspace_sha256": "3" * 64,
                "principal_angles_radians": list(angles),
                "rank_thresholds": [1e-6, 1e-8, 1e-10],
                "signed_leading_eigenvalue_gaps": list(gaps),
                "truth_effective_ranks": list(truth_ranks),
                "truth_top_subspace_sha256": "4" * 64,
            },
            "restricted_noiseless_optimization": {
                "attained_infidelity_upper_bound": final_attained,
                "attained_infidelity_source": attained_source,
                "best_successful_audited_exact_infidelity": best_audited,
                "cached_solver_attained_infidelity_upper_bound": attained_bound,
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
    method = _method(summary, 0, "model_hessian")

    assert method.trial_count == 3
    assert method.success_probability.value == pytest.approx(2 / 3)
    assert method.conditional_first_certified_queries == (4, 9)
    assert method.censored_first_certified_queries == (4, 9, 200)
    assert method.total_shots == 413_000
    assert method.exact_infidelity_trajectory is None
    assert len(method.median_best_observed_infidelity_trajectory) == 200


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
    method = _method(summary, 0, "model_hessian")

    assert method.trial_count == 3
    assert method.failure_count == 1
    assert method.success_probability.denominator == 3


def _method(summary, stratum_index: int, method: str):
    return next(
        item
        for item in summary.strata[stratum_index].methods
        if item.method == method
    )


def test_analysis_separates_system_dimension_gap_and_shot_strata() -> None:
    trials = [
        _trial(_config("model_hessian", seed=1), certified_query=4),
        _trial(
            _config("model_hessian", seed=1, dimension=1),
            certified_query=4,
        ),
        _trial(
            _config("model_hessian", seed=1, gap=0.05),
            certified_query=4,
        ),
        _trial(
            _config("model_hessian", seed=1, shots=None),
            certified_query=4,
        ),
        _trial(
            _config("model_hessian", seed=1, system="two_qubit"),
            certified_query=4,
        ),
    ]

    summary = analyze_trials(trials, bootstrap_samples=20)

    assert len(summary.strata) == 5
    identities = {
        (
            item.key.hilbert_dimension,
            item.key.search_dimension,
            item.key.gap,
            item.key.shots,
        )
        for item in summary.strata
    }
    assert identities == {
        (2, 1, 0.02, 1_000),
        (2, 2, 0.02, 1_000),
        (2, 2, 0.05, 1_000),
        (2, 2, 0.02, None),
        (4, 2, 0.02, 1_000),
    }


def test_full_comparator_is_reused_once_per_k_stratum() -> None:
    model_k1 = _trial(
        _config("model_hessian", seed=1, dimension=1),
        certified_query=4,
    )
    model_k2 = _trial(
        _config("model_hessian", seed=1, dimension=2),
        certified_query=4,
    )
    full = _trial(
        _config("full", seed=1, dimension=3),
        certified_query=6,
    )

    summary = analyze_trials(
        [model_k1, model_k2, full],
        bootstrap_seed=9,
        bootstrap_samples=30,
    )

    assert [item.key.search_dimension for item in summary.strata] == [1, 2]
    for stratum in summary.strata:
        full_method = next(item for item in stratum.methods if item.method == "full")
        effect = next(
            item for item in stratum.paired_differences if item.baseline == "full"
        )
        assert full_method.trial_count == 1
        assert effect.pair_count == effect.cluster_count == 1


def test_method_success_intervals_and_paired_effect_keep_failures() -> None:
    records = []
    for seed, model_query, random_query in (
        (1, 4, 6),
        (2, None, None),
        (3, 9, None),
    ):
        records.extend(
            (
                _trial(
                    _config("model_hessian", seed=seed),
                    certified_query=model_query,
                ),
                _trial(
                    _config("random", seed=seed),
                    certified_query=random_query,
                ),
            )
        )

    summary = analyze_trials(records, bootstrap_seed=4, bootstrap_samples=100)
    model = _method(summary, 0, "model_hessian")
    random = _method(summary, 0, "random")
    effect = next(
        item for item in summary.strata[0].paired_differences
        if item.baseline == "random"
    )

    assert model.success_probability.numerator == 2
    assert model.success_probability.denominator == 3
    assert model.success_probability.low < 2 / 3 < model.success_probability.high
    assert random.success_probability.numerator == 1
    assert random.success_probability.denominator == 3
    assert effect.success_probability_difference.estimate == pytest.approx(1 / 3)
    assert effect.pair_count == effect.cluster_count == 3


def test_schema_v3_exact_bands_and_geometry_are_aggregated() -> None:
    first = _trial(
        _config("model_hessian", seed=1, kind="production"),
        certified_query=2,
        exact_values=(0.5, 0.3),
        attained_bound=0.2,
        principal_angles=(0.1, 0.2),
        model_ranks=(1, 2, 2),
        truth_ranks=(2, 2, 3),
        signed_gaps=(0.4, -0.2),
    )
    second = _trial(
        _config("model_hessian", seed=2, kind="production"),
        certified_query=2,
        exact_values=(0.4, 0.2),
        attained_bound=0.4,
        principal_angles=(0.3, 0.4),
        model_ranks=(2, 2, 3),
        truth_ranks=(2, 3, 3),
        signed_gaps=(0.2, 0.0),
    )

    summary = analyze_trials(
        [first, second],
        bootstrap_seed=7,
        bootstrap_samples=40,
    )
    method = _method(summary, 0, "model_hessian")

    assert method.metric_availability.state == "available"
    assert method.exact_infidelity_trajectory.median[:2] == pytest.approx((0.45, 0.25))
    assert len(method.exact_infidelity_trajectory.low) == 2_000
    assert method.median_attained_infidelity_upper_bound == pytest.approx(0.2)
    assert method.median_principal_angles == pytest.approx((0.2, 0.3))
    assert method.median_model_effective_ranks == pytest.approx((1.5, 2.0, 2.5))
    assert method.median_truth_effective_ranks == pytest.approx((2.0, 2.5, 3.0))
    assert method.median_signed_eigenvalue_gaps == pytest.approx((0.3, -0.1))


def test_development_metrics_have_explicit_unavailability() -> None:
    summary = analyze_trials(
        [_trial(_config("model_hessian", seed=1), certified_query=4)],
        bootstrap_samples=20,
    )
    method = _method(summary, 0, "model_hessian")

    assert method.metric_availability.state == "unavailable"
    assert method.metric_availability.reason == "schema_v3_metrics_not_available"
    assert method.exact_infidelity_trajectory is None
    assert method.median_principal_angles is None


def test_missing_required_production_metrics_are_rejected() -> None:
    trial = _trial(
        _config("model_hessian", seed=1, kind="production"),
        certified_query=2,
    ).canonical_dict()
    del trial["result"]["derived_metrics"]

    with pytest.raises(AnalysisError, match="invalid trial|derived"):
        analyze_trials([trial], bootstrap_samples=20)


def test_summary_canonical_round_trip_and_strict_validation() -> None:
    summary = analyze_trials(
        [
            _trial(_config("model_hessian", seed=1), certified_query=4),
            _trial(
                _config("model_hessian", seed=1, dimension=1),
                certified_query=4,
            ),
        ],
        bootstrap_samples=20,
    )
    payload = summary.canonical_dict()

    assert payload["schema_version"] == 1
    assert Summary.from_canonical_dict(
        json.loads(json.dumps(payload, allow_nan=False))
    ) == summary
    malformed = json.loads(json.dumps(payload, allow_nan=False))
    malformed["strata"][0]["methods"][0]["trial_count"] = True
    with pytest.raises(AnalysisError, match="trial_count|integer"):
        Summary.from_canonical_dict(malformed)
    malformed = json.loads(json.dumps(payload, allow_nan=False))
    malformed["strata"].reverse()
    with pytest.raises(AnalysisError, match="sorted|canonical"):
        Summary.from_canonical_dict(malformed)


def test_chunked_bootstrap_is_chunk_size_independent() -> None:
    differences = (1.0, -1.0, 2.0, 0.5)

    one = paired_bootstrap_ci(
        differences,
        seed=17,
        samples=200,
        chunk_size=1,
    )
    many = paired_bootstrap_ci(
        differences,
        seed=17,
        samples=200,
        chunk_size=37,
    )

    assert one == many


def test_production_scale_bootstrap_never_allocates_full_sample_matrix(
    monkeypatch,
) -> None:
    requested_shapes: list[tuple[int, int]] = []

    class RecordingRng:
        def integers(self, low, high, *, size):
            requested_shapes.append(size)
            return np.zeros(size, dtype=np.int64)

    monkeypatch.setattr(
        analysis_module.np.random,
        "default_rng",
        lambda seed: RecordingRng(),
    )

    paired_bootstrap_ci(
        np.ones(9_500),
        seed=1,
        samples=257,
        chunk_size=16,
    )

    assert requested_shapes
    assert max(rows for rows, _ in requested_shapes) <= 16
    assert {columns for _, columns in requested_shapes} == {9_500}


@pytest.mark.parametrize(
    ("system", "segments", "full_dimension", "target_dimension"),
    (
        ("one_qubit", 12, 24, 3),
        ("two_qubit", 20, 80, 4),
    ),
)
def test_full_schema_v3_geometry_is_sliced_to_target_k_and_round_trips(
    system,
    segments,
    full_dimension,
    target_dimension,
) -> None:
    model = _trial(
        _config(
            "model_hessian",
            seed=1,
            kind="production",
            system=system,
            segments=segments,
            dimension=target_dimension,
        ),
        certified_query=2,
        principal_angles=tuple(0.01 * index for index in range(target_dimension)),
        signed_gaps=tuple(-0.02 * index for index in range(target_dimension)),
    )
    full_angles = tuple(0.01 * index for index in range(full_dimension))
    full_gaps = tuple(-0.02 * index for index in range(full_dimension))
    full = _trial(
        _config(
            "full",
            seed=1,
            kind="production",
            system=system,
            segments=segments,
            dimension=full_dimension,
        ),
        certified_query=2,
        principal_angles=full_angles,
        signed_gaps=full_gaps,
        model_ranks=(7, 8, 9),
        truth_ranks=(6, 7, 8),
    )

    summary = analyze_trials([model, full], bootstrap_samples=20)
    full_method = _method(summary, 0, "full")

    assert full_method.median_principal_angles == full_angles[:target_dimension]
    assert full_method.median_signed_eigenvalue_gaps == full_gaps[:target_dimension]
    assert full_method.median_model_effective_ranks == (7.0, 8.0, 9.0)
    assert len(
        full.result["derived_metrics"]["geometry"]["principal_angles_radians"]
    ) == full_dimension
    assert Summary.from_canonical_dict(summary.canonical_dict()) == summary


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("low", 0.0),
        ("high", 0.1),
        ("method", "jeffreys"),
        ("confidence", 0.9),
    ),
)
def test_summary_reader_recomputes_wilson_interval(field, value) -> None:
    summary = analyze_trials(
        [
            _trial(_config("model_hessian", seed=1), certified_query=4),
            _trial(_config("model_hessian", seed=2), certified_query=None),
            _trial(_config("model_hessian", seed=3), certified_query=9),
        ],
        bootstrap_samples=20,
    )
    payload = summary.canonical_dict()
    payload["strata"][0]["methods"][0]["success_probability"][field] = value

    with pytest.raises(AnalysisError, match="probability|Wilson|confidence"):
        Summary.from_canonical_dict(payload)


@pytest.mark.parametrize("duplicate_kind", ("stratum", "method", "baseline"))
def test_summary_reader_rejects_duplicate_named_entries(duplicate_kind) -> None:
    summary = analyze_trials(
        [
            _trial(_config("model_hessian", seed=1), certified_query=4),
            _trial(_config("random", seed=1), certified_query=6),
        ],
        bootstrap_samples=20,
    )
    payload = summary.canonical_dict()
    if duplicate_kind == "stratum":
        payload["strata"].append(payload["strata"][0])
    elif duplicate_kind == "method":
        payload["strata"][0]["methods"].append(
            payload["strata"][0]["methods"][0]
        )
        payload["strata"][0]["methods"].sort(key=lambda item: item["method"])
    else:
        payload["strata"][0]["paired_differences"].append(
            payload["strata"][0]["paired_differences"][0]
        )

    with pytest.raises(AnalysisError, match="duplicate"):
        Summary.from_canonical_dict(payload)


def test_reordered_trials_have_identical_summary_bytes() -> None:
    records = [
        _trial(_config("model_hessian", seed=1), certified_query=9),
        _trial(_config("model_hessian", seed=2), certified_query=None),
        _trial(_config("model_hessian", seed=3), certified_query=4),
    ]

    forward = analyze_trials(records, bootstrap_seed=7, bootstrap_samples=40)
    reverse = analyze_trials(
        reversed(records),
        bootstrap_seed=7,
        bootstrap_samples=40,
    )

    assert canonical_json_bytes(forward.canonical_dict()) == canonical_json_bytes(
        reverse.canonical_dict()
    )
    method = _method(forward, 0, "model_hessian")
    assert method.conditional_first_certified_queries == (4, 9)
    assert method.censored_first_certified_queries == (4, 9, 200)
    assert method.total_shots_by_trial == (104_000, 109_000, 200_000)


def test_public_pairing_handles_multiple_k_without_cross_pairing() -> None:
    records = []
    for dimension in (1, 2):
        records.extend(
            (
                _trial(
                    _config("model_hessian", seed=1, dimension=dimension),
                    certified_query=4,
                ),
                _trial(
                    _config("random", seed=1, dimension=dimension),
                    certified_query=6,
                ),
                _trial(
                    _config("oracle", seed=1, dimension=dimension),
                    certified_query=5,
                ),
            )
        )
    records.append(
        _trial(_config("full", seed=1, dimension=3), certified_query=7)
    )

    pairs = pair_trials(records)

    assert {name: len(items) for name, items in pairs.items()} == {
        "full": 2,
        "oracle": 2,
        "random": 2,
    }
    for baseline in ("oracle", "random"):
        assert [
            (
                reference.config["search"]["dimension"],
                comparison.config["search"]["dimension"],
            )
            for reference, comparison in pairs[baseline]
        ] == [(1, 1), (2, 2)]
