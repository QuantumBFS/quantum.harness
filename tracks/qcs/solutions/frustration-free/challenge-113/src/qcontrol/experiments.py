from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import re
import threading
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from qcontrol.artifacts import ArtifactConflict, ArtifactStore, canonical_json_bytes
from qcontrol.closed_loop import SearchSpace, make_search_space, run_closed_loop
from qcontrol.config import DeviceConfig, ExperimentConfig, SearchConfig, SystemConfig
from qcontrol.device import Observation, make_query_device
from qcontrol.landscape import analyze_landscape
from qcontrol.objectives import normalized_infidelity
from qcontrol.offline import (
    compute_geometry_diagnostics,
    cumulative_best_exact_infidelity,
    make_offline_evaluator,
    optimize_restricted_noiseless_upper_bound,
)
from qcontrol.open_loop import optimize_open_loop
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem, make_system, perturb_system


_DERIVED_CACHE_LOCK = threading.RLock()
_DERIVED_STATIC_CACHE: dict[str, dict[tuple[object, ...], object]] = {}


def _content_id(prefix: str, payload: object, length: int = 24) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:length]
    return f"{prefix}-{digest}"


def _stream_seed(stream_id: str) -> int:
    digest = hashlib.sha256(stream_id.encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big")


def _array_sha256(value: object) -> str:
    array = np.ascontiguousarray(np.asarray(value, dtype=np.float64))
    digest = hashlib.sha256()
    digest.update(
        canonical_json_bytes(
            {"dtype": "float64", "shape": list(array.shape)}
        )
    )
    digest.update(array.tobytes())
    return digest.hexdigest()


def config_from_dict(payload: object) -> ExperimentConfig:
    if not isinstance(payload, Mapping):
        raise ValueError("configuration payload must be a mapping")
    if set(payload) != {"device", "run_kind", "search", "system", "trial_seed"}:
        raise ValueError("configuration payload fields are not canonical")
    try:
        system = payload["system"]
        device = payload["device"]
        search = payload["search"]
        if not all(isinstance(item, Mapping) for item in (system, device, search)):
            raise ValueError("nested configuration payloads must be mappings")
        if set(system) != {
            "amplitude_bound",
            "duration",
            "name",
            "segments",
        } or set(device) != {
            "gap",
            "perturbation_seed",
            "shots",
        } or set(search) != {
            "budget",
            "dimension",
            "method",
        }:
            raise ValueError("nested configuration fields are not canonical")
        return ExperimentConfig(
            run_kind=payload["run_kind"],
            system=SystemConfig(
                name=system["name"],
                segments=system["segments"],
                amplitude_bound=system["amplitude_bound"],
                duration=system["duration"],
            ),
            device=DeviceConfig(
                gap=device["gap"],
                shots=device["shots"],
                perturbation_seed=device["perturbation_seed"],
            ),
            search=SearchConfig(
                method=search["method"],
                dimension=search["dimension"],
                budget=search["budget"],
            ),
            trial_seed=payload["trial_seed"],
        )
    except KeyError as error:
        raise ValueError(f"configuration payload missing {error.args[0]!r}") from None


@dataclass(frozen=True, slots=True)
class TrialSpec:
    trial_id: str
    device_id: str
    observation_stream_id: str
    config: ExperimentConfig

    def __post_init__(self) -> None:
        for name, value in (
            ("trial ID", self.trial_id),
            ("device ID", self.device_id),
            ("observation stream ID", self.observation_stream_id),
        ):
            if (
                not isinstance(value, str)
                or re.fullmatch(
                    r"[a-z0-9][a-z0-9_-]*",
                    value,
                    re.ASCII,
                )
                is None
            ):
                raise ValueError(f"{name} must be a strict ASCII token")
        if not isinstance(self.config, ExperimentConfig):
            raise ValueError("config must be an ExperimentConfig")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "config": self.config.canonical_dict(),
            "device_id": self.device_id,
            "observation_stream_id": self.observation_stream_id,
            "trial_id": self.trial_id,
        }

    @classmethod
    def from_canonical_dict(cls, payload: object) -> TrialSpec:
        if not isinstance(payload, Mapping):
            raise ValueError("trial specification must be a mapping")
        try:
            spec = cls(
                trial_id=payload["trial_id"],
                device_id=payload["device_id"],
                observation_stream_id=payload["observation_stream_id"],
                config=config_from_dict(payload["config"]),
            )
        except KeyError as error:
            raise ValueError(f"trial specification missing {error.args[0]!r}") from None
        expected = generate_paired_trials([spec.config])
        if len(expected) != 1 or expected[0] != spec:
            raise ValueError("trial specification identities are not canonical")
        return spec


_OBSERVATION_FIELDS = {
    "attempt_index",
    "estimate",
    "observation_seed",
    "optimizer_query_index",
    "seed_digest",
    "shots",
    "validation",
}
_ATTEMPT_FIELDS = {
    "attempt_index",
    "charged_shots",
    "error_category",
    "estimate",
    "observation_seed",
    "optimizer_query_index",
    "requested_shots",
    "seed_digest",
    "status",
    "validation",
}
_RESULT_FIELDS = {
    "best_observation",
    "best_pulse",
    "budget",
    "budget_exhausted",
    "certified",
    "evaluations",
    "first_certified_query",
    "observations",
    "provisional_crossings",
    "schema_version",
    "search",
    "stop_reason",
    "validation_attempts",
    "validation_result",
}
_DERIVED_RESULT_FIELDS = _RESULT_FIELDS | {"derived_metrics"}


