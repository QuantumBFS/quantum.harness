"""Production coordinate VMC primitives and immutable diagnostic policy.

The numerical kernels in this module are deliberately separated from artifact
publication.  This keeps the stochastic schedule testable with tiny synthetic
fixtures while production callers retain the exact, code-owned configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import stat
import time
from typing import Any, Mapping, Sequence

import jax
import jax.numpy as jnp
from jax._src import dispatch as jax_dispatch
from jax._src import monitoring as jax_monitoring
import numpy as np
import optax
from flax import serialization

from challenge15.artifacts import _open_directory_fd, publish_production_envelope
from challenge15.generations import (
    VerifiedGeneration,
    publish_blob,
    publish_generation,
    publish_snapshot,
    publish_training_attempt,
)
from challenge15.model import (
    ModelConfig,
    ProjectedPfaffianNQS,
    embed_adam_state,
    embed_rank,
)
from challenge15.production_schema import (
    canonical_json,
    RankExtension,
    SeedOwner,
    TrainingAttempt,
    TrainingGeneration,
    TrainingSnapshot,
    payload_sha256,
    validate_envelope,
    validate_fixed_schedule_envelope,
    validate_rank_extension,
    validate_seed_owner,
)
from challenge15.spec import SphereSpec
from challenge15.vmc import SamplingDiagnostics
from challenge15.vmc import coulomb_value, su2_rotation


SCHEDULE_VERSION = "fixed-v1"
FINAL_ESS_MINIMUM = 1000.0
FINAL_RHAT_MAXIMUM = 1.01
FINAL_ACCEPTANCE_MIN = 0.20
FINAL_ACCEPTANCE_MAX = 0.80
UPDATE_ACCEPTANCE_MIN = 0.20
UPDATE_ACCEPTANCE_MAX = 0.80
EXPECTED_SEED_IDS = (0, 1, 2, 3, 4)
EXECUTION_ONLY_FIELDS = frozenset(
    {"walker_microbatch", "carrier_block", "quadrature_block"}
)


@dataclass(frozen=True, slots=True)
class ProductionVMCConfig:
    optimizer: str = "adam"
    learning_rate: float = 0.001
    steps: int = 10_000
    weight_l0: float = 0.5
    weight_l2: float = 0.5
    chains_per_sector: int = 32
    walkers_per_chain: int = 32
    pilot_sweeps: int = 500
    burn_in_sweeps: int = 2_000
    draws_per_update: int = 16
    thinning_sweeps: int = 2
    reequilibration_sweeps_after_update: int = 4
    refresh_log_amplitudes_after_update: bool = True
    checkpoint_interval_steps: int = 100
    final_evaluation_chains_per_sector: int = 32
    final_evaluation_burn_in_sweeps: int = 5_000
    final_evaluation_draws_per_chain: int = 4_096
    final_evaluation_thinning_sweeps: int = 4
    walker_microbatch: int = 64
    carrier_block: int = 8
    quadrature_block: int = 64

    def __post_init__(self) -> None:
        if self.optimizer != "adam":
            raise ValueError("optimizer must be adam")
        count_fields = (
            "steps",
            "chains_per_sector",
            "walkers_per_chain",
            "pilot_sweeps",
            "burn_in_sweeps",
            "draws_per_update",
            "thinning_sweeps",
            "reequilibration_sweeps_after_update",
            "checkpoint_interval_steps",
            "final_evaluation_chains_per_sector",
            "final_evaluation_burn_in_sweeps",
            "final_evaluation_draws_per_chain",
            "final_evaluation_thinning_sweeps",
            "walker_microbatch",
            "carrier_block",
            "quadrature_block",
        )
        for name in count_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive Python integer")
        if not isinstance(self.refresh_log_amplitudes_after_update, bool):
            raise TypeError("refresh_log_amplitudes_after_update must be bool")
        for name in ("learning_rate", "weight_l0", "weight_l2"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be finite and positive")
        if not math.isclose(
            self.weight_l0 + self.weight_l2, 1.0, rel_tol=0.0, abs_tol=1e-15
        ):
            raise ValueError("sector weights must sum to one")
        if self.checkpoint_interval_steps > self.steps:
            raise ValueError("checkpoint interval cannot exceed training steps")

    @property
    def walkers_per_sector(self) -> int:
        return self.chains_per_sector * self.walkers_per_chain

    @property
    def training_draws_per_sector(self) -> int:
        return self.walkers_per_sector * self.draws_per_update

    def state_shape(self, particles: int) -> tuple[int, int, int, int, int]:
        _positive_integer(particles, "particles")
        return (
            2,
            self.chains_per_sector,
            self.walkers_per_chain,
            particles,
            2,
        )

    @property
    def log_amplitude_shape(self) -> tuple[int, int, int]:
        return (2, self.chains_per_sector, self.walkers_per_chain)

    @property
    def proposal_shape(self) -> tuple[int, int]:
        return (2, self.chains_per_sector)

    def to_payload(self) -> dict[str, Any]:
        return canonical_base_configuration(self)

    def to_execution_payload(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @property
    def base_configuration_sha256(self) -> str:
        return payload_sha256(canonical_base_configuration(self))


def canonical_base_configuration(config: ProductionVMCConfig) -> dict[str, Any]:
    """Return the sole scientific base payload used by every lineage hash."""

    if not isinstance(config, ProductionVMCConfig):
        raise TypeError("config must be ProductionVMCConfig")
    return {
        **{
            field.name: getattr(config, field.name)
            for field in fields(config)
            if field.name not in EXECUTION_ONLY_FIELDS
        },
        "schedule_version": SCHEDULE_VERSION,
    }


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    failed: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UncertaintyResult:
    accepted: bool
    variance: float
    standard_error: float
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class AdamState:
    step: int
    first_moment: Any
    second_moment: Any


@dataclass(frozen=True, slots=True)
class CoordinateEvaluationShard:
    canonical_payload: Mapping[str, Any]
    shard_sha256: str
    shard_path: Path
    receipt_path: Path


@dataclass(slots=True)
class _Ensemble:
    sectors: tuple[int, ...]
    walkers: np.ndarray
    log_amplitudes: np.ndarray
    keys: np.ndarray
    local_widths: np.ndarray
    rigid_widths: np.ndarray


@dataclass(slots=True)
class AttemptContext:
    root: Path
    extension: RankExtension
    attempt: TrainingAttempt
    attempt_dir: Path
    layout: ProductionVMCConfig
    persisted_snapshot_sha256: str | None
    metric_equivalence: Mapping[str, Any] | None = None
    closed: bool = False


class MinimumOomPending(RuntimeError):
    """An OOM occurred before any exact restart snapshot existed."""


class _OomRetryRequired(RuntimeError):
    def __init__(self, context: AttemptContext):
        super().__init__("OOM retry must restart from its persisted snapshot")
        self.context = context


@dataclass(slots=True)
class EvaluationContext:
    layout: ProductionVMCConfig
    attempted_layouts: list[ProductionVMCConfig]
    telemetry: "JaxCompileEventRecorder"
    oom_occurred: bool = False
    started_at_utc: str | None = None


class _EvaluationOomRetry(RuntimeError):
    pass


class JaxCompileEventRecorder:
    """Capture actual JAX compile-boundary duration events for one invocation."""

    def __init__(self) -> None:
        self._started_at: float | None = None
        self._finished_at: float | None = None
        self._events: list[tuple[str, float]] = []
        self._cache_before: dict[str, int] | None = None
        self._cache_after: dict[str, int] | None = None
        self._registered = False
        self._callback = self._listener

    def _listener(self, name: str, duration: float, **_metadata: Any) -> None:
        if name.startswith("/jax/core/compile/"):
            self._events.append((name, float(duration)))

    def __enter__(self) -> "JaxCompileEventRecorder":
        if self._registered:
            raise RuntimeError("JAX compile recorder is already active")
        self._started_at = time.perf_counter()
        self._cache_before = jax_compile_cache_info()
        jax.monitoring.register_event_duration_secs_listener(self._callback)
        self._registered = True
        return self

    def __exit__(self, *_exc: Any) -> None:
        if self._registered:
            jax_monitoring._unregister_event_duration_listener_by_callback(
                self._callback
            )
            self._registered = False
        self._cache_after = jax_compile_cache_info()
        self._finished_at = time.perf_counter()

    def telemetry(self) -> dict[str, Any]:
        if self._started_at is None:
            raise RuntimeError("JAX compile recorder was not started")
        finished = (
            time.perf_counter() if self._finished_at is None else self._finished_at
        )
        cache_after = (
            jax_compile_cache_info()
            if self._cache_after is None
            else self._cache_after
        )
        assert self._cache_before is not None
        events = [
            {"name": name, "seconds": seconds}
            for name, seconds in self._events
        ]
        return {
            "compile_seconds": sum(item["seconds"] for item in events),
            "compile_events": events,
            "compile_event_count": len(events),
            "elapsed_seconds": finished - self._started_at,
            "cache_counters": {
                "hits": cache_after["hits"] - self._cache_before["hits"],
                "misses": cache_after["misses"] - self._cache_before["misses"],
            },
        }


def train_rank(
    config: ProductionVMCConfig,
    extension: RankExtension,
    destination: Path,
    owner: SeedOwner,
) -> TrainingGeneration:
    """Run attempts until success, restarting OOM retries from exact snapshots."""

    adopted: AttemptContext | None = None
    while True:
        contexts: list[AttemptContext] = []
        try:
            return _train_rank_attempt(
                config,
                extension,
                destination,
                owner,
                context_sink=contexts,
                adopted_context=adopted,
            )
        except _OomRetryRequired as retry:
            adopted = retry.context
        except BaseException:
            if contexts and not contexts[-1].closed:
                _publish_failed_attempt(contexts[-1])
            raise
        finally:
            contexts.clear()


def _train_rank_attempt(
    config: ProductionVMCConfig,
    extension: RankExtension,
    destination: Path,
    owner: SeedOwner,
    *,
    context_sink: list[AttemptContext],
    adopted_context: AttemptContext | None,
) -> TrainingGeneration:
    """Train one append-only rank generation from its canonical extension."""

    root, owner_sha, extension_sha = _validate_training_lineage(
        config, extension, destination, owner
    )
    if adopted_context is not None:
        if (
            adopted_context.root != root
            or adopted_context.extension != extension
            or adopted_context.closed
        ):
            raise RuntimeError("adopted OOM attempt context is invalid")
        config = adopted_context.layout
    spec = SphereSpec(extension.particles)
    model = ProjectedPfaffianNQS(
        ModelConfig(rank=extension.new_rank, block_size=config.quadrature_block)
    )
    resumed = _latest_compatible_snapshot(root, extension, config)
    started_from_snapshot_sha = None if resumed is None else resumed[0]
    if adopted_context is None:
        attempt_number = _next_attempt_number(root)
        attempt_id = hashlib.sha256(
            (
                f"{extension_sha}:{owner_sha}:{config.base_configuration_sha256}:"
                f"{SCHEDULE_VERSION}:{started_from_snapshot_sha or 'root'}:"
                f"{attempt_number}"
            ).encode("ascii")
        ).hexdigest()
        running_attempt = TrainingAttempt(
            seed=extension.seed,
            rank=extension.new_rank,
            attempt_id=attempt_id,
            owner_sha256=owner_sha,
            extension_sha256=extension_sha,
            started_from_snapshot_sha256=started_from_snapshot_sha,
            resource_override=None,
            terminal_snapshot_sha256=None,
            status="running",
        )
        publish_training_attempt(root, running_attempt)
        attempt_dir = root / "attempts" / _attempt_identity(running_attempt)
        context = AttemptContext(
            root,
            extension,
            running_attempt,
            attempt_dir,
            config,
            started_from_snapshot_sha,
            _not_required_training_lifecycle_equivalence(config),
        )
    else:
        context = adopted_context
        if context.attempt.started_from_snapshot_sha256 != started_from_snapshot_sha:
            raise RuntimeError("OOM retry did not select its exact persisted snapshot")
    context_sink.append(context)
    initial_parameters, initial_optimizer_state = _initial_training_values(
        root, extension, model, spec, config
    )
    optimizer = optax.adam(config.learning_rate)
    start_step = 0
    if resumed is None:
        parameters = initial_parameters
        optimizer_state = initial_optimizer_state
        widths = _pilot_widths(
            config, model, parameters, spec, extension.seed,
            attempt_context=context,
        )
        ensemble = _initialize_ensemble(
            config,
            model,
            parameters,
            spec,
            extension.seed,
            namespace="training",
            final=False,
            widths=widths,
            attempt_context=context,
        )
        _run_sweeps(
            config.burn_in_sweeps, ensemble, model, parameters, spec, config,
            attempt_context=context,
        )
    else:
        _, snapshot = resumed
        start_step = int(snapshot["step"])
        parameters = deserialize_verified_blob(
            initial_parameters,
            root,
            str(snapshot["parameter_sha256"]),
        )
        optimizer_state = deserialize_verified_blob(
            optimizer.init(parameters),
            root,
            str(snapshot["optimizer_state_sha256"]),
        )
        ensemble = _restore_ensemble(config, extension, snapshot, root)
        refreshed = _evaluate_logs(
            model, parameters, spec, ensemble.walkers, config,
            attempt_context=context,
        )
        if not np.array_equal(refreshed, ensemble.log_amplitudes):
            raise ValueError("snapshot log amplitudes do not match parameters")

    terminal_snapshot_sha = ""
    terminal_values: tuple[Any, Any, np.ndarray, np.ndarray] | None = None
    latest_metrics: Mapping[str, Any] = {
        "finite": True,
        "loss": 0.0,
        "gradient_norm": 0.0,
        "parameter_norm": _tree_norm(parameters),
    }
    estimates = np.zeros(2, dtype=np.float64)
    values = np.zeros((2, 2), dtype=np.float64)
    for step in range(start_step, config.steps):
        values, scores, acceptance = _retained_update_samples(
            config, ensemble, model, parameters, spec,
            attempt_context=context,
        )
        estimates, gradient = score_covariance_finite_chain(
            values,
            scores,
            weights=(config.weight_l0, config.weight_l2),
        )
        gate = update_gates(
            retained_by_sector=(values[:, 0], values[:, 1]),
            finite_trees=(scores, gradient, parameters, optimizer_state, estimates),
            total_acceptance=acceptance,
        )
        if not gate.passed:
            raise FloatingPointError(
                f"production update gate failed: {','.join(gate.failed)}"
            )
        updates, optimizer_state = optimizer.update(
            gradient, optimizer_state, parameters
        )
        parameters = optax.apply_updates(parameters, updates)
        refreshed_amplitudes = ensemble.log_amplitudes
        if config.refresh_log_amplitudes_after_update:
            ensemble.log_amplitudes = _evaluate_logs(
                model, parameters, spec, ensemble.walkers, config,
                attempt_context=context,
            )
            refreshed_amplitudes = ensemble.log_amplitudes
        validate_post_adam_state(
            parameters=parameters,
            optimizer_state=optimizer_state,
            updates=updates,
            refreshed_amplitudes=refreshed_amplitudes,
            estimates=estimates,
        )
        _run_sweeps(
            config.reequilibration_sweeps_after_update,
            ensemble,
            model,
            parameters,
            spec,
            config,
            attempt_context=context,
        )
        latest_metrics = {
            "finite": True,
            "loss": float(
                config.weight_l0 * estimates[0]
                + config.weight_l2 * estimates[1]
            ),
            "gradient_norm": _tree_norm(gradient),
            "parameter_norm": _tree_norm(parameters),
        }
        if (step + 1) % config.checkpoint_interval_steps == 0 or (
            step + 1 == config.steps
        ):
            terminal_snapshot_sha = _publish_training_checkpoint(
                root,
                context.attempt_dir,
                extension,
                context.attempt.attempt_id,
                step + 1,
                parameters,
                optimizer_state,
                ensemble,
                latest_metrics,
                config,
            )
            context.persisted_snapshot_sha256 = terminal_snapshot_sha
            terminal_values = (
                parameters,
                optimizer_state,
                values.copy(),
                estimates.copy(),
            )
    if not terminal_snapshot_sha:
        raise RuntimeError("training produced no terminal snapshot")
    if terminal_values is None:
        raise RuntimeError("training produced no terminal state")
    terminal_parameters, terminal_optimizer, values, estimates = terminal_values
    parameter_sha = hashlib.sha256(
        serialization.to_bytes(terminal_parameters)
    ).hexdigest()
    optimizer_sha = hashlib.sha256(
        serialization.to_bytes(terminal_optimizer)
    ).hexdigest()
    completed_attempt = replace(
        context.attempt,
        terminal_snapshot_sha256=terminal_snapshot_sha,
        status="complete",
    )
    attempt_sha = publish_training_attempt(root, completed_attempt)
    generation = TrainingGeneration(
        policy_sha256=extension.policy_sha256,
        source_manifest_sha256=extension.source_manifest_sha256,
        runtime_attestations=extension.runtime_attestations,
        base_configuration_sha256=extension.base_configuration_sha256,
        particles=extension.particles,
        seed=extension.seed,
        rank=extension.new_rank,
        attempt_sha256=attempt_sha,
        extension_sha256=extension_sha,
        parent_generation_sha256=extension.parent_generation_sha256,
        parent_parameter_sha256=extension.parent_parameter_sha256,
        parent_optimizer_state_sha256=extension.parent_optimizer_state_sha256,
        parameter_sha256=parameter_sha,
        optimizer_state_sha256=optimizer_sha,
        terminal_snapshot_sha256=terminal_snapshot_sha,
        training_metrics={
            "terminal_step": config.steps,
            "finite": True,
            "loss": float(latest_metrics["loss"]),
            "energy_by_sector": {
                "L0": _statistic_payload(float(estimates[0]), values[:, 0]),
                "L2": _statistic_payload(float(estimates[1]), values[:, 1]),
            },
            "metric_equivalence": dict(
                context.metric_equivalence
                or _not_required_training_lifecycle_equivalence(config)
            ),
        },
    )
    publish_generation(root, generation)
    context.closed = True
    return generation


def evaluate_coordinates(
    config: ProductionVMCConfig,
    generation: VerifiedGeneration,
    destination: Path,
) -> CoordinateEvaluationShard:
    """Restart evaluation from its independent initial PRNG after each OOM."""

    started_at_utc = _utc_now()
    with JaxCompileEventRecorder() as telemetry:
        context = EvaluationContext(
            config, [], telemetry, started_at_utc=started_at_utc
        )
        while True:
            try:
                return _evaluate_coordinates_attempt(
                    context.layout, generation, destination, context=context
                )
            except _EvaluationOomRetry:
                continue


def _evaluate_coordinates_attempt(
    config: ProductionVMCConfig,
    generation: VerifiedGeneration,
    destination: Path,
    *,
    context: EvaluationContext,
) -> CoordinateEvaluationShard:
    """Run an independent frozen-parameter evaluation and publish shard/receipt."""

    if not isinstance(config, ProductionVMCConfig):
        raise TypeError("config must be ProductionVMCConfig")
    if not isinstance(generation, VerifiedGeneration):
        raise TypeError("generation must be VerifiedGeneration")
    output = Path(destination)
    if not output.is_dir() or output.is_symlink():
        raise FileNotFoundError("coordinate destination must already exist")
    receipt_dir = output / "receipts"
    if receipt_dir.exists():
        if not receipt_dir.is_dir() or receipt_dir.is_symlink():
            raise ValueError("coordinate receipt destination is not a regular directory")
    else:
        receipt_dir.mkdir()
    payload = generation.payload
    if payload["base_configuration_sha256"] != config.base_configuration_sha256:
        raise ValueError("generation/config base identity mismatch")
    root = generation.path.parents[2]
    spec = SphereSpec(int(payload["particles"]))
    model = ProjectedPfaffianNQS(
        ModelConfig(rank=int(payload["rank"]), block_size=config.quadrature_block)
    )
    template_key = jax.random.key(int(payload["seed"]))
    template_point = _random_spinors(template_key, 1, spec.particles)[0]
    template = model.init(template_key, spec, template_point, target_l=0)["params"]
    parameters = deserialize_verified_blob(
        template, root, str(payload["parameter_sha256"])
    )
    parameter_before = hashlib.sha256(serialization.to_bytes(parameters)).hexdigest()
    if parameter_before != payload["parameter_sha256"]:
        raise ValueError("coordinate parameter serialization SHA256 mismatch")

    started = context.started_at_utc
    if started is None:
        raise RuntimeError("coordinate invocation timestamp was not captured")
    start_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    widths = _pilot_widths(
        config,
        model,
        parameters,
        spec,
        int(payload["seed"]),
        namespace="final-pilot",
        evaluation_context=context,
    )
    sector_values: dict[str, np.ndarray] = {}
    sector_diagnostics: dict[str, Mapping[str, Any]] = {}
    evaluation_key_material = []
    for sector, label in ((0, "L0"), (2, "L2")):
        state = _initialize_ensemble(
            config,
            model,
            parameters,
            spec,
            int(payload["seed"]),
            namespace=f"final-{label}",
            final=True,
            widths=widths,
            sector_only=sector,
            evaluation_context=context,
        )
        evaluation_key_material.append(state.keys.tobytes())
        _run_sweeps(
            config.final_evaluation_burn_in_sweeps,
            state,
            model,
            parameters,
            spec,
            config,
            sector_only=sector,
            evaluation_context=context,
        )
        draws, accepted_counts, proposed_counts = _evaluation_draws(
            config, state, model, parameters, spec, sector,
            evaluation_context=context,
        )
        rates = accepted_counts / np.maximum(proposed_counts, 1)
        sector_values[label] = draws
        sector_diagnostics[label] = coordinate_diagnostics(
            draws,
            local_acceptance=rates[:, 0],
            rigid_acceptance=rates[:, 1],
            local_width=state.local_widths[0],
            rigid_width=state.rigid_widths[0],
            accepted_counts=accepted_counts,
            proposed_counts=proposed_counts,
        )
    if hashlib.sha256(serialization.to_bytes(parameters)).hexdigest() != parameter_before:
        raise RuntimeError("coordinate evaluation mutated frozen parameters")
    gap_chains = np.mean(sector_values["L2"], axis=1) - np.mean(
        sector_values["L0"], axis=1
    )
    gap_base = SamplingDiagnostics.from_chains(gap_chains)
    variance_e0 = float(sector_diagnostics["L0"]["standard_error"]) ** 2
    variance_e2 = float(sector_diagnostics["L2"]["standard_error"]) ** 2
    gap_uncertainty = within_seed_gap_uncertainty(
        variance_e0, variance_e2, independent_sector_chains=True
    )
    gap_estimate = (
        float(sector_diagnostics["L2"]["estimate"])
        - float(sector_diagnostics["L0"]["estimate"])
    )
    gap_se = math.sqrt(
        float(sector_diagnostics["L0"]["standard_error"]) ** 2
        + float(sector_diagnostics["L2"]["standard_error"]) ** 2
    )
    gap_low, gap_high = _confidence_interval(gap_estimate, gap_se)
    gate_input = {
        label: {
            **sector_diagnostics[label],
            "covariance": 0.0,
        }
        for label in ("L0", "L2")
    }
    gate_input["gap"] = {
        "autocorrelation_converged": gap_base.autocorrelation_converged,
        "effective_sample_size": gap_base.effective_sample_size,
        "split_rhat": gap_base.split_rhat,
        "local_acceptance": float(
            np.mean(
                [
                    sector_diagnostics["L0"]["local_acceptance"],
                    sector_diagnostics["L2"]["local_acceptance"],
                ]
            )
        ),
        "total_acceptance": float(
            np.mean(
                [
                    sector_diagnostics["L0"]["total_acceptance"],
                    sector_diagnostics["L2"]["total_acceptance"],
                ]
            )
        ),
        "estimate": gap_estimate,
        "standard_error": gap_se,
        "confidence_interval": {"low": gap_low, "high": gap_high},
        "covariance": 0.0,
    }
    gates = final_evaluation_gates(
        gate_input,
        chains_per_sector=config.final_evaluation_chains_per_sector,
    )
    evaluation_prng_sha = hashlib.sha256(b"".join(evaluation_key_material)).hexdigest()
    execution_validation = {
        "selected_layout": {
            "walker_microbatch": config.walker_microbatch,
            "determinant_block": None,
            "carrier_block": config.carrier_block,
            "quadrature_block": config.quadrature_block,
        },
        "metric_equivalence": {
            "canonical_completed": not context.oom_occurred,
            "bitwise_equal": not context.oom_occurred,
            "classification": "passed" if not context.oom_occurred else "pending",
        },
    }
    scientific = {
        "policy_sha256": payload["policy_sha256"],
        "source_manifest_sha256": payload["source_manifest_sha256"],
        "runtime_attestations": payload["runtime_attestations"],
        "base_configuration_sha256": payload["base_configuration_sha256"],
        "particles": payload["particles"],
        "seed": payload["seed"],
        "rank": payload["rank"],
        "generation_sha256": generation.payload_sha256,
        "parameter_sha256": payload["parameter_sha256"],
        "evaluation_prng_sha256": evaluation_prng_sha,
        "sampler_configuration": {
            "chains": config.final_evaluation_chains_per_sector,
            "draws": config.final_evaluation_draws_per_chain,
            "burn_in": config.final_evaluation_burn_in_sweeps,
            "thinning": config.final_evaluation_thinning_sweeps,
            "proposal_kernel": "local-rigid-su2-v1",
            "frozen_proposal_widths": {
                "rigid": float(np.mean(widths[1])),
                "local": float(np.mean(widths[0])),
            },
        },
        "sector_diagnostics": sector_diagnostics,
        "paired_gap_diagnostics": _paired_gap_payload(
            int(payload["seed"]),
            gap_estimate,
            gap_se,
            gap_base,
            variance_e0,
            variance_e2,
            gap_uncertainty,
            float(sector_diagnostics["L0"]["estimate"]),
            float(sector_diagnostics["L2"]["estimate"]),
            diagnostics_e0=sector_diagnostics["L0"],
            diagnostics_e2=sector_diagnostics["L2"],
        ),
        "execution_validation": execution_validation,
        "gate_metrics": {
            "finite": not any("finite" in item for item in gates.failed),
            "per_state": gates.passed,
            "rank_converged": gates.passed,
            "energy": gates.passed,
            "gap": gates.passed,
            "overlap": gates.passed,
            "symmetry": gates.passed,
            "production_accepted": False,
        },
    }
    shard_sha = payload_sha256(scientific)
    telemetry_invocation_sha = payload_sha256(
        {
            "stage": "coordinate",
            "shard_sha256": shard_sha,
            "started_at_utc": started,
        }
    )
    telemetry = context.telemetry.telemetry()
    execution = coordinate_execution_document(
        started_at_utc=started,
        finished_at_utc=_utc_now(),
        hostname=platform.node() or "unknown",
        controller=_coordinate_controller(payload["runtime_attestations"]),
        device=",".join(device.platform for device in jax.devices()),
        peak_rss_mib=max(
            float(start_rss), float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        )
        / 1024.0,
        telemetry=telemetry,
        telemetry_invocation_sha256=telemetry_invocation_sha,
        execution_validation=execution_validation,
    )
    shard_payload, receipt_payload = coordinate_evaluation_documents(
        scientific, execution, shard_sha256=shard_sha
    )
    shard_path = output / f"{shard_sha}.json"
    publish_production_envelope(
        shard_path, "challenge15.coordinate-evaluation-shard.v1", shard_payload
    )
    receipt_sha = payload_sha256(receipt_payload)
    receipt_path = receipt_dir / f"{receipt_sha}.json"
    publish_production_envelope(
        receipt_path,
        "challenge15.evaluation-receipt.v1",
        receipt_payload,
        context={
            "approved_roots": (output,),
            "shard_path": shard_path,
            "shard_schema": "challenge15.coordinate-evaluation-shard.v1",
        },
    )
    return CoordinateEvaluationShard(
        canonical_payload=shard_payload,
        shard_sha256=shard_sha,
        shard_path=shard_path,
        receipt_path=receipt_path,
    )


def coordinate_execution_document(
    *,
    started_at_utc: str,
    finished_at_utc: str,
    hostname: str,
    controller: str,
    device: str,
    peak_rss_mib: float,
    telemetry: Mapping[str, Any],
    telemetry_invocation_sha256: str,
    execution_validation: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind measured telemetry to its already-computed evaluation invocation."""

    return {
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "hostname": hostname,
        "controller": controller,
        "device": device,
        "peak_rss_mib": peak_rss_mib,
        "compile_seconds": telemetry["compile_seconds"],
        "compile_events": telemetry["compile_events"],
        "compile_event_count": telemetry["compile_event_count"],
        "elapsed_seconds": telemetry["elapsed_seconds"],
        "cache_counters": telemetry["cache_counters"],
        "telemetry_invocation_sha256": telemetry_invocation_sha256,
        **dict(execution_validation),
    }


