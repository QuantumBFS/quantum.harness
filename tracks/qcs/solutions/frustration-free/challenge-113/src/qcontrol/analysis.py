from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
import math
from statistics import median
from typing import Any

import numpy as np

from qcontrol.artifacts import ArtifactConflict, ArtifactStore, canonical_json_bytes
from qcontrol.experiments import TrialResult, read_plan, validate_sweep


class AnalysisError(ValueError):
    """Verified artifacts cannot be analyzed without changing the study."""


@dataclass(frozen=True, slots=True)
class ProbabilityEstimate:
    value: float
    numerator: int
    denominator: int


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    estimate: float
    low: float
    high: float
    confidence: float
    samples: int
    seed: int


@dataclass(frozen=True, slots=True)
class PairedSummary:
    baseline: str
    pair_count: int
    success_probability_difference: float
    censored_query_difference: BootstrapInterval
    total_shot_difference: BootstrapInterval


@dataclass(frozen=True, slots=True)
class Summary:
    trial_count: int
    failure_count: int
    success_probability: ProbabilityEstimate
    conditional_first_certified_queries: tuple[int, ...]
    censored_first_certified_queries: tuple[int, ...]
    total_shots: int
    median_best_observed_infidelity_trajectories: dict[str, tuple[float, ...]]
    median_best_exact_infidelity_trajectories: dict[str, tuple[float, ...]]
    paired_differences: dict[str, PairedSummary]
    principal_angles: tuple[float, ...] = ()
    restricted_floors: tuple[float, ...] = ()
    effective_ranks: tuple[int, ...] = ()
    eigenvalue_gaps: tuple[float, ...] = ()


def _finite_number(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(f"{name} must be a finite number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise AnalysisError(f"{name} must be finite")
    return numeric


def _strict_nonnegative_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise AnalysisError(f"{name} must be a nonnegative integer")
    return value


def _trial(value: object) -> TrialResult:
    if isinstance(value, TrialResult):
        return value
    if not isinstance(value, Mapping):
        raise AnalysisError("invalid trial: expected a TrialResult or mapping")
    try:
        return TrialResult.from_canonical_dict(value)
    except (KeyError, TypeError, ValueError) as error:
        raise AnalysisError(f"invalid trial: {error}") from error


def _strict_json_file(store: ArtifactStore, relative: str) -> object:
    path = store.root / relative

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise AnalysisError(f"duplicate JSON key {key!r} in {relative}")
            result[key] = value
        return result

    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except AnalysisError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalysisError(f"invalid JSON artifact {relative}") from error
    try:
        canonical = canonical_json_bytes(payload)
    except (TypeError, ValueError) as error:
        raise AnalysisError(f"non-finite JSON artifact {relative}") from error
    if raw != canonical:
        raise AnalysisError(f"noncanonical JSON artifact {relative}")
    return payload


def _result_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, TrialResult):
        return value.result
    if not isinstance(value, Mapping):
        raise AnalysisError("history must be a trial or result mapping")
    if "result" in value:
        return _trial(value).result
    return value


def first_certified_query(history: object) -> int | None:
    """Return only an independently certified optimizer-query crossing."""
    result = _result_mapping(history)
    certified = result.get("certified")
    query = result.get("first_certified_query")
    crossings = result.get("provisional_crossings", [])
    if type(certified) is not bool:
        raise AnalysisError("certified must be a boolean")
    if not isinstance(crossings, list) or any(
        type(item) is not int or item <= 0 for item in crossings
    ):
        raise AnalysisError("provisional crossings must be positive integers")
    if query is not None and (type(query) is not int or query <= 0):
        raise AnalysisError("first certified query must be a positive integer or None")
    if certified != (query is not None):
        raise AnalysisError("certification state is inconsistent")
    if query is not None and query not in crossings:
        raise AnalysisError("certified query must occur in validation crossings")
    return query


def _certified(value: object) -> bool:
    if isinstance(value, TrialResult) or (
        isinstance(value, Mapping) and "trial_id" in value
    ):
        return first_certified_query(_trial(value)) is not None
    return first_certified_query(value) is not None


def success_probability(trials: Iterable[object]) -> ProbabilityEstimate:
    materialized = tuple(trials)
    if not materialized:
        raise AnalysisError("success probability requires at least one trial")
    successes = sum(_certified(trial) for trial in materialized)
    return ProbabilityEstimate(
        value=successes / len(materialized),
        numerator=successes,
        denominator=len(materialized),
    )


def paired_bootstrap_ci(
    differences: Sequence[float],
    *,
    seed: int,
    samples: int = 10_000,
    confidence: float = 0.95,
) -> BootstrapInterval:
    if type(seed) is not int or seed < 0:
        raise AnalysisError("bootstrap seed must be a nonnegative integer")
    if type(samples) is not int or samples <= 0:
        raise AnalysisError("bootstrap samples must be a positive integer")
    confidence_value = _finite_number(confidence, name="bootstrap confidence")
    if not 0.0 < confidence_value < 1.0:
        raise AnalysisError("bootstrap confidence must lie strictly between zero and one")
    values = np.asarray(
        [_finite_number(value, name="paired difference") for value in differences],
        dtype=np.float64,
    )
    if values.size == 0:
        raise AnalysisError("paired bootstrap requires at least one difference")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, values.size, size=(samples, values.size))
    estimates = np.mean(values[indices], axis=1)
    alpha = (1.0 - confidence_value) / 2.0
    low, high = np.quantile(estimates, [alpha, 1.0 - alpha])
    return BootstrapInterval(
        estimate=float(np.mean(values)),
        low=float(low),
        high=float(high),
        confidence=confidence_value,
        samples=samples,
        seed=seed,
    )