def _exact_nonnegative_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _observation(value: object, *, validation: bool | None = None) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _OBSERVATION_FIELDS:
        raise ValueError("observation fields are not canonical")
    payload = dict(value)
    estimate = payload["estimate"]
    if (
        isinstance(estimate, bool)
        or not isinstance(estimate, (int, float))
        or not math.isfinite(float(estimate))
        or not 0.0 <= float(estimate) <= 1.0
    ):
        raise ValueError("observation estimate must be a finite probability")
    for key in ("attempt_index", "observation_seed", "optimizer_query_index", "shots"):
        _exact_nonnegative_int(payload[key], name=key)
    if type(payload["validation"]) is not bool:
        raise ValueError("observation validation must be a boolean")
    if validation is not None and payload["validation"] is not validation:
        raise ValueError("observation kind is inconsistent")
    if (
        not isinstance(payload["seed_digest"], str)
        or re.fullmatch(r"[0-9a-f]{64}", payload["seed_digest"], re.ASCII) is None
    ):
        raise ValueError("observation seed digest is invalid")
    return payload


def _attempt_observation(attempt: Mapping[str, object]) -> dict[str, object]:
    return {
        "attempt_index": attempt["attempt_index"],
        "estimate": attempt["estimate"],
        "observation_seed": attempt["observation_seed"],
        "optimizer_query_index": attempt["optimizer_query_index"],
        "seed_digest": attempt["seed_digest"],
        "shots": attempt["charged_shots"],
        "validation": attempt["validation"],
    }


def _finite_probability(value: object, *, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(f"{name} must be a finite probability")
    return float(value)


def _validate_derived_metrics(
    value: object,
    *,
    evaluations: int,
    attempts: tuple[dict[str, object], ...],
    config: ExperimentConfig,
) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "exact_infidelity",
        "geometry",
        "restricted_noiseless_optimization",
    }:
        raise ValueError("derived metric fields are not canonical")
    exact = value["exact_infidelity"]
    if not isinstance(exact, Mapping) or set(exact) != {
        "cumulative_best_by_optimizer_query",
        "initial_infidelity",
    }:
        raise ValueError("exact-infidelity fields are not canonical")
    initial = _finite_probability(
        exact["initial_infidelity"],
        name="initial exact infidelity",
    )
    trajectory = exact["cumulative_best_by_optimizer_query"]
    if not isinstance(trajectory, list) or len(trajectory) != evaluations:
        raise ValueError("exact-infidelity trajectory must align with optimizer queries")
    values = [
        _finite_probability(item, name="exact-infidelity trajectory value")
        for item in trajectory
    ]
    if any(current > previous for previous, current in zip([initial, *values], values)):
        raise ValueError("exact-infidelity trajectory must be cumulative nonincreasing")
    optimizer_attempts = [item for item in attempts if not item["validation"]]
    previous = initial
    for item, current in zip(optimizer_attempts, values, strict=True):
        if item["status"] != "succeeded" and current != previous:
            raise ValueError("failed optimizer queries require exact carry-forward")
        previous = current

    restricted = value["restricted_noiseless_optimization"]
    restricted_fields = {
        "attained_infidelity_upper_bound",
        "consistency_tolerance",
        "converged",
        "function_evaluations",
        "gradient_tolerance",
        "iterations",
        "max_iterations",
        "solver",
        "starting_infidelity_upper_bound",
        "termination",
    }
    if not isinstance(restricted, Mapping) or set(restricted) != restricted_fields:
        raise ValueError("restricted-optimization fields are not canonical")
    attained = _finite_probability(
        restricted["attained_infidelity_upper_bound"],
        name="restricted attained upper bound",
    )
    starting = _finite_probability(
        restricted["starting_infidelity_upper_bound"],
        name="restricted starting upper bound",
    )
    if (
        type(restricted["max_iterations"]) is not int
        or restricted["max_iterations"] <= 0
        or type(restricted["function_evaluations"]) is not int
        or restricted["function_evaluations"] <= 0
        or type(restricted["iterations"]) is not int
        or restricted["iterations"] < 0
        or type(restricted["converged"]) is not bool
        or restricted["solver"] != "L-BFGS-B"
        or restricted["termination"] not in {"converged", "iteration_budget"}
        or restricted["converged"]
        != (restricted["termination"] == "converged")
    ):
        raise ValueError("restricted-optimization solver metadata is invalid")
    gradient_tolerance = restricted["gradient_tolerance"]
    consistency_tolerance = restricted["consistency_tolerance"]
    if (
        isinstance(gradient_tolerance, bool)
        or not isinstance(gradient_tolerance, (int, float))
        or not math.isfinite(float(gradient_tolerance))
        or float(gradient_tolerance) <= 0.0
        or isinstance(consistency_tolerance, bool)
        or not isinstance(consistency_tolerance, (int, float))
        or not math.isfinite(float(consistency_tolerance))
        or float(consistency_tolerance) < 0.0
    ):
        raise ValueError("restricted-optimization tolerances are invalid")
    if attained > starting + float(consistency_tolerance) or attained > min(
        [initial, *values]
    ) + float(consistency_tolerance):
        raise ValueError("restricted attained upper bound is inconsistent")

    geometry = value["geometry"]
    geometry_fields = {
        "model_effective_ranks",
        "model_top_subspace_sha256",
        "principal_angles_radians",
        "rank_thresholds",
        "signed_leading_eigenvalue_gaps",
        "truth_effective_ranks",
        "truth_top_subspace_sha256",
    }
    if not isinstance(geometry, Mapping) or set(geometry) != geometry_fields:
        raise ValueError("geometry fields are not canonical")
    thresholds = geometry["rank_thresholds"]
    model_ranks = geometry["model_effective_ranks"]
    truth_ranks = geometry["truth_effective_ranks"]
    if (
        not isinstance(thresholds, list)
        or thresholds != [1e-6, 1e-8, 1e-10]
        or not isinstance(model_ranks, list)
        or not isinstance(truth_ranks, list)
        or len(model_ranks) != len(thresholds)
        or len(truth_ranks) != len(thresholds)
    ):
        raise ValueError("geometry rank diagnostics are dimensionally inconsistent")
    for ranks in (model_ranks, truth_ranks):
        if any(
            type(rank) is not int
            or not 0 <= rank <= config.system.parameter_count
            for rank in ranks
        ) or any(current < previous for previous, current in zip(ranks, ranks[1:])):
            raise ValueError("geometry effective ranks are invalid")
    dimension = config.search.dimension
    gaps = geometry["signed_leading_eigenvalue_gaps"]
    angles = geometry["principal_angles_radians"]
    if (
        not isinstance(gaps, list)
        or not isinstance(angles, list)
        or len(gaps) != dimension
        or len(angles) != dimension
        or any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            for item in gaps
        )
        or any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            or not 0.0 <= float(item) <= math.pi / 2.0 + 1e-12
            for item in angles
        )
    ):
        raise ValueError("geometry subspace diagnostics are invalid")
    for key in ("model_top_subspace_sha256", "truth_top_subspace_sha256"):
        if (
            not isinstance(geometry[key], str)
            or re.fullmatch(r"[0-9a-f]{64}", geometry[key], re.ASCII) is None
        ):
            raise ValueError("geometry subspace hash is invalid")