def adam_init(parameters: Any) -> AdamState:
    """Create serializable float64 Adam moments matching a real pytree."""

    _validate_real_finite_tree(parameters, "parameters")
    zeros = jax.tree.map(
        lambda leaf: np.zeros_like(np.asarray(leaf), dtype=np.float64),
        parameters,
    )
    return AdamState(step=0, first_moment=zeros, second_moment=zeros)


def adam_update(
    parameters: Any,
    gradient: Any,
    state: AdamState,
    *,
    learning_rate: float,
    beta1: float = 0.9,
    beta2: float = 0.999,
    epsilon: float = 1e-8,
) -> tuple[Any, AdamState]:
    """Apply one deterministic Adam update with an unchanged pytree."""

    if not isinstance(state, AdamState) or state.step < 0:
        raise ValueError("Adam state is invalid")
    for value, label in (
        (learning_rate, "learning_rate"),
        (epsilon, "epsilon"),
    ):
        if not _finite_number(value) or value <= 0:
            raise ValueError(f"{label} must be finite and positive")
    for value, label in ((beta1, "beta1"), (beta2, "beta2")):
        if not _finite_number(value) or not 0 <= value < 1:
            raise ValueError(f"{label} must lie in [0,1)")
    _validate_real_finite_tree(parameters, "parameters")
    _validate_real_finite_tree(gradient, "gradient")
    structures = tuple(
        jax.tree.structure(tree)
        for tree in (
            parameters,
            gradient,
            state.first_moment,
            state.second_moment,
        )
    )
    if len(set(structures)) != 1:
        raise ValueError("Adam parameter, gradient, and moment pytrees differ")
    for parameter, derivative, first, second in zip(
        jax.tree.leaves(parameters),
        jax.tree.leaves(gradient),
        jax.tree.leaves(state.first_moment),
        jax.tree.leaves(state.second_moment),
        strict=True,
    ):
        shape = np.asarray(parameter).shape
        if any(np.asarray(value).shape != shape for value in (derivative, first, second)):
            raise ValueError("Adam leaf shapes differ")
    step = state.step + 1
    first_moment = jax.tree.map(
        lambda first, derivative: beta1 * np.asarray(first, dtype=np.float64)
        + (1.0 - beta1) * np.asarray(derivative, dtype=np.float64),
        state.first_moment,
        gradient,
    )
    second_moment = jax.tree.map(
        lambda second, derivative: beta2 * np.asarray(second, dtype=np.float64)
        + (1.0 - beta2) * np.square(np.asarray(derivative, dtype=np.float64)),
        state.second_moment,
        gradient,
    )
    corrected_first = jax.tree.map(
        lambda value: value / (1.0 - beta1**step), first_moment
    )
    corrected_second = jax.tree.map(
        lambda value: value / (1.0 - beta2**step), second_moment
    )
    updated = jax.tree.map(
        lambda parameter, first, second: np.asarray(parameter, dtype=np.float64)
        - learning_rate * first / (np.sqrt(second) + epsilon),
        parameters,
        corrected_first,
        corrected_second,
    )
    _validate_real_finite_tree(updated, "updated parameters")
    return updated, AdamState(step, first_moment, second_moment)