def _pair_identity(trial: TrialResult) -> tuple[object, ...]:
    config = trial.config
    system = config["system"]
    device = config["device"]
    return (
        tuple(sorted(system.items())),
        device["perturbation_seed"],
        device["gap"],
        device["shots"],
        config["trial_seed"],
        trial.device_id,
    )


def pair_trials(
    trials: Iterable[TrialResult | Mapping[str, object]],
    *,
    reference_method: str = "model_hessian",
) -> dict[str, tuple[tuple[TrialResult, TrialResult], ...]]:
    records = tuple(_trial(value) for value in trials)
    methods = {record.config["search"]["method"] for record in records}
    references = [
        record
        for record in records
        if record.config["search"]["method"] == reference_method
    ]
    if not references and methods - {reference_method}:
        raise AnalysisError(f"pair coverage has no {reference_method!r} trials")
    result: dict[str, tuple[tuple[TrialResult, TrialResult], ...]] = {}
    for baseline in sorted(methods - {reference_method}):
        candidates = [
            record
            for record in records
            if record.config["search"]["method"] == baseline
        ]
        pairs: list[tuple[TrialResult, TrialResult]] = []
        used: set[str] = set()
        for reference in references:
            matches = [
                candidate
                for candidate in candidates
                if _pair_identity(candidate) == _pair_identity(reference)
                and (
                    baseline == "full"
                    or candidate.config["search"]["dimension"]
                    == reference.config["search"]["dimension"]
                )
            ]
            if len(matches) != 1:
                raise AnalysisError(
                    f"pair coverage mismatch for {baseline!r} and "
                    f"{reference.trial_id!r}"
                )
            match = matches[0]
            if baseline != "full" and match.trial_id in used:
                raise AnalysisError(f"duplicate pair coverage for {match.trial_id!r}")
            used.add(match.trial_id)
            pairs.append((reference, match))
        if len(used) != len(candidates):
            raise AnalysisError(f"unmatched pair coverage for {baseline!r}")
        result[baseline] = tuple(pairs)
    return result


def _censored_query(trial: TrialResult) -> int:
    query = first_certified_query(trial)
    return trial.result["budget"] if query is None else query


def _best_infidelity_trajectory(trial: TrialResult) -> tuple[float, ...]:
    budget = _strict_nonnegative_int(trial.result["budget"], name="budget")
    by_query: dict[int, float] = {}
    for observation in trial.result["observations"]:
        query = _strict_nonnegative_int(
            observation["optimizer_query_index"],
            name="optimizer query index",
        )
        estimate = _finite_number(observation["estimate"], name="observation estimate")
        by_query[query] = min(by_query.get(query, 1.0), 1.0 - estimate)
    best = 1.0
    trajectory: list[float] = []
    for query in range(1, budget + 1):
        if query in by_query:
            best = min(best, by_query[query])
        trajectory.append(best)
    return tuple(trajectory)


def _median_trajectories(trials: Sequence[TrialResult]) -> dict[str, tuple[float, ...]]:
    grouped: dict[str, list[tuple[float, ...]]] = {}
    for trial in trials:
        grouped.setdefault(
            str(trial.config["search"]["method"]),
            [],
        ).append(_best_infidelity_trajectory(trial))
    return {
        method: tuple(
            float(median(values))
            for values in zip(*trajectories, strict=True)
        )
        for method, trajectories in sorted(grouped.items())
    }