def _validate_result_and_attempts(
    result: object,
    ledger: Mapping[str, int],
    attempts: tuple[dict[str, object], ...],
    config: ExperimentConfig,
) -> None:
    if not isinstance(result, Mapping):
        raise ValueError("public result fields are not canonical")
    schema_version = result.get("schema_version")
    expected_fields = _DERIVED_RESULT_FIELDS if schema_version == 3 else _RESULT_FIELDS
    if set(result) != expected_fields:
        raise ValueError("public result fields are not canonical")
    if type(schema_version) is not int or schema_version not in {2, 3}:
        raise ValueError("unsupported public result schema")
    if schema_version == 2 and config.run_kind == "production":
        raise ValueError("production trials require derived-metric schema 3")
    search = result["search"]
    if not isinstance(search, Mapping) or set(search) != {
        "basis_sha256",
        "dimension",
        "method",
        "origin_sha256",
    }:
        raise ValueError("public search identity fields are not canonical")
    if (
        search["method"] != config.search.method
        or search["dimension"] != config.search.dimension
        or type(search["dimension"]) is not int
        or any(
            not isinstance(search[key], str)
            or re.fullmatch(r"[0-9a-f]{64}", search[key], re.ASCII) is None
            for key in ("basis_sha256", "origin_sha256")
        )
    ):
        raise ValueError("public search identity does not match configuration")
    evaluations = _exact_nonnegative_int(
        result["evaluations"],
        name="evaluations",
    )
    budget = _exact_nonnegative_int(result["budget"], name="budget")
    if budget != config.search.budget or evaluations != ledger["optimizer_queries"]:
        raise ValueError("result budget/evaluations do not match config and ledger")
    if type(result["budget_exhausted"]) is not bool or type(result["certified"]) is not bool:
        raise ValueError("result completion flags must be booleans")
    if result["stop_reason"] not in {"budget", "certified", "optimizer_stopped"}:
        raise ValueError("result stop reason is invalid")
    if (
        not isinstance(result["best_pulse"], list)
        or len(result["best_pulse"]) != config.system.parameter_count
        or any(
        isinstance(item, bool)
        or not isinstance(item, (int, float))
        or not math.isfinite(float(item))
        or not -1.0 <= float(item) <= 1.0
        for item in result["best_pulse"]
        )
    ):
        raise ValueError("best pulse must contain finite numbers")
    if not isinstance(result["observations"], list) or not isinstance(
        result["validation_attempts"], list
    ):
        raise ValueError("result histories must be lists")
    first_certified = result["first_certified_query"]
    if first_certified is not None:
        _exact_nonnegative_int(
            first_certified,
            name="first_certified_query",
        )
    if not isinstance(result["provisional_crossings"], list) or any(
        type(item) is not int or item <= 0
        for item in result["provisional_crossings"]
    ):
        raise ValueError("provisional crossings must be positive integers")
    if result["certified"]:
        if (
            result["stop_reason"] != "certified"
            or result["budget_exhausted"]
            or first_certified is None
        ):
            raise ValueError("certified result state is inconsistent")
    elif evaluations == budget:
        if result["stop_reason"] != "budget" or not result["budget_exhausted"]:
            raise ValueError("budget-exhausted result state is inconsistent")
    elif result["stop_reason"] != "optimizer_stopped" or result["budget_exhausted"]:
        raise ValueError("early result state is inconsistent")

    if any(not isinstance(attempt, Mapping) or set(attempt) != _ATTEMPT_FIELDS for attempt in attempts):
        raise ValueError("attempt fields are not canonical")
    indices: list[int] = []
    optimizer_records: list[dict[str, object]] = []
    validation_records: list[dict[str, object]] = []
    for attempt in attempts:
        attempt_index = _exact_nonnegative_int(
            attempt["attempt_index"],
            name="attempt_index",
        )
        if attempt_index == 0:
            raise ValueError("attempt indices are one-based")
        indices.append(attempt_index)
        _exact_nonnegative_int(
            attempt["optimizer_query_index"],
            name="optimizer_query_index",
        )
        _exact_nonnegative_int(attempt["charged_shots"], name="charged_shots")
        requested = attempt["requested_shots"]
        if requested is not None:
            _exact_nonnegative_int(requested, name="requested_shots")
        if type(attempt["validation"]) is not bool:
            raise ValueError("attempt validation must be a boolean")
        if attempt["status"] not in {"succeeded", "failed", "aborted"}:
            raise ValueError("attempt status is invalid")
        if attempt["status"] == "succeeded":
            _observation(_attempt_observation(attempt), validation=attempt["validation"])
            if attempt["error_category"] is not None:
                raise ValueError("successful attempts cannot have errors")
        else:
            if attempt["estimate"] is not None or not isinstance(
                attempt["error_category"], str
            ):
                raise ValueError("failed attempts require only an error category")
            if attempt["observation_seed"] is not None:
                _exact_nonnegative_int(
                    attempt["observation_seed"],
                    name="observation_seed",
                )
            if attempt["seed_digest"] is not None and (
                not isinstance(attempt["seed_digest"], str)
                or re.fullmatch(
                    r"[0-9a-f]{64}",
                    attempt["seed_digest"],
                    re.ASCII,
                )
                is None
            ):
                raise ValueError("failed-attempt seed digest is invalid")
        expected_requested = (
            100_000
            if attempt["validation"]
            else (0 if config.device.shots is None else config.device.shots)
        )
        if requested != expected_requested:
            raise ValueError("attempt requested shots do not match configuration")
        if attempt["charged_shots"] not in {0, expected_requested}:
            raise ValueError("attempt charged shots are inconsistent")
        if (
            attempt["status"] == "succeeded"
            and attempt["charged_shots"] != expected_requested
        ):
            raise ValueError("successful attempt must charge requested shots")
        (validation_records if attempt["validation"] else optimizer_records).append(attempt)

    if indices != list(range(1, len(attempts) + 1)):
        raise ValueError("attempt indices must be unique and contiguous")
    if [item["optimizer_query_index"] for item in optimizer_records] != list(
        range(1, len(optimizer_records) + 1)
    ):
        raise ValueError("optimizer query indices are not contiguous")
    if len(optimizer_records) != ledger["optimizer_queries"] or len(
        validation_records
    ) != ledger["validation_queries"]:
        raise ValueError("attempt counts do not match ledger")
    if sum(item["charged_shots"] for item in optimizer_records) != ledger[
        "optimizer_shots"
    ] or sum(item["charged_shots"] for item in validation_records) != ledger[
        "validation_shots"
    ]:
        raise ValueError("attempt shots do not match ledger")
    if len(attempts) != ledger["total_queries"]:
        raise ValueError("attempt total does not match ledger")

    optimizer_observations = [
        _attempt_observation(item)
        for item in optimizer_records
        if item["status"] == "succeeded"
    ]
    serialized_observations = [
        _observation(item, validation=False) for item in result["observations"]
    ]
    if serialized_observations != optimizer_observations:
        raise ValueError("optimizer observations do not reconcile with attempts")
    best = result["best_observation"]
    if best is not None and _observation(best, validation=False) not in serialized_observations:
        raise ValueError("best observation is not in optimizer history")

    validation_by_attempt = {
        item["attempt_index"]: item for item in validation_records
    }
    used_validation_attempts: set[int] = set()
    serialized_validation_observations: list[dict[str, object]] = []
    crossings: list[int] = []
    certified_crossings: list[int] = []
    for item in result["validation_attempts"]:
        if not isinstance(item, Mapping):
            raise ValueError("validation attempt must be a mapping")
        required = {
            "best_observation",
            "certified",
            "device_attempt_index",
            "failure_category",
            "optimizer_query_index",
            "pulse",
            "status",
            "validation_observation",
        }
        if set(item) != required:
            raise ValueError("validation-attempt fields are not canonical")
        device_index = _exact_nonnegative_int(
            item["device_attempt_index"],
            name="device_attempt_index",
        )
        if device_index == 0 or device_index in used_validation_attempts:
            raise ValueError("validation attempt identities must be unique")
        used_validation_attempts.add(device_index)
        record = validation_by_attempt.get(device_index)
        if record is None:
            raise ValueError("validation history has no matching ledger attempt")
        crossing = _exact_nonnegative_int(
            item["optimizer_query_index"],
            name="optimizer_query_index",
        )
        crossings.append(crossing)
        best_observation = _observation(
            item["best_observation"],
            validation=False,
        )
        if (
            record["optimizer_query_index"] != crossing
            or best_observation["optimizer_query_index"] != crossing
        ):
            raise ValueError("validation optimizer query identity is inconsistent")
        if best_observation not in serialized_observations:
            raise ValueError("validation best observation is not in optimizer history")
        if (
            not isinstance(item["pulse"], list)
            or len(item["pulse"]) != len(result["best_pulse"])
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not -1.0 <= float(value) <= 1.0
                for value in item["pulse"]
            )
        ):
            raise ValueError("validation pulse is invalid")
        if type(item["certified"]) is not bool or item["status"] not in {
            "certified",
            "failed",
            "rejected",
        }:
            raise ValueError("validation status is invalid")
        validation_observation = item["validation_observation"]
        if record["status"] == "succeeded":
            observed = _observation(validation_observation, validation=True)
            if observed != _attempt_observation(record):
                raise ValueError("validation observation does not match attempt")
            serialized_validation_observations.append(observed)
            if item["failure_category"] is not None:
                raise ValueError("successful validation cannot have a failure")
            expected_status = "certified" if item["certified"] else "rejected"
            if item["status"] != expected_status:
                raise ValueError("successful validation status is inconsistent")
        elif (
            validation_observation is not None
            or item["failure_category"] != record["error_category"]
        ):
            raise ValueError("failed validation does not match attempt")
        elif item["status"] != "failed" or item["certified"]:
            raise ValueError("failed validation status is inconsistent")
        if item["certified"]:
            certified_crossings.append(item["optimizer_query_index"])
    if len(result["validation_attempts"]) != len(validation_records):
        raise ValueError("validation history does not cover all attempts")
    if used_validation_attempts != set(validation_by_attempt):
        raise ValueError("validation ledger attempts are not covered exactly once")
    if any(
        current <= previous
        for previous, current in zip(crossings, crossings[1:])
    ):
        raise ValueError(
            "validation optimizer queries must be strictly increasing"
        )
    if result["provisional_crossings"] != crossings:
        raise ValueError("provisional crossings do not match validation history")
    latest_validation = (
        serialized_validation_observations[-1]
        if serialized_validation_observations
        else None
    )
    if result["validation_result"] != latest_validation:
        raise ValueError("latest validation result is inconsistent")
    expected_first = certified_crossings[0] if certified_crossings else None
    if (
        len(certified_crossings) > 1
        or result["certified"] != bool(certified_crossings)
        or first_certified != expected_first
    ):
        raise ValueError("certification history is inconsistent")
    if certified_crossings and certified_crossings[0] != crossings[-1]:
        raise ValueError("certified validation attempt must be final")
    if schema_version == 3:
        _validate_derived_metrics(
            result["derived_metrics"],
            evaluations=evaluations,
            attempts=attempts,
            config=config,
        )


