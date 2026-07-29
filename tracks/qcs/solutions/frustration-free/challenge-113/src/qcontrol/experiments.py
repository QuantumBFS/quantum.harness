from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from qcontrol.artifacts import ArtifactConflict, ArtifactStore, canonical_json_bytes
from qcontrol.closed_loop import ClosedLoopResult, make_search_space, run_closed_loop
from qcontrol.config import DeviceConfig, ExperimentConfig, SearchConfig, SystemConfig
from qcontrol.device import make_query_device
from qcontrol.landscape import analyze_landscape
from qcontrol.objectives import normalized_infidelity
from qcontrol.open_loop import optimize_open_loop
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system, perturb_system


def _content_id(prefix: str, payload: object, length: int = 24) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:length]
    return f"{prefix}-{digest}"


def _stream_seed(stream_id: str) -> int:
    digest = hashlib.sha256(stream_id.encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big")


def config_from_dict(payload: object) -> ExperimentConfig:
    if not isinstance(payload, Mapping):
        raise ValueError("configuration payload must be a mapping")
    try:
        system = payload["system"]
        device = payload["device"]
        search = payload["search"]
        if not all(isinstance(item, Mapping) for item in (system, device, search)):
            raise ValueError("nested configuration payloads must be mappings")
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
                trial_id=str(payload["trial_id"]),
                device_id=str(payload["device_id"]),
                observation_stream_id=str(payload["observation_stream_id"]),
                config=config_from_dict(payload["config"]),
            )
        except KeyError as error:
            raise ValueError(f"trial specification missing {error.args[0]!r}") from None
        expected = generate_paired_trials([spec.config])
        if len(expected) != 1 or expected[0] != spec:
            raise ValueError("trial specification identities are not canonical")
        return spec


@dataclass(frozen=True, slots=True)
class TrialResult:
    trial_id: str
    device_id: str
    observation_stream_id: str
    config: dict[str, object]
    result: dict[str, object]
    ledger: dict[str, int]
    execution: int | None = None

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (
                self.trial_id,
                self.device_id,
                self.observation_stream_id,
            )
        ):
            raise ValueError("trial identities must be nonempty strings")
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
        if self.execution is not None and (
            isinstance(self.execution, bool)
            or not isinstance(self.execution, int)
            or self.execution <= 0
        ):
            raise ValueError("execution must be a positive integer or None")

    def canonical_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "config": self.config,
            "device_id": self.device_id,
            "ledger": self.ledger,
            "observation_stream_id": self.observation_stream_id,
            "result": self.result,
            "schema_version": 1,
            "trial_id": self.trial_id,
        }
        if self.execution is not None:
            payload["execution"] = self.execution
        return payload

    @classmethod
    def from_canonical_dict(cls, payload: object) -> TrialResult:
        if not isinstance(payload, Mapping) or payload.get("schema_version") != 1:
            raise ValueError("unsupported trial-result schema")
        try:
            result = cls(
                trial_id=payload["trial_id"],
                device_id=payload["device_id"],
                observation_stream_id=payload["observation_stream_id"],
                config=dict(payload["config"]),
                result=dict(payload["result"]),
                ledger={key: int(value) for key, value in payload["ledger"].items()},
                execution=payload.get("execution"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid trial-result payload") from error
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
    closed = run_closed_loop(
        device,
        search_space,
        config.search.budget,
        config.trial_seed,
    )
    ledger = device.ledger
    return TrialResult(
        trial_id=spec.trial_id,
        device_id=spec.device_id,
        observation_stream_id=spec.observation_stream_id,
        config=config.canonical_dict(),
        result=closed.canonical_dict(),
        ledger={
            "optimizer_queries": ledger.optimizer_queries,
            "optimizer_shots": ledger.optimizer_shots,
            "validation_queries": ledger.validation_queries,
            "validation_shots": ledger.validation_shots,
            "total_queries": ledger.total_queries,
            "total_shots": ledger.total_shots,
        },
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
    path = store.root / "plan.json"
    if path.exists():
        if store.read_json("plan.json") != payload:
            raise ArtifactConflict("persisted trial plan does not match requested plan")
        store.bind_provenance(provenance_config)
        return
    store.bind_provenance(provenance_config)
    store.publish_json("plan.json", payload, immutable=True)


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
            if spec.trial_id in store.completed_trial_ids():
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
        return ()
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
    allowed = {Path("plan.json"), Path("index.json"), Path("manifest.json")}
    allowed.update(Path("trials") / f"{spec.trial_id}.json" for spec in specs)
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
            closed = ClosedLoopResult.from_canonical_dict(result.result)
            if closed.evaluations != result.ledger["optimizer_queries"]:
                raise ValueError("closed-loop evaluations do not match ledger")
        except (ArtifactConflict, TypeError, ValueError) as error:
            errors.append(f"invalid trial {trial_id}: {error}")

    allowed = _allowed_files(store, specs)
    for path in store.root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(store.root)
        if relative.parts and relative.parts[0] == "claims":
            errors.append(f"unexpected active claim: {relative.as_posix()}")
        elif relative not in allowed:
            errors.append(f"unexpected file: {relative.as_posix()}")
    status = SweepStatus(len(expected), len(completed & expected), len(missing))
    return ValidationReport(not errors, status, tuple(errors))


def default_sweep_configs(kind: str) -> tuple[ExperimentConfig, ...]:
    if kind not in {"development", "production"}:
        raise ValueError("kind must be development or production")
    production = kind == "production"
    system = SystemConfig(
        "two_qubit" if production else "one_qubit",
        20 if production else 6,
        4.0,
    )
    budget = 2_000 if production else 200
    dimensions = (5, 10, 15) if production else (2, 3)
    gaps = (0.0, 0.02, 0.05, 0.10, 0.20) if production else (0.0, 0.05)
    shots = (None, 1_000, 10_000) if production else (None, 1_000)
    seeds = range(20) if production else range(3)
    configs: list[ExperimentConfig] = []
    for seed in seeds:
        for gap in gaps:
            for shot_count in shots:
                for dimension in dimensions:
                    for method in ("full", "model_hessian", "random", "oracle"):
                        configs.append(
                            ExperimentConfig(
                                run_kind=kind,
                                system=system,
                                device=DeviceConfig(
                                    gap=gap,
                                    shots=shot_count,
                                    perturbation_seed=seed,
                                ),
                                search=SearchConfig(method, dimension, budget),
                                trial_seed=seed,
                            )
                        )
    return tuple(configs)