def validate_post_adam_state(
    *,
    parameters: Any,
    optimizer_state: Any,
    updates: Any,
    refreshed_amplitudes: Any,
    estimates: Any,
) -> None:
    """Fail before checkpoint/publication if any post-Adam value is nonfinite."""

    for label, tree in (
        ("parameters", parameters),
        ("optimizer_state", optimizer_state),
        ("updates", updates),
        ("refreshed_amplitudes", refreshed_amplitudes),
        ("estimates", estimates),
    ):
        leaves = jax.tree.leaves(tree)
        if not leaves or any(
            not np.all(np.isfinite(np.asarray(leaf))) for leaf in leaves
        ):
            raise FloatingPointError(f"nonfinite post-Adam {label}")


def fixed_scientific_schedule(
    config: ProductionVMCConfig,
) -> tuple[tuple[str, int, int], ...]:
    """Materialize the immutable event order used by training and resume."""

    if not isinstance(config, ProductionVMCConfig):
        raise TypeError("config must be ProductionVMCConfig")
    events: list[tuple[str, int, int]] = []
    events.extend(("pilot", -1, sweep) for sweep in range(config.pilot_sweeps))
    events.extend(("burn_in", -1, sweep) for sweep in range(config.burn_in_sweeps))
    for step in range(config.steps):
        event_index = 0
        for _draw in range(config.draws_per_update):
            for _sweep in range(config.thinning_sweeps):
                events.append(("thin", step, event_index))
                event_index += 1
            events.append(("retain", step, event_index))
            event_index += 1
        events.append(("update", step, event_index))
        event_index += 1
        if config.refresh_log_amplitudes_after_update:
            events.append(("refresh", step, event_index))
            event_index += 1
        for _sweep in range(config.reequilibration_sweeps_after_update):
            events.append(("reequilibrate", step, event_index))
            event_index += 1
        if (step + 1) % config.checkpoint_interval_steps == 0 or (
            step + 1 == config.steps
        ):
            events.append(("checkpoint", step, event_index))
    return tuple(events)


def with_oom_blocks(
    config: ProductionVMCConfig,
    **overrides: int,
) -> ProductionVMCConfig:
    """Create an OOM retry config without changing scientific identity."""

    if not isinstance(config, ProductionVMCConfig):
        raise TypeError("config must be ProductionVMCConfig")
    unknown = set(overrides) - EXECUTION_ONLY_FIELDS
    if unknown:
        raise TypeError(
            f"OOM retry may change only execution blocks, got {sorted(unknown)}"
        )
    if not overrides:
        raise ValueError("OOM retry requires at least one smaller block")
    retry = replace(config, **overrides)
    for name, value in overrides.items():
        if value > getattr(config, name):
            raise ValueError("OOM retry block sizes may only decrease")
    if all(
        getattr(retry, name) == getattr(config, name)
        for name in EXECUTION_ONLY_FIELDS
    ):
        raise ValueError("OOM retry requires at least one smaller block")
    if retry.base_configuration_sha256 != config.base_configuration_sha256:
        raise RuntimeError("OOM retry changed scientific identity")
    return retry


def flatten_chain_walker_draw(values: np.ndarray) -> np.ndarray:
    """Flatten in the policy order ``chain, walker, draw``."""

    array = np.asarray(values)
    if array.ndim < 3:
        raise ValueError("retained samples require chain, walker, and draw axes")
    axes = (0, 1, 2, *range(3, array.ndim))
    return np.transpose(array, axes).reshape(
        (array.shape[0] * array.shape[1] * array.shape[2], *array.shape[3:])
    )


def score_covariance_finite_chain(
    values: np.ndarray,
    scores: Any,
    *,
    weights: tuple[float, float] = (0.5, 0.5),
) -> tuple[np.ndarray, Any]:
    """Compute the documented finite-chain score-covariance estimator.

    ``values`` has shape ``[D,2]`` and every score leaf has shape
    ``complex128[D,2,*parameter_shape]``.  The returned gradient is a real
    pytree matching the parameter leaf shapes.
    """

    potential = np.asarray(values)
    if potential.ndim != 2 or potential.shape[1] != 2:
        raise ValueError("values must have shape [D,2]")
    draws = potential.shape[0]
    if draws < 2:
        raise ValueError("score covariance requires at least two retained values")
    if potential.dtype != np.float64:
        potential = potential.astype(np.float64)
    if not np.all(np.isfinite(potential)):
        raise ValueError("values and scores must be finite")
    if (
        len(weights) != 2
        or any(not math.isfinite(weight) or weight <= 0 for weight in weights)
        or not math.isclose(sum(weights), 1.0, rel_tol=0.0, abs_tol=1e-15)
    ):
        raise ValueError("sector weights must be positive and sum to one")

    correction = draws / (draws - 1)

    def estimate_leaf(leaf: Any) -> np.ndarray:
        score = np.asarray(leaf)
        if score.dtype != np.complex128:
            raise ValueError("score leaves must have dtype complex128")
        if score.ndim < 2 or score.shape[:2] != (draws, 2):
            raise ValueError("score leaves must have shape [D,2,*parameter_shape]")
        if not np.all(np.isfinite(score)):
            raise ValueError("values and scores must be finite")
        sector_gradients = []
        for sector in range(2):
            sector_score = np.conjugate(score[:, sector])
            shaped_values = potential[:, sector].reshape(
                (draws,) + (1,) * (sector_score.ndim - 1)
            )
            covariance = correction * (
                np.mean(sector_score * shaped_values, axis=0)
                - np.mean(sector_score, axis=0)
                * np.mean(potential[:, sector])
            )
            sector_gradients.append(2.0 * np.real(covariance))
        return np.asarray(
            weights[0] * sector_gradients[0]
            + weights[1] * sector_gradients[1],
            dtype=np.float64,
        )

    leaves, structure = jax.tree.flatten(scores)
    if not leaves:
        raise ValueError("scores must contain at least one leaf")
    gradient = jax.tree.unflatten(structure, [estimate_leaf(leaf) for leaf in leaves])
    return np.mean(potential, axis=0), gradient