@dataclass(frozen=True, slots=True)
class TrialResult:
    trial_id: str
    device_id: str
    observation_stream_id: str
    config: dict[str, object]
    result: dict[str, object]
    ledger: dict[str, int]
    attempts: tuple[dict[str, object], ...] | Iterable[dict[str, object]]
    execution: int | None = None

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str)
            and re.fullmatch(
                r"[a-z0-9][a-z0-9_-]*",
                value,
                re.ASCII,
            )
            is not None
            for value in (
                self.trial_id,
                self.device_id,
                self.observation_stream_id,
            )
        ):
            raise ValueError("trial identities must be strict ASCII tokens")
        canonical_config = config_from_dict(self.config).canonical_dict()
        if self.config != canonical_config:
            raise ValueError("trial configuration is not canonical")
        required_ledger = {
            "optimizer_queries",
            "optimizer_shots",
            "validation_queries",
            "validation_shots",
            "total_queries",
            "total_shots",
        }
        if set(self.ledger) != required_ledger or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in self.ledger.values()
        ):
            raise ValueError("ledger must contain nonnegative canonical totals")
        if self.ledger["total_queries"] != (
            self.ledger["optimizer_queries"] + self.ledger["validation_queries"]
        ):
            raise ValueError("ledger query total is inconsistent")
        if self.ledger["total_shots"] != (
            self.ledger["optimizer_shots"] + self.ledger["validation_shots"]
        ):
            raise ValueError("ledger shot total is inconsistent")
        attempts = tuple(dict(attempt) for attempt in self.attempts)
        _validate_result_and_attempts(
            self.result,
            self.ledger,
            attempts,
            config_from_dict(self.config),
        )
        if self.execution is not None and (
            isinstance(self.execution, bool)
            or not isinstance(self.execution, int)
            or self.execution <= 0
        ):
            raise ValueError("execution must be a positive integer or None")
        object.__setattr__(self, "attempts", attempts)

    def canonical_dict(self) -> dict[str, object]:
        schema_version = self.result["schema_version"]
        payload: dict[str, object] = {
            "attempts": list(self.attempts),
            "config": self.config,
            "device_id": self.device_id,
            "ledger": self.ledger,
            "observation_stream_id": self.observation_stream_id,
            "result": self.result,
            "schema_version": schema_version,
            "trial_id": self.trial_id,
        }
        if self.execution is not None:
            payload["execution"] = self.execution
        return payload

    @classmethod
    def from_canonical_dict(cls, payload: object) -> TrialResult:
        if not isinstance(payload, Mapping) or payload.get("schema_version") not in {
            2,
            3,
        }:
            raise ValueError("unsupported trial-result schema")
        expected = {
            "attempts",
            "config",
            "device_id",
            "ledger",
            "observation_stream_id",
            "result",
            "schema_version",
            "trial_id",
        }
        if "execution" in payload:
            expected.add("execution")
        if set(payload) != expected:
            raise ValueError("invalid trial-result fields")
        result_payload = payload.get("result")
        if (
            not isinstance(result_payload, Mapping)
            or result_payload.get("schema_version") != payload["schema_version"]
        ):
            raise ValueError("trial and public result schema versions differ")
        try:
            result = cls(
                trial_id=payload["trial_id"],
                device_id=payload["device_id"],
                observation_stream_id=payload["observation_stream_id"],
                config=dict(payload["config"]),
                result=dict(payload["result"]),
                ledger=dict(payload["ledger"]),
                attempts=tuple(dict(item) for item in payload["attempts"]),
                execution=payload.get("execution"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid trial-result payload: {error}") from error
        return result


@dataclass(frozen=True, slots=True)
class SweepStatus:
    expected: int
    completed: int
    pending: int

    def canonical_dict(self) -> dict[str, int]:
        return {
            "completed": self.completed,
            "expected": self.expected,
            "pending": self.pending,
        }


@dataclass(frozen=True, slots=True)
class ValidationReport:
    valid: bool
    status: SweepStatus
    errors: tuple[str, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "errors": list(self.errors),
            **self.status.canonical_dict(),
            "valid": self.valid,
        }


def _normalized_full_config(config: ExperimentConfig) -> ExperimentConfig:
    if config.search.method != "full":
        return config
    return replace(
        config,
        search=SearchConfig(
            method="full",
            dimension=config.system.parameter_count,
            budget=config.search.budget,
        ),
    )


def _device_payload(config: ExperimentConfig) -> dict[str, object]:
    canonical = config.canonical_dict()
    return {
        "device": canonical["device"],
        "run_kind": canonical["run_kind"],
        "system": canonical["system"],
        "trial_seed": canonical["trial_seed"],
    }


def generate_paired_trials(configs: Iterable[ExperimentConfig]) -> tuple[TrialSpec, ...]:
    materialized = tuple(configs)
    if any(not isinstance(config, ExperimentConfig) for config in materialized):
        raise ValueError("configs must contain ExperimentConfig values")
    run_kinds = {config.run_kind for config in materialized}
    if len(run_kinds) > 1:
        raise ValueError("development and production run kinds cannot be mixed")

    by_trial_id: dict[str, TrialSpec] = {}
    for original in materialized:
        config = _normalized_full_config(original)
        canonical = config.canonical_dict()
        device_id = _content_id("device", _device_payload(config))
        trial_id = _content_id("trial", canonical)
        stream_id = _content_id(
            "stream",
            {
                "device_id": device_id,
                "dimension": config.search.dimension,
                "method": config.search.method,
                "trial_seed": config.trial_seed,
            },
        )
        spec = TrialSpec(trial_id, device_id, stream_id, config)
        prior = by_trial_id.setdefault(trial_id, spec)
        if prior != spec:
            raise ArtifactConflict("trial identifier collision")
    return tuple(by_trial_id[key] for key in sorted(by_trial_id))


def _oracle_basis(
    truth: object,
    pulse_space: PulseSpace,
    origin: np.ndarray,
) -> np.ndarray:
    point = jnp.asarray(origin, dtype=jnp.float64)
    hessian = np.asarray(
        jax.hessian(
            lambda pulse: normalized_infidelity(pulse, truth, pulse_space)
        )(point),
        dtype=np.float64,
    )
    eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (hessian + hessian.T))
    ordering = np.argsort(np.abs(eigenvalues))[::-1]
    return np.asarray(eigenvectors[:, ordering], dtype=np.float64)


def _cached_static_derived_metrics(
    config: ExperimentConfig,
    model: ControlSystem,
    truth: ControlSystem,
    pulse_space: PulseSpace,
    search_space: SearchSpace,
    audited_queries: Sequence[tuple[np.ndarray, Observation | None]],
) -> tuple[object, object]:
    system = config.canonical_dict()["system"]
    device = config.canonical_dict()["device"]
    geometry_key = (
        canonical_json_bytes(system),
        device["gap"],
        device["perturbation_seed"],
        device["shots"],
        config.trial_seed,
        _array_sha256(search_space.origin),
        search_space.dimension,
    )
    pulse_matrix = np.stack(
        [np.asarray(pulse, dtype=np.float64) for pulse, _ in audited_queries],
        axis=0,
    )
    restricted_key = (
        geometry_key,
        _array_sha256(search_space.basis),
        _array_sha256(search_space.lower_bounds),
        _array_sha256(search_space.upper_bounds),
        _array_sha256(pulse_matrix),
    )
    with _DERIVED_CACHE_LOCK:
        geometry_cache = _DERIVED_STATIC_CACHE.setdefault("geometry", {})
        geometry = geometry_cache.get(geometry_key)
        if geometry is None:
            geometry = compute_geometry_diagnostics(
                model,
                truth,
                pulse_space,
                search_space.origin,
                top_k=search_space.dimension,
            )
            geometry_cache[geometry_key] = geometry
        restricted_cache = _DERIVED_STATIC_CACHE.setdefault("restricted", {})
        restricted = restricted_cache.get(restricted_key)
        if restricted is None:
            restricted = optimize_restricted_noiseless_upper_bound(
                truth,
                pulse_space,
                search_space,
                candidate_pulses=tuple(pulse for pulse, _ in audited_queries),
            )
            restricted_cache[restricted_key] = restricted
    return geometry, restricted


def run_trial(config: ExperimentConfig, store: ArtifactStore) -> TrialResult:
    del store
    specs = generate_paired_trials([config])
    if len(specs) != 1:
        raise ValueError("config must identify exactly one trial")
    spec = specs[0]
    config = spec.config

    model = make_system(config.system)
    pulse_space = PulseSpace.from_system(model, config.system.segments)
    open_loop = optimize_open_loop(model, pulse_space, seed=config.trial_seed)
    landscape = analyze_landscape(
        model,
        pulse_space,
        open_loop,
        leading_count=min(
            pulse_space.parameter_count,
            max(config.search.dimension, model.dimension**2 - 1),
        ),
        dense_validation=pulse_space.parameter_count <= 80,
    )
    origin = np.asarray(
        (
            landscape.polishing.normalized_pulse
            if landscape.polishing is not None
            else open_loop.normalized_pulse
        ),
        dtype=np.float64,
    )
    truth = perturb_system(
        model,
        config.device.gap,
        config.device.perturbation_seed,
    )
    oracle_basis = (
        _oracle_basis(truth, pulse_space, origin)
        if config.search.method == "oracle"
        else None
    )
    search_space = make_search_space(
        config.search,
        origin,
        model_basis=landscape.model_basis,
        oracle_basis=oracle_basis,
        seed=config.trial_seed,
    )
    device = make_query_device(
        truth,
        pulse_space,
        config.device,
        seed=_stream_seed(spec.observation_stream_id),
    )
    audited_queries: list[tuple[np.ndarray, Observation | None]] = []

    def record_query(
        pulse: np.ndarray,
        observation: Observation | None,
    ) -> None:
        audited_queries.append(
            (np.array(pulse, dtype=np.float64, copy=True), observation)
        )

    closed = run_closed_loop(
        device,
        search_space,
        config.search.budget,
        config.trial_seed,
        audit_sink=record_query,
    )
    ledger = device.ledger
    accounting_before_offline = (
        ledger.optimizer_queries,
        ledger.optimizer_shots,
        ledger.validation_queries,
        ledger.validation_shots,
        ledger.total_queries,
        ledger.total_shots,
    )
    exact_trajectory = cumulative_best_exact_infidelity(
        make_offline_evaluator(truth, pulse_space),
        initial_pulse=search_space.origin,
        audited_queries=audited_queries,
    )
    geometry, restricted = _cached_static_derived_metrics(
        config,
        model,
        truth,
        pulse_space,
        search_space,
        audited_queries,
    )
    accounting_after_offline = (
        ledger.optimizer_queries,
        ledger.optimizer_shots,
        ledger.validation_queries,
        ledger.validation_shots,
        ledger.total_queries,
        ledger.total_shots,
    )
    if accounting_after_offline != accounting_before_offline:
        raise RuntimeError("offline derived metrics changed device accounting")
    public_result = closed.canonical_dict()
    public_result.pop("space")
    public_result["schema_version"] = 3
    public_result["search"] = {
        "basis_sha256": _array_sha256(search_space.basis),
        "dimension": search_space.dimension,
        "method": config.search.method,
        "origin_sha256": _array_sha256(search_space.origin),
    }
    public_result["derived_metrics"] = {
        "exact_infidelity": exact_trajectory.canonical_dict(),
        "geometry": {
            "model_effective_ranks": list(geometry.model_effective_ranks),
            "model_top_subspace_sha256": _array_sha256(
                geometry.model_top_subspace
            ),
            "principal_angles_radians": list(
                geometry.principal_angles_radians
            ),
            "rank_thresholds": list(geometry.rank_thresholds),
            "signed_leading_eigenvalue_gaps": list(
                geometry.signed_leading_eigenvalue_gaps
            ),
            "truth_effective_ranks": list(geometry.truth_effective_ranks),
            "truth_top_subspace_sha256": _array_sha256(
                geometry.truth_top_subspace
            ),
        },
        "restricted_noiseless_optimization": restricted.canonical_dict(),
    }
    attempts = tuple(
        {
            "attempt_index": record.attempt_index,
            "charged_shots": record.charged_shots,
            "error_category": record.error_category,
            "estimate": record.estimate,
            "observation_seed": record.observation_seed,
            "optimizer_query_index": record.optimizer_query_index,
            "requested_shots": record.requested_shots,
            "seed_digest": record.seed_digest,
            "status": record.status,
            "validation": record.validation,
        }
        for record in ledger.records
    )
    return TrialResult(
        trial_id=spec.trial_id,
        device_id=spec.device_id,
        observation_stream_id=spec.observation_stream_id,
        config=config.canonical_dict(),
        result=public_result,
        ledger={
            "optimizer_queries": ledger.optimizer_queries,
            "optimizer_shots": ledger.optimizer_shots,
            "validation_queries": ledger.validation_queries,
            "validation_shots": ledger.validation_shots,
            "total_queries": ledger.total_queries,
            "total_shots": ledger.total_shots,
        },
        attempts=attempts,
    )


def _plan_payload(specs: Sequence[TrialSpec]) -> dict[str, object]:
    return {
        "run_kind": specs[0].config.run_kind if specs else None,
        "schema_version": 1,
        "trials": [spec.canonical_dict() for spec in specs],
    }


def _bind_plan(specs: Sequence[TrialSpec], store: ArtifactStore) -> None:
    payload = _plan_payload(specs)
    provenance_config = {
        "run_kind": payload["run_kind"],
        "trials": [spec.config.canonical_dict() for spec in specs],
    }
    store.initialize_run(provenance_config, payload)


def _validated_result_for_spec(payload: object, spec: TrialSpec) -> TrialResult:
    result = TrialResult.from_canonical_dict(payload)
    if (
        result.trial_id != spec.trial_id
        or result.device_id != spec.device_id
        or result.observation_stream_id != spec.observation_stream_id
        or result.config != spec.config.canonical_dict()
    ):
        raise ValueError("trial identity does not match plan")
    return result


def run_sweep(
    specs: Sequence[TrialSpec],
    store: ArtifactStore,
    *,
    executor: Callable[[TrialSpec], TrialResult] | None = None,
    stop_after: int | None = None,
) -> SweepStatus:
    specs = tuple(specs)
    if stop_after is not None and (
        isinstance(stop_after, bool)
        or not isinstance(stop_after, int)
        or stop_after < 0
    ):
        raise ValueError("stop_after must be a nonnegative integer or None")
    _bind_plan(specs, store)
    completed = store.completed_trial_ids()
    expected = {spec.trial_id for spec in specs}
    if not completed <= expected:
        raise ArtifactConflict("completed trials are not in the requested plan")
    execute = executor or (lambda spec: run_trial(spec.config, store))
    newly_executed = 0

    for spec in specs:
        if spec.trial_id in completed:
            continue
        if stop_after is not None and newly_executed >= stop_after:
            break
        with store.claim_trial(spec.trial_id):
            if store.adopt_trial(
                spec.trial_id,
                lambda payload, expected=spec: _validated_result_for_spec(
                    payload,
                    expected,
                ),
            ):
                continue
            result = execute(spec)
            if (
                not isinstance(result, TrialResult)
                or result.trial_id != spec.trial_id
                or result.device_id != spec.device_id
                or result.observation_stream_id != spec.observation_stream_id
                or result.config != spec.config.canonical_dict()
            ):
                raise ArtifactConflict("executor returned a mismatched trial result")
            store.verify_bound_provenance()
            store.publish_trial(spec.trial_id, result.canonical_dict())
            newly_executed += 1

    completed_count = len(store.completed_trial_ids() & expected)
    return SweepStatus(
        expected=len(expected),
        completed=completed_count,
        pending=len(expected) - completed_count,
    )


def read_plan(store: ArtifactStore) -> tuple[TrialSpec, ...]:
    path = store.root / "plan.json"
    if not path.exists():
        if (store.root / "ready.json").exists():
            raise ArtifactConflict("initialized store has no trial plan")
        return ()
    if not (store.root / "ready.json").exists():
        raise ArtifactConflict("trial plan initialization is incomplete")
    ready = store.read_json("ready.json")
    if (
        not isinstance(ready, Mapping)
        or not isinstance(ready.get("plan_sha256"), str)
        or not store.verify_file("plan.json", ready["plan_sha256"])
    ):
        raise ArtifactConflict("trial plan does not match initialization marker")
    payload = store.read_json("plan.json")
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema_version") != 1
        or not isinstance(payload.get("trials"), list)
    ):
        raise ArtifactConflict("invalid trial plan schema")
    try:
        specs = tuple(
            TrialSpec.from_canonical_dict(item) for item in payload["trials"]
        )
    except ValueError as error:
        raise ArtifactConflict("invalid trial plan") from error
    if payload.get("run_kind") != (specs[0].config.run_kind if specs else None):
        raise ArtifactConflict("trial plan run kind is inconsistent")
    if specs != generate_paired_trials(spec.config for spec in specs):
        raise ArtifactConflict("trial plan is not canonical")
    return specs


