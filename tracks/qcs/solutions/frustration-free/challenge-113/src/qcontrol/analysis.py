from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from statistics import NormalDist
from typing import Any

import numpy as np

from qcontrol.artifacts import ArtifactConflict, ArtifactStore, canonical_json_bytes
from qcontrol.experiments import TrialResult, read_plan, validate_sweep


class AnalysisError(ValueError):
    """Verified artifacts cannot be analyzed without changing the study."""


def _finite_number(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(f"{name} must be a finite number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise AnalysisError(f"{name} must be finite")
    return numeric


def _probability(value: object, *, name: str) -> float:
    numeric = _finite_number(value, name=name)
    if not 0.0 <= numeric <= 1.0:
        raise AnalysisError(f"{name} must be a probability")
    return numeric


def _strict_nonnegative_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise AnalysisError(f"{name} must be a nonnegative integer")
    return value


def _strict_positive_int(value: object, *, name: str) -> int:
    integer = _strict_nonnegative_int(value, name=name)
    if integer == 0:
        raise AnalysisError(f"{name} must be positive")
    return integer


def _mapping(value: object, fields: set[str], *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise AnalysisError(f"{name} fields are not canonical")
    return value


def _number_tuple(value: object, *, name: str) -> tuple[float, ...]:
    if not isinstance(value, list):
        raise AnalysisError(f"{name} must be a list")
    return tuple(_finite_number(item, name=name) for item in value)


def _integer_tuple(value: object, *, name: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise AnalysisError(f"{name} must be a list")
    return tuple(_strict_nonnegative_int(item, name=name) for item in value)


@dataclass(frozen=True, slots=True)
class ProbabilityEstimate:
    value: float
    numerator: int
    denominator: int
    low: float
    high: float
    confidence: float = 0.95
    method: str = "wilson"

    def canonical_dict(self) -> dict[str, object]:
        return {
            "confidence": self.confidence,
            "denominator": self.denominator,
            "high": self.high,
            "low": self.low,
            "method": self.method,
            "numerator": self.numerator,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    estimate: float
    low: float
    high: float
    confidence: float
    samples: int
    seed: int

    def canonical_dict(self) -> dict[str, object]:
        return {
            "confidence": self.confidence,
            "estimate": self.estimate,
            "high": self.high,
            "low": self.low,
            "samples": self.samples,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class MetricAvailability:
    state: str
    reason: str | None

    def canonical_dict(self) -> dict[str, object]:
        return {"reason": self.reason, "state": self.state}


@dataclass(frozen=True, slots=True)
class TrajectoryBand:
    median: tuple[float, ...]
    low: tuple[float, ...]
    high: tuple[float, ...]
    confidence: float
    samples: int
    seed: int

    def canonical_dict(self) -> dict[str, object]:
        return {
            "confidence": self.confidence,
            "high": list(self.high),
            "low": list(self.low),
            "median": list(self.median),
            "samples": self.samples,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class PairedSummary:
    baseline: str
    pair_count: int
    cluster_count: int
    success_probability_difference: BootstrapInterval
    censored_query_difference: BootstrapInterval
    total_shot_difference: BootstrapInterval

    def canonical_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline,
            "censored_query_difference": self.censored_query_difference.canonical_dict(),
            "cluster_count": self.cluster_count,
            "pair_count": self.pair_count,
            "success_probability_difference": (
                self.success_probability_difference.canonical_dict()
            ),
            "total_shot_difference": self.total_shot_difference.canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class StratumKey:
    system_name: str
    hilbert_dimension: int
    segments: int
    amplitude_bound: float
    duration: float
    search_dimension: int
    gap: float
    shots: int | None

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.system_name,
            self.hilbert_dimension,
            self.segments,
            self.amplitude_bound,
            self.duration,
            self.search_dimension,
            self.gap,
            -1 if self.shots is None else self.shots,
        )

    def core_key(self) -> tuple[object, ...]:
        return (*self.sort_key()[:5], self.gap, self.shots)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "amplitude_bound": self.amplitude_bound,
            "duration": self.duration,
            "gap": self.gap,
            "hilbert_dimension": self.hilbert_dimension,
            "search_dimension": self.search_dimension,
            "segments": self.segments,
            "shots": self.shots,
            "system_name": self.system_name,
        }


@dataclass(frozen=True, slots=True)
class MethodSummary:
    method: str
    trial_count: int
    failure_count: int
    success_probability: ProbabilityEstimate
    conditional_first_certified_queries: tuple[int, ...]
    censored_first_certified_queries: tuple[int, ...]
    total_shots: int
    median_best_observed_infidelity_trajectory: tuple[float, ...]
    metric_availability: MetricAvailability
    exact_infidelity_trajectory: TrajectoryBand | None
    median_attained_infidelity_upper_bound: float | None
    median_principal_angles: tuple[float, ...] | None
    median_model_effective_ranks: tuple[float, ...] | None
    median_truth_effective_ranks: tuple[float, ...] | None
    median_signed_eigenvalue_gaps: tuple[float, ...] | None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "conditional_first_certified_queries": list(
                self.conditional_first_certified_queries
            ),
            "censored_first_certified_queries": list(
                self.censored_first_certified_queries
            ),
            "exact_infidelity_trajectory": (
                None
                if self.exact_infidelity_trajectory is None
                else self.exact_infidelity_trajectory.canonical_dict()
            ),
            "failure_count": self.failure_count,
            "median_attained_infidelity_upper_bound": (
                self.median_attained_infidelity_upper_bound
            ),
            "median_best_observed_infidelity_trajectory": list(
                self.median_best_observed_infidelity_trajectory
            ),
            "median_model_effective_ranks": (
                None
                if self.median_model_effective_ranks is None
                else list(self.median_model_effective_ranks)
            ),
            "median_principal_angles": (
                None
                if self.median_principal_angles is None
                else list(self.median_principal_angles)
            ),
            "median_signed_eigenvalue_gaps": (
                None
                if self.median_signed_eigenvalue_gaps is None
                else list(self.median_signed_eigenvalue_gaps)
            ),
            "median_truth_effective_ranks": (
                None
                if self.median_truth_effective_ranks is None
                else list(self.median_truth_effective_ranks)
            ),
            "method": self.method,
            "metric_availability": self.metric_availability.canonical_dict(),
            "success_probability": self.success_probability.canonical_dict(),
            "total_shots": self.total_shots,
            "trial_count": self.trial_count,
        }


@dataclass(frozen=True, slots=True)
class StratumSummary:
    key: StratumKey
    methods: tuple[MethodSummary, ...]
    paired_differences: tuple[PairedSummary, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "key": self.key.canonical_dict(),
            "methods": [item.canonical_dict() for item in self.methods],
            "paired_differences": [
                item.canonical_dict() for item in self.paired_differences
            ],
        }


@dataclass(frozen=True, slots=True)
class Summary:
    strata: tuple[StratumSummary, ...]
    bootstrap_confidence: float
    bootstrap_samples: int
    bootstrap_seed: int
    schema_version: int = 1

    def canonical_dict(self) -> dict[str, object]:
        return {
            "bootstrap_confidence": self.bootstrap_confidence,
            "bootstrap_samples": self.bootstrap_samples,
            "bootstrap_seed": self.bootstrap_seed,
            "schema_version": self.schema_version,
            "strata": [item.canonical_dict() for item in self.strata],
        }

    @classmethod
    def from_canonical_dict(cls, value: object) -> Summary:
        payload = _mapping(
            value,
            {
                "bootstrap_confidence",
                "bootstrap_samples",
                "bootstrap_seed",
                "schema_version",
                "strata",
            },
            name="summary",
        )
        if payload["schema_version"] != 1 or type(payload["schema_version"]) is not int:
            raise AnalysisError("unsupported summary schema version")
        confidence = _probability(
            payload["bootstrap_confidence"],
            name="bootstrap confidence",
        )
        if confidence in {0.0, 1.0}:
            raise AnalysisError("bootstrap confidence must be interior")
        samples = _strict_positive_int(
            payload["bootstrap_samples"],
            name="bootstrap samples",
        )
        seed = _strict_nonnegative_int(payload["bootstrap_seed"], name="bootstrap seed")
        raw_strata = payload["strata"]
        if not isinstance(raw_strata, list) or not raw_strata:
            raise AnalysisError("summary strata must be a nonempty list")
        strata = tuple(_parse_stratum(item) for item in raw_strata)
        if tuple(sorted(strata, key=lambda item: item.key.sort_key())) != strata:
            raise AnalysisError("summary strata must be sorted canonically")
        for stratum in strata:
            for method in stratum.methods:
                if method.success_probability.confidence != confidence:
                    raise AnalysisError("method confidence does not match summary")
                if method.exact_infidelity_trajectory is not None and (
                    method.exact_infidelity_trajectory.confidence != confidence
                    or method.exact_infidelity_trajectory.samples != samples
                ):
                    raise AnalysisError("trajectory bootstrap metadata is inconsistent")
            for paired in stratum.paired_differences:
                intervals = (
                    paired.success_probability_difference,
                    paired.censored_query_difference,
                    paired.total_shot_difference,
                )
                if any(
                    item.confidence != confidence or item.samples != samples
                    for item in intervals
                ):
                    raise AnalysisError("paired bootstrap metadata is inconsistent")
        summary = cls(strata, confidence, samples, seed)
        if summary.canonical_dict() != dict(payload):
            raise AnalysisError("summary is not canonical")
        return summary


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
    return first_certified_query(value) is not None


def success_probability(
    trials: Iterable[object],
    *,
    confidence: float = 0.95,
) -> ProbabilityEstimate:
    materialized = tuple(trials)
    if not materialized:
        raise AnalysisError("success probability requires at least one trial")
    confidence_value = _finite_number(confidence, name="binomial confidence")
    if not 0.0 < confidence_value < 1.0:
        raise AnalysisError("binomial confidence must be interior")
    successes = sum(_certified(trial) for trial in materialized)
    count = len(materialized)
    estimate = successes / count
    z = NormalDist().inv_cdf(0.5 + confidence_value / 2.0)
    denominator = 1.0 + z * z / count
    center = (estimate + z * z / (2.0 * count)) / denominator
    radius = (
        z
        * math.sqrt(
            estimate * (1.0 - estimate) / count
            + z * z / (4.0 * count * count)
        )
        / denominator
    )
    return ProbabilityEstimate(
        value=estimate,
        numerator=successes,
        denominator=count,
        low=max(0.0, center - radius),
        high=min(1.0, center + radius),
        confidence=confidence_value,
    )


def _bootstrap_estimates(
    values: np.ndarray,
    *,
    seed: int,
    samples: int,
    chunk_size: int,
    statistic: Callable[[np.ndarray], np.ndarray],
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    estimates = np.empty(samples, dtype=np.float64)
    for start in range(0, samples, chunk_size):
        stop = min(samples, start + chunk_size)
        indices = rng.integers(0, values.size, size=(stop - start, values.size))
        estimates[start:stop] = statistic(values[indices])
    return estimates


def paired_bootstrap_ci(
    differences: Sequence[float],
    *,
    seed: int,
    samples: int = 10_000,
    confidence: float = 0.95,
    chunk_size: int = 256,
) -> BootstrapInterval:
    seed_value = _strict_nonnegative_int(seed, name="bootstrap seed")
    sample_count = _strict_positive_int(samples, name="bootstrap samples")
    chunk = _strict_positive_int(chunk_size, name="bootstrap chunk size")
    confidence_value = _finite_number(confidence, name="bootstrap confidence")
    if not 0.0 < confidence_value < 1.0:
        raise AnalysisError("bootstrap confidence must be interior")
    values = np.asarray(
        [_finite_number(value, name="paired difference") for value in differences],
        dtype=np.float64,
    )
    if values.size == 0:
        raise AnalysisError("paired bootstrap requires at least one difference")
    estimates = _bootstrap_estimates(
        values,
        seed=seed_value,
        samples=sample_count,
        chunk_size=chunk,
        statistic=lambda selected: np.mean(selected, axis=1),
    )
    alpha = (1.0 - confidence_value) / 2.0
    low, high = np.quantile(estimates, [alpha, 1.0 - alpha])
    return BootstrapInterval(
        estimate=float(np.mean(values)),
        low=float(low),
        high=float(high),
        confidence=confidence_value,
        samples=sample_count,
        seed=seed_value,
    )


def _hilbert_dimension(system_name: str) -> int:
    dimensions = {"one_qubit": 2, "two_qubit": 4}
    try:
        return dimensions[system_name]
    except KeyError as error:
        raise AnalysisError(f"unsupported system {system_name!r}") from error


def _stratum_key(trial: TrialResult, *, dimension: int | None = None) -> StratumKey:
    system = trial.config["system"]
    device = trial.config["device"]
    return StratumKey(
        system_name=str(system["name"]),
        hilbert_dimension=_hilbert_dimension(str(system["name"])),
        segments=int(system["segments"]),
        amplitude_bound=float(system["amplitude_bound"]),
        duration=float(system["duration"]),
        search_dimension=(
            int(trial.config["search"]["dimension"])
            if dimension is None
            else dimension
        ),
        gap=float(device["gap"]),
        shots=device["shots"],
    )


def _cluster_identity(trial: TrialResult) -> tuple[object, ...]:
    return (
        trial.device_id,
        trial.config["device"]["perturbation_seed"],
        trial.config["trial_seed"],
    )


def _pair_identity(trial: TrialResult) -> tuple[object, ...]:
    return (*_stratum_key(trial).core_key(), *_cluster_identity(trial))


def pair_trials(
    trials: Iterable[TrialResult | Mapping[str, object]],
    *,
    reference_method: str = "model_hessian",
) -> dict[str, tuple[tuple[TrialResult, TrialResult], ...]]:
    records = tuple(_trial(value) for value in trials)
    references = [
        item for item in records if item.config["search"]["method"] == reference_method
    ]
    methods = {str(item.config["search"]["method"]) for item in records}
    result: dict[str, tuple[tuple[TrialResult, TrialResult], ...]] = {}
    for baseline in sorted(methods - {reference_method}):
        candidates = [
            item for item in records if item.config["search"]["method"] == baseline
        ]
        by_identity = {_pair_identity(item): item for item in candidates}
        if len(by_identity) != len(candidates):
            raise AnalysisError(f"duplicate pair coverage for {baseline!r}")
        pairs: list[tuple[TrialResult, TrialResult]] = []
        used: set[str] = set()
        for reference in references:
            match = by_identity.get(_pair_identity(reference))
            if match is None:
                raise AnalysisError(
                    f"pair coverage mismatch for {baseline!r} and "
                    f"{reference.trial_id!r}"
                )
            if (
                baseline != "full"
                and match.config["search"]["dimension"]
                != reference.config["search"]["dimension"]
            ):
                raise AnalysisError(f"pair dimension mismatch for {baseline!r}")
            pairs.append((reference, match))
            used.add(match.trial_id)
        if len(used) != len(candidates) or (
            baseline != "full" and len(pairs) != len(candidates)
        ):
            raise AnalysisError(f"unmatched pair coverage for {baseline!r}")
        result[baseline] = tuple(pairs)
    return result


def _censored_query(trial: TrialResult) -> int:
    query = first_certified_query(trial)
    return int(trial.result["budget"]) if query is None else query


def _extend(values: Sequence[float], length: int) -> tuple[float, ...]:
    if not values:
        raise AnalysisError("trajectory cannot be empty")
    numeric = tuple(_probability(item, name="trajectory value") for item in values)
    if len(numeric) > length:
        raise AnalysisError("trajectory exceeds declared budget")
    return (*numeric, *((numeric[-1],) * (length - len(numeric))))


def _best_observed_trajectory(trial: TrialResult) -> tuple[float, ...]:
    budget = int(trial.result["budget"])
    by_query: dict[int, float] = {}
    for observation in trial.result["observations"]:
        query = int(observation["optimizer_query_index"])
        infidelity = 1.0 - _probability(
            observation["estimate"],
            name="observation estimate",
        )
        by_query[query] = min(by_query.get(query, 1.0), infidelity)
    best = 1.0
    values: list[float] = []
    for query in range(1, budget + 1):
        if query in by_query:
            best = min(best, by_query[query])
        values.append(best)
    return tuple(values)


def _median_rows(rows: Sequence[Sequence[float]]) -> tuple[float, ...]:
    matrix = np.asarray(rows, dtype=np.float64)
    if matrix.ndim != 2 or not np.all(np.isfinite(matrix)):
        raise AnalysisError("metric rows must form a finite matrix")
    return tuple(float(item) for item in np.median(matrix, axis=0))


def _derived_seed(seed: int, *parts: object) -> int:
    digest = hashlib.sha256(canonical_json_bytes([seed, *parts])).digest()
    return int.from_bytes(digest[:8], "big")


def _trajectory_band(
    rows: Sequence[Sequence[float]],
    *,
    seed: int,
    samples: int,
    confidence: float,
    chunk_size: int,
) -> TrajectoryBand:
    matrix = np.asarray(rows, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or not np.all(np.isfinite(matrix)):
        raise AnalysisError("exact trajectories must form a finite matrix")
    alpha = (1.0 - confidence) / 2.0
    lows: list[float] = []
    highs: list[float] = []
    for column in range(matrix.shape[1]):
        estimates = _bootstrap_estimates(
            matrix[:, column],
            seed=seed,
            samples=samples,
            chunk_size=chunk_size,
            statistic=lambda selected: np.median(selected, axis=1),
        )
        low, high = np.quantile(estimates, [alpha, 1.0 - alpha])
        lows.append(float(low))
        highs.append(float(high))
    return TrajectoryBand(
        median=tuple(float(item) for item in np.median(matrix, axis=0)),
        low=tuple(lows),
        high=tuple(highs),
        confidence=confidence,
        samples=samples,
        seed=seed,
    )


def _method_summary(
    records: Sequence[TrialResult],
    *,
    bootstrap_seed: int,
    bootstrap_samples: int,
    confidence: float,
    chunk_size: int,
) -> MethodSummary:
    method = str(records[0].config["search"]["method"])
    probability = success_probability(records, confidence=confidence)
    budgets = {int(item.result["budget"]) for item in records}
    if len(budgets) != 1:
        raise AnalysisError("method trajectories require one common budget")
    observed = _median_rows([_best_observed_trajectory(item) for item in records])
    has_metrics = ["derived_metrics" in item.result for item in records]
    if any(has_metrics) and not all(has_metrics):
        raise AnalysisError("metric availability cannot be mixed within a method")
    if not all(has_metrics):
        if any(item.config["run_kind"] == "production" for item in records):
            raise AnalysisError("production trials require schema-v3 derived metrics")
        availability = MetricAvailability(
            "unavailable",
            "schema_v3_metrics_not_available",
        )
        exact_band = None
        attained = None
        angles = None
        model_ranks = None
        truth_ranks = None
        gaps = None
    else:
        availability = MetricAvailability("available", None)
        budget = next(iter(budgets))
        exact_rows = [
            _extend(
                item.result["derived_metrics"]["exact_infidelity"][
                    "cumulative_best_by_optimizer_query"
                ],
                budget,
            )
            for item in records
        ]
        exact_band = _trajectory_band(
            exact_rows,
            seed=_derived_seed(bootstrap_seed, method, "exact"),
            samples=bootstrap_samples,
            confidence=confidence,
            chunk_size=chunk_size,
        )
        restricted = [
            item.result["derived_metrics"]["restricted_noiseless_optimization"]
            for item in records
        ]
        geometry = [item.result["derived_metrics"]["geometry"] for item in records]
        attained = float(
            np.median(
                [
                    item["attained_infidelity_upper_bound"]
                    for item in restricted
                ]
            )
        )
        angles = _median_rows([item["principal_angles_radians"] for item in geometry])
        model_ranks = _median_rows(
            [item["model_effective_ranks"] for item in geometry]
        )
        truth_ranks = _median_rows(
            [item["truth_effective_ranks"] for item in geometry]
        )
        gaps = _median_rows(
            [item["signed_leading_eigenvalue_gaps"] for item in geometry]
        )
    conditional = tuple(
        query
        for item in records
        if (query := first_certified_query(item)) is not None
    )
    return MethodSummary(
        method=method,
        trial_count=len(records),
        failure_count=len(records) - probability.numerator,
        success_probability=probability,
        conditional_first_certified_queries=conditional,
        censored_first_certified_queries=tuple(_censored_query(item) for item in records),
        total_shots=sum(int(item.ledger["total_shots"]) for item in records),
        median_best_observed_infidelity_trajectory=observed,
        metric_availability=availability,
        exact_infidelity_trajectory=exact_band,
        median_attained_infidelity_upper_bound=attained,
        median_principal_angles=angles,
        median_model_effective_ranks=model_ranks,
        median_truth_effective_ranks=truth_ranks,
        median_signed_eigenvalue_gaps=gaps,
    )


def _paired_summaries(
    records: Sequence[TrialResult],
    *,
    bootstrap_seed: int,
    bootstrap_samples: int,
    confidence: float,
    chunk_size: int,
    reference_method: str = "model_hessian",
) -> tuple[PairedSummary, ...]:
    by_method: dict[str, dict[tuple[object, ...], TrialResult]] = {}
    for item in records:
        method = str(item.config["search"]["method"])
        identity = _cluster_identity(item)
        target = by_method.setdefault(method, {})
        if identity in target:
            raise AnalysisError(f"duplicate cluster unit for {method!r}")
        target[identity] = item
    references = by_method.get(reference_method)
    if references is None:
        if len(by_method) > 1:
            raise AnalysisError(f"pair coverage has no {reference_method!r} trials")
        return ()
    result: list[PairedSummary] = []
    for baseline in sorted(set(by_method) - {reference_method}):
        comparisons = by_method[baseline]
        if comparisons.keys() != references.keys():
            raise AnalysisError(f"pair cluster coverage mismatch for {baseline!r}")
        identities = sorted(references, key=repr)
        success = [
            float(_certified(references[key])) - float(_certified(comparisons[key]))
            for key in identities
        ]
        queries = [
            float(_censored_query(comparisons[key]) - _censored_query(references[key]))
            for key in identities
        ]
        shots = [
            float(
                comparisons[key].ledger["total_shots"]
                - references[key].ledger["total_shots"]
            )
            for key in identities
        ]
        seed = _derived_seed(bootstrap_seed, baseline)
        result.append(
            PairedSummary(
                baseline=baseline,
                pair_count=len(identities),
                cluster_count=len(identities),
                success_probability_difference=paired_bootstrap_ci(
                    success,
                    seed=_derived_seed(seed, "success"),
                    samples=bootstrap_samples,
                    confidence=confidence,
                    chunk_size=chunk_size,
                ),
                censored_query_difference=paired_bootstrap_ci(
                    queries,
                    seed=_derived_seed(seed, "query"),
                    samples=bootstrap_samples,
                    confidence=confidence,
                    chunk_size=chunk_size,
                ),
                total_shot_difference=paired_bootstrap_ci(
                    shots,
                    seed=_derived_seed(seed, "shots"),
                    samples=bootstrap_samples,
                    confidence=confidence,
                    chunk_size=chunk_size,
                ),
            )
        )
    return tuple(result)


def _stratify(records: Sequence[TrialResult]) -> tuple[tuple[StratumKey, tuple[TrialResult, ...]], ...]:
    target_keys = {
        _stratum_key(item)
        for item in records
        if item.config["search"]["method"] != "full"
    }
    if not target_keys:
        target_keys = {_stratum_key(item) for item in records}
    strata: list[tuple[StratumKey, tuple[TrialResult, ...]]] = []
    for key in sorted(target_keys, key=StratumKey.sort_key):
        selected = tuple(
            item
            for item in records
            if _stratum_key(item).core_key() == key.core_key()
            and (
                item.config["search"]["method"] == "full"
                or item.config["search"]["dimension"] == key.search_dimension
            )
        )
        if selected:
            strata.append((key, selected))
    return tuple(strata)


def analyze_trials(
    trials: Iterable[TrialResult | Mapping[str, object]],
    *,
    bootstrap_seed: int = 0,
    bootstrap_samples: int = 10_000,
    bootstrap_confidence: float = 0.95,
    bootstrap_chunk_size: int = 256,
) -> Summary:
    records = tuple(_trial(value) for value in trials)
    if not records:
        raise AnalysisError("analysis requires at least one trial")
    if len({item.trial_id for item in records}) != len(records):
        raise AnalysisError("duplicate trial coverage")
    seed = _strict_nonnegative_int(bootstrap_seed, name="bootstrap seed")
    samples = _strict_positive_int(bootstrap_samples, name="bootstrap samples")
    chunk = _strict_positive_int(bootstrap_chunk_size, name="bootstrap chunk size")
    confidence = _finite_number(
        bootstrap_confidence,
        name="bootstrap confidence",
    )
    if not 0.0 < confidence < 1.0:
        raise AnalysisError("bootstrap confidence must be interior")
    summaries: list[StratumSummary] = []
    for key, selected in _stratify(records):
        grouped: dict[str, list[TrialResult]] = {}
        for item in selected:
            grouped.setdefault(str(item.config["search"]["method"]), []).append(item)
        methods = tuple(
            _method_summary(
                tuple(grouped[method]),
                bootstrap_seed=_derived_seed(seed, key.canonical_dict(), method),
                bootstrap_samples=samples,
                confidence=confidence,
                chunk_size=chunk,
            )
            for method in sorted(grouped)
        )
        summaries.append(
            StratumSummary(
                key=key,
                methods=methods,
                paired_differences=_paired_summaries(
                    selected,
                    bootstrap_seed=_derived_seed(seed, key.canonical_dict(), "paired"),
                    bootstrap_samples=samples,
                    confidence=confidence,
                    chunk_size=chunk,
                ),
            )
        )
    return Summary(tuple(summaries), confidence, samples, seed)


def aggregate_run(
    store: ArtifactStore,
    *,
    bootstrap_seed: int = 0,
    bootstrap_samples: int = 10_000,
    bootstrap_confidence: float = 0.95,
    bootstrap_chunk_size: int = 256,
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
        bootstrap_confidence=bootstrap_confidence,
        bootstrap_chunk_size=bootstrap_chunk_size,
    )


def _parse_probability(value: object) -> ProbabilityEstimate:
    payload = _mapping(
        value,
        {"confidence", "denominator", "high", "low", "method", "numerator", "value"},
        name="success probability",
    )
    numerator = _strict_nonnegative_int(payload["numerator"], name="numerator")
    denominator = _strict_positive_int(payload["denominator"], name="denominator")
    estimate = _probability(payload["value"], name="probability estimate")
    low = _probability(payload["low"], name="probability low")
    high = _probability(payload["high"], name="probability high")
    confidence = _probability(payload["confidence"], name="probability confidence")
    if (
        numerator > denominator
        or estimate != numerator / denominator
        or low > high
        or payload["method"] != "wilson"
        or confidence in {0.0, 1.0}
    ):
        raise AnalysisError("success probability is inconsistent")
    return ProbabilityEstimate(
        estimate,
        numerator,
        denominator,
        low,
        high,
        confidence,
    )


def _parse_interval(value: object) -> BootstrapInterval:
    payload = _mapping(
        value,
        {"confidence", "estimate", "high", "low", "samples", "seed"},
        name="bootstrap interval",
    )
    low = _finite_number(payload["low"], name="bootstrap low")
    high = _finite_number(payload["high"], name="bootstrap high")
    if low > high:
        raise AnalysisError("bootstrap interval bounds are reversed")
    confidence = _probability(payload["confidence"], name="bootstrap confidence")
    if confidence in {0.0, 1.0}:
        raise AnalysisError("bootstrap confidence must be interior")
    return BootstrapInterval(
        _finite_number(payload["estimate"], name="bootstrap estimate"),
        low,
        high,
        confidence,
        _strict_positive_int(payload["samples"], name="bootstrap samples"),
        _strict_nonnegative_int(payload["seed"], name="bootstrap seed"),
    )


def _parse_availability(value: object) -> MetricAvailability:
    payload = _mapping(value, {"reason", "state"}, name="metric availability")
    state = payload["state"]
    reason = payload["reason"]
    if state == "available":
        if reason is not None:
            raise AnalysisError("available metrics cannot have a reason")
    elif state == "unavailable":
        if not isinstance(reason, str) or not reason:
            raise AnalysisError("unavailable metrics require a reason")
    else:
        raise AnalysisError("invalid metric availability state")
    return MetricAvailability(state, reason)


def _parse_band(value: object) -> TrajectoryBand:
    payload = _mapping(
        value,
        {"confidence", "high", "low", "median", "samples", "seed"},
        name="trajectory band",
    )
    median = _number_tuple(payload["median"], name="trajectory median")
    low = _number_tuple(payload["low"], name="trajectory low")
    high = _number_tuple(payload["high"], name="trajectory high")
    if not median or len(low) != len(median) or len(high) != len(median):
        raise AnalysisError("trajectory band dimensions are inconsistent")
    if any(not 0.0 <= item <= 1.0 for item in (*median, *low, *high)):
        raise AnalysisError("trajectory band values must be probabilities")
    if any(
        lower > center or center > upper
        for lower, center, upper in zip(low, median, high, strict=True)
    ):
        raise AnalysisError("trajectory band does not contain its median")
    confidence = _probability(payload["confidence"], name="trajectory confidence")
    if confidence in {0.0, 1.0}:
        raise AnalysisError("trajectory confidence must be interior")
    return TrajectoryBand(
        median,
        low,
        high,
        confidence,
        _strict_positive_int(payload["samples"], name="trajectory samples"),
        _strict_nonnegative_int(payload["seed"], name="trajectory seed"),
    )


def _parse_key(value: object) -> StratumKey:
    payload = _mapping(
        value,
        {
            "amplitude_bound",
            "duration",
            "gap",
            "hilbert_dimension",
            "search_dimension",
            "segments",
            "shots",
            "system_name",
        },
        name="stratum key",
    )
    if not isinstance(payload["system_name"], str) or not payload["system_name"]:
        raise AnalysisError("stratum system_name must be a string")
    shots = payload["shots"]
    if shots is not None:
        shots = _strict_positive_int(shots, name="stratum shots")
    key = StratumKey(
        payload["system_name"],
        _strict_positive_int(payload["hilbert_dimension"], name="hilbert_dimension"),
        _strict_positive_int(payload["segments"], name="segments"),
        _finite_number(payload["amplitude_bound"], name="amplitude_bound"),
        _finite_number(payload["duration"], name="duration"),
        _strict_positive_int(payload["search_dimension"], name="search_dimension"),
        _finite_number(payload["gap"], name="gap"),
        shots,
    )
    if key.hilbert_dimension != _hilbert_dimension(key.system_name):
        raise AnalysisError("stratum system and Hilbert dimension disagree")
    return key


def _optional_tuple(value: object, *, name: str) -> tuple[float, ...] | None:
    return None if value is None else _number_tuple(value, name=name)


def _parse_method(value: object) -> MethodSummary:
    fields = {
        "conditional_first_certified_queries",
        "censored_first_certified_queries",
        "exact_infidelity_trajectory",
        "failure_count",
        "median_attained_infidelity_upper_bound",
        "median_best_observed_infidelity_trajectory",
        "median_model_effective_ranks",
        "median_principal_angles",
        "median_signed_eigenvalue_gaps",
        "median_truth_effective_ranks",
        "method",
        "metric_availability",
        "success_probability",
        "total_shots",
        "trial_count",
    }
    payload = _mapping(value, fields, name="method summary")
    method = payload["method"]
    if not isinstance(method, str) or not method:
        raise AnalysisError("method must be a string")
    trial_count = _strict_positive_int(payload["trial_count"], name="trial_count")
    failure_count = _strict_nonnegative_int(
        payload["failure_count"],
        name="failure_count",
    )
    probability = _parse_probability(payload["success_probability"])
    availability = _parse_availability(payload["metric_availability"])
    exact = (
        None
        if payload["exact_infidelity_trajectory"] is None
        else _parse_band(payload["exact_infidelity_trajectory"])
    )
    attained_raw = payload["median_attained_infidelity_upper_bound"]
    attained = (
        None
        if attained_raw is None
        else _probability(attained_raw, name="median attained upper bound")
    )
    optional = (
        exact,
        attained,
        payload["median_principal_angles"],
        payload["median_model_effective_ranks"],
        payload["median_truth_effective_ranks"],
        payload["median_signed_eigenvalue_gaps"],
    )
    if availability.state == "available" and any(item is None for item in optional):
        raise AnalysisError("available metrics must be complete")
    if availability.state == "unavailable" and any(item is not None for item in optional):
        raise AnalysisError("unavailable metrics must not contain values")
    if probability.denominator != trial_count or failure_count != (
        trial_count - probability.numerator
    ):
        raise AnalysisError("method trial counts are inconsistent")
    conditional = _integer_tuple(
        payload["conditional_first_certified_queries"],
        name="conditional queries",
    )
    censored = _integer_tuple(
        payload["censored_first_certified_queries"],
        name="censored queries",
    )
    observed = _number_tuple(
        payload["median_best_observed_infidelity_trajectory"],
        name="observed trajectory",
    )
    if (
        any(item <= 0 for item in (*conditional, *censored))
        or len(censored) != trial_count
        or len(conditional) != probability.numerator
        or not observed
        or any(not 0.0 <= item <= 1.0 for item in observed)
    ):
        raise AnalysisError("method trajectories or query counts are inconsistent")
    angles = _optional_tuple(
        payload["median_principal_angles"],
        name="principal angles",
    )
    model_ranks = _optional_tuple(
        payload["median_model_effective_ranks"],
        name="model ranks",
    )
    truth_ranks = _optional_tuple(
        payload["median_truth_effective_ranks"],
        name="truth ranks",
    )
    gaps = _optional_tuple(
        payload["median_signed_eigenvalue_gaps"],
        name="signed gaps",
    )
    if availability.state == "available" and (
        exact is None
        or len(exact.median) != len(observed)
        or angles is None
        or model_ranks is None
        or truth_ranks is None
        or gaps is None
        or len(model_ranks) != 3
        or len(truth_ranks) != 3
        or any(item < 0.0 for item in (*model_ranks, *truth_ranks))
        or any(not 0.0 <= item <= math.pi / 2.0 for item in angles)
    ):
        raise AnalysisError("available metric dimensions are inconsistent")
    return MethodSummary(
        method,
        trial_count,
        failure_count,
        probability,
        conditional,
        censored,
        _strict_nonnegative_int(payload["total_shots"], name="total_shots"),
        observed,
        availability,
        exact,
        attained,
        angles,
        model_ranks,
        truth_ranks,
        gaps,
    )


def _parse_paired(value: object) -> PairedSummary:
    payload = _mapping(
        value,
        {
            "baseline",
            "censored_query_difference",
            "cluster_count",
            "pair_count",
            "success_probability_difference",
            "total_shot_difference",
        },
        name="paired summary",
    )
    if not isinstance(payload["baseline"], str) or not payload["baseline"]:
        raise AnalysisError("paired baseline must be a string")
    pair_count = _strict_positive_int(payload["pair_count"], name="pair_count")
    cluster_count = _strict_positive_int(
        payload["cluster_count"],
        name="cluster_count",
    )
    if pair_count != cluster_count:
        raise AnalysisError("paired bootstrap must contain one row per cluster")
    return PairedSummary(
        payload["baseline"],
        pair_count,
        cluster_count,
        _parse_interval(payload["success_probability_difference"]),
        _parse_interval(payload["censored_query_difference"]),
        _parse_interval(payload["total_shot_difference"]),
    )


def _parse_stratum(value: object) -> StratumSummary:
    payload = _mapping(
        value,
        {"key", "methods", "paired_differences"},
        name="stratum",
    )
    raw_methods = payload["methods"]
    raw_pairs = payload["paired_differences"]
    if not isinstance(raw_methods, list) or not raw_methods:
        raise AnalysisError("stratum methods must be a nonempty list")
    if not isinstance(raw_pairs, list):
        raise AnalysisError("paired differences must be a list")
    methods = tuple(_parse_method(item) for item in raw_methods)
    pairs = tuple(_parse_paired(item) for item in raw_pairs)
    if tuple(sorted(methods, key=lambda item: item.method)) != methods:
        raise AnalysisError("stratum methods must be sorted")
    if tuple(sorted(pairs, key=lambda item: item.baseline)) != pairs:
        raise AnalysisError("paired differences must be sorted")
    key = _parse_key(payload["key"])
    if any(
        item.metric_availability.state == "available"
        and (
            item.median_principal_angles is None
            or len(item.median_principal_angles) != key.search_dimension
            or item.median_signed_eigenvalue_gaps is None
            or len(item.median_signed_eigenvalue_gaps) != key.search_dimension
        )
        for item in methods
    ):
        raise AnalysisError("geometry metrics do not match stratum dimension")
    method_names = {item.method for item in methods}
    if any(item.baseline not in method_names for item in pairs):
        raise AnalysisError("paired baseline is absent from method summaries")
    return StratumSummary(key, methods, pairs)