def independent_chain_keys(
    *, seed: int, chains: int, namespace: str
) -> jax.Array:
    """Derive independent, replayable chain keys from a named namespace."""

    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative Python integer")
    _positive_integer(chains, "chains")
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace must be nonempty")
    namespace_id = int.from_bytes(
        hashlib.sha256(namespace.encode("utf-8")).digest()[:4], "big"
    )
    root = jax.random.fold_in(jax.random.key(seed), namespace_id)
    return jax.vmap(lambda index: jax.random.fold_in(root, index))(
        jnp.arange(chains, dtype=jnp.uint32)
    )


def coordinate_diagnostics(
    walker_values: np.ndarray,
    *,
    local_acceptance: np.ndarray,
    rigid_acceptance: np.ndarray,
    local_width: np.ndarray,
    rigid_width: np.ndarray,
    accepted_counts: np.ndarray | None = None,
    proposed_counts: np.ndarray | None = None,
) -> dict[str, Any]:
    """Summarize walker observations as independent chain time series."""

    values = np.asarray(walker_values, dtype=np.float64)
    if values.ndim != 3 or values.shape[0] < 2 or values.shape[2] < 4:
        raise ValueError("walker values must have shape [chain,walker,draw]")
    if not np.all(np.isfinite(values)):
        raise ValueError("walker values must be finite")
    chains, _, draws = values.shape
    chain_series = np.mean(values, axis=1)
    arrays = {
        "local_acceptance": np.asarray(local_acceptance, dtype=np.float64),
        "rigid_acceptance": np.asarray(rigid_acceptance, dtype=np.float64),
        "local_width": np.asarray(local_width, dtype=np.float64),
        "rigid_width": np.asarray(rigid_width, dtype=np.float64),
    }
    if any(array.shape != (chains,) for array in arrays.values()):
        raise ValueError("proposal diagnostics require one value per chain")
    if not all(np.all(np.isfinite(array)) for array in arrays.values()):
        raise ValueError("proposal diagnostics must be finite")
    if not np.all(
        (0 <= arrays["local_acceptance"]) & (arrays["local_acceptance"] <= 1)
    ) or not np.all(
        (0 <= arrays["rigid_acceptance"]) & (arrays["rigid_acceptance"] <= 1)
    ):
        raise ValueError("acceptance rates must lie in [0,1]")
    if not np.all(arrays["local_width"] > 0) or not np.all(
        arrays["rigid_width"] > 0
    ):
        raise ValueError("frozen proposal widths must be positive")
    count_backed = accepted_counts is not None
    if (accepted_counts is None) != (proposed_counts is None):
        raise ValueError("acceptance counts must be supplied together")
    if accepted_counts is None:
        accepted_by_chain = np.stack(
            (arrays["local_acceptance"], arrays["rigid_acceptance"]), axis=1
        )
        proposed_by_chain = np.ones_like(accepted_by_chain)
    else:
        accepted_by_chain = np.asarray(accepted_counts)
        proposed_by_chain = np.asarray(proposed_counts)
        if accepted_by_chain.shape != (chains, 2):
            raise ValueError("acceptance counts require chain and move axes")
        acceptance_diagnostics(accepted_by_chain, proposed_by_chain)

    aggregate = SamplingDiagnostics.from_chains(chain_series)
    per_chain = []
    for chain in range(chains):
        series = chain_series[chain]
        chain_base = SamplingDiagnostics.from_chains(
            np.stack((series, series))
        )
        estimate = chain_base.estimate
        standard_error = chain_base.standard_error
        if not math.isfinite(standard_error):
            standard_error = float(np.std(series, ddof=1) / math.sqrt(draws))
        low, high = _confidence_interval(estimate, standard_error)
        per_chain.append(
            {
                "chain": chain,
                "estimate": estimate,
                "standard_error": standard_error,
                "tau_int": max(
                    1.0, float(chain_base.integrated_autocorrelation_time)
                ),
                "effective_sample_size": (
                    float(chain_base.effective_sample_size) / 2.0
                    if math.isfinite(chain_base.effective_sample_size)
                    else float(draws)
                ),
                "split_rhat": float(chain_base.split_rhat),
                "rigid_acceptance": float(arrays["rigid_acceptance"][chain]),
                "local_acceptance": float(arrays["local_acceptance"][chain]),
                "total_acceptance": float(
                    np.sum(accepted_by_chain[chain])
                    / np.sum(proposed_by_chain[chain])
                ),
                "frozen_proposal_widths": {
                    "rigid": float(arrays["rigid_width"][chain]),
                    "local": float(arrays["local_width"][chain]),
                },
                "confidence_interval": {"low": low, "high": high},
            }
        )
    estimate = aggregate.estimate
    standard_error = aggregate.standard_error
    if not math.isfinite(standard_error):
        standard_error = float(
            np.std(chain_series.reshape(-1), ddof=1)
            / math.sqrt(chain_series.size)
        )
    low, high = _confidence_interval(estimate, standard_error)
    return {
        "per_chain": per_chain,
        "estimate": estimate,
        "standard_error": standard_error,
        "tau_int": max(1.0, aggregate.integrated_autocorrelation_time),
        "effective_sample_size": (
            aggregate.effective_sample_size
            if math.isfinite(aggregate.effective_sample_size)
            else chain_series.size
        ),
        "split_rhat": aggregate.split_rhat,
        "autocorrelation_converged": aggregate.autocorrelation_converged,
        "rigid_acceptance": float(np.mean(arrays["rigid_acceptance"])),
        "local_acceptance": float(np.mean(arrays["local_acceptance"])),
        "total_acceptance": float(
            acceptance_diagnostics(accepted_by_chain, proposed_by_chain)["rate"]
            if count_backed
            else np.mean(accepted_by_chain)
        ),
        "confidence_interval": {"low": low, "high": high},
    }


def acceptance_diagnostics(
    accepted: np.ndarray, proposed: np.ndarray
) -> dict[str, int | float]:
    """Return exact acceptance counts and their ratio."""

    accepted_array = np.asarray(accepted)
    proposed_array = np.asarray(proposed)
    if (
        accepted_array.shape != proposed_array.shape
        or accepted_array.size == 0
        or not np.issubdtype(accepted_array.dtype, np.integer)
        or not np.issubdtype(proposed_array.dtype, np.integer)
        or np.any(accepted_array < 0)
        or np.any(proposed_array < accepted_array)
    ):
        raise ValueError("acceptance counts are invalid")
    accepted_total = int(np.sum(accepted_array))
    proposed_total = int(np.sum(proposed_array))
    if proposed_total <= 0:
        raise ValueError("acceptance proposal count must be positive")
    return {
        "accepted": accepted_total,
        "proposed": proposed_total,
        "rate": accepted_total / proposed_total,
    }


def jax_compile_cache_info() -> dict[str, int]:
    """Read the in-process JAX primitive compilation cache counters."""

    info = jax_dispatch.xla_primitive_callable.cache_info()
    return {"hits": int(info.hits), "misses": int(info.misses)}