def sweep_status(specs: Sequence[TrialSpec], store: ArtifactStore) -> SweepStatus:
    expected = {spec.trial_id for spec in specs}
    completed = store.completed_trial_ids() if (store.root / "index.json").exists() else frozenset()
    matching = completed & expected
    return SweepStatus(len(expected), len(matching), len(expected) - len(matching))


def _allowed_files(store: ArtifactStore, specs: Sequence[TrialSpec]) -> set[Path]:
    allowed = {
        Path(".store.lock"),
        Path("index.json"),
        Path("manifest.json"),
        Path("plan.json"),
        Path("ready.json"),
    }
    allowed.update(Path("trials") / f"{spec.trial_id}.json" for spec in specs)
    claims = store.root / "claims"
    if claims.is_dir():
        allowed.update(
            path.relative_to(store.root)
            for path in claims.glob("*.flock")
            if path.is_file() and not path.is_symlink()
        )
    return allowed


def validate_sweep(
    specs: Sequence[TrialSpec],
    store: ArtifactStore,
) -> ValidationReport:
    specs = tuple(specs)
    errors: list[str] = []
    try:
        _bind_plan(specs, store)
        completed = store.completed_trial_ids()
    except ArtifactConflict as error:
        completed = frozenset()
        errors.append(str(error))
    expected = {spec.trial_id for spec in specs}
    missing = expected - completed
    extra = completed - expected
    if missing:
        errors.append(f"missing trials: {len(missing)}")
    if extra:
        errors.append(f"unexpected indexed trials: {len(extra)}")

    by_id = {spec.trial_id: spec for spec in specs}
    for trial_id in sorted(completed & expected):
        try:
            result = TrialResult.from_canonical_dict(
                store.read_json(f"trials/{trial_id}.json")
            )
            spec = by_id[trial_id]
            if (
                result.trial_id != spec.trial_id
                or result.device_id != spec.device_id
                or result.observation_stream_id != spec.observation_stream_id
                or result.config != spec.config.canonical_dict()
            ):
                raise ValueError("trial identity does not match plan")
        except (ArtifactConflict, TypeError, ValueError) as error:
            errors.append(f"invalid trial {trial_id}: {error}")

    allowed = _allowed_files(store, specs)
    for path in store.root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(store.root)
        if (
            relative.parts
            and relative.parts[0] == "claims"
            and relative.suffixes[-2:] == [".owner", ".json"]
        ):
            errors.append(f"unexpected active claim: {relative.as_posix()}")
        elif relative not in allowed:
            errors.append(f"unexpected file: {relative.as_posix()}")
    status = SweepStatus(len(expected), len(completed & expected), len(missing))
    return ValidationReport(not errors, status, tuple(errors))