def _paired_summaries(
    trials: Sequence[TrialResult],
    *,
    bootstrap_seed: int,
    bootstrap_samples: int,
) -> dict[str, PairedSummary]:
    summaries: dict[str, PairedSummary] = {}
    for offset, (baseline, pairs) in enumerate(pair_trials(trials).items()):
        success_differences = [
            float(_certified(reference)) - float(_certified(comparison))
            for reference, comparison in pairs
        ]
        query_differences = [
            float(_censored_query(comparison) - _censored_query(reference))
            for reference, comparison in pairs
        ]
        shot_differences = [
            float(comparison.ledger["total_shots"] - reference.ledger["total_shots"])
            for reference, comparison in pairs
        ]
        summaries[baseline] = PairedSummary(
            baseline=baseline,
            pair_count=len(pairs),
            success_probability_difference=float(np.mean(success_differences)),
            censored_query_difference=paired_bootstrap_ci(
                query_differences,
                seed=bootstrap_seed + 2 * offset,
                samples=bootstrap_samples,
            ),
            total_shot_difference=paired_bootstrap_ci(
                shot_differences,
                seed=bootstrap_seed + 2 * offset + 1,
                samples=bootstrap_samples,
            ),
        )
    return summaries


def analyze_trials(
    trials: Iterable[TrialResult | Mapping[str, object]],
    *,
    bootstrap_seed: int = 0,
    bootstrap_samples: int = 10_000,
) -> Summary:
    records = tuple(_trial(value) for value in trials)
    if not records:
        raise AnalysisError("analysis requires at least one trial")
    identities = [record.trial_id for record in records]
    if len(set(identities)) != len(identities):
        raise AnalysisError("duplicate trial coverage")
    probability = success_probability(records)
    conditional = tuple(
        query
        for record in records
        if (query := first_certified_query(record)) is not None
    )
    censored = tuple(_censored_query(record) for record in records)
    return Summary(
        trial_count=len(records),
        failure_count=len(records) - probability.numerator,
        success_probability=probability,
        conditional_first_certified_queries=conditional,
        censored_first_certified_queries=censored,
        total_shots=sum(record.ledger["total_shots"] for record in records),
        median_best_observed_infidelity_trajectories=_median_trajectories(records),
        # Task 8 intentionally persists neither private truth nor per-query pulses,
        # so exact trajectories cannot be reconstructed from its verified schema.
        median_best_exact_infidelity_trajectories={},
        paired_differences=_paired_summaries(
            records,
            bootstrap_seed=bootstrap_seed,
            bootstrap_samples=bootstrap_samples,
        ),
    )


def aggregate_run(
    store: ArtifactStore,
    *,
    bootstrap_seed: int = 0,
    bootstrap_samples: int = 10_000,
) -> Summary:
    if not isinstance(store, ArtifactStore):
        raise AnalysisError("store must be an ArtifactStore")
    try:
        _strict_json_file(store, "ready.json")
        _strict_json_file(store, "plan.json")
        _strict_json_file(store, "index.json")
        specs = read_plan(store)
        report = validate_sweep(specs, store)
    except (ArtifactConflict, TypeError, ValueError) as error:
        raise AnalysisError(f"invalid aggregate coverage: {error}") from error
    if not specs or not report.valid or report.status.completed != report.status.expected:
        detail = "; ".join(report.errors) if report.errors else "empty or incomplete plan"
        raise AnalysisError(f"invalid aggregate coverage: {detail}")
    records: list[TrialResult] = []
    for spec in specs:
        try:
            payload: Any = _strict_json_file(
                store,
                f"trials/{spec.trial_id}.json",
            )
            trial = _trial(payload)
        except (ArtifactConflict, AnalysisError) as error:
            raise AnalysisError(f"invalid trial coverage for {spec.trial_id}: {error}") from error
        if (
            trial.trial_id != spec.trial_id
            or trial.device_id != spec.device_id
            or trial.observation_stream_id != spec.observation_stream_id
            or trial.config != spec.config.canonical_dict()
        ):
            raise AnalysisError(f"trial identity mismatch for {spec.trial_id}")
        records.append(trial)
    return analyze_trials(
        records,
        bootstrap_seed=bootstrap_seed,
        bootstrap_samples=bootstrap_samples,
    )