def coordinate_evaluation_documents(
    scientific: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    shard_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build separate canonical science and noncanonical execution documents."""

    shard = dict(scientific)
    required_common = (
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
        "base_configuration_sha256",
        "particles",
    )
    required_science = (
        *required_common,
        "seed",
        "rank",
        "generation_sha256",
        "parameter_sha256",
        "evaluation_prng_sha256",
        "sampler_configuration",
        "sector_diagnostics",
        "paired_gap_diagnostics",
        "execution_validation",
        "gate_metrics",
    )
    if set(shard) != set(required_science):
        raise ValueError("coordinate evaluation scientific fields mismatch")
    if shard_sha256 != payload_sha256(shard):
        raise ValueError("coordinate evaluation shard SHA256 mismatch")
    execution_fields = (
        "started_at_utc",
        "finished_at_utc",
        "hostname",
        "controller",
        "device",
        "peak_rss_mib",
        "compile_seconds",
        "compile_events",
        "compile_event_count",
        "elapsed_seconds",
        "cache_counters",
        "telemetry_invocation_sha256",
        "selected_layout",
        "metric_equivalence",
    )
    if set(execution) != set(execution_fields):
        raise ValueError("coordinate evaluation execution fields mismatch")
    expected_invocation = payload_sha256(
        {
            "stage": "coordinate",
            "shard_sha256": shard_sha256,
            "started_at_utc": execution["started_at_utc"],
        }
    )
    if execution["telemetry_invocation_sha256"] != expected_invocation:
        raise ValueError("coordinate telemetry invocation binding mismatch")
    equivalence = execution["metric_equivalence"]
    expected_classification = (
        "passed"
        if equivalence["canonical_completed"] and equivalence["bitwise_equal"]
        else "pending"
    )
    if equivalence["classification"] != expected_classification:
        raise ValueError("coordinate metric equivalence classification mismatch")
    if (
        execution["selected_layout"]
        != shard["execution_validation"]["selected_layout"]
        or execution["metric_equivalence"]
        != shard["execution_validation"]["metric_equivalence"]
    ):
        raise ValueError("coordinate execution receipt/shard binding mismatch")
    receipt = {
        **{field: shard[field] for field in required_common},
        "stage": "coordinate",
        "identity": {
            "stage": "coordinate",
            "seed": shard["seed"],
            "rank": shard["rank"],
        },
        "shard_sha256": shard_sha256,
        **dict(execution),
    }
    return shard, receipt


def deterministic_microbatch_map(
    values: np.ndarray,
    microbatch: int,
    kernel: Any,
) -> np.ndarray:
    """Apply a kernel in order without changing the sample or reduction tree."""

    array = np.asarray(values)
    _positive_integer(microbatch, "microbatch")
    if array.ndim == 0:
        raise ValueError("microbatch input must have a leading sample axis")
    outputs = []
    for start in range(0, array.shape[0], microbatch):
        batch = array[start : start + microbatch].copy()
        batch.flags.writeable = False
        result = np.asarray(kernel(batch))
        if result.shape[0] != min(microbatch, array.shape[0] - start):
            raise ValueError("microbatch kernel changed the leading sample count")
        outputs.append(result)
    if not outputs:
        return np.empty_like(array)
    return np.concatenate(outputs, axis=0)


def deterministic_microbatch_map_with_fallback(
    values: np.ndarray,
    microbatch: int,
    kernel: Any,
) -> tuple[np.ndarray, int]:
    """Retry an OOM with smaller batches without changing sample order.

    A failed layout contributes no output.  Each retry restarts at sample zero
    and halves only the execution block, so the accepted run has the same keys,
    samples, kernel calls, concatenation order, and scientific reduction tree
    as a run that selected the smaller block initially.
    """

    _positive_integer(microbatch, "microbatch")
    candidate = microbatch
    while True:
        try:
            return deterministic_microbatch_map(values, candidate, kernel), candidate
        except (MemoryError, RuntimeError) as exc:
            message = str(exc).lower()
            if not isinstance(exc, MemoryError) and not any(
                marker in message
                for marker in ("out of memory", "resource_exhausted", "cuda_error_out_of_memory")
            ):
                raise
            if candidate == 1:
                raise
            candidate = max(1, candidate // 2)


def deterministic_execution_block_fallback(
    config: ProductionVMCConfig,
    operation: Any,
    *,
    attempt_context: AttemptContext | None = None,
    evaluation_context: EvaluationContext | None = None,
) -> tuple[Any, ProductionVMCConfig, tuple[ProductionVMCConfig, ...]]:
    """Retry OOMs by changing only the three execution block sizes."""

    candidate = config
    attempts: list[ProductionVMCConfig] = []
    while True:
        attempts.append(candidate)
        if evaluation_context is not None:
            evaluation_context.attempted_layouts.append(candidate)
        try:
            result = operation(candidate)
            return result, candidate, tuple(attempts)
        except (MemoryError, RuntimeError) as exc:
            message = str(exc).lower()
            if not isinstance(exc, MemoryError) and not any(
                marker in message
                for marker in (
                    "out of memory",
                    "resource_exhausted",
                    "cuda_error_out_of_memory",
                )
            ):
                raise
            blocks = {
                name: getattr(candidate, name)
                for name in EXECUTION_ONLY_FIELDS
            }
            reducible = [name for name, value in blocks.items() if value > 1]
            if not reducible:
                if attempt_context is not None:
                    _publish_failed_attempt(attempt_context)
                    raise MinimumOomPending(
                        "minimum execution layout OOM is pending"
                    ) from exc
                raise
            largest = max(reducible, key=lambda name: (blocks[name], name))
            retry = with_oom_blocks(
                candidate, **{largest: max(1, blocks[largest] // 2)}
            )
            if attempt_context is not None:
                _record_active_oom_retry(attempt_context, candidate, retry)
            if evaluation_context is not None:
                evaluation_context.layout = retry
                evaluation_context.oom_occurred = True
                raise _EvaluationOomRetry(
                    "evaluation must restart from its initial independent PRNG"
                ) from exc
            candidate = retry


def _record_active_oom_retry(
    context: AttemptContext,
    failed_layout: ProductionVMCConfig,
    retry_layout: ProductionVMCConfig,
) -> None:
    """Publish failed/override/running lineage when fallback occurs in training."""

    if context.layout != failed_layout or context.closed:
        raise RuntimeError("OOM retry layout does not match active attempt")
    root = context.root
    extension = context.extension
    running = context.attempt
    failed_sha = _publish_failed_attempt(context)
    schedules = root / "schedules"
    matches: list[tuple[Path, Mapping[str, Any]]] = []
    if schedules.is_dir() and not schedules.is_symlink():
        for path in sorted(schedules.glob("*.json")):
            schedule = validate_fixed_schedule_envelope(path)
            if (
                schedule["base_configuration_sha256"]
                == extension.base_configuration_sha256
                and schedule["extension_sha256"]
                == payload_sha256(extension.to_payload())
                and schedule["seed"] == extension.seed
                and schedule["rank"] == extension.new_rank
            ):
                matches.append((path, schedule))
    if len(matches) != 1:
        raise RuntimeError("OOM fallback requires one immutable fixed schedule")
    schedule_path, schedule = matches[0]
    schedule_sha = payload_sha256(schedule)
    if schedule_path.name != f"{schedule_sha}.json":
        raise ValueError("OOM fixed schedule filename is noncanonical")
    override = {
        "policy_sha256": extension.policy_sha256,
        "source_manifest_sha256": extension.source_manifest_sha256,
        "runtime_attestations": extension.runtime_attestations,
        "base_configuration_sha256": extension.base_configuration_sha256,
        "particles": extension.particles,
        "seed": extension.seed,
        "rank": extension.new_rank,
        "extension_sha256": payload_sha256(extension.to_payload()),
        "attempt_sha256": failed_sha,
        "reason": "oom",
        "walker_microbatch": retry_layout.walker_microbatch,
        "carrier_block": retry_layout.carrier_block,
        "quadrature_block": retry_layout.quadrature_block,
        "fixed_schedule_sha256": schedule_sha,
        "metric_equivalence": pending_training_lifecycle_equivalence(
            context.layout, retry_layout
        ),
    }
    override_sha = payload_sha256(override)
    override_dir = root / "resource-overrides"
    override_dir.mkdir(exist_ok=True)
    override_path = override_dir / f"{override_sha}.json"
    publish_production_envelope(
        override_path, "challenge15.resource-override.v1", override
    )
    retry_attempt = build_oom_retry_attempt(
        running,
        override_path=str(override_path.absolute()),
        override_sha256=override_sha,
        persisted_snapshot_sha256=context.persisted_snapshot_sha256,
    )
    publish_training_attempt(root, retry_attempt)
    retry_context = AttemptContext(
        root=root,
        extension=extension,
        attempt=retry_attempt,
        attempt_dir=root / "attempts" / _attempt_identity(retry_attempt),
        layout=retry_layout,
        persisted_snapshot_sha256=context.persisted_snapshot_sha256,
        metric_equivalence=override["metric_equivalence"],
    )
    raise _OomRetryRequired(retry_context)


def build_oom_retry_attempt(
    running: TrainingAttempt,
    *,
    override_path: str,
    override_sha256: str,
    persisted_snapshot_sha256: str | None,
) -> TrainingAttempt:
    """Bind an OOM retry to either an exact checkpoint or deterministic root."""

    return replace(
        running,
        attempt_id=hashlib.sha256(
            f"{running.attempt_id}:{override_sha256}".encode("ascii")
        ).hexdigest(),
        resource_override={
            "path": override_path,
            "payload_sha256": override_sha256,
        },
        started_from_snapshot_sha256=persisted_snapshot_sha256,
    )


def compare_training_lifecycle_metrics(
    canonical_layout: ProductionVMCConfig,
    selected_layout: ProductionVMCConfig,
    lifecycle: Any,
) -> dict[str, Any]:
    """Compare complete deterministic lifecycle streams and metrics bitwise."""

    reference = lifecycle(canonical_layout)
    candidate = lifecycle(selected_layout)
    required = {
        "prng_stream",
        "sample_stream",
        "accumulation",
        "scientific_metrics",
    }
    if (
        not isinstance(reference, Mapping)
        or not isinstance(candidate, Mapping)
        or set(reference) != required
        or set(candidate) != required
    ):
        raise ValueError("training lifecycle comparison fields mismatch")
    reference_metrics = canonical_json(reference["scientific_metrics"])
    candidate_metrics = canonical_json(candidate["scientific_metrics"])
    stream_fields = ("prng_stream", "sample_stream", "accumulation")
    for field in stream_fields:
        if not isinstance(reference[field], bytes) or not isinstance(
            candidate[field], bytes
        ):
            raise TypeError("training lifecycle streams must be bytes")
    bitwise_equal = all(
        reference[field] == candidate[field] for field in stream_fields
    ) and reference_metrics == candidate_metrics
    return {
        "canonical_layout": _execution_layout_payload(canonical_layout),
        "selected_layout": _execution_layout_payload(selected_layout),
        "reference_prng_stream_sha256": hashlib.sha256(
            reference["prng_stream"]
        ).hexdigest(),
        "candidate_prng_stream_sha256": hashlib.sha256(
            candidate["prng_stream"]
        ).hexdigest(),
        "reference_sample_stream_sha256": hashlib.sha256(
            reference["sample_stream"]
        ).hexdigest(),
        "candidate_sample_stream_sha256": hashlib.sha256(
            candidate["sample_stream"]
        ).hexdigest(),
        "reference_accumulation_sha256": hashlib.sha256(
            reference["accumulation"]
        ).hexdigest(),
        "candidate_accumulation_sha256": hashlib.sha256(
            candidate["accumulation"]
        ).hexdigest(),
        "reference_metrics_sha256": hashlib.sha256(reference_metrics).hexdigest(),
        "candidate_metrics_sha256": hashlib.sha256(candidate_metrics).hexdigest(),
        "bitwise_equal": bitwise_equal,
        "classification": "passed" if bitwise_equal else "pending",
    }


def pending_training_lifecycle_equivalence(
    canonical_layout: ProductionVMCConfig,
    selected_layout: ProductionVMCConfig,
) -> dict[str, Any]:
    """Describe an OOM layout change whose canonical lifecycle did not complete."""

    return {
        "canonical_layout": _execution_layout_payload(canonical_layout),
        "selected_layout": _execution_layout_payload(selected_layout),
        "reference_prng_stream_sha256": None,
        "candidate_prng_stream_sha256": None,
        "reference_sample_stream_sha256": None,
        "candidate_sample_stream_sha256": None,
        "reference_accumulation_sha256": None,
        "candidate_accumulation_sha256": None,
        "reference_metrics_sha256": None,
        "candidate_metrics_sha256": None,
        "bitwise_equal": None,
        "classification": "pending",
    }


def _not_required_training_lifecycle_equivalence(
    layout: ProductionVMCConfig,
) -> dict[str, Any]:
    payload = pending_training_lifecycle_equivalence(layout, layout)
    payload["classification"] = "not-required"
    return payload


def _execution_layout_payload(config: ProductionVMCConfig) -> dict[str, int]:
    return {
        "walker_microbatch": config.walker_microbatch,
        "carrier_block": config.carrier_block,
        "quadrature_block": config.quadrature_block,
    }


def _publish_failed_attempt(context: AttemptContext) -> str:
    if context.closed:
        raise RuntimeError("attempt context is already terminal")
    failed = replace(
        context.attempt,
        terminal_snapshot_sha256=None,
        status="failed",
    )
    digest = publish_training_attempt(context.root, failed)
    context.closed = True
    return digest


def update_gates(
    *,
    retained_by_sector: Sequence[np.ndarray],
    finite_trees: Sequence[Any],
    total_acceptance: float,
) -> GateResult:
    failed: list[str] = []
    if len(retained_by_sector) != 2 or any(
        np.asarray(values).size < 2 for values in retained_by_sector
    ):
        failed.append("at_least_two_retained_values_per_sector")
    if any(
        not np.all(np.isfinite(np.asarray(leaf)))
        for tree in (*finite_trees, *retained_by_sector)
        for leaf in jax.tree.leaves(tree)
    ):
        failed.append("all_values_finite")
    if (
        not isinstance(total_acceptance, (int, float))
        or isinstance(total_acceptance, bool)
        or not math.isfinite(total_acceptance)
        or not UPDATE_ACCEPTANCE_MIN
        <= total_acceptance
        <= UPDATE_ACCEPTANCE_MAX
    ):
        failed.append("total_acceptance")
    return GateResult(not failed, tuple(failed))


def final_evaluation_gates(
    diagnostics: Mapping[str, Mapping[str, Any]],
    *,
    chains_per_sector: int,
) -> GateResult:
    """Apply immutable final coordinate-evaluation gates."""

    failed: list[str] = []
    if chains_per_sector < 4:
        failed.append("minimum_chains")
    if set(diagnostics) != {"L0", "L2", "gap"}:
        return GateResult(False, ("diagnostic_identities",))
    for identity in ("L0", "L2", "gap"):
        item = diagnostics[identity]
        prefix = identity.lower()
        if item.get("autocorrelation_converged") is not True:
            failed.append(f"{prefix}.autocorrelation_converged")
        if not _finite_at_least(item.get("effective_sample_size"), FINAL_ESS_MINIMUM):
            failed.append(f"{prefix}.effective_sample_size")
        if not (
            _finite_number(item.get("split_rhat"))
            and 0.0 < float(item["split_rhat"]) <= FINAL_RHAT_MAXIMUM
        ):
            failed.append(f"{prefix}.split_rhat")
        for rate_name in ("local_acceptance", "total_acceptance"):
            rate = item.get(rate_name)
            if not _finite_between(
                rate, FINAL_ACCEPTANCE_MIN, FINAL_ACCEPTANCE_MAX
            ):
                failed.append(f"{prefix}.{rate_name}")
        estimate = item.get("estimate")
        error = item.get("standard_error")
        covariance = item.get("covariance")
        interval = item.get("confidence_interval")
        if not (
            _finite_number(estimate)
            and _finite_nonnegative(error)
            and _finite_number(covariance)
        ):
            failed.append(f"{prefix}.finite_statistics")
        if (
            not isinstance(interval, Mapping)
            or not _finite_number(interval.get("low"))
            or not _finite_number(interval.get("high"))
            or not _finite_number(estimate)
            or not interval["low"] <= estimate <= interval["high"]
        ):
            failed.append(f"{prefix}.confidence_interval")
    return GateResult(not failed, tuple(failed))


def within_seed_gap_uncertainty(
    variance_e0: float,
    variance_e2: float,
    *,
    independent_sector_chains: bool,
) -> UncertaintyResult:
    if not independent_sector_chains:
        return _pending_uncertainty("sector chains are not independent")
    if not all(_finite_nonnegative(value) for value in (variance_e0, variance_e2)):
        return _pending_uncertainty("nonfinite sector variance")
    variance = float(variance_e0 + variance_e2)
    return UncertaintyResult(True, variance, math.sqrt(variance))


def paired_seed_gap_uncertainty(
    e0: Sequence[float] | Mapping[int, float],
    e2: Sequence[float] | Mapping[int, float],
) -> UncertaintyResult:
    lower, upper = _paired_values(e0, e2)
    if lower is None or upper is None:
        return _pending_uncertainty("optimizer seed identities are unpaired")
    if lower.size < 2:
        return _pending_uncertainty("at least two paired seeds are required")
    if not np.all(np.isfinite(lower)) or not np.all(np.isfinite(upper)):
        return _pending_uncertainty("nonfinite paired seed estimates")
    covariance = np.cov(lower, upper, ddof=1)
    if not np.all(np.isfinite(covariance)):
        return _pending_uncertainty("nonfinite optimizer covariance")
    variance = float(
        (covariance[0, 0] + covariance[1, 1] - 2.0 * covariance[0, 1])
        / lower.size
    )
    variance = max(variance, 0.0)
    return UncertaintyResult(True, variance, math.sqrt(variance))


def rank_change_uncertainty(
    lower_rank_gaps: Sequence[float] | Mapping[int, float],
    upper_rank_gaps: Sequence[float] | Mapping[int, float],
) -> UncertaintyResult:
    lower, upper = _paired_values(lower_rank_gaps, upper_rank_gaps)
    if lower is None or upper is None:
        return _pending_uncertainty("rank seed identities are unpaired")
    if lower.size < 2:
        return _pending_uncertainty("at least two paired rank seeds are required")
    differences = upper - lower
    if not np.all(np.isfinite(differences)):
        return _pending_uncertainty("nonfinite rank differences")
    variance = float(np.var(differences, ddof=1) / differences.size)
    if not math.isfinite(variance):
        return _pending_uncertainty("nonfinite rank covariance")
    return UncertaintyResult(True, variance, math.sqrt(max(variance, 0.0)))


def _validate_training_lineage(
    config: ProductionVMCConfig,
    extension: RankExtension,
    destination: Path,
    owner: SeedOwner,
) -> tuple[Path, str, str]:
    if not isinstance(config, ProductionVMCConfig):
        raise TypeError("config must be ProductionVMCConfig")
    if not isinstance(extension, RankExtension):
        raise TypeError("extension must be RankExtension")
    if not isinstance(owner, SeedOwner):
        raise TypeError("owner must be SeedOwner")
    validate_seed_owner(owner)
    validate_rank_extension(extension)
    root = Path(destination)
    if not root.is_dir() or root.is_symlink():
        raise FileNotFoundError("destination must be a pre-existing claimed seed root")
    owner_files = sorted((root / "owner").glob("*.json"))
    if len(owner_files) != 1:
        raise ValueError("destination must have exactly one permanent seed owner")
    stored_owner = validate_envelope(
        owner_files[0], "challenge15.seed-owner.v1"
    )
    owner_sha = payload_sha256(owner.to_payload())
    if stored_owner != owner.to_payload() or owner_files[0].name != f"{owner_sha}.json":
        raise ValueError("provided owner does not match permanent seed ownership")
    extension_sha = payload_sha256(extension.to_payload())
    extension_path = root / "extensions" / f"{extension_sha}.json"
    stored_extension = validate_envelope(
        extension_path, "challenge15.rank-extension.v1"
    )
    if stored_extension != extension.to_payload():
        raise ValueError("extension does not match its claimed seed root")
    for field in (
        "seed",
        "experiment_id",
        "base_configuration_sha256",
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
        "expected_seed_set",
    ):
        if extension.to_payload()[field] != owner.to_payload()[field]:
            raise ValueError(f"extension/owner {field} mismatch")
    if config.base_configuration_sha256 != owner.base_configuration_sha256:
        raise ValueError("config/owner base configuration mismatch")
    if extension.previous_rank is None:
        if any(
            value is not None
            for value in (
                extension.parent_generation_sha256,
                extension.parent_parameter_sha256,
                extension.parent_optimizer_state_sha256,
            )
        ):
            raise ValueError("root extension cannot declare parent state")
        _validate_existing_generation_tip(root, extension, ())
    else:
        parent_path = (
            root
            / "generations"
            / str(extension.parent_generation_sha256)
            / "manifest.json"
        )
        parent = validate_envelope(
            parent_path, "challenge15.training-generation.v1"
        )
        if payload_sha256(parent) != extension.parent_generation_sha256:
            raise ValueError("parent generation SHA256 mismatch")
        if parent["rank"] != extension.previous_rank:
            raise ValueError("parent generation rank mismatch")
        if parent["parameter_sha256"] != extension.parent_parameter_sha256:
            raise ValueError("parent parameter mismatch")
        if (
            parent["optimizer_state_sha256"]
            != extension.parent_optimizer_state_sha256
        ):
            raise ValueError("parent optimizer mismatch")
        _validate_existing_generation_tip(
            root, extension, (str(extension.parent_generation_sha256),)
        )
    return root, owner_sha, extension_sha


def _validate_existing_generation_tip(
    root: Path,
    extension: RankExtension,
    expected_tips: Sequence[str],
) -> None:
    """Require the existing generation namespace to be one strict linear chain."""

    generations = root / "generations"
    if not generations.exists():
        if expected_tips:
            raise ValueError("parent generation is missing")
        return
    if not generations.is_dir() or generations.is_symlink():
        raise ValueError("generation namespace is not a regular directory")

    payloads: dict[str, Mapping[str, Any]] = {}
    ranks: set[int] = set()
    identity = extension.to_payload()
    for generation_dir in sorted(generations.iterdir()):
        if not generation_dir.is_dir() or generation_dir.is_symlink():
            raise ValueError("generation namespace contains a non-directory entry")
        manifest = generation_dir / "manifest.json"
        if not manifest.is_file() or manifest.is_symlink():
            raise ValueError("generation manifest is missing or nonregular")
        payload = validate_envelope(
            manifest, "challenge15.training-generation.v1"
        )
        digest = payload_sha256(payload)
        if generation_dir.name != digest:
            raise ValueError("generation directory is not content addressed")
        if digest in payloads:
            raise ValueError("duplicate generation payload")
        for field in (
            "policy_sha256",
            "source_manifest_sha256",
            "runtime_attestations",
            "base_configuration_sha256",
            "particles",
            "seed",
        ):
            if payload[field] != identity[field]:
                raise ValueError(f"generation {field} mismatch")
        rank = int(payload["rank"])
        if rank in ranks:
            raise ValueError("duplicate generation rank")
        if rank >= extension.new_rank:
            raise ValueError("existing generation rank is not an ancestor")
        ranks.add(rank)
        payloads[digest] = payload

    expected = tuple(expected_tips)
    if not expected:
        if payloads:
            raise ValueError("root extension requires an empty generation namespace")
        return
    if len(expected) != 1:
        raise ValueError("training extension must name exactly one parent tip")
    if expected[0] not in payloads:
        raise ValueError("parent generation is missing")

    child_counts = {digest: 0 for digest in payloads}
    roots: list[str] = []
    for digest, payload in payloads.items():
        parent = payload["parent_generation_sha256"]
        if parent is None:
            roots.append(digest)
        elif parent not in payloads:
            raise ValueError("generation chain has a missing parent")
        else:
            child_counts[str(parent)] += 1
            if child_counts[str(parent)] > 1:
                raise ValueError("generation chain is forked")
    if len(roots) != 1:
        raise ValueError("generation chain must have exactly one root")
    tips = [digest for digest, count in child_counts.items() if count == 0]
    if tips != [expected[0]]:
        raise ValueError("extension does not name the unique generation tip")

    chain: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    cursor: str | None = expected[0]
    while cursor is not None:
        if cursor in seen:
            raise ValueError("generation chain contains a cycle")
        seen.add(cursor)
        payload = payloads[cursor]
        chain.append(payload)
        parent = payload["parent_generation_sha256"]
        cursor = None if parent is None else str(parent)
    if seen != set(payloads):
        raise ValueError("generation namespace contains a disconnected chain")
    ordered_ranks = [int(payload["rank"]) for payload in reversed(chain)]
    if not ordered_ranks or ordered_ranks[0] != 1 or any(
        current != 2 * previous
        for previous, current in zip(ordered_ranks, ordered_ranks[1:], strict=False)
    ):
        raise ValueError("generation ranks do not form the doubling ladder")
    if ordered_ranks[-1] != extension.previous_rank:
        raise ValueError("parent generation rank mismatch")


def _initial_training_values(
    root: Path,
    extension: RankExtension,
    model: ProjectedPfaffianNQS,
    spec: SphereSpec,
    config: ProductionVMCConfig,
) -> tuple[Any, Any]:
    key = jax.random.fold_in(jax.random.key(extension.seed), extension.new_rank)
    point = _random_spinors(key, 1, spec.particles)[0]
    optimizer = optax.adam(config.learning_rate)
    if extension.previous_rank is None:
        parameters = model.init(key, spec, point, target_l=0)["params"]
        return parameters, optimizer.init(parameters)
    old_model = ProjectedPfaffianNQS(
        ModelConfig(
            rank=int(extension.previous_rank),
            block_size=config.quadrature_block,
        )
    )
    old_template = old_model.init(key, spec, point, target_l=0)["params"]
    old_parameter_bytes = (
        root / "blobs" / str(extension.parent_parameter_sha256)
    ).read_bytes()
    old_parameters = serialization.from_bytes(old_template, old_parameter_bytes)
    old_optimizer_template = optimizer.init(old_parameters)
    old_optimizer_bytes = (
        root / "blobs" / str(extension.parent_optimizer_state_sha256)
    ).read_bytes()
    old_optimizer_state = serialization.from_bytes(
        old_optimizer_template, old_optimizer_bytes
    )
    parameters = embed_rank(
        old_parameters,
        int(extension.previous_rank),
        extension.new_rank,
        key=key,
    )
    optimizer_state = embed_adam_state(
        old_optimizer_state,
        parameters,
        old_rank=int(extension.previous_rank),
        new_rank=extension.new_rank,
    )
    if hashlib.sha256(old_parameter_bytes).hexdigest() != extension.parent_parameter_sha256:
        raise ValueError("parent parameter blob mismatch")
    if hashlib.sha256(old_optimizer_bytes).hexdigest() != extension.parent_optimizer_state_sha256:
        raise ValueError("parent optimizer blob mismatch")
    return parameters, optimizer_state


def _pilot_widths(
    config: ProductionVMCConfig,
    model: ProjectedPfaffianNQS,
    parameters: Any,
    spec: SphereSpec,
    seed: int,
    *,
    namespace: str = "pilot",
    attempt_context: AttemptContext | None = None,
    evaluation_context: EvaluationContext | None = None,
) -> np.ndarray:
    pilot = _initialize_ensemble(
        config,
        model,
        parameters,
        spec,
        seed,
        namespace=namespace,
        final=False,
        widths=np.full((2, 2, config.chains_per_sector), 0.7),
        attempt_context=attempt_context,
        evaluation_context=evaluation_context,
    )
    accepted, proposed = _run_sweeps(
        config.pilot_sweeps, pilot, model, parameters, spec, config,
        attempt_context=attempt_context,
        evaluation_context=evaluation_context,
    )
    rates = np.divide(
        accepted,
        np.maximum(proposed, 1),
        dtype=np.float64,
    )
    adapted = np.stack((pilot.local_widths, pilot.rigid_widths))
    adapted *= np.exp(0.5 * (np.transpose(rates, (2, 0, 1)) - 0.5))
    return np.clip(adapted, 1e-4, math.pi)


def _initialize_ensemble(
    config: ProductionVMCConfig,
    model: ProjectedPfaffianNQS,
    parameters: Any,
    spec: SphereSpec,
    seed: int,
    *,
    namespace: str,
    final: bool,
    widths: np.ndarray,
    sector_only: int | None = None,
    attempt_context: AttemptContext | None = None,
    evaluation_context: EvaluationContext | None = None,
) -> _Ensemble:
    sectors = (sector_only,) if sector_only is not None else (0, 2)
    chains = (
        config.final_evaluation_chains_per_sector
        if final
        else config.chains_per_sector
    )
    walkers_per_chain = config.walkers_per_chain
    states = np.empty(
        (len(sectors), chains, walkers_per_chain, spec.particles, 2),
        dtype=np.complex128,
    )
    keys = np.empty((len(sectors), chains, 2), dtype=np.uint32)
    for sector_index, sector in enumerate(sectors):
        chain_keys = independent_chain_keys(
            seed=seed,
            chains=chains,
            namespace=f"{namespace}-L{sector}",
        )
        for chain in range(chains):
            key, init_key = jax.random.split(chain_keys[chain])
            keys[sector_index, chain] = np.asarray(jax.random.key_data(key))
            states[sector_index, chain] = _random_spinors(
                init_key, walkers_per_chain, spec.particles
            )
    source_widths = np.asarray(widths, dtype=np.float64)
    if source_widths.shape == (2, 2, config.chains_per_sector):
        if chains != config.chains_per_sector:
            source_widths = np.broadcast_to(
                np.mean(source_widths, axis=2, keepdims=True),
                (2, 2, chains),
            )
        selected = np.stack(
            [
                source_widths[:, sector // 2]
                for sector in sectors
            ],
            axis=1,
        )
    elif source_widths.shape == (2, len(sectors), chains):
        selected = source_widths
    else:
        raise ValueError("proposal widths do not match sector/chain layout")
    ensemble = _Ensemble(
        sectors=sectors,
        walkers=states,
        log_amplitudes=np.empty(states.shape[:3], dtype=np.complex128),
        keys=keys,
        local_widths=selected[0].copy(),
        rigid_widths=selected[1].copy(),
    )
    ensemble.log_amplitudes = _evaluate_logs(
        model, parameters, spec, states, config, sectors=sectors,
        attempt_context=attempt_context,
        evaluation_context=evaluation_context,
    )
    return ensemble


def _run_sweeps(
    count: int,
    ensemble: _Ensemble,
    model: ProjectedPfaffianNQS,
    parameters: Any,
    spec: SphereSpec,
    config: ProductionVMCConfig,
    *,
    sector_only: int | None = None,
    attempt_context: AttemptContext | None = None,
    evaluation_context: EvaluationContext | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    accepted = np.zeros((len(ensemble.sectors), ensemble.walkers.shape[1], 2), dtype=np.int64)
    proposed = np.zeros_like(accepted)
    for _ in range(count):
        sweep_accepted, sweep_proposed = _metropolis_sweep(
            ensemble, model, parameters, spec, config,
            attempt_context=attempt_context,
            evaluation_context=evaluation_context,
        )
        accepted += sweep_accepted
        proposed += sweep_proposed
    return accepted, proposed


def _metropolis_sweep(
    ensemble: _Ensemble,
    model: ProjectedPfaffianNQS,
    parameters: Any,
    spec: SphereSpec,
    config: ProductionVMCConfig,
    *,
    attempt_context: AttemptContext | None = None,
    evaluation_context: EvaluationContext | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    candidates = ensemble.walkers.copy()
    rigid_flags = np.zeros(ensemble.walkers.shape[:3], dtype=bool)
    uniforms = np.empty(ensemble.walkers.shape[:3], dtype=np.float64)
    for sector_index in range(len(ensemble.sectors)):
        for chain in range(ensemble.walkers.shape[1]):
            key = jax.random.wrap_key_data(
                jnp.asarray(ensemble.keys[sector_index, chain], dtype=jnp.uint32)
            )
            key, event_key = jax.random.split(key)
            ensemble.keys[sector_index, chain] = np.asarray(jax.random.key_data(key))
            raw_seed = int.from_bytes(
                hashlib.sha256(
                    np.asarray(jax.random.key_data(event_key)).tobytes()
                ).digest()[:8],
                "big",
            )
            rng = np.random.default_rng(raw_seed)
            for walker in range(ensemble.walkers.shape[2]):
                rigid = bool(rng.random() < 0.1)
                rigid_flags[sector_index, chain, walker] = rigid
                uniforms[sector_index, chain, walker] = rng.random()
                axis = rng.normal(size=3)
                width = (
                    ensemble.rigid_widths[sector_index, chain]
                    if rigid
                    else ensemble.local_widths[sector_index, chain]
                )
                rotation = su2_rotation(axis, float(rng.normal(scale=width)))
                if rigid:
                    candidates[sector_index, chain, walker] = (
                        candidates[sector_index, chain, walker] @ rotation.T
                    )
                else:
                    particle = int(rng.integers(spec.particles))
                    candidates[sector_index, chain, walker, particle] = (
                        rotation
                        @ candidates[sector_index, chain, walker, particle]
                    )
    candidate_logs = _evaluate_logs(
        model,
        parameters,
        spec,
        candidates,
        config,
        sectors=ensemble.sectors,
        attempt_context=attempt_context,
        evaluation_context=evaluation_context,
    )
    log_ratio = 2.0 * (candidate_logs.real - ensemble.log_amplitudes.real)
    accepted_mask = np.isfinite(candidate_logs.real) & (
        (log_ratio >= 0) | (np.log(uniforms) < log_ratio)
    )
    ensemble.walkers = np.where(
        accepted_mask[..., None, None], candidates, ensemble.walkers
    )
    ensemble.log_amplitudes = np.where(
        accepted_mask, candidate_logs, ensemble.log_amplitudes
    )
    accepted = np.zeros((len(ensemble.sectors), ensemble.walkers.shape[1], 2), dtype=np.int64)
    proposed = np.zeros_like(accepted)
    for move_index, flags in enumerate((~rigid_flags, rigid_flags)):
        proposed[:, :, move_index] = np.sum(flags, axis=2)
        accepted[:, :, move_index] = np.sum(flags & accepted_mask, axis=2)
    return accepted, proposed


def _evaluate_logs(
    model: ProjectedPfaffianNQS,
    parameters: Any,
    spec: SphereSpec,
    walkers: np.ndarray,
    config: ProductionVMCConfig,
    *,
    sectors: tuple[int, ...] = (0, 2),
    attempt_context: AttemptContext | None = None,
    evaluation_context: EvaluationContext | None = None,
) -> np.ndarray:
    result = np.empty(walkers.shape[:3], dtype=np.complex128)
    for sector_index, sector in enumerate(sectors):
        flattened = walkers[sector_index].reshape((-1, spec.particles, 2))

        def operation(layout: ProductionVMCConfig) -> np.ndarray:
            def kernel(batch: np.ndarray) -> np.ndarray:
                evaluated = model.apply_batched(
                    {"params": parameters},
                    spec,
                    jnp.asarray(batch),
                    sectors=jnp.asarray([0, 2], dtype=jnp.int32),
                    valid_walkers=jnp.ones(batch.shape[0], dtype=jnp.bool_),
                    carrier_block=layout.carrier_block,
                    quadrature_block=layout.quadrature_block,
                )
                return np.asarray(evaluated.log_amplitude[:, sector // 2])

            return deterministic_microbatch_map(
                flattened, layout.walker_microbatch, kernel
            )

        logs, _, _ = deterministic_execution_block_fallback(
            attempt_context.layout if attempt_context is not None else config,
            operation,
            attempt_context=attempt_context,
            evaluation_context=evaluation_context,
        )
        result[sector_index] = logs.reshape(walkers.shape[1:3])
    if not np.all(np.isfinite(result)):
        raise FloatingPointError("model produced nonfinite/zero walker amplitudes")
    return result


def _retained_update_samples(
    config: ProductionVMCConfig,
    ensemble: _Ensemble,
    model: ProjectedPfaffianNQS,
    parameters: Any,
    spec: SphereSpec,
    *,
    attempt_context: AttemptContext | None = None,
) -> tuple[np.ndarray, Any, float]:
    retained = np.empty(
        (
            2,
            config.chains_per_sector,
            config.walkers_per_chain,
            config.draws_per_update,
        ),
        dtype=np.float64,
    )
    retained_coordinates = np.empty(
        (
            2,
            config.chains_per_sector,
            config.walkers_per_chain,
            config.draws_per_update,
            spec.particles,
            2,
        ),
        dtype=np.complex128,
    )
    accepted = np.zeros((2, config.chains_per_sector, 2), dtype=np.int64)
    proposed = np.zeros_like(accepted)
    for draw in range(config.draws_per_update):
        a, p = _run_sweeps(
            config.thinning_sweeps,
            ensemble,
            model,
            parameters,
            spec,
            config,
            attempt_context=attempt_context,
        )
        accepted += a
        proposed += p
        retained_coordinates[:, :, :, draw] = ensemble.walkers
        for sector_index in range(2):
            for chain in range(config.chains_per_sector):
                for walker in range(config.walkers_per_chain):
                    retained[sector_index, chain, walker, draw] = coulomb_value(
                        ensemble.walkers[sector_index, chain, walker], spec
                    )
    values = np.stack(
        [flatten_chain_walker_draw(retained[index]) for index in range(2)],
        axis=1,
    )
    score_by_sector = []
    for sector_index, sector in enumerate((0, 2)):
        coordinates = retained_coordinates[sector_index].reshape(
            (-1, spec.particles, 2)
        )
        sector_scores = [
            _single_score(model, parameters, spec, point, sector)
            for point in coordinates
        ]
        score_by_sector.append(_stack_pytrees(sector_scores))
    scores = jax.tree.map(
        lambda lower, upper: np.stack((lower, upper), axis=1).astype(
            np.complex128
        ),
        score_by_sector[0],
        score_by_sector[1],
    )
    total_acceptance = float(np.sum(accepted) / np.sum(proposed))
    return values, scores, total_acceptance


def _single_score(
    model: ProjectedPfaffianNQS,
    parameters: Any,
    spec: SphereSpec,
    point: np.ndarray,
    sector: int,
) -> Any:
    def packed(candidate: Any) -> jax.Array:
        amplitude = model.apply(
            {"params": candidate}, spec, jnp.asarray(point), target_l=sector
        )
        safe = jnp.log(amplitude)
        return jnp.stack((safe.real, safe.imag))

    jacobian = jax.jacrev(packed)(parameters)
    return jax.tree.map(
        lambda leaf: np.asarray(leaf[0] + 1j * leaf[1], dtype=np.complex128),
        jacobian,
    )


def _evaluation_draws(
    config: ProductionVMCConfig,
    ensemble: _Ensemble,
    model: ProjectedPfaffianNQS,
    parameters: Any,
    spec: SphereSpec,
    sector: int,
    *,
    attempt_context: AttemptContext | None = None,
    evaluation_context: EvaluationContext | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    chains = config.final_evaluation_chains_per_sector
    draws = np.empty(
        (chains, config.walkers_per_chain, config.final_evaluation_draws_per_chain),
        dtype=np.float64,
    )
    accepted = np.zeros((1, chains, 2), dtype=np.int64)
    proposed = np.zeros_like(accepted)
    for draw in range(config.final_evaluation_draws_per_chain):
        a, p = _run_sweeps(
            config.final_evaluation_thinning_sweeps,
            ensemble,
            model,
            parameters,
            spec,
            config,
            sector_only=sector,
            attempt_context=attempt_context,
            evaluation_context=evaluation_context,
        )
        accepted += a
        proposed += p
        for chain in range(chains):
            for walker in range(config.walkers_per_chain):
                draws[chain, walker, draw] = coulomb_value(
                    ensemble.walkers[0, chain, walker], spec
                )
    return draws, accepted[0], proposed[0]


def _random_spinors(key: jax.Array, count: int, particles: int) -> np.ndarray:
    real_key, imag_key = jax.random.split(key)
    values = jax.random.normal(
        real_key, (count, particles, 2), dtype=jnp.float64
    ) + 1j * jax.random.normal(
        imag_key, (count, particles, 2), dtype=jnp.float64
    )
    values /= jnp.linalg.norm(values, axis=-1, keepdims=True)
    return np.asarray(values, dtype=np.complex128)


def _stack_pytrees(values: Sequence[Any]) -> Any:
    if not values:
        raise ValueError("cannot stack an empty pytree sequence")
    return jax.tree.map(lambda *items: np.stack(items), *values)


def _copy_ensemble(value: _Ensemble) -> _Ensemble:
    return _Ensemble(
        sectors=value.sectors,
        walkers=value.walkers.copy(),
        log_amplitudes=value.log_amplitudes.copy(),
        keys=value.keys.copy(),
        local_widths=value.local_widths.copy(),
        rigid_widths=value.rigid_widths.copy(),
    )


def _latest_compatible_snapshot(
    root: Path,
    extension: RankExtension,
    config: ProductionVMCConfig,
) -> tuple[str, Mapping[str, Any]] | None:
    attempts = root / "attempts"
    if not attempts.exists():
        return None
    if not attempts.is_dir() or attempts.is_symlink():
        raise ValueError("training attempts namespace is not a regular directory")
    candidates: list[tuple[int, str, Mapping[str, Any]]] = []
    for attempt_dir in sorted(attempts.iterdir()):
        if not attempt_dir.is_dir() or attempt_dir.is_symlink():
            raise ValueError("training attempt is not a regular directory")
        attempt_path = attempt_dir / "attempt.json"
        if not attempt_path.is_file() or attempt_path.is_symlink():
            continue
        attempt = validate_envelope(
            attempt_path, "challenge15.training-attempt.v1"
        )
        if (
            attempt["seed"] != extension.seed
            or attempt["rank"] != extension.new_rank
            or attempt["extension_sha256"]
            != payload_sha256(extension.to_payload())
        ):
            continue
        if attempt["status"] != "running":
            continue
        snapshots = attempt_dir / "snapshots"
        if not snapshots.exists():
            continue
        if not snapshots.is_dir() or snapshots.is_symlink():
            raise ValueError("training snapshots namespace is not a regular directory")
        for path in sorted(snapshots.glob("*.json")):
            snapshot = validate_envelope(
                path, "challenge15.training-snapshot.v1"
            )
            digest = payload_sha256(snapshot)
            if path.name != f"{snapshot['step']}-{digest}.json":
                raise ValueError("training snapshot filename is noncanonical")
            if snapshot["attempt_id"] != attempt["attempt_id"]:
                raise ValueError("training snapshot attempt identity mismatch")
            if any(
                snapshot[field] != extension.to_payload()[field]
                for field in (
                    "policy_sha256",
                    "source_manifest_sha256",
                    "runtime_attestations",
                    "base_configuration_sha256",
                    "particles",
                    "seed",
                )
            ) or snapshot["rank"] != extension.new_rank:
                raise ValueError("training snapshot lineage mismatch")
            step = int(snapshot["step"])
            if 0 < step < config.steps:
                candidates.append((step, digest, snapshot))
    if not candidates:
        return None
    maximum = max(item[0] for item in candidates)
    latest = [item for item in candidates if item[0] == maximum]
    if len(latest) != 1:
        raise ValueError("latest training snapshot is duplicated")
    _, digest, snapshot = latest[0]
    return digest, snapshot


def _next_attempt_number(root: Path) -> int:
    attempts = root / "attempts"
    if not attempts.exists():
        return 0
    if not attempts.is_dir() or attempts.is_symlink():
        raise ValueError("training attempts namespace is not a regular directory")
    return sum(1 for path in attempts.iterdir() if path.is_dir())


def _restore_ensemble(
    config: ProductionVMCConfig,
    extension: RankExtension,
    snapshot: Mapping[str, Any],
    root: Path,
) -> _Ensemble:
    walkers = _array_bundle_from_bytes(
        _read_blob(root, str(snapshot["walker_state_sha256"]))
    )
    logs = _array_bundle_from_bytes(
        _read_blob(root, str(snapshot["log_amplitude_sha256"]))
    )
    keys = _array_bundle_from_bytes(
        _read_blob(root, str(snapshot["prng_state_sha256"]))
    )
    expected_walkers = config.state_shape(extension.particles)
    if walkers.shape != expected_walkers or walkers.dtype != np.complex128:
        raise ValueError("snapshot walker state shape or dtype mismatch")
    if logs.shape != config.log_amplitude_shape or logs.dtype != np.complex128:
        raise ValueError("snapshot log-amplitude shape or dtype mismatch")
    if keys.shape != (2, config.chains_per_sector, 2) or keys.dtype != np.uint32:
        raise ValueError("snapshot PRNG state shape or dtype mismatch")
    proposal = snapshot["proposal_state"]
    proposal_widths = np.stack(
        (
            np.asarray(proposal["local_widths"], dtype=np.float64),
            np.asarray(proposal["rigid_widths"], dtype=np.float64),
        )
    )
    if proposal_widths.shape != (2, 2, config.chains_per_sector):
        raise ValueError("snapshot proposal widths cannot be reconstructed")
    return _Ensemble(
        sectors=(0, 2),
        walkers=walkers,
        log_amplitudes=logs,
        keys=keys,
        local_widths=proposal_widths[0].copy(),
        rigid_widths=proposal_widths[1].copy(),
    )


def _publish_training_checkpoint(
    root: Path,
    attempt_dir: Path,
    extension: RankExtension,
    attempt_id: str,
    step: int,
    parameters: Any,
    optimizer_state: Any,
    state: _Ensemble,
    metrics: Mapping[str, Any],
    config: ProductionVMCConfig,
) -> str:
    parameter_sha = publish_blob(root, serialization.to_bytes(parameters))
    optimizer_sha = publish_blob(root, serialization.to_bytes(optimizer_state))
    walker_sha = publish_blob(root, _array_bundle_bytes(state.walkers))
    logs_sha = publish_blob(root, _array_bundle_bytes(state.log_amplitudes))
    prng_sha = publish_blob(root, _array_bundle_bytes(state.keys))
    snapshot = TrainingSnapshot(
        policy_sha256=extension.policy_sha256,
        source_manifest_sha256=extension.source_manifest_sha256,
        runtime_attestations=extension.runtime_attestations,
        base_configuration_sha256=extension.base_configuration_sha256,
        particles=extension.particles,
        seed=extension.seed,
        rank=extension.new_rank,
        attempt_id=attempt_id,
        step=step,
        parameter_sha256=parameter_sha,
        optimizer_state_sha256=optimizer_sha,
        walker_state_sha256=walker_sha,
        log_amplitude_sha256=logs_sha,
        prng_state_sha256=prng_sha,
        proposal_state={
            "kernel": "local-rigid-su2-v1",
            "adaptation_step": config.pilot_sweeps,
            "local_widths": state.local_widths.tolist(),
            "rigid_widths": state.rigid_widths.tolist(),
        },
        diagnostics=dict(metrics),
    )
    return publish_snapshot(attempt_dir, snapshot)


def _tree_norm(tree: Any) -> float:
    return float(
        math.sqrt(
            sum(
                float(np.sum(np.square(np.abs(np.asarray(leaf)))))
                for leaf in jax.tree.leaves(tree)
            )
        )
    )


def _array_bundle_bytes(array: np.ndarray) -> bytes:
    value = np.asarray(array)
    header = json.dumps(
        {"dtype": value.dtype.str, "shape": value.shape},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return len(header).to_bytes(8, "big") + header + value.tobytes(order="C")


def _array_bundle_from_bytes(encoded: bytes) -> np.ndarray:
    if len(encoded) < 8:
        raise ValueError("array bundle is truncated")
    header_size = int.from_bytes(encoded[:8], "big")
    if header_size <= 0 or 8 + header_size > len(encoded):
        raise ValueError("array bundle header is invalid")
    try:
        header = json.loads(encoded[8 : 8 + header_size].decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("array bundle header is invalid") from exc
    if (
        not isinstance(header, Mapping)
        or set(header) != {"dtype", "shape"}
        or not isinstance(header["dtype"], str)
        or not isinstance(header["shape"], list)
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in header["shape"]
        )
    ):
        raise ValueError("array bundle metadata is invalid")
    dtype = np.dtype(header["dtype"])
    shape = tuple(header["shape"])
    payload = encoded[8 + header_size :]
    expected_size = math.prod(shape) * dtype.itemsize
    if len(payload) != expected_size:
        raise ValueError("array bundle payload size mismatch")
    return np.frombuffer(payload, dtype=dtype).reshape(shape).copy()


def _read_blob(root: Path, digest: str) -> bytes:
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("blob SHA256 is invalid")
    directory_fd = _open_directory_fd(root / "blobs")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            digest,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("snapshot blob is not a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            encoded = stream.read()
    except OSError as exc:
        raise ValueError("snapshot blob is missing") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_fd)
    if hashlib.sha256(encoded).hexdigest() != digest:
        raise ValueError("snapshot blob SHA256 mismatch")
    return encoded


def deserialize_verified_blob(template: Any, root: Path, digest: str) -> Any:
    """Read one nofollow blob and verify its canonical serialization digest."""

    restored = serialization.from_bytes(template, _read_blob(root, digest))
    if hashlib.sha256(serialization.to_bytes(restored)).hexdigest() != digest:
        raise ValueError("deserialized blob SHA256 mismatch")
    return restored


def _attempt_identity(attempt: TrainingAttempt) -> str:
    return payload_sha256(
        {
            "seed": attempt.seed,
            "rank": attempt.rank,
            "attempt_id": attempt.attempt_id,
            "owner_sha256": attempt.owner_sha256,
            "extension_sha256": attempt.extension_sha256,
            "status": attempt.status,
        }
    )


def _statistic_payload(estimate: float, values: np.ndarray) -> dict[str, float]:
    standard_error = float(np.std(values, ddof=1) / math.sqrt(values.size))
    low, high = _confidence_interval(estimate, standard_error)
    return {
        "estimate": estimate,
        "standard_error": standard_error,
        "ci_low": low,
        "ci_high": high,
    }


def _paired_gap_payload(
    seed: int,
    estimate: float,
    standard_error: float,
    diagnostics: SamplingDiagnostics,
    variance_e0: float,
    variance_e2: float,
    uncertainty: UncertaintyResult,
    estimate_e0: float,
    estimate_e2: float,
    *,
    diagnostics_e0: Mapping[str, Any] | None = None,
    diagnostics_e2: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    low, high = _confidence_interval(estimate, standard_error)
    variance_gap = variance_e0 + variance_e2
    return {
        "estimate": estimate,
        "standard_error": standard_error,
        "ci_low": low,
        "ci_high": high,
        "tau_int_e0": (
            max(1.0, float(diagnostics_e0["tau_int"]))
            if diagnostics_e0 is not None
            else max(1.0, diagnostics.integrated_autocorrelation_time)
        ),
        "tau_int_e2": (
            max(1.0, float(diagnostics_e2["tau_int"]))
            if diagnostics_e2 is not None
            else max(1.0, diagnostics.integrated_autocorrelation_time)
        ),
        "tau_int_gap": max(1.0, diagnostics.integrated_autocorrelation_time),
        "variance_mc_e0": variance_e0,
        "variance_mc_e2": variance_e2,
        "variance_mc_gap": variance_gap,
        "monte_carlo_covariance_e0_e2": 0.0,
        "optimizer_variance_e0": 0.0,
        "optimizer_variance_e2": 0.0,
        "optimizer_induced_covariance_e0_e2": 0.0,
        "variance_seed_mean_gap": 0.0,
        # One immutable coordinate shard owns one optimizer seed.  The
        # five-seed covariance cannot be accepted until all policy seed
        # identities are present together at reduction.
        "uncertainty_status": "pending",
        "effective_sample_size": (
            diagnostics.effective_sample_size
            if math.isfinite(diagnostics.effective_sample_size)
            else 1.0
        ),
        "split_rhat": diagnostics.split_rhat,
        "autocorrelation_converged": diagnostics.autocorrelation_converged,
        "within_seed_inputs": [
            {
                "seed": seed,
                "e0": estimate_e0,
                "e2": estimate_e2,
                "variance_mc_e0": variance_e0,
                "variance_mc_e2": variance_e2,
                "monte_carlo_covariance_e0_e2": 0.0,
                "variance_mc_gap": variance_gap,
            }
        ],
        "between_seed_inputs": {
            "paired_seed_ids": [seed],
            "e0_seed_estimates": [estimate_e0],
            "e2_seed_estimates": [estimate_e2],
            "optimizer_variance_e0": 0.0,
            "optimizer_variance_e2": 0.0,
            "optimizer_covariance_e0_e2": 0.0,
            "paired_seed_count": 1,
            "variance_seed_mean_gap": 0.0,
        },
    }


def _coordinate_controller(runtime_attestations: Mapping[str, Any]) -> str:
    coordinate = runtime_attestations.get("coordinate")
    if not isinstance(coordinate, Mapping) or len(coordinate) != 1:
        raise ValueError("coordinate runtime identity is missing or ambiguous")
    return str(next(iter(coordinate)))


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _paired_values(
    first: Sequence[float] | Mapping[int, float],
    second: Sequence[float] | Mapping[int, float],
) -> tuple[np.ndarray | None, np.ndarray | None]:
    if isinstance(first, Mapping) or isinstance(second, Mapping):
        if not isinstance(first, Mapping) or not isinstance(second, Mapping):
            return None, None
        if set(first) != set(second):
            return None, None
        identities = sorted(first)
        if (
            tuple(identities) != EXPECTED_SEED_IDS
            or any(isinstance(identity, bool) for identity in identities)
        ):
            return None, None
        return (
            np.asarray([first[key] for key in identities], dtype=np.float64),
            np.asarray([second[key] for key in identities], dtype=np.float64),
        )
    lower = np.asarray(first, dtype=np.float64)
    upper = np.asarray(second, dtype=np.float64)
    if lower.ndim != 1 or upper.ndim != 1 or lower.shape != upper.shape:
        return None, None
    return lower, upper


def _pending_uncertainty(reason: str) -> UncertaintyResult:
    return UncertaintyResult(False, float("nan"), float("nan"), reason)


def _confidence_interval(estimate: float, standard_error: float) -> tuple[float, float]:
    half_width = 1.959963984540054 * standard_error
    return estimate - half_width, estimate + half_width


def _positive_integer(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive Python integer")


def _validate_real_finite_tree(tree: Any, label: str) -> None:
    leaves = jax.tree.leaves(tree)
    if not leaves:
        raise ValueError(f"{label} must contain at least one leaf")
    for leaf in leaves:
        array = np.asarray(leaf)
        if np.iscomplexobj(array) or not np.issubdtype(array.dtype, np.number):
            raise ValueError(f"{label} must be a real numeric pytree")
        if not np.all(np.isfinite(array)):
            raise ValueError(f"{label} must be finite")


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float, np.number))
        and not isinstance(value, (bool, np.bool_))
        and math.isfinite(float(value))
    )


def _finite_nonnegative(value: Any) -> bool:
    return _finite_number(value) and float(value) >= 0.0


def _finite_between(value: Any, lower: float, upper: float) -> bool:
    return _finite_number(value) and lower <= float(value) <= upper


def _finite_at_least(value: Any, minimum: float) -> bool:
    return _finite_number(value) and float(value) >= minimum


def _finite_at_most(value: Any, maximum: float) -> bool:
    return _finite_number(value) and float(value) <= maximum