def default_sweep_configs(kind: str) -> tuple[ExperimentConfig, ...]:
    if kind not in {"development", "production"}:
        raise ValueError("kind must be development or production")
    budget = 2_000 if kind == "production" else 200
    gaps = (
        (0.0, 0.02, 0.05, 0.10, 0.20)
        if kind == "production"
        else (0.0, 0.05)
    )
    seeds = range(20) if kind == "production" else range(3)
    matrices = (
        (
            SystemConfig("two_qubit", 20, 4.0),
            (5, 10, 15, 20, 30, 80),
            (None, 1_000, 10_000),
        ),
        (
            SystemConfig("one_qubit", 12, 4.0),
            (1, 2, 3, 4, 6, 24),
            (None, 1_000),
        ),
    ) if kind == "production" else (
        (
            SystemConfig("one_qubit", 6, 4.0),
            (2, 3),
            (None, 1_000),
        ),
    )
    configs: list[ExperimentConfig] = []
    for system, dimensions, shots in matrices:
        for seed in seeds:
            for gap in gaps:
                for shot_count in shots:
                    for dimension in dimensions:
                        for method in (
                            "full",
                            "model_hessian",
                            "random",
                            "oracle",
                        ):
                            configs.append(
                                ExperimentConfig(
                                    run_kind=kind,
                                    system=system,
                                    device=DeviceConfig(
                                        gap=gap,
                                        shots=shot_count,
                                        perturbation_seed=seed,
                                    ),
                                    search=SearchConfig(
                                        method,
                                        dimension,
                                        budget,
                                    ),
                                    trial_seed=seed,
                                )
                            )
    return tuple(configs)
