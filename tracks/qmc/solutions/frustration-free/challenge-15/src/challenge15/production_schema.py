"""Strict canonical envelopes and production artifact value objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any, Mapping

from .production_policy import (
    ARTIFACT_SCHEMAS,
    RUNTIME_ROLES,
    policy_sha256 as current_policy_sha256,
    production_policy,
)
from .provenance import validate_fingerprint


JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
SHA256 = str
RuntimeAttestations = Mapping[str, Mapping[str, SHA256]]

ENVELOPE_FIELDS = frozenset({"schema", "payload", "payload_sha256"})
RECEIPT_CONTEXT_VALIDATOR_REGISTRY = {
    "challenge15.runtime-set-copies.v1": "runtime-copies",
    "challenge15.runtime-set-publication-receipt.v1": "runtime-publication",
    "challenge15.attestation-bootstrap-transfer.v1": "bootstrap-transfer",
    "challenge15.recovery-receipt.v1": "recovery",
    "challenge15.state-manifest-backup-receipt.v1": "state-manifest-backup",
    "challenge15.submission-receipt.v1": "submission",
    "challenge15.output-promotion.v1": "promotion",
    "challenge15.export-bundle.v1": "export",
    "challenge15.import-bundle.v1": "import",
    "challenge15.transfer-receipt.v1": "transfer",
    "challenge15.dry-run-receipt.v1": "dry-run",
    "challenge15.deployment-receipt.v1": "deployment",
    "challenge15.evaluation-receipt.v1": "evaluation",
    "challenge15.reduction-receipt.v1": "reduction",
    "challenge15.report-receipt.v1": "report",
}
CONTEXT_REQUIRED_SCHEMAS = frozenset(RECEIPT_CONTEXT_VALIDATOR_REGISTRY)
COMMON = {
    "policy_sha256",
    "source_manifest_sha256",
    "runtime_attestations",
    "base_configuration_sha256",
    "particles",
}


def _fields(*names: str, common: bool = False) -> frozenset[str]:
    return frozenset(names) | (COMMON if common else frozenset())


# This registry is the sole schema inventory.  Payload field sets are exact.
SCHEMA_FIELDS: dict[str, frozenset[str]] = {
    "challenge15.production-policy.v1": frozenset(production_policy()),
    "challenge15.source-manifest.v1": _fields(
        "git_revision", "members", "policy_sha256"
    ),
    "challenge15.allowed-runtime.v1": _fields(
        "profile",
        "role",
        "controller",
        "python_version",
        "python_abi",
        "platform_tag",
        "minimum_glibc",
        "packages",
        "wheel_sha256",
        "source_manifest_sha256",
        "policy_sha256",
        "backend",
        "x64_enabled",
        "device_platforms",
        "cuda_driver",
        "smoke_payload_sha256",
        "attestation_test_members",
        "attested_hostname_class",
        "attested_at_utc",
    ),
    "challenge15.runtime-attestation-set.v1": _fields(
        "set_name", "particles", "roles"
    ),
    "challenge15.runtime-set-copies.v1": _fields(
        "particles",
        "payload_sha256",
        "role_map_sha256",
        "local_path_identity",
        "local_sha256",
        "cpu_controller",
        "cpu_remote_path_identity",
        "cpu_remote_sha256",
        "cpu_resolving_receipt_sha256",
        "gpu_controller",
        "gpu_remote_path_identity",
        "gpu_remote_sha256",
        "gpu_resolving_receipt_sha256",
    ),
    "challenge15.runtime-set-publication-receipt.v1": _fields(
        "controller",
        "deployment_receipt_sha256",
        "controller_local_path_identity",
        "payload_sha256",
        "role_map_sha256",
        "source_manifest_sha256",
        "policy_sha256",
        "published_at_utc",
    ),
    "challenge15.attestation-bootstrap-transfer.v1": _fields(
        "source_controller",
        "destination_controller",
        "role",
        "allowed_runtime_sha256",
        "source_manifest_sha256",
        "policy_sha256",
        "source_deployment_receipt_sha256",
        "destination_deployment_receipt_sha256",
        "export_bundle_sha256",
        "import_bundle_sha256",
        "verified_at_utc",
    ),
    "challenge15.cluster-profile.v1": _fields(
        "controller",
        "partition",
        "account",
        "qos",
        "nodes",
        "ntasks",
        "cpus_per_task",
        "memory",
        "wall_time",
        "array_concurrency",
        "approved_project_root",
        "approved_results_root",
        "scheduler_facts",
    ),
    "challenge15.production-oracle.v1": _fields(
        "sphere_spec",
        "physical_conventions",
        "coulomb_builder_diagnostics",
        "sector_summaries",
        "low_energy_scan",
        "array_manifest",
        "gate_metrics",
        common=True,
    ),
    "challenge15.chiral-response.v1": _fields(
        "particles",
        "orientation",
        "initial_state",
        "configuration",
        "physical_conventions",
        "source",
        "channels",
        "delta_weight",
        "contrast",
        "contrast_floor",
        "diagnostics",
        "input_sha256",
        "input_identities",
        "execution_fingerprint",
    ),
    "challenge15.seed-owner.v1": _fields(
        "seed",
        "experiment_id",
        "base_configuration_sha256",
        "expected_seed_set",
        "owner_uuid",
        "claimed_at_utc",
        "claim_host",
        "claim_process",
        "claim_nonce_sha256",
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
    ),
    "challenge15.rank-extension.v1": _fields(
        "particles",
        "seed",
        "experiment_id",
        "base_configuration_sha256",
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
        "expected_seed_set",
        "previous_rank",
        "new_rank",
        "parent_generation_sha256",
        "parent_parameter_sha256",
        "parent_optimizer_state_sha256",
        "rank_extension_decision_sha256",
        "embedding_algorithm",
        "rank_growth_prng",
        "reason",
        "created_by_git_revision",
    ),
    "challenge15.rank-extension-decision.v1": _fields(
        "seed",
        "current_rank",
        "new_rank",
        "prior_expected_ranks_sha256",
        "prior_reduction_sha256",
        "prior_finalization_sha256",
        "prior_import_receipt_sha256",
        "prior_transfer_receipt_sha256",
        "decision",
        "reason",
        "decision_metrics",
        common=True,
    ),
    "challenge15.training-attempt.v1": _fields(
        "seed",
        "rank",
        "attempt_id",
        "owner_sha256",
        "extension_sha256",
        "started_from_snapshot_sha256",
        "resource_override",
        "terminal_snapshot_sha256",
        "status",
    ),
    "challenge15.training-snapshot.v1": _fields(
        "seed",
        "rank",
        "attempt_id",
        "step",
        "parameter_sha256",
        "optimizer_state_sha256",
        "walker_state_sha256",
        "log_amplitude_sha256",
        "prng_state_sha256",
        "proposal_state",
        "diagnostics",
        common=True,
    ),
    "challenge15.training-generation.v1": _fields(
        "seed",
        "rank",
        "attempt_sha256",
        "extension_sha256",
        "parent_generation_sha256",
        "parent_parameter_sha256",
        "parent_optimizer_state_sha256",
        "parameter_sha256",
        "optimizer_state_sha256",
        "terminal_snapshot_sha256",
        "training_metrics",
        common=True,
    ),
    "challenge15.recovery-receipt.v1": _fields(
        "seed",
        "rank",
        "attempt_sha256",
        "stale_lock_sha256",
        "scheduler_query",
        "scheduler_state",
        "recovered_by",
        "recovered_at_utc",
    ),
    "challenge15.resource-override.v1": _fields(
        "seed",
        "rank",
        "extension_sha256",
        "attempt_sha256",
        "reason",
        "walker_microbatch",
        "carrier_block",
        "quadrature_block",
        "fixed_schedule_sha256",
        "metric_equivalence",
        common=True,
    ),
    "challenge15.identity-map.v1": _fields(
        "stage",
        "expected_ranks",
        "expected_ranks_sha256",
        "expected_seeds",
        "task_count",
        "tasks",
        "array_concurrency",
        common=True,
    ),
    "challenge15.submission-receipt.v1": _fields(
        "stage",
        "identity_map_sha256",
        "profile_sha256",
        "interpreter_sha256",
        "submitted_at_utc",
        "controller",
        "scheduler_job_id",
        "array_spec",
        "dependency_mode",
        "correlation_id",
        "scheduler_job_name",
        "scheduler_comment",
        "script_sha256",
        "input_sha256s",
        "remote_claim_sha256",
        common=True,
    ),
    "challenge15.orchestration-state-key.v1": _fields(
        "particles",
        "base_configuration_sha256",
        "policy_sha256",
        "source_manifest_sha256",
        "rank_ladder",
        "rank_extension_policy_sha256",
        "seed_set",
        "runtime_set_local_sha256",
        "runtime_set_local_path_identity",
        "cpu_runtime_set_remote_sha256",
        "cpu_runtime_set_remote_path_identity",
        "cpu_runtime_set_receipt_sha256",
        "gpu_runtime_set_remote_sha256",
        "gpu_runtime_set_remote_path_identity",
        "gpu_runtime_set_receipt_sha256",
        "prerequisite_terminal_selection_sha256",
        "cpu_controller",
        "gpu_controller",
        "cpu_profile_sha256",
        "gpu_profile_sha256",
        "cpu_deployment_receipt_sha256",
        "gpu_deployment_receipt_sha256",
        "cpu_results_root_identity",
        "gpu_results_root_identity",
        "durable_state_root_base_identity",
        "state_backup_uri_identity",
        "state_mirror_root_identity",
        "transition_action_manifest_sha256",
        "canonical_path_identities",
    ),
    "challenge15.orchestration-attempt-intent.v1": _fields(
        "state_key_sha256",
        "transition_identity_sha256",
        "attempt",
        "action_kind",
        "correlation_id",
        "source_controller",
        "destination_controller",
        "script_sha256",
        "canonical_argv_sha256",
        "input_sha256s",
        "profile_sha256",
        "deployment_receipt_sha256",
        "runtime_set_sha256",
        "source_manifest_sha256",
        "policy_sha256",
        "base_configuration_sha256",
        "particles",
        "seed",
        "rank",
        "parent_sha256s",
        "expected_output_identities",
        "create_only_namespace_identities",
        "scheduler_job_name",
        "scheduler_comment",
        "remote_claim_path_identity",
        "created_at_utc",
    ),
    "challenge15.orchestration-transition.v1": _fields(
        "state_key",
        "state",
        "attempt",
        "input_sha256s",
        "output_sha256s",
        "output_promotion_sha256s",
        "import_receipt_sha256s",
        "transfer_receipt_sha256s",
        "scheduler_receipt_sha256s",
        "outcome",
        "created_at_utc",
    ),
    "challenge15.orchestration-state-manifest.v1": _fields(
        "state_key_sha256",
        "source_revision",
        "transition_receipt_sha256s",
        "completion_marker_sha256s",
        "attempt_intent_sha256s",
        "output_promotion_sha256s",
        "expected_remote_output_sha256s",
        "previous_state_manifest_sha256",
        "backup_uri_identity",
        "mirror_root_identity",
        "created_at_utc",
    ),
    "challenge15.state-manifest-backup-receipt.v1": _fields(
        "source_state_manifest",
        "source_sha256",
        "intent_sha256",
        "profile_sha256",
        "destination",
        "created_at_utc",
    ),
    "challenge15.output-promotion.v1": _fields(
        "state_key_sha256",
        "transition_identity_sha256",
        "output_schema",
        "output_payload_sha256",
        "output_absolute_path_identity",
        "producer_intent_sha256",
        "selector_kind",
        "selector_namespace_identity",
        "candidate_computed_sha256",
        "candidate_count",
        "promoted_at_utc",
    ),
    "challenge15.export-bundle.v1": _fields(
        "bundle_role",
        "source_controller",
        "source_root",
        "source_artifact_sha256",
        "member_manifest",
        "sha256sums_sha256",
        "bundle_sha256",
        "created_at_utc",
        common=True,
    ),
    "challenge15.import-bundle.v1": _fields(
        "bundle_sha256",
        "destination_controller",
        "destination_root",
        "member_manifest",
        "imported_artifact_sha256",
        "verified_at_utc",
        common=True,
    ),
    "challenge15.transfer-receipt.v1": _fields(
        "direction",
        "export_bundle_sha256",
        "import_bundle_sha256",
        "source_controller",
        "destination_controller",
        "source_identity",
        "destination_identity",
        "partial_path",
        "final_path",
        "bytes",
        "attempt_intent_sha256",
        "correlation_id",
        "remote_claim_sha256",
        "started_at_utc",
        "verified_at_utc",
        common=True,
    ),
    "challenge15.dry-run-receipt.v1": _fields(
        "profile_sha256",
        "bundle_sha256",
        "destination",
        "interpreter",
        "interpreter_sha256",
        "scheduler_test",
        "validated_at_utc",
    ),
    "challenge15.deployment-receipt.v1": _fields(
        "dry_run_receipt_sha256",
        "profile_sha256",
        "bundle_sha256",
        "deployment_root",
        "interpreter",
        "interpreter_sha256",
        "installed_wheel_sha256",
        "deployed_at_utc",
    ),
    "challenge15.exact-evaluation-shard.v1": _fields(
        "seed",
        "rank",
        "generation_sha256",
        "oracle_sha256",
        "parameter_sha256",
        "block_layout",
        "primitive_metrics",
        "metric_equivalence",
        "gate_metrics",
        common=True,
    ),
    "challenge15.coordinate-evaluation-shard.v1": _fields(
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
        common=True,
    ),
    "challenge15.evaluation-receipt.v1": _fields(
        "stage",
        "identity",
        "shard_sha256",
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
        common=True,
    ),
    "challenge15.size-result.v1": _fields(
        "expected_ranks",
        "expected_seeds",
        "oracle_sha256",
        "generation_sha256_by_identity",
        "exact_sha256_by_identity",
        "coordinate_sha256_by_identity",
        "coordinate_uncertainty_by_rank",
        "prerequisite",
        "primitive_metrics",
        "rank_transitions",
        "seed_gate",
        "missing_identities",
        "failed_gates",
        "production_accepted",
        "claim",
        common=True,
    ),
    "challenge15.reduction-receipt.v1": _fields(
        "canonical_payload_sha256",
        "started_at_utc",
        "finished_at_utc",
        "hostname",
        "slurm_job_id",
        "devices",
        "peak_rss_mib",
        "stage_elapsed_seconds",
        "cache_counters",
        common=True,
    ),
    "challenge15.reduction-finalization.v1": _fields(
        "expected_ranks",
        "expected_ranks_sha256",
        "selected_reduction_sha256",
        "selected_reduction_path",
        "production_accepted",
        "finalized_at_utc",
        "finalized_by",
        common=True,
    ),
    "challenge15.terminal-selection.v1": _fields(
        "selected_expected_ranks_sha256",
        "selected_finalization_sha256",
        "selected_reduction_sha256",
        "production_accepted",
        "selected_at_utc",
        "selected_by",
        common=True,
    ),
    "challenge15.cross-size-manifest.v1": _fields(
        "policy_sha256",
        "source_manifest_sha256",
        "n6_sha256",
        "n7_sha256",
        "n8_sha256",
        "n6_terminal_selection_sha256",
        "n7_terminal_selection_sha256",
        "n8_terminal_selection_sha256",
        "particles",
        "base_configuration_sha256_by_size",
        "runtime_attestation_sets_by_size",
        "lineage",
        "production_accepted_n6_n8",
        "claim",
    ),
    "challenge15.final-report.v1": _fields(
        "cross_size_manifest_sha256",
        "size_summaries",
        "particles",
        "base_configuration_sha256_by_size",
        "runtime_attestation_sets_by_size",
        "source_manifest_sha256",
        "policy_sha256",
        "resource_summary",
        "statistical_summary",
        "failed_gates",
        "production_accepted_n6_n8",
        "statement",
    ),
    "challenge15.report-receipt.v1": _fields(
        "particles",
        "base_configuration_sha256_by_size",
        "final_report_sha256",
        "markdown_sha256",
        "cross_size_manifest_sha256",
        "runtime_attestation_sets_by_size",
        "source_manifest_sha256",
        "policy_sha256",
        "started_at_utc",
        "finished_at_utc",
        "hostname",
        "interpreter_sha256",
    ),
}

if set(SCHEMA_FIELDS) != set(ARTIFACT_SCHEMAS):  # pragma: no cover - import invariant
    raise RuntimeError("production schema registry does not match policy inventory")

_EXPECTED_CONTEXT_SCHEMAS = {
    schema for schema in SCHEMA_FIELDS if schema.endswith("-receipt.v1")
} | {
    "challenge15.runtime-set-copies.v1",
    "challenge15.attestation-bootstrap-transfer.v1",
    "challenge15.output-promotion.v1",
    "challenge15.export-bundle.v1",
    "challenge15.import-bundle.v1",
}
if CONTEXT_REQUIRED_SCHEMAS != _EXPECTED_CONTEXT_SCHEMAS:
    raise RuntimeError("receipt context registry omits a publisher schema")


class Payload:
    """Mixin for frozen production value objects."""

    def to_payload(self) -> dict[str, JSONValue]:
        return _json_value(asdict(self))


@dataclass(frozen=True, slots=True)
class SeedOwner(Payload):
    seed: int
    experiment_id: str
    base_configuration_sha256: SHA256
    expected_seed_set: tuple[int, ...]
    owner_uuid: str
    claimed_at_utc: str
    claim_host: str
    claim_process: str
    claim_nonce_sha256: SHA256
    policy_sha256: SHA256
    source_manifest_sha256: SHA256
    runtime_attestations: RuntimeAttestations


@dataclass(frozen=True, slots=True)
class RankExtensionDecision(Payload):
    policy_sha256: SHA256
    source_manifest_sha256: SHA256
    runtime_attestations: RuntimeAttestations
    base_configuration_sha256: SHA256
    particles: int
    seed: int
    current_rank: int | None
    new_rank: int
    prior_expected_ranks_sha256: SHA256 | None
    prior_reduction_sha256: SHA256 | None
    prior_finalization_sha256: SHA256 | None
    prior_import_receipt_sha256: SHA256 | None
    prior_transfer_receipt_sha256: SHA256 | None
    decision: str
    reason: str
    decision_metrics: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True)
class RankExtension(Payload):
    particles: int
    seed: int
    experiment_id: str
    base_configuration_sha256: SHA256
    policy_sha256: SHA256
    source_manifest_sha256: SHA256
    runtime_attestations: RuntimeAttestations
    expected_seed_set: tuple[int, ...]
    previous_rank: int | None
    new_rank: int
    parent_generation_sha256: SHA256 | None
    parent_parameter_sha256: SHA256 | None
    parent_optimizer_state_sha256: SHA256 | None
    rank_extension_decision_sha256: SHA256 | None
    embedding_algorithm: str
    rank_growth_prng: Mapping[str, JSONValue]
    reason: str
    created_by_git_revision: str


@dataclass(frozen=True, slots=True)
class TrainingAttempt(Payload):
    seed: int
    rank: int
    attempt_id: str
    owner_sha256: SHA256
    extension_sha256: SHA256
    started_from_snapshot_sha256: SHA256 | None
    resource_override: Mapping[str, JSONValue] | None
    terminal_snapshot_sha256: SHA256 | None
    status: str


@dataclass(frozen=True, slots=True)
class TrainingSnapshot(Payload):
    policy_sha256: SHA256
    source_manifest_sha256: SHA256
    runtime_attestations: RuntimeAttestations
    base_configuration_sha256: SHA256
    particles: int
    seed: int
    rank: int
    attempt_id: str
    step: int
    parameter_sha256: SHA256
    optimizer_state_sha256: SHA256
    walker_state_sha256: SHA256
    log_amplitude_sha256: SHA256
    prng_state_sha256: SHA256
    proposal_state: Mapping[str, JSONValue]
    diagnostics: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True)
class TrainingGeneration(Payload):
    policy_sha256: SHA256
    source_manifest_sha256: SHA256
    runtime_attestations: RuntimeAttestations
    base_configuration_sha256: SHA256
    particles: int
    seed: int
    rank: int
    attempt_sha256: SHA256
    extension_sha256: SHA256
    parent_generation_sha256: SHA256 | None
    parent_parameter_sha256: SHA256 | None
    parent_optimizer_state_sha256: SHA256 | None
    parameter_sha256: SHA256
    optimizer_state_sha256: SHA256
    terminal_snapshot_sha256: SHA256
    training_metrics: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True)
class RecoveryReceipt(Payload):
    seed: int
    rank: int
    attempt_sha256: SHA256
    stale_lock_sha256: SHA256
    scheduler_query: Mapping[str, JSONValue]
    scheduler_state: str
    recovered_by: str
    recovered_at_utc: str


@dataclass(frozen=True, slots=True)
class OrchestrationAttemptIntent(Payload):
    state_key_sha256: SHA256
    transition_identity_sha256: SHA256
    attempt: int
    action_kind: str
    correlation_id: SHA256
    source_controller: str | None
    destination_controller: str | None
    script_sha256: SHA256 | None
    canonical_argv_sha256: SHA256
    input_sha256s: tuple[SHA256, ...]
    profile_sha256: SHA256
    deployment_receipt_sha256: SHA256
    runtime_set_sha256: SHA256
    source_manifest_sha256: SHA256
    policy_sha256: SHA256
    base_configuration_sha256: SHA256
    particles: int
    seed: int | None
    rank: int | None
    parent_sha256s: Mapping[str, SHA256 | None]
    expected_output_identities: tuple[Mapping[str, JSONValue], ...]
    create_only_namespace_identities: tuple[str, ...]
    scheduler_job_name: str | None
    scheduler_comment: str | None
    remote_claim_path_identity: str | None
    created_at_utc: str


def canonical_json(value: Any) -> bytes:
    """Encode strict finite canonical JSON."""

    try:
        return json.dumps(
            _json_value(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must contain strict finite JSON values") from exc


def payload_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json(_payload(payload))).hexdigest()


def envelope_for(schema: str, payload: Any) -> dict[str, JSONValue]:
    if schema not in SCHEMA_FIELDS:
        raise ValueError(f"unknown production schema: {schema}")
    value = _payload(payload)
    SCHEMA_VALIDATORS[schema](value)
    return {
        "schema": schema,
        "payload": value,
        "payload_sha256": payload_sha256(value),
    }


def validate_envelope(
    value: str | bytes | Mapping[str, Any] | Path,
    expected_schema: str | None = None,
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, JSONValue]:
    """Parse and validate an exact envelope, returning a detached payload."""

    document = _load_document(value)
    if isinstance(value, Path):
        if value.read_bytes() != canonical_json(document) + b"\n":
            raise ValueError("stored envelope bytes are not exact canonical JSON")
    elif isinstance(value, bytes):
        if value not in {canonical_json(document), canonical_json(document) + b"\n"}:
            raise ValueError("envelope bytes are not canonical JSON")
    elif isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        if value.encode("utf-8") not in {
            canonical_json(document),
            canonical_json(document) + b"\n",
        }:
            raise ValueError("envelope text is not canonical JSON")
    if set(document) != ENVELOPE_FIELDS:
        raise ValueError("envelope fields do not match the exact schema")
    schema = document.get("schema")
    if not isinstance(schema, str) or schema not in SCHEMA_FIELDS:
        raise ValueError("envelope schema is unknown")
    if expected_schema is not None and schema != expected_schema:
        raise ValueError(f"envelope schema mismatch: expected {expected_schema}")
    payload = document.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("envelope payload must be an object")
    SCHEMA_VALIDATORS[schema](payload)
    claimed = document.get("payload_sha256")
    _require_sha256(claimed, "envelope payload SHA256")
    if claimed != payload_sha256(payload):
        raise ValueError("envelope payload SHA256 mismatch")
    if context is not None:
        validate_receipt_context(schema, payload, context)
    return _json_value(payload)


FIXED_SCHEDULE_SCHEMA = "challenge15.fixed-schedule.v1"
FIXED_SCHEDULE_FIELDS = frozenset(
    {
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
        "base_configuration_sha256",
        "particles",
        "seed",
        "rank",
        "owner_sha256",
        "extension_sha256",
        "schedule_version",
        "optimizer",
        "learning_rate",
        "steps",
        "weight_l0",
        "weight_l2",
        "chains_per_sector",
        "walkers_per_chain",
        "pilot_sweeps",
        "burn_in_sweeps",
        "draws_per_update",
        "thinning_sweeps",
        "reequilibration_sweeps_after_update",
        "refresh_log_amplitudes_after_update",
        "checkpoint_interval_steps",
        "final_evaluation_chains_per_sector",
        "final_evaluation_burn_in_sweeps",
        "final_evaluation_draws_per_chain",
        "final_evaluation_thinning_sweeps",
    }
)


def fixed_schedule_envelope(payload: Mapping[str, Any]) -> dict[str, JSONValue]:
    value = _payload(payload)
    validate_fixed_schedule_payload(value)
    return {
        "schema": FIXED_SCHEDULE_SCHEMA,
        "payload": value,
        "payload_sha256": payload_sha256(value),
    }


def validate_fixed_schedule_envelope(
    value: str | bytes | Mapping[str, Any] | Path,
) -> dict[str, JSONValue]:
    document = _load_document(value)
    if isinstance(value, Path) and value.read_bytes() != canonical_json(document) + b"\n":
        raise ValueError("stored fixed schedule is not exact canonical JSON")
    if set(document) != ENVELOPE_FIELDS or document.get("schema") != FIXED_SCHEDULE_SCHEMA:
        raise ValueError("fixed schedule envelope schema mismatch")
    payload = document.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("fixed schedule payload must be an object")
    validate_fixed_schedule_payload(payload)
    if document.get("payload_sha256") != payload_sha256(payload):
        raise ValueError("fixed schedule payload SHA256 mismatch")
    return _json_value(payload)


def validate_fixed_schedule_payload(payload: Mapping[str, Any]) -> None:
    if set(payload) != FIXED_SCHEDULE_FIELDS:
        raise ValueError("fixed schedule fields mismatch")
    if payload["policy_sha256"] != current_policy_sha256():
        raise ValueError("fixed schedule has stale policy")
    for field in (
        "policy_sha256",
        "source_manifest_sha256",
        "base_configuration_sha256",
        "owner_sha256",
        "extension_sha256",
    ):
        _require_sha256(payload[field], f"fixed schedule {field}")
    validate_runtime_attestations(payload["runtime_attestations"])
    for field in (
        "particles",
        "rank",
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
    ):
        _require_integer(payload[field], f"fixed schedule {field}", minimum=1)
    _require_integer(payload["seed"], "fixed schedule seed", minimum=0)
    if not isinstance(payload["refresh_log_amplitudes_after_update"], bool):
        raise ValueError("fixed schedule refresh flag is invalid")
    if payload["particles"] not in {6, 7, 8}:
        raise ValueError("fixed schedule particles are unsupported")
    if (
        payload["chains_per_sector"] != 32
        or payload["walkers_per_chain"] != 32
    ):
        raise ValueError("fixed schedule walker/chains constraint failed")
    if payload["checkpoint_interval_steps"] > payload["steps"]:
        raise ValueError("fixed schedule checkpoint cadence exceeds training")
    if payload["schedule_version"] != "fixed-v1":
        raise ValueError("fixed schedule version mismatch")
    if payload["optimizer"] != "adam" or payload["learning_rate"] != 1e-3:
        raise ValueError("fixed schedule optimizer is unsupported")
    learning_rate = payload["learning_rate"]
    if (
        not isinstance(learning_rate, (int, float))
        or isinstance(learning_rate, bool)
        or not math.isfinite(learning_rate)
        or learning_rate <= 0
    ):
        raise ValueError("fixed schedule learning rate is invalid")
    weights = (payload["weight_l0"], payload["weight_l2"])
    if any(not isinstance(weight, float) or weight <= 0 for weight in weights) or not math.isclose(
        sum(weights), 1.0, rel_tol=0.0, abs_tol=1e-15
    ):
        raise ValueError("fixed schedule sector weights are invalid")
    for field, expected in (
        ("steps", 10_000),
        ("pilot_sweeps", 500),
        ("burn_in_sweeps", 2_000),
        ("draws_per_update", 16),
        ("thinning_sweeps", 2),
        ("reequilibration_sweeps_after_update", 4),
        ("refresh_log_amplitudes_after_update", True),
        ("checkpoint_interval_steps", 100),
        ("final_evaluation_chains_per_sector", 32),
        ("final_evaluation_burn_in_sweeps", 5_000),
        ("final_evaluation_draws_per_chain", 4_096),
        ("final_evaluation_thinning_sweeps", 4),
    ):
        if payload[field] != expected:
            raise ValueError(f"fixed schedule {field} mismatch")


PRODUCTION_VMC_CONFIG_SCHEMA = "challenge15.production-vmc-config.v1"
PRODUCTION_VMC_CONFIG_FIELDS = frozenset(
    {
        "optimizer",
        "learning_rate",
        "steps",
        "weight_l0",
        "weight_l2",
        "chains_per_sector",
        "walkers_per_chain",
        "pilot_sweeps",
        "burn_in_sweeps",
        "draws_per_update",
        "thinning_sweeps",
        "reequilibration_sweeps_after_update",
        "refresh_log_amplitudes_after_update",
        "checkpoint_interval_steps",
        "final_evaluation_chains_per_sector",
        "final_evaluation_burn_in_sweeps",
        "final_evaluation_draws_per_chain",
        "final_evaluation_thinning_sweeps",
        "schedule_version",
    }
)


def production_vmc_config_envelope(payload: Mapping[str, Any]) -> dict[str, JSONValue]:
    value = _payload(payload)
    if set(value) != PRODUCTION_VMC_CONFIG_FIELDS:
        raise ValueError("production VMC config fields mismatch")
    expected = {
        "optimizer": "adam",
        "learning_rate": 1e-3,
        "steps": 10_000,
        "weight_l0": 0.5,
        "weight_l2": 0.5,
        "chains_per_sector": 32,
        "walkers_per_chain": 32,
        "pilot_sweeps": 500,
        "burn_in_sweeps": 2_000,
        "draws_per_update": 16,
        "thinning_sweeps": 2,
        "reequilibration_sweeps_after_update": 4,
        "refresh_log_amplitudes_after_update": True,
        "checkpoint_interval_steps": 100,
        "final_evaluation_chains_per_sector": 32,
        "final_evaluation_burn_in_sweeps": 5_000,
        "final_evaluation_draws_per_chain": 4_096,
        "final_evaluation_thinning_sweeps": 4,
        "schedule_version": "fixed-v1",
    }
    if value != expected:
        raise ValueError("production VMC config differs from DESIGN section 7.1")
    return {
        "schema": PRODUCTION_VMC_CONFIG_SCHEMA,
        "payload": value,
        "payload_sha256": payload_sha256(value),
    }


def validate_production_vmc_config_envelope(
    value: str | bytes | Mapping[str, Any] | Path,
) -> dict[str, JSONValue]:
    document = _load_document(value)
    if isinstance(value, Path) and value.read_bytes() != canonical_json(document) + b"\n":
        raise ValueError("stored production VMC config is not exact canonical JSON")
    if (
        set(document) != ENVELOPE_FIELDS
        or document.get("schema") != PRODUCTION_VMC_CONFIG_SCHEMA
    ):
        raise ValueError("production VMC config envelope schema mismatch")
    payload = document.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("production VMC config payload must be an object")
    expected = production_vmc_config_envelope(payload)
    if document != expected:
        raise ValueError("production VMC config payload hash mismatch")
    return _json_value(payload)


def validate_runtime_attestations(
    value: Any,
    *,
    particles: int | None = None,
) -> None:
    if not isinstance(value, Mapping) or set(value) != set(RUNTIME_ROLES):
        raise ValueError("runtime attestations must contain every exact role")
    if particles == 8:
        cpu_controller = "wuzh02"
    elif particles is None:
        oracle = value.get("oracle")
        if not isinstance(oracle, Mapping) or len(oracle) != 1:
            raise ValueError("oracle runtime controller is missing")
        cpu_controller = next(iter(oracle))
        if cpu_controller not in {"lasg02", "wuzh02"}:
            raise ValueError("oracle runtime controller does not match production policy")
    else:
        cpu_controller = "lasg02"
    expected = {
        "training": "qdeshell",
        "coordinate": "qdeshell",
        "oracle": cpu_controller,
        "exact": cpu_controller,
        "reducer": cpu_controller,
    }
    seen: set[str] = set()
    for role, controller_map in value.items():
        if not isinstance(controller_map, Mapping) or set(controller_map) != {expected[role]}:
            raise ValueError(f"{role} runtime controller does not match production policy")
        digest = controller_map[expected[role]]
        _require_sha256(digest, f"{role}/{expected[role]} runtime")
        if digest in seen:
            raise ValueError("runtime digest is copied across role/controller identities")
        seen.add(digest)


def validate_seed_owner(owner: SeedOwner) -> None:
    payload = owner.to_payload()
    _validate_payload_fields("challenge15.seed-owner.v1", payload)
    if tuple(owner.expected_seed_set) != (0, 1, 2, 3, 4):
        raise ValueError("owner expected seed set does not match policy")
    _require_integer(owner.seed, "owner seed", minimum=0)
    if owner.seed not in owner.expected_seed_set:
        raise ValueError("owner seed is outside expected seed set")
    for field in (
        "base_configuration_sha256",
        "claim_nonce_sha256",
        "policy_sha256",
        "source_manifest_sha256",
    ):
        _require_sha256(getattr(owner, field), field.replace("_", " "))
    validate_runtime_attestations(owner.runtime_attestations)
    if owner.policy_sha256 != current_policy_sha256():
        raise ValueError("seed owner has stale production policy")


def validate_rank_extension_decision(decision: RankExtensionDecision) -> None:
    _validate_payload_fields(
        "challenge15.rank-extension-decision.v1", decision.to_payload()
    )
    _validate_common(decision.to_payload())
    _require_integer(decision.seed, "decision seed", minimum=0)
    _require_integer(decision.new_rank, "decision new rank", minimum=1)
    if decision.current_rank is not None:
        _require_integer(decision.current_rank, "decision current rank", minimum=1)
    if decision.current_rank is None:
        if decision.new_rank != 1 or decision.reason != "initial":
            raise ValueError("root rank extension decision must be exact")
        prior = (
            decision.prior_expected_ranks_sha256,
            decision.prior_reduction_sha256,
            decision.prior_finalization_sha256,
            decision.prior_import_receipt_sha256,
            decision.prior_transfer_receipt_sha256,
        )
        if any(value is not None for value in prior):
            raise ValueError("root rank extension decision cannot have prior receipts")
    else:
        if decision.new_rank != 2 * decision.current_rank:
            raise ValueError("rank extension decision must consecutively double")
        if decision.reason not in {
            "scheduled_initial_ladder",
            "rank_convergence_pending",
        }:
            raise ValueError("non-root rank extension decision reason is invalid")
        for field in (
            "prior_expected_ranks_sha256",
            "prior_reduction_sha256",
            "prior_finalization_sha256",
            "prior_import_receipt_sha256",
            "prior_transfer_receipt_sha256",
        ):
            _require_sha256(getattr(decision, field), field.replace("_", " "))


def validate_rank_extension(
    extension: RankExtension,
    decision: RankExtensionDecision | None = None,
) -> None:
    _validate_payload_fields("challenge15.rank-extension.v1", extension.to_payload())
    if tuple(extension.expected_seed_set) != (0, 1, 2, 3, 4):
        raise ValueError("rank extension expected seed set does not match policy")
    _require_integer(extension.particles, "particles", minimum=1)
    _require_integer(extension.seed, "seed", minimum=0)
    _require_integer(extension.new_rank, "new rank", minimum=1)
    if extension.previous_rank is not None:
        _require_integer(extension.previous_rank, "previous rank", minimum=1)
    if extension.seed not in extension.expected_seed_set:
        raise ValueError("rank extension seed is outside expected seed set")
    if extension.embedding_algorithm != "copy-old-append-zero-gates-v1":
        raise ValueError("rank extension embedding algorithm is invalid")
    _validate_common(extension.to_payload())
    _require_sha256(
        extension.rank_extension_decision_sha256,
        "rank extension decision SHA256",
    )
    if extension.previous_rank is None:
        if extension.new_rank != 1 or extension.reason != "initial":
            raise ValueError("root rank extension must be rank 1 with initial reason")
        if any(
            value is not None
            for value in (
                extension.parent_generation_sha256,
                extension.parent_parameter_sha256,
                extension.parent_optimizer_state_sha256,
            )
        ):
            raise ValueError("root rank extension cannot have parent state")
    else:
        if extension.new_rank != 2 * extension.previous_rank:
            raise ValueError("rank extension must consecutively double")
        if extension.reason not in {
            "scheduled_initial_ladder",
            "rank_convergence_pending",
        }:
            raise ValueError("non-root rank extension reason is invalid")
        _require_sha256(extension.parent_generation_sha256, "parent generation")
        _require_sha256(extension.parent_parameter_sha256, "parent parameter")
        _require_sha256(
            extension.parent_optimizer_state_sha256, "parent optimizer state"
        )
    if decision is not None:
        validate_rank_extension_decision(decision)
        if extension.rank_extension_decision_sha256 != payload_sha256(
            decision.to_payload()
        ):
            raise ValueError("rank extension decision SHA256 mismatch")
        bindings = {
            "seed": (extension.seed, decision.seed),
            "current rank": (extension.previous_rank, decision.current_rank),
            "new rank": (extension.new_rank, decision.new_rank),
            "base configuration": (
                extension.base_configuration_sha256,
                decision.base_configuration_sha256,
            ),
            "policy": (extension.policy_sha256, decision.policy_sha256),
            "source": (
                extension.source_manifest_sha256,
                decision.source_manifest_sha256,
            ),
            "runtime": (
                extension.to_payload()["runtime_attestations"],
                decision.to_payload()["runtime_attestations"],
            ),
            "reason": (extension.reason, decision.reason),
        }
        for name, (actual, expected) in bindings.items():
            if actual != expected:
                raise ValueError(f"rank extension decision {name} mismatch")


def validate_training_snapshot(snapshot: TrainingSnapshot) -> None:
    payload = snapshot.to_payload()
    _validate_payload_fields("challenge15.training-snapshot.v1", payload)
    _validate_common(payload)
    if snapshot.step < 0:
        raise ValueError("snapshot step must be nonnegative")
    for field in (
        "parameter_sha256",
        "optimizer_state_sha256",
        "walker_state_sha256",
        "log_amplitude_sha256",
        "prng_state_sha256",
    ):
        _require_sha256(getattr(snapshot, field), field.replace("_", " "))


def validate_training_attempt(attempt: TrainingAttempt) -> None:
    payload = attempt.to_payload()
    _validate_payload_fields("challenge15.training-attempt.v1", payload)
    if attempt.seed < 0 or attempt.rank < 1 or not attempt.attempt_id:
        raise ValueError("training attempt identity is invalid")
    _require_sha256(attempt.owner_sha256, "training attempt owner")
    _require_sha256(attempt.extension_sha256, "training attempt extension")
    if attempt.started_from_snapshot_sha256 is not None:
        _require_sha256(
            attempt.started_from_snapshot_sha256,
            "training attempt starting snapshot",
        )
    if attempt.terminal_snapshot_sha256 is not None:
        _require_sha256(
            attempt.terminal_snapshot_sha256,
            "training attempt terminal snapshot",
        )
    if (attempt.status == "complete") != (
        attempt.terminal_snapshot_sha256 is not None
    ):
        raise ValueError("only complete attempts bind a terminal snapshot")
    if attempt.status not in {"running", "failed", "complete"}:
        raise ValueError("training attempt status is invalid")


def validate_recovery_receipt(receipt: RecoveryReceipt) -> None:
    payload = receipt.to_payload()
    _validate_payload_fields("challenge15.recovery-receipt.v1", payload)
    if receipt.seed < 0 or receipt.rank < 1:
        raise ValueError("recovery receipt identity is invalid")
    _require_sha256(receipt.attempt_sha256, "recovery attempt")
    _require_sha256(receipt.stale_lock_sha256, "recovery stale lock")
    if receipt.scheduler_state not in {
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "TIMEOUT",
        "OUT_OF_MEMORY",
        "ABSENT",
    }:
        raise ValueError("recovery scheduler state is not provably inactive")


def validate_training_generation(generation: TrainingGeneration) -> None:
    payload = generation.to_payload()
    _validate_payload_fields("challenge15.training-generation.v1", payload)
    _validate_common(payload)
    if generation.rank < 1:
        raise ValueError("generation rank must be positive")
    for field in (
        "attempt_sha256",
        "extension_sha256",
        "parameter_sha256",
        "optimizer_state_sha256",
        "terminal_snapshot_sha256",
    ):
        _require_sha256(getattr(generation, field), field.replace("_", " "))
    parents = (
        generation.parent_generation_sha256,
        generation.parent_parameter_sha256,
        generation.parent_optimizer_state_sha256,
    )
    if generation.rank == 1:
        if any(value is not None for value in parents):
            raise ValueError("root generation cannot have parent state")
    else:
        for label, value in zip(
            ("parent generation", "parent parameter", "parent optimizer state"),
            parents,
            strict=True,
        ):
            _require_sha256(value, label)


def _validate_common(payload: Mapping[str, Any]) -> None:
    for field in (
        "policy_sha256",
        "source_manifest_sha256",
        "base_configuration_sha256",
    ):
        _require_sha256(payload.get(field), field.replace("_", " "))
    particles = payload.get("particles")
    if not isinstance(particles, int) or isinstance(particles, bool) or particles <= 0:
        raise ValueError("particles must be a positive integer")
    validate_runtime_attestations(payload.get("runtime_attestations"), particles=particles)
    if payload["policy_sha256"] != current_policy_sha256():
        raise ValueError("artifact has stale production policy")


def validate_orchestration_attempt_intent(
    intent: OrchestrationAttemptIntent,
) -> None:
    payload = intent.to_payload()
    _validate_payload_fields("challenge15.orchestration-attempt-intent.v1", payload)
    _validate_schema_semantics("challenge15.orchestration-attempt-intent.v1", payload)
    if intent.attempt < 1:
        raise ValueError("orchestration attempt number must be positive")
    if not intent.expected_output_identities:
        raise ValueError("attempt intent must declare output identities")
    if not intent.create_only_namespace_identities:
        raise ValueError("attempt intent must declare create-only namespaces")
    if len(set(intent.create_only_namespace_identities)) != len(
        intent.create_only_namespace_identities
    ):
        raise ValueError("attempt intent has duplicate create-only namespaces")
    expected = attempt_correlation_id(intent)
    if intent.correlation_id != expected:
        raise ValueError("attempt intent correlation ID mismatch")
    if intent.scheduler_job_name is not None:
        if intent.scheduler_job_name != f"c15-{intent.correlation_id[:24]}":
            raise ValueError("attempt intent scheduler job name mismatch")
        if intent.scheduler_comment != intent.correlation_id:
            raise ValueError("attempt intent scheduler comment mismatch")


def attempt_correlation_id(intent: OrchestrationAttemptIntent) -> str:
    """Derive the deterministic external-action correlation identity."""

    identity = {
        "state_key_sha256": intent.state_key_sha256,
        "transition_identity_sha256": intent.transition_identity_sha256,
        "attempt": intent.attempt,
        "action_kind": intent.action_kind,
        "source_controller": intent.source_controller,
        "destination_controller": intent.destination_controller,
        "script_sha256": intent.script_sha256,
        "canonical_argv_sha256": intent.canonical_argv_sha256,
        "input_sha256s": list(intent.input_sha256s),
    }
    return payload_sha256(identity)


def _require_finite_float(
    value: Any,
    label: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite JSON float")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be at most {maximum}")
    return value


def _require_exact_object(
    value: Any,
    fields: set[str] | frozenset[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(fields):
        raise ValueError(f"{label} nested fields mismatch")
    return value


def _chiral_close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)


def _validate_chiral_response(payload: Mapping[str, Any]) -> None:
    _require_integer(payload["particles"], "chiral response particles", minimum=2)
    if payload["particles"] > 8:
        raise ValueError("chiral response particles must be at most 8")
    if type(payload["orientation"]) is not int or payload["orientation"] != 1:
        raise ValueError("chiral response orientation must be outward positive Q")

    physical = _require_exact_object(
        payload["physical_conventions"],
        {
            "spatial_geometry",
            "spatial_metric_varied",
            "area_varied",
            "radius",
            "integration_measure",
            "chord_coulomb_varied",
            "interaction",
            "sphere_orientation",
            "electron_charge",
            "monopole_sign",
            "response_source",
            "curved_sphere_effective_mass_claim",
            "landau_level_derivative_used",
        },
        "chiral response physical conventions",
    )
    expected_physical = {
        "spatial_geometry": "fixed-round-sphere",
        "spatial_metric_varied": False,
        "area_varied": False,
        "radius": "sqrt(Q)*l_B",
        "integration_measure": "fixed-round-sphere",
        "chord_coulomb_varied": False,
        "interaction": "physical-chord-Coulomb",
        "sphere_orientation": "outward",
        "electron_charge": "-e",
        "monopole_sign": "Q>0",
        "response_source": (
            "LHYR-planar-projected-Coulomb-Wigner-Eckart-covariantization"
        ),
        "curved_sphere_effective_mass_claim": False,
        "landau_level_derivative_used": False,
    }
    physical_flags = (
        "spatial_metric_varied",
        "area_varied",
        "chord_coulomb_varied",
        "curved_sphere_effective_mass_claim",
        "landau_level_derivative_used",
    )
    if any(type(physical[field]) is not bool for field in physical_flags) or dict(
        physical
    ) != expected_physical:
        raise ValueError("chiral response physical conventions mismatch")

    source = _require_exact_object(
        payload["source"],
        {
            "fixture_sha256",
            "fixture_schema",
            "normalization",
            "minus_direction",
            "plus_direction",
            "plus_definition",
            "expected_channel",
            "expected_local_frame_helicity",
            "global_tensor_components",
        },
        "chiral response source",
    )
    _require_sha256(source["fixture_sha256"], "chiral response fixture")
    expected_source = {
        "fixture_sha256": source["fixture_sha256"],
        "fixture_schema": "challenge15.chiral-covariant-pair-fixture.v1",
        "normalization": "raw-LHYR-planar-Coulomb-E_C-resolution-eq-5.6",
        "minus_direction": "m_plus_2_to_m",
        "plus_direction": "m_to_m_plus_2",
        "plus_definition": "O_{+,M}=(-1)^M(O_{-,-M})†",
        "expected_channel": "-",
        "expected_local_frame_helicity": -2,
        "global_tensor_components": ["-2", "-1", "0", "1", "2"],
    }
    if (
        type(source["expected_local_frame_helicity"]) is not int
        or dict(source) != expected_source
    ):
        raise ValueError("chiral response source conventions mismatch")

    initial = _require_exact_object(
        payload["initial_state"],
        {
            "kind",
            "coefficient_sha256",
            "estimator_scope",
            "rank",
            "seed",
            "checkpoint_sha256",
            "checkpoint_record_sha256",
            "generation_sha256",
            "parameter_sha256",
            "determinant_block",
            "exact_ground_overlap",
        },
        "chiral response initial state",
    )
    configuration = _require_exact_object(
        payload["configuration"],
        {
            "mode",
            "particles",
            "oracle_sha256",
            "generation_sha256",
            "checkpoint_sha256",
            "checkpoint_record_sha256",
            "parameter_sha256",
            "rank",
            "seed",
            "determinant_block",
        },
        "chiral response configuration",
    )
    if configuration["mode"] not in {"exact-size", "oracle-reuse", "mixed"}:
        raise ValueError("chiral response configuration mode is invalid")
    if (
        type(configuration["particles"]) is not int
        or configuration["particles"] != payload["particles"]
    ):
        raise ValueError("chiral response configuration particles mismatch")
    _require_sha256(
        configuration["oracle_sha256"],
        "chiral response configuration oracle",
    )
    inputs = _require_exact_object(
        payload["input_sha256"],
        {
            "fixture",
            "oracle_artifact",
            "oracle_cache",
            "nqs_generation",
            "nqs_checkpoint",
            "parameter",
            "configuration",
        },
        "chiral response input SHA256",
    )
    identities = _require_exact_object(
        payload["input_identities"],
        {
            "oracle",
            "generation",
            "checkpoint",
            "checkpoint_record",
            "parameter",
            "configuration",
        },
        "chiral response input identities",
    )
    for name in ("fixture", "configuration"):
        _require_sha256(inputs[name], f"chiral response input {name}")
    oracle_inputs = (inputs["oracle_artifact"], inputs["oracle_cache"])
    if sum(value is not None for value in oracle_inputs) != 1:
        raise ValueError("chiral response requires exactly one oracle artifact/cache")
    for name in (
        "oracle_artifact",
        "oracle_cache",
        "nqs_generation",
        "nqs_checkpoint",
        "parameter",
    ):
        if inputs[name] is not None:
            _require_sha256(inputs[name], f"chiral response input {name}")
    if inputs["fixture"] != source["fixture_sha256"]:
        raise ValueError("chiral response fixture provenance mismatch")
    if inputs["configuration"] != payload_sha256(configuration):
        raise ValueError("chiral response configuration provenance mismatch")
    selected_oracle_sha = (
        inputs["oracle_artifact"]
        if inputs["oracle_artifact"] is not None
        else inputs["oracle_cache"]
    )
    if configuration["oracle_sha256"] != selected_oracle_sha:
        raise ValueError("chiral response oracle provenance mismatch")
    expected_identity_schemas = {
        "oracle": (
                "challenge15.oracle-cache.v2"
            if inputs["oracle_cache"] is not None
            else "challenge15.cli-oracle.v1"
        ),
        "generation": "challenge15.training-generation.v1",
        "checkpoint": "challenge15.train-checkpoint.v1",
        "checkpoint_record": "challenge15.train-checkpoint-record.v1",
        "parameter": "challenge15.parameter-blob.v1",
        "configuration": "challenge15.response-configuration.v1",
    }
    expected_identity_hashes = {
        "oracle": selected_oracle_sha,
        "generation": inputs["nqs_generation"],
        "checkpoint": inputs["nqs_checkpoint"],
        "checkpoint_record": initial["checkpoint_record_sha256"],
        "parameter": inputs["parameter"],
        "configuration": inputs["configuration"],
    }
    for role, expected_sha in expected_identity_hashes.items():
        identity = identities[role]
        if expected_sha is None:
            if identity is not None:
                raise ValueError(
                    f"chiral response {role} identity must be null"
                )
            continue
        item = _require_exact_object(
            identity,
            {"identity_role", "artifact_schema", "sha256"},
            f"chiral response {role} identity",
        )
        _require_sha256(item["sha256"], f"chiral response {role} identity")
        if (
            item["identity_role"] != role
            or item["artifact_schema"] != expected_identity_schemas[role]
            or item["sha256"] != expected_sha
        ):
            raise ValueError(f"chiral response {role} typed identity mismatch")
    exact_role_digests = {
        "oracle": selected_oracle_sha,
        "configuration": inputs["configuration"],
    }
    if len(set(exact_role_digests.values())) != len(exact_role_digests):
        raise ValueError("chiral response role identities must be distinct")

    nqs_pair = (inputs["nqs_generation"], inputs["nqs_checkpoint"])
    if initial["kind"] == "exact-ground":
        if (
            initial["coefficient_sha256"] is not None
            or initial["estimator_scope"] != "exact-ED-initial-and-final-states"
            or any(value is not None for value in nqs_pair)
            or inputs["parameter"] is not None
            or any(
                initial[field] is not None
                for field in (
                    "rank",
                    "seed",
                    "checkpoint_sha256",
                    "checkpoint_record_sha256",
                    "generation_sha256",
                    "parameter_sha256",
                    "determinant_block",
                    "exact_ground_overlap",
                )
            )
            or any(
                configuration[field] is not None
                for field in (
                    "generation_sha256",
                    "checkpoint_sha256",
                    "checkpoint_record_sha256",
                    "parameter_sha256",
                    "rank",
                    "seed",
                    "determinant_block",
                )
            )
            or configuration["mode"] not in {"exact-size", "oracle-reuse"}
        ):
            raise ValueError("exact chiral response initial-state provenance mismatch")
    elif initial["kind"] == "nqs-determinant":
        _require_sha256(
            initial["coefficient_sha256"],
            "chiral response initial coefficient",
        )
        if (
            initial["estimator_scope"]
            != "exact-finite-Hilbert-contraction-with-exact-ED-L2-finals"
            or any(value is None for value in nqs_pair)
            or inputs["parameter"] is None
            or configuration["mode"] != "mixed"
        ):
            raise ValueError("NQS chiral response initial-state provenance mismatch")
        for field in ("rank", "determinant_block"):
            _require_integer(
                initial[field],
                f"chiral response initial state {field}",
                minimum=1,
            )
        _require_integer(
            initial["seed"],
            "chiral response initial state seed",
            minimum=0,
        )
        for field in (
            "checkpoint_sha256",
            "checkpoint_record_sha256",
            "generation_sha256",
            "parameter_sha256",
        ):
            _require_sha256(
                initial[field],
                f"chiral response initial state {field}",
            )
        _require_finite_float(
            initial["exact_ground_overlap"],
            "chiral response exact-ground overlap",
            minimum=0.0,
            maximum=1.0,
        )
        metadata_fields = (
            "rank",
            "seed",
            "checkpoint_sha256",
            "checkpoint_record_sha256",
            "generation_sha256",
            "parameter_sha256",
            "determinant_block",
        )
        if any(initial[field] != configuration[field] for field in metadata_fields):
            raise ValueError("chiral response mixed metadata mismatch")
        if (
            initial["generation_sha256"] != inputs["nqs_generation"]
            or initial["checkpoint_sha256"] != inputs["nqs_checkpoint"]
            or initial["parameter_sha256"] != inputs["parameter"]
        ):
            raise ValueError("chiral response mixed metadata input mismatch")
        if inputs["nqs_generation"] == inputs["nqs_checkpoint"]:
            raise ValueError(
                "chiral response generation and checkpoint identities must be distinct"
            )
        mixed_role_digests = {
            **exact_role_digests,
            "generation": inputs["nqs_generation"],
            "checkpoint": inputs["nqs_checkpoint"],
            "checkpoint_record": initial["checkpoint_record_sha256"],
            "parameter": inputs["parameter"],
        }
        if len(set(mixed_role_digests.values())) != len(mixed_role_digests):
            raise ValueError("chiral response role identities must be distinct")
    else:
        raise ValueError("chiral response initial-state kind is invalid")

    channels = _require_exact_object(
        payload["channels"], {"+", "-"}, "chiral response channels"
    )
    channel_fields = {
        "component_weights",
        "poles",
        "spectral_weight",
        "direct_sum_weight",
        "recovered_fraction",
        "lowest_pole_weight",
        "pole_fraction",
        "zero_source",
    }
    component_keys = {"-2", "-1", "0", "1", "2"}
    identically_zero_sources: dict[str, bool] = {}
    for helicity in ("+", "-"):
        channel = _require_exact_object(
            channels[helicity],
            channel_fields,
            f"chiral response channel {helicity}",
        )
        components = _require_exact_object(
            channel["component_weights"],
            component_keys,
            f"chiral response channel {helicity} components",
        )
        component_values = [
            _require_finite_float(
                components[key],
                f"chiral response channel {helicity} component {key}",
                minimum=0.0,
            )
            for key in ("-2", "-1", "0", "1", "2")
        ]
        identically_zero_source = all(weight == 0.0 for weight in component_values)
        identically_zero_sources[helicity] = identically_zero_source
        spectral = _require_finite_float(
            channel["spectral_weight"],
            f"chiral response channel {helicity} spectral weight",
            minimum=0.0,
        )
        direct = _require_finite_float(
            channel["direct_sum_weight"],
            f"chiral response channel {helicity} direct sum weight",
            minimum=0.0,
        )
        lowest = _require_finite_float(
            channel["lowest_pole_weight"],
            f"chiral response channel {helicity} lowest pole weight",
            minimum=0.0,
        )
        recovered = _require_finite_float(
            channel["recovered_fraction"],
            f"chiral response channel {helicity} recovered fraction",
            minimum=0.99,
        )
        pole_fraction = _require_finite_float(
            channel["pole_fraction"],
            f"chiral response channel {helicity} pole fraction",
            minimum=0.0,
            maximum=1.0,
        )
        if type(channel["zero_source"]) is not bool:
            raise ValueError(
                f"chiral response channel {helicity} zero-source diagnostic is invalid"
            )
        poles = channel["poles"]
        if not isinstance(poles, list):
            raise ValueError(f"chiral response channel {helicity} poles must be a list")
        pole_weights: list[float] = []
        previous_energy: float | None = None
        seen_member_indices: set[int] = set()
        for index, pole_value in enumerate(poles):
            pole = _require_exact_object(
                pole_value,
                {
                    "energy",
                    "degeneracy",
                    "member_indices",
                    "member_weights",
                    "weight",
                    "fraction",
                },
                f"chiral response channel {helicity} pole {index}",
            )
            energy = _require_finite_float(
                pole["energy"],
                f"chiral response channel {helicity} pole {index} energy",
                minimum=0.0,
            )
            if previous_energy is not None and energy < previous_energy:
                raise ValueError(
                    f"chiral response channel {helicity} poles are not energy ordered"
                )
            previous_energy = energy
            _require_integer(
                pole["degeneracy"],
                f"chiral response channel {helicity} pole {index} degeneracy",
                minimum=1,
            )
            member_indices = pole["member_indices"]
            member_weights = pole["member_weights"]
            if (
                not isinstance(member_indices, list)
                or not isinstance(member_weights, list)
                or len(member_indices) != pole["degeneracy"]
                or len(member_weights) != pole["degeneracy"]
            ):
                raise ValueError(
                    f"chiral response channel {helicity} pole {index} members mismatch"
                )
            for member_index in member_indices:
                _require_integer(
                    member_index,
                    f"chiral response channel {helicity} pole member index",
                    minimum=0,
                )
                if member_index in seen_member_indices:
                    raise ValueError(
                        f"chiral response channel {helicity} has duplicate pole member"
                    )
                seen_member_indices.add(member_index)
            member_weight_values = [
                _require_finite_float(
                    member_weight,
                    f"chiral response channel {helicity} pole member weight",
                    minimum=0.0,
                )
                for member_weight in member_weights
            ]
            pole_weight = _require_finite_float(
                pole["weight"],
                f"chiral response channel {helicity} pole {index} weight",
                minimum=0.0,
            )
            if not _chiral_close(pole_weight, math.fsum(member_weight_values)):
                raise ValueError(
                    f"chiral response channel {helicity} pole member weights mismatch"
                )
            _require_finite_float(
                pole["fraction"],
                f"chiral response channel {helicity} pole {index} fraction",
                minimum=0.0,
                maximum=1.0,
            )
            pole_weights.append(pole_weight)
        expected_lowest = pole_weights[0] if pole_weights else 0.0
        expected_pole_fraction = 0.0 if spectral == 0.0 else lowest / spectral
        if identically_zero_source:
            if (
                direct != 0.0
                or spectral != 0.0
                or lowest != 0.0
                or any(weight != 0.0 for weight in pole_weights)
                or any(pole["fraction"] != 0.0 for pole in poles)
                or any(
                    member_weight != 0.0
                    for pole in poles
                    for member_weight in pole["member_weights"]
                )
            ):
                raise ValueError(
                    f"chiral response channel {helicity} zero source has nonzero spectrum"
                )
            if recovered != 1.0:
                raise ValueError(
                    f"chiral response channel {helicity} zero-source recovered fraction"
                )
            if pole_fraction != 0.0:
                raise ValueError(
                    f"chiral response channel {helicity} zero-source pole fraction"
                )
            if channel["zero_source"] is not True:
                raise ValueError(
                    f"chiral response channel {helicity} zero-source diagnostic mismatch"
                )
        else:
            if direct <= 0.0:
                raise ValueError(
                    f"chiral response channel {helicity} positive source has "
                    "nonpositive direct weight"
                )
            if not _chiral_close(direct, math.fsum(component_values)):
                raise ValueError("chiral response direct sum weight is inconsistent")
            if not _chiral_close(spectral, math.fsum(pole_weights)):
                raise ValueError("chiral response spectral pole weights are inconsistent")
            if not _chiral_close(lowest, expected_lowest):
                raise ValueError("chiral response lowest pole weight is inconsistent")
            if lowest > spectral + 1e-12:
                raise ValueError("chiral response lowest pole exceeds spectral weight")
            for index, (pole, pole_weight) in enumerate(
                zip(poles, pole_weights, strict=True)
            ):
                expected_fraction = (
                    0.0 if spectral == 0.0 else pole_weight / spectral
                )
                if not _chiral_close(pole["fraction"], expected_fraction):
                    raise ValueError(
                        f"chiral response channel {helicity} pole {index} "
                        "fraction mismatch"
                    )
            expected_recovered = spectral / direct
            if not _chiral_close(recovered, expected_recovered):
                raise ValueError("chiral response recovered fraction is inconsistent")
            if not _chiral_close(pole_fraction, expected_pole_fraction):
                raise ValueError("chiral response pole fraction is inconsistent")
            if channel["zero_source"] is not False:
                raise ValueError(
                    f"chiral response channel {helicity} zero-source diagnostic mismatch"
                )

    minus_lowest = channels["-"]["lowest_pole_weight"]
    plus_lowest = channels["+"]["lowest_pole_weight"]
    expected_delta = minus_lowest - plus_lowest
    delta = _require_finite_float(payload["delta_weight"], "chiral response delta weight")
    both_sources_zero = all(identically_zero_sources.values())
    if both_sources_zero:
        if delta != 0.0:
            raise ValueError("chiral response both-zero delta weight must be exact zero")
    elif not _chiral_close(delta, expected_delta):
        raise ValueError("chiral response delta weight is inconsistent")
    floor = _require_finite_float(
        payload["contrast_floor"],
        "chiral response contrast floor",
        minimum=0.0,
    )
    if floor <= 0.0:
        raise ValueError("chiral response contrast floor must be positive")
    denominator = minus_lowest + plus_lowest
    contrast = payload["contrast"]
    if both_sources_zero:
        if contrast is not None:
            raise ValueError("chiral response both-zero contrast must be null")
    elif denominator < floor:
        if contrast is not None:
            raise ValueError("chiral response contrast must be null below floor")
    else:
        expected_contrast = expected_delta / denominator
        actual_contrast = _require_finite_float(
            contrast, "chiral response contrast"
        )
        if not _chiral_close(actual_contrast, expected_contrast):
            raise ValueError("chiral response contrast is inconsistent")

    diagnostics = _require_exact_object(
        payload["diagnostics"],
        {
            "tensor_commutator",
            "adjoint",
            "eigenpair",
            "degeneracy",
            "sum_rules_passed",
            "chirality_resolved",
        },
        "chiral response diagnostics",
    )
    diagnostic_specs = {
        "tensor_commutator": ("residual_max", 1e-10),
        "adjoint": ("residual", 1e-12),
        "eigenpair": ("residual_max", 1e-10),
    }
    for name, (residual_field, expected_tolerance) in diagnostic_specs.items():
        item = _require_exact_object(
            diagnostics[name],
            {residual_field, "tolerance", "passed"},
            f"chiral response diagnostic {name}",
        )
        residual = _require_finite_float(
            item[residual_field],
            f"chiral response diagnostic {name} residual",
            minimum=0.0,
        )
        tolerance = _require_finite_float(
            item["tolerance"],
            f"chiral response diagnostic {name} tolerance",
            minimum=0.0,
        )
        if tolerance != expected_tolerance:
            raise ValueError(f"chiral response diagnostic {name} tolerance mismatch")
        if type(item["passed"]) is not bool or item["passed"] is not (
            residual <= tolerance
        ):
            raise ValueError(f"chiral response diagnostic {name} passed mismatch")
    degeneracy = _require_exact_object(
        diagnostics["degeneracy"],
        {"absolute_tolerance_E_C", "relative_tolerance"},
        "chiral response degeneracy diagnostic",
    )
    if (
        _require_finite_float(
            degeneracy["absolute_tolerance_E_C"],
            "chiral response degeneracy absolute tolerance",
            minimum=0.0,
        )
        != 1e-10
        or _require_finite_float(
            degeneracy["relative_tolerance"],
            "chiral response degeneracy relative tolerance",
            minimum=0.0,
        )
        != 1e-9
    ):
        raise ValueError("chiral response degeneracy tolerance mismatch")
    if type(diagnostics["sum_rules_passed"]) is not bool or not diagnostics[
        "sum_rules_passed"
    ]:
        raise ValueError("chiral response sum-rule diagnostic mismatch")
    expected_chirality = (
        contrast is not None
        and delta > 0.0
        and diagnostics["sum_rules_passed"]
        and all(diagnostics[name]["passed"] for name in diagnostic_specs)
    )
    if (
        type(diagnostics["chirality_resolved"]) is not bool
        or diagnostics["chirality_resolved"] is not expected_chirality
    ):
        raise ValueError("chiral response chirality diagnostic mismatch")
    validate_fingerprint(
        payload["execution_fingerprint"],
        context="chiral response",
    )


def _validate_schema_semantics(schema: str, payload: Mapping[str, Any]) -> None:
    _validate_named_hashes(payload)
    _validate_recursive_conventions(payload)
    if COMMON <= set(payload):
        _validate_common(payload)
    if "policy_sha256" in payload and payload["policy_sha256"] != current_policy_sha256():
        raise ValueError("artifact has stale production policy")
    if schema == "challenge15.production-policy.v1":
        if payload != production_policy():
            raise ValueError("production policy payload differs from canonical policy")
    elif schema == "challenge15.chiral-response.v1":
        _validate_chiral_response(payload)
    elif schema == "challenge15.allowed-runtime.v1":
        role = payload["role"]
        controller = payload["controller"]
        if role not in RUNTIME_ROLES:
            raise ValueError("allowed runtime role is invalid")
        if controller not in {"qdeshell", "lasg02", "wuzh02"}:
            raise ValueError("allowed runtime controller is invalid")
        if role in {"training", "coordinate"} and controller != "qdeshell":
            raise ValueError("GPU runtime role/controller mismatch")
        if role in {"oracle", "exact", "reducer"} and controller == "qdeshell":
            raise ValueError("CPU runtime role/controller mismatch")
        if payload["backend"] not in {"cpu", "gpu"}:
            raise ValueError("allowed runtime backend is invalid")
        if (controller == "qdeshell") != (payload["backend"] == "gpu"):
            raise ValueError("allowed runtime backend/controller mismatch")
        tests = payload["attestation_test_members"]
        if not isinstance(tests, list) or not tests:
            raise ValueError("allowed runtime tests must be a nonempty ordered list")
        for item in tests:
            if not isinstance(item, Mapping) or set(item) != {
                "nodeid",
                "test_file_sha256",
                "result_sha256",
            }:
                raise ValueError("allowed runtime test member fields mismatch")
            if not isinstance(item["nodeid"], str) or not item["nodeid"]:
                raise ValueError("allowed runtime test nodeid is invalid")
    elif schema == "challenge15.runtime-attestation-set.v1":
        particles = payload["particles"]
        roles = payload["roles"]
        if not isinstance(roles, Mapping) or set(roles) != set(RUNTIME_ROLES):
            raise ValueError("runtime attestation set roles are incomplete")
        cpu = "wuzh02" if particles == 8 else "lasg02"
        for role, item in roles.items():
            if not isinstance(item, Mapping) or set(item) != {
                "controller",
                "allowed_runtime_sha256",
                "deployment_receipt_sha256",
                "backend",
            }:
                raise ValueError("runtime attestation role fields mismatch")
            expected_controller = (
                "qdeshell" if role in {"training", "coordinate"} else cpu
            )
            expected_backend = (
                "gpu" if role in {"training", "coordinate"} else "cpu"
            )
            if (
                item["controller"] != expected_controller
                or item["backend"] != expected_backend
            ):
                raise ValueError("runtime attestation role/controller mismatch")
    elif schema in {
        "challenge15.cross-size-manifest.v1",
        "challenge15.final-report.v1",
        "challenge15.report-receipt.v1",
    }:
        if payload["particles"] != [6, 7, 8]:
            raise ValueError("aggregate particles must be exactly [6,7,8]")
        by_size = payload["base_configuration_sha256_by_size"]
        if not isinstance(by_size, Mapping) or set(by_size) != {"6", "7", "8"}:
            raise ValueError("aggregate base configuration sizes mismatch")
        for digest in by_size.values():
            _require_sha256(digest, "aggregate base configuration")
    elif schema == "challenge15.identity-map.v1":
        tasks = payload["tasks"]
        if not isinstance(tasks, list) or len(tasks) != payload["task_count"]:
            raise ValueError("identity map task count mismatch")
        seen: set[int] = set()
        for task in tasks:
            if not isinstance(task, Mapping) or set(task) != {
                "array_index",
                "rank",
                "seed",
                "input_sha256",
                "input_path_identity",
                "output_relative_path",
            }:
                raise ValueError("identity map task fields mismatch")
            _require_integer(task["array_index"], "array index", minimum=0)
            if task["array_index"] in seen:
                raise ValueError("identity map has duplicate array index")
            seen.add(task["array_index"])
            if Path(task["output_relative_path"]).is_absolute() or ".." in Path(
                task["output_relative_path"]
            ).parts:
                raise ValueError("identity map output path is invalid")
            _require_absolute_identity(
                task["input_path_identity"], "identity map input path"
            )
    if schema in {
        "challenge15.dry-run-receipt.v1",
        "challenge15.deployment-receipt.v1",
    }:
        for field in ("interpreter",):
            _require_absolute_identity(payload[field], field)
    if schema == "challenge15.deployment-receipt.v1":
        _require_absolute_identity(payload["deployment_root"], "deployment root")
    if schema == "challenge15.seed-owner.v1":
        validate_seed_owner(
            SeedOwner(
                **{
                    **payload,
                    "expected_seed_set": tuple(payload["expected_seed_set"]),
                }
            )
        )
    elif schema == "challenge15.rank-extension.v1":
        validate_rank_extension(
            RankExtension(
                **{
                    **payload,
                    "expected_seed_set": tuple(payload["expected_seed_set"]),
                }
            )
        )
    elif schema == "challenge15.rank-extension-decision.v1":
        validate_rank_extension_decision(RankExtensionDecision(**payload))
    elif schema == "challenge15.training-attempt.v1":
        validate_training_attempt(TrainingAttempt(**payload))
    elif schema == "challenge15.training-snapshot.v1":
        validate_training_snapshot(TrainingSnapshot(**payload))
    elif schema == "challenge15.training-generation.v1":
        validate_training_generation(TrainingGeneration(**payload))


def _validate_named_hashes(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "input_sha256" and isinstance(item, Mapping):
                pass
            elif key.endswith("_sha256") and item is not None:
                _require_sha256(item, key.replace("_", " "))
            elif key.endswith("_sha256s"):
                if isinstance(item, Mapping):
                    digests = [digest for digest in item.values() if digest is not None]
                elif isinstance(item, (list, tuple)):
                    digests = list(item)
                else:
                    raise ValueError(f"{key} must contain SHA256 identities")
                for digest in digests:
                    _require_sha256(digest, key.replace("_", " "))
            elif key in {"members", "member_manifest"} and isinstance(item, Mapping):
                for digest in item.values():
                    _require_sha256(digest, f"{key} member")
            _validate_named_hashes(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_named_hashes(item)


def _validate_recursive_conventions(value: Any, key: str | None = None) -> None:
    integer_fields = {
        "particles",
        "seed",
        "rank",
        "new_rank",
        "previous_rank",
        "current_rank",
        "attempt",
        "step",
        "bytes",
        "task_count",
        "array_concurrency",
        "array_index",
        "walker_microbatch",
        "carrier_block",
        "quadrature_block",
        "nodes",
        "ntasks",
        "cpus_per_task",
        "candidate_count",
    }
    if key in integer_fields and value is not None:
        if key == "particles" and value == [6, 7, 8]:
            pass
        else:
            _require_integer(value, key.replace("_", " "), minimum=0)
    if key == "controller" and value not in {"qdeshell", "lasg02", "wuzh02"}:
        raise ValueError("controller enum is invalid")
    if key in {"source_controller", "destination_controller", "cpu_controller", "gpu_controller"}:
        if value is not None and value not in {"qdeshell", "lasg02", "wuzh02"}:
            raise ValueError(f"{key} enum is invalid")
    if key == "backend" and value not in {"cpu", "gpu"}:
        raise ValueError("backend enum is invalid")
    if key == "role" and value not in set(RUNTIME_ROLES):
        raise ValueError("runtime role enum is invalid")
    if key and (key.endswith("_at_utc") or key.endswith("_utc")):
        if not isinstance(value, str) or not value.endswith("Z") or "T" not in value:
            raise ValueError(f"{key} must be a UTC timestamp")
    if isinstance(value, Mapping):
        for nested_key, nested in value.items():
            if not isinstance(nested_key, str):
                raise ValueError("JSON object keys must be strings")
            _validate_recursive_conventions(nested, nested_key)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _validate_recursive_conventions(nested)


def _require_absolute_identity(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.startswith("/") or "/../" in value:
        raise ValueError(f"{label} must be an absolute canonical path identity")


def validate_canonical_path(
    path: Path | str,
    approved_roots: tuple[Path | str, ...],
) -> Path:
    """Validate an absolute, symlink-free path beneath one approved root."""

    candidate = Path(path)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("path must be absolute without traversal")
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current = current / part
        try:
            if current.is_symlink():
                raise ValueError(f"symlink path component is forbidden: {current}")
        except OSError as exc:
            raise ValueError("path component cannot be inspected") from exc
    roots = tuple(Path(root) for root in approved_roots)
    for root in roots:
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("approved root must be absolute and symlink-free")
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        return candidate
    raise ValueError("path is outside every approved root")


def validate_deployment_context(
    deployment: Mapping[str, Any],
    *,
    approved_roots: tuple[Path | str, ...],
) -> None:
    root = validate_canonical_path(deployment["deployment_root"], approved_roots)
    interpreter = validate_canonical_path(deployment["interpreter"], (root,))
    if interpreter == root:
        raise ValueError("deployment interpreter cannot equal deployment root")


def _open_nofollow(path: Path, *, directory: bool = False) -> int:
    absolute = path.absolute()
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, component in enumerate(absolute.parts[1:]):
            final = index == len(absolute.parts[1:]) - 1
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            if not final or directory:
                flags |= os.O_DIRECTORY
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _hash_open_file(descriptor: int) -> tuple[str, int]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("bundle member is not a regular file")
    digest = hashlib.sha256()
    count = 0
    while chunk := os.read(descriptor, 1024 * 1024):
        digest.update(chunk)
        count += len(chunk)
    after = os.fstat(descriptor)
    if (before.st_dev, before.st_ino, before.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
    ) or count != before.st_size:
        raise ValueError("bundle member changed while hashing")
    return digest.hexdigest(), count


def _manifest_from_directory_fd(root: Path) -> tuple[dict[str, str], int]:
    root_fd = _open_nofollow(root, directory=True)
    manifest: dict[str, str] = {}
    total = 0

    def walk(directory_fd: int, prefix: str) -> None:
        nonlocal total
        for name in sorted(os.listdir(directory_fd)):
            metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            relative = f"{prefix}/{name}" if prefix else name
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError("bundle manifest contains a symlink")
            if stat.S_ISDIR(metadata.st_mode):
                child = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=directory_fd,
                )
                try:
                    walk(child, relative)
                finally:
                    os.close(child)
            elif stat.S_ISREG(metadata.st_mode):
                member = os.open(
                    name,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=directory_fd,
                )
                try:
                    digest, size = _hash_open_file(member)
                finally:
                    os.close(member)
                manifest[relative] = digest
                total += size
            else:
                raise ValueError("bundle manifest contains a special file")

    try:
        walk(root_fd, "")
    finally:
        os.close(root_fd)
    return manifest, total


def _hash_bundle_file(path: Path, approved_roots: tuple[Path | str, ...]) -> tuple[str, int]:
    validate_canonical_path(path, approved_roots)
    descriptor = _open_nofollow(path)
    try:
        return _hash_open_file(descriptor)
    finally:
        os.close(descriptor)


def validate_export_context(
    payload: Mapping[str, Any],
    context: Mapping[str, Any],
) -> int:
    approved = tuple(context["approved_roots"])
    root = validate_canonical_path(payload["source_root"], approved)
    if payload["source_controller"] != context["source_controller"]:
        raise ValueError("export source controller mismatch")
    if payload["bundle_role"] != context["bundle_role"]:
        raise ValueError("export bundle role mismatch")
    manifest, _ = _manifest_from_directory_fd(root)
    if payload["member_manifest"] != manifest:
        raise ValueError("export member manifest mismatch")
    sums = "".join(f"{digest}  {name}\n" for name, digest in sorted(manifest.items()))
    if payload["sha256sums_sha256"] != hashlib.sha256(sums.encode()).hexdigest():
        raise ValueError("export SHA256SUMS mismatch")
    bundle_sha, bundle_bytes = _hash_bundle_file(Path(context["bundle_path"]), approved)
    if payload["bundle_sha256"] != bundle_sha:
        raise ValueError("export bundle payload hash mismatch")
    if payload["source_artifact_sha256"] != context["source_artifact_sha256"]:
        raise ValueError("export source artifact mismatch")
    return bundle_bytes


def validate_import_context(
    payload: Mapping[str, Any],
    context: Mapping[str, Any],
) -> int:
    approved = tuple(context["approved_roots"])
    root = validate_canonical_path(payload["destination_root"], approved)
    if payload["destination_controller"] != context["destination_controller"]:
        raise ValueError("import destination controller mismatch")
    member_root = validate_canonical_path(context.get("member_root", root), (root,))
    manifest, _ = _manifest_from_directory_fd(member_root)
    if payload["member_manifest"] != manifest:
        raise ValueError("import member manifest mismatch")
    bundle_sha, bundle_bytes = _hash_bundle_file(Path(context["bundle_path"]), approved)
    if payload["bundle_sha256"] != bundle_sha:
        raise ValueError("import bundle payload hash mismatch")
    if payload["imported_artifact_sha256"] != context["imported_artifact_sha256"]:
        raise ValueError("import artifact mismatch")
    return bundle_bytes


def _context_envelope_digest(
    path: Path | str,
    schema: str,
    approved_roots: tuple[Path | str, ...],
) -> str:
    canonical = validate_canonical_path(path, approved_roots)
    return payload_sha256(validate_envelope(canonical, schema))


def _context_file_digest(
    path: Path | str,
    approved_roots: tuple[Path | str, ...],
) -> str:
    return _hash_bundle_file(Path(path), approved_roots)[0]


def validate_transfer_context(
    export_payload: Mapping[str, Any],
    import_payload: Mapping[str, Any],
    transfer_payload: Mapping[str, Any],
    *,
    approved_source_roots: tuple[Path | str, ...],
    approved_destination_roots: tuple[Path | str, ...],
) -> None:
    if transfer_payload["export_bundle_sha256"] != payload_sha256(export_payload):
        raise ValueError("transfer/export bundle binding mismatch")
    if transfer_payload["import_bundle_sha256"] != payload_sha256(import_payload):
        raise ValueError("transfer/import bundle binding mismatch")
    if export_payload["bundle_sha256"] != import_payload["bundle_sha256"]:
        raise ValueError("export/import bundle identity mismatch")
    if (
        export_payload["source_controller"] != transfer_payload["source_controller"]
        or import_payload["destination_controller"]
        != transfer_payload["destination_controller"]
    ):
        raise ValueError("transfer controller binding mismatch")
    if export_payload["member_manifest"] != import_payload["member_manifest"]:
        raise ValueError("transfer member manifest mismatch")
    validate_canonical_path(export_payload["source_root"], approved_source_roots)
    destination_root = validate_canonical_path(
        import_payload["destination_root"],
        approved_destination_roots,
    )
    validate_canonical_path(transfer_payload["partial_path"], (destination_root,))
    validate_canonical_path(transfer_payload["final_path"], (destination_root,))


def validate_receipt_context(
    schema: str,
    payload: Mapping[str, Any],
    context: Mapping[str, Any],
) -> None:
    """Bind a receipt to all externally supplied endpoint and parent objects."""

    def bind(field: str, context_key: str) -> None:
        if context_key not in context:
            raise ValueError(f"receipt context is missing {context_key}")
        candidate = context[context_key]
        digest = (
            payload_sha256(candidate)
            if isinstance(candidate, Mapping)
            else str(candidate)
        )
        if payload[field] != digest:
            raise ValueError(f"receipt context binding mismatch for {field}")

    def exact(fields: tuple[str, ...]) -> None:
        for field in fields:
            if field not in context or payload[field] != context[field]:
                raise ValueError(f"receipt context binding mismatch for {field}")

    if schema == "challenge15.deployment-receipt.v1":
        bind("dry_run_receipt_sha256", "dry_run_receipt")
        dry_run = context["dry_run_receipt"]
        for field in ("profile_sha256", "bundle_sha256", "interpreter", "interpreter_sha256"):
            if payload[field] != dry_run[field]:
                raise ValueError(f"deployment/dry-run {field} mismatch")
        if payload["deployment_root"] != context["deployment_root"]:
            raise ValueError("deployment root context mismatch")
        validate_deployment_context(
            payload,
            approved_roots=tuple(context["approved_roots"]),
        )
    elif schema == "challenge15.dry-run-receipt.v1":
        if payload["profile_sha256"] != payload_sha256(context["profile"]):
            raise ValueError("dry-run profile mismatch")
        if payload["bundle_sha256"] != payload_sha256(context["bundle"]):
            raise ValueError("dry-run bundle mismatch")
        if payload["scheduler_test"] != context["scheduler_test"]:
            raise ValueError("dry-run scheduler test mismatch")
        for field in ("destination", "interpreter", "interpreter_sha256"):
            if payload[field] != context[field]:
                raise ValueError(f"dry-run {field} context mismatch")
        validate_canonical_path(payload["destination"], tuple(context["approved_roots"]))
        validate_canonical_path(payload["interpreter"], (payload["destination"],))
    elif schema == "challenge15.attestation-bootstrap-transfer.v1":
        bind("allowed_runtime_sha256", "allowed_runtime")
        bind("source_deployment_receipt_sha256", "source_deployment")
        bind("destination_deployment_receipt_sha256", "destination_deployment")
        bind("export_bundle_sha256", "export_bundle")
        bind("import_bundle_sha256", "import_bundle")
        allowed = context["allowed_runtime"]
        if payload["role"] != allowed["role"]:
            raise ValueError("bootstrap role mismatch")
        for field in ("source_manifest_sha256", "policy_sha256"):
            if payload[field] != allowed[field]:
                raise ValueError(f"bootstrap {field} mismatch")
        export = context["export_bundle"]
        imported = context["import_bundle"]
        if export["source_artifact_sha256"] != payload["allowed_runtime_sha256"]:
            raise ValueError("bootstrap exported runtime mismatch")
        if export["member_manifest"] != imported["member_manifest"]:
            raise ValueError("bootstrap import manifest mismatch")
        for field in ("source_controller", "destination_controller"):
            if payload[field] != context[field]:
                raise ValueError(f"bootstrap {field} mismatch")
    elif schema == "challenge15.runtime-set-publication-receipt.v1":
        bind("deployment_receipt_sha256", "deployment")
        runtime_set = context["runtime_set"]
        if payload["payload_sha256"] != payload_sha256(runtime_set):
            raise ValueError("runtime-set publication payload mismatch")
        if payload["controller"] != context["controller"]:
            raise ValueError("runtime-set publication controller mismatch")
        if payload["controller_local_path_identity"] != context[
            "controller_local_path_identity"
        ]:
            raise ValueError("runtime-set publication path mismatch")
        if payload["role_map_sha256"] != context["role_map_sha256"]:
            raise ValueError("runtime-set publication role map mismatch")
    elif schema == "challenge15.runtime-set-copies.v1":
        runtime_set = context["runtime_set"]
        if payload["payload_sha256"] != payload_sha256(runtime_set):
            raise ValueError("runtime-set copies payload mismatch")
        for prefix in ("cpu", "gpu"):
            receipt = context[f"{prefix}_publication_receipt"]
            if (
                payload[f"{prefix}_resolving_receipt_sha256"]
                != payload_sha256(receipt)
                or payload[f"{prefix}_controller"] != receipt["controller"]
            ):
                raise ValueError(f"runtime-set {prefix} copy receipt mismatch")
            if payload[f"{prefix}_remote_sha256"] != payload["payload_sha256"]:
                raise ValueError(f"runtime-set {prefix} remote payload mismatch")
        if payload["local_sha256"] != payload["payload_sha256"]:
            raise ValueError("runtime-set local payload mismatch")
        for field in (
            "local_path_identity",
            "cpu_remote_path_identity",
            "gpu_remote_path_identity",
            "role_map_sha256",
        ):
            if payload[field] != context[field]:
                raise ValueError(f"runtime-set copies {field} mismatch")
    elif schema == "challenge15.state-manifest-backup-receipt.v1":
        exact(
            (
                "source_state_manifest",
                "source_sha256",
                "intent_sha256",
                "profile_sha256",
                "destination",
            )
        )
    elif schema == "challenge15.recovery-receipt.v1":
        exact(
            (
                "seed",
                "rank",
                "attempt_sha256",
                "stale_lock_sha256",
                "scheduler_query",
                "scheduler_state",
                "recovered_by",
            )
        )
    elif schema == "challenge15.submission-receipt.v1":
        approved = tuple(context["approved_roots"])
        if payload["identity_map_sha256"] != _context_envelope_digest(
            context["identity_map_path"], "challenge15.identity-map.v1", approved
        ):
            raise ValueError("submission identity map mismatch")
        if payload["profile_sha256"] != _context_envelope_digest(
            context["profile_path"], "challenge15.cluster-profile.v1", approved
        ):
            raise ValueError("submission profile mismatch")
        for field in ("interpreter", "script", "remote_claim"):
            if payload[f"{field}_sha256"] != _context_file_digest(
                context[f"{field}_path"], approved
            ):
                raise ValueError(f"submission {field} mismatch")
        recomputed_inputs = [
            _context_file_digest(path, approved) for path in context["input_paths"]
        ]
        if payload["input_sha256s"] != recomputed_inputs:
            raise ValueError("submission inputs mismatch")
        exact(
            (
                "stage", "controller", "scheduler_job_id", "array_spec",
                "dependency_mode", "correlation_id", "scheduler_job_name",
                "scheduler_comment",
            )
        )
    elif schema == "challenge15.export-bundle.v1":
        validate_export_context(payload, context)
    elif schema == "challenge15.import-bundle.v1":
        validate_import_context(payload, context)
    elif schema == "challenge15.transfer-receipt.v1":
        exported_bytes = validate_export_context(
            context["export_bundle"], context["export_context"]
        )
        imported_bytes = validate_import_context(
            context["import_bundle"], context["import_context"]
        )
        validate_transfer_context(
            context["export_bundle"],
            context["import_bundle"],
            payload,
            approved_source_roots=tuple(context["approved_source_roots"]),
            approved_destination_roots=tuple(context["approved_destination_roots"]),
        )
        if payload["attempt_intent_sha256"] != payload_sha256(context["attempt_intent"]):
            raise ValueError("transfer attempt intent mismatch")
        if payload["correlation_id"] != context["attempt_intent"]["correlation_id"]:
            raise ValueError("transfer correlation mismatch")
        export = context["export_bundle"]
        imported = context["import_bundle"]
        if payload["source_controller"] != export["source_controller"]:
            raise ValueError("transfer source controller mismatch")
        if payload["destination_controller"] != imported["destination_controller"]:
            raise ValueError("transfer destination controller mismatch")
        if export["member_manifest"] != imported["member_manifest"]:
            raise ValueError("transfer member manifest mismatch")
        if payload["export_bundle_sha256"] != payload_sha256(export):
            raise ValueError("transfer export bundle mismatch")
        if payload["import_bundle_sha256"] != payload_sha256(imported):
            raise ValueError("transfer import bundle mismatch")
        expected_direction = (
            f"{payload['source_controller']}->{payload['destination_controller']}"
        )
        if payload["direction"] != expected_direction:
            raise ValueError("transfer direction mismatch")
        if payload["remote_claim_sha256"] != context["remote_claim_sha256"]:
            raise ValueError("transfer remote claim mismatch")
        if exported_bytes != imported_bytes or payload["bytes"] != exported_bytes:
            raise ValueError("transfer byte count mismatch")
        for field in (
            "source_identity",
            "destination_identity",
            "partial_path",
            "final_path",
            "bytes",
        ):
            if payload[field] != context[field]:
                raise ValueError(f"transfer {field} context mismatch")
        if Path(payload["source_identity"]).absolute() != Path(
            context["export_context"]["bundle_path"]
        ).absolute():
            raise ValueError("transfer source endpoint mismatch")
        if Path(payload["destination_identity"]).absolute() != Path(
            context["import_context"]["bundle_path"]
        ).absolute():
            raise ValueError("transfer destination endpoint mismatch")
        if payload["final_path"] != payload["destination_identity"]:
            raise ValueError("transfer final identity mismatch")
        if Path(payload["partial_path"]).exists():
            raise ValueError("transfer partial path remains occupied")
    elif schema == "challenge15.evaluation-receipt.v1":
        shard_schema = context["shard_schema"]
        stage_by_schema = {
            "challenge15.exact-evaluation-shard.v1": "exact",
            "challenge15.coordinate-evaluation-shard.v1": "coordinate",
        }
        if shard_schema not in stage_by_schema:
            raise ValueError("evaluation shard schema mismatch")
        approved_roots = tuple(context["approved_roots"])
        shard_path = validate_canonical_path(
            context["shard_path"], approved_roots
        )
        shard_payload = validate_envelope(shard_path, shard_schema)
        if payload["shard_sha256"] != payload_sha256(shard_payload):
            raise ValueError("evaluation shard mismatch")
        expected_telemetry = payload_sha256(
            {
                "stage": payload["stage"],
                "shard_sha256": payload["shard_sha256"],
                "started_at_utc": payload["started_at_utc"],
            }
        )
        if payload["telemetry_invocation_sha256"] != expected_telemetry:
            raise ValueError("evaluation telemetry invocation mismatch")
        equivalence = payload["metric_equivalence"]
        expected_equivalence = (
            "passed"
            if equivalence["canonical_completed"] and equivalence["bitwise_equal"]
            else "pending"
        )
        if equivalence["classification"] != expected_equivalence:
            raise ValueError("evaluation metric equivalence mismatch")
        if shard_schema == "challenge15.coordinate-evaluation-shard.v1" and (
            payload["selected_layout"]
            != shard_payload["execution_validation"]["selected_layout"]
            or payload["metric_equivalence"]
            != shard_payload["execution_validation"]["metric_equivalence"]
        ):
            raise ValueError("coordinate receipt execution binding mismatch")
        expected_stage = stage_by_schema[shard_schema]
        if (
            payload["stage"] != expected_stage
            or payload["identity"]["stage"] != expected_stage
        ):
            raise ValueError("evaluation stage mismatch")
        if (
            payload["identity"]["seed"] != shard_payload["seed"]
            or payload["identity"]["rank"] != shard_payload["rank"]
        ):
            raise ValueError("evaluation identity mismatch")
        for field in COMMON:
            if payload[field] != shard_payload[field]:
                raise ValueError(
                    f"evaluation provenance mismatch for {field}"
                )
        runtime_attestations = shard_payload["runtime_attestations"]
        stage_runtimes = (
            runtime_attestations.get(expected_stage)
            if isinstance(runtime_attestations, Mapping)
            else None
        )
        if (
            not isinstance(stage_runtimes, Mapping)
            or payload["controller"] not in stage_runtimes
        ):
            raise ValueError("evaluation controller runtime mismatch")
    elif schema == "challenge15.reduction-receipt.v1":
        if payload["canonical_payload_sha256"] != _context_envelope_digest(
            context["canonical_payload_path"],
            "challenge15.size-result.v1",
            tuple(context["approved_roots"]),
        ):
            raise ValueError("reduction canonical payload mismatch")
        exact(("hostname", "slurm_job_id", "devices", "cache_counters"))
    elif schema == "challenge15.report-receipt.v1":
        approved = tuple(context["approved_roots"])
        if payload["final_report_sha256"] != _context_envelope_digest(
            context["final_report_path"], "challenge15.final-report.v1", approved
        ):
            raise ValueError("report final payload mismatch")
        if payload["cross_size_manifest_sha256"] != _context_envelope_digest(
            context["cross_size_manifest_path"],
            "challenge15.cross-size-manifest.v1",
            approved,
        ):
            raise ValueError("report cross-size manifest mismatch")
        for field in ("markdown", "interpreter"):
            if payload[f"{field}_sha256"] != _context_file_digest(
                context[f"{field}_path"], approved
            ):
                raise ValueError(f"report {field} mismatch")
        exact(
            (
                "particles", "base_configuration_sha256_by_size",
                "runtime_attestation_sets_by_size", "source_manifest_sha256",
                "policy_sha256", "hostname",
            )
        )
    elif schema == "challenge15.output-promotion.v1":
        intent = context["attempt_intent"]
        candidate = context["candidate"]
        if payload["producer_intent_sha256"] != payload_sha256(intent):
            raise ValueError("promotion intent mismatch")
        if payload["candidate_computed_sha256"] != payload_sha256(candidate):
            raise ValueError("promotion candidate mismatch")
        if payload["selector_namespace_identity"] not in intent[
            "create_only_namespace_identities"
        ]:
            raise ValueError("promotion selector namespace mismatch")
        if payload["candidate_count"] != 1:
            raise ValueError("promotion candidate count must be one")
        for field in (
            "output_schema",
            "output_absolute_path_identity",
            "selector_kind",
        ):
            if payload[field] != context[field]:
                raise ValueError(f"promotion {field} mismatch")
    else:
        raise ValueError(f"schema has no context validator: {schema}")


def _validate_payload_fields(schema: str, payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be an object")
    if schema == "challenge15.chiral-response.v1":
        _reject_nested_schema(
            {
                key: value
                for key, value in payload.items()
                if key != "execution_fingerprint"
            }
        )
    else:
        _reject_nested_schema(payload)
    expected = SCHEMA_FIELDS[schema]
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{schema} payload fields mismatch; missing={missing}, extra={extra}")
    canonical_json(payload)


def _reject_nested_schema(value: Any) -> None:
    if isinstance(value, Mapping):
        if "schema" in value:
            raise ValueError("schema is forbidden inside payload objects")
        for nested in value.values():
            _reject_nested_schema(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_nested_schema(nested)


def _load_document(value: Any) -> dict[str, Any]:
    if isinstance(value, Path):
        raw: str | bytes = value.read_bytes()
        parse = True
    elif isinstance(value, (str, bytes)):
        if isinstance(value, str) and not value.lstrip().startswith(("{", "[")):
            candidate = Path(value)
            if candidate.exists():
                raw = candidate.read_bytes()
            else:
                raw = value
        else:
            raw = value
        parse = True
    elif isinstance(value, Mapping):
        document = _json_value(value)
        parse = False
    else:
        raise ValueError("envelope must be JSON bytes, path, or object")
    if parse:
        try:
            document = json.loads(
                raw,
                parse_constant=_reject_constant,
                object_pairs_hook=_object_without_duplicates,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("envelope is not strict UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("envelope must be a JSON object")
    return document


def _payload(value: Any) -> dict[str, JSONValue]:
    if isinstance(value, Payload) or is_dataclass(value):
        value = asdict(value)
    if not isinstance(value, Mapping):
        raise ValueError("payload must be a JSON object")
    return _json_value(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _require_sha256(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA256")


def _require_integer(
    value: Any,
    label: str,
    *,
    minimum: int | None = None,
) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be at least {minimum}")


def _reject_constant(value: str) -> None:
    raise ValueError(f"JSON numeric value must be finite: {value}")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


_STATISTIC_CONTRACT = {
    "estimate": "number",
    "standard_error": "nonnegative-number",
    "ci_low": "number",
    "ci_high": "number",
}
_SECTOR_STATISTICS_CONTRACT = {
    "L0": _STATISTIC_CONTRACT,
    "L2": _STATISTIC_CONTRACT,
}
_GATE_CONTRACT = {
    "finite": "bool",
    "per_state": "bool",
    "rank_converged": "bool",
    "energy": "bool",
    "gap": "bool",
    "overlap": "bool",
    "symmetry": "bool",
    "production_accepted": "bool",
}
_EXACT_GATE_CONTRACT = {
    field: contract
    for field, contract in _GATE_CONTRACT.items()
    if field not in {"rank_converged", "production_accepted"}
}
_PRIMITIVE_METRICS_CONTRACT = {
    "energy_by_sector": _SECTOR_STATISTICS_CONTRACT,
    "gap": {
        **_STATISTIC_CONTRACT,
        "monte_carlo_covariance_e0_e2": "number",
        "optimizer_induced_covariance_e0_e2": "number",
    },
    "overlap_by_sector": {
        "L0": _STATISTIC_CONTRACT,
        "L2": _STATISTIC_CONTRACT,
    },
    "symmetry_residual_by_sector": {
        "L0": "nonnegative-number",
        "L2": "nonnegative-number",
    },
    "per_state_gate_inputs_by_sector": {
        "L0": {"finite": "bool", "normalized_amplitude_nonzero": "bool"},
        "L2": {"finite": "bool", "normalized_amplitude_nonzero": "bool"},
    },
    "quadrature_change_by_sector": {
        "L0": {
            "normalized_amplitude": "nonnegative-number",
            "energy": "nonnegative-number",
            "symmetry": "nonnegative-number",
        },
        "L2": {
            "normalized_amplitude": "nonnegative-number",
            "energy": "nonnegative-number",
            "symmetry": "nonnegative-number",
        },
    },
    "projected_span": {
        "singular_values_by_sector": {
            "L0": ["nonnegative-number"],
            "L2": ["nonnegative-number"],
        },
        "numerical_rank_by_sector": {"L0": "nonnegative-int", "L2": "nonnegative-int"},
        "dim_m_l_by_sector": {"L0": "nonnegative-int", "L2": "nonnegative-int"},
        "completeness_claim_by_sector": {"L0": "bool", "L2": "bool"},
    },
}
_COMPLEX_COEFFICIENT_CONTRACT = {"real": "number", "imag": "number"}
_QUADRATURE_ORDER_CONTRACT = {
    "minimal": {"alpha": "positive-int", "beta": "positive-int"},
    "doubled": {"alpha": "positive-int", "beta": "positive-int"},
}
_EXACT_PRIMITIVE_METRICS_CONTRACT = {
    **_PRIMITIVE_METRICS_CONTRACT,
    "normalized_coefficients_by_sector": {
        "L0": [_COMPLEX_COEFFICIENT_CONTRACT],
        "L2": [_COMPLEX_COEFFICIENT_CONTRACT],
    },
    "hamiltonian_variance_by_sector": {
        "L0": "nonnegative-number",
        "L2": "nonnegative-number",
    },
    "quadrature": {
        "orders_by_sector": {
            "L0": _QUADRATURE_ORDER_CONTRACT,
            "L2": _QUADRATURE_ORDER_CONTRACT,
        },
        "coefficient_relative_change_by_sector": {
            "L0": "nonnegative-number",
            "L2": "nonnegative-number",
        },
        "energy_relative_change_by_sector": {
            "L0": "nonnegative-number",
            "L2": "nonnegative-number",
        },
    },
}
_CHAIN_DIAGNOSTIC_CONTRACT = {
    "chain": "nonnegative-int",
    "estimate": "number",
    "standard_error": "nonnegative-number",
    "tau_int": "positive-number",
    "effective_sample_size": "positive-number",
    "split_rhat": "positive-number",
    "rigid_acceptance": "unit-number",
    "local_acceptance": "unit-number",
    "total_acceptance": "unit-number",
    "frozen_proposal_widths": {
        "rigid": "positive-number",
        "local": "positive-number",
    },
    "confidence_interval": {"low": "number", "high": "number"},
}
_TRAINING_METRIC_EQUIVALENCE_CONTRACT = {
    "canonical_layout": {
        "walker_microbatch": "positive-int",
        "carrier_block": "positive-int",
        "quadrature_block": "positive-int",
    },
    "selected_layout": {
        "walker_microbatch": "positive-int",
        "carrier_block": "positive-int",
        "quadrature_block": "positive-int",
    },
    "reference_prng_stream_sha256": ("nullable", "sha"),
    "candidate_prng_stream_sha256": ("nullable", "sha"),
    "reference_sample_stream_sha256": ("nullable", "sha"),
    "candidate_sample_stream_sha256": ("nullable", "sha"),
    "reference_accumulation_sha256": ("nullable", "sha"),
    "candidate_accumulation_sha256": ("nullable", "sha"),
    "reference_metrics_sha256": ("nullable", "sha"),
    "candidate_metrics_sha256": ("nullable", "sha"),
    "bitwise_equal": ("nullable", "bool"),
    "classification": ("enum", ("not-required", "pending", "passed")),
}

# Exact nested interfaces consumed by later oracle/evaluation/reduction tasks.
SCIENTIFIC_NESTED_CONTRACTS: dict[str, dict[str, Any]] = {
    "challenge15.production-oracle.v1": {
        "sphere_spec": {
            "particles": "positive-int",
            "flux_2q": "positive-int",
            "radius_squared_magnetic_lengths": "positive-number",
            "hilbert_dimension": "positive-int",
        },
        "physical_conventions": {
            "energy_unit": ("enum", ("E_C",)),
            "monopole_harmonic_gauge": "str",
            "rotation_convention": "str",
            "quadrupole_components": ("fixed-list", (-2, -1, 0, 1, 2)),
        },
        "coulomb_builder_diagnostics": {
            "relative_hermiticity_defect": "nonnegative-number",
            "independent_builder_error_ec": "nonnegative-number",
            "lz_commutator_residual": "nonnegative-number",
            "l2_commutator_residual": "nonnegative-number",
            "eigenpair_residual_max": "nonnegative-number",
        },
        "sector_summaries": {
            "L0": {
                "multiplicity_dimension": "positive-int",
                "lowest_energy_ec": "number",
                "eigenpair_residual": "nonnegative-number",
            },
            "L2": {
                "multiplicity_dimension": "positive-int",
                "lowest_energy_ec": "number",
                "eigenpair_residual": "nonnegative-number",
            },
        },
        "low_energy_scan": {
            "ordered_levels": [
                {"L": "nonnegative-int", "index": "nonnegative-int", "energy_ec": "number"}
            ]
        },
        "array_manifest": {
            "members": [
                {"identity": "str", "sha256": "sha", "shape": ["positive-int"], "dtype": "str"}
            ]
        },
        "gate_metrics": {
            "hilbert_space": "bool",
            "gauge_rotation": "bool",
            "hamiltonian": "bool",
            "production_accepted": "bool",
        },
    },
    "challenge15.training-snapshot.v1": {
        "proposal_state": {
            "kernel": "str",
            "adaptation_step": "nonnegative-int",
            "local_widths": [["positive-number"]],
            "rigid_widths": [["positive-number"]],
        },
        "diagnostics": {
            "finite": "bool",
            "loss": "number",
            "gradient_norm": "nonnegative-number",
            "parameter_norm": "nonnegative-number",
        },
    },
    "challenge15.training-generation.v1": {
        "training_metrics": {
            "terminal_step": "nonnegative-int",
            "finite": "bool",
            "loss": "number",
            "energy_by_sector": _SECTOR_STATISTICS_CONTRACT,
            "metric_equivalence": _TRAINING_METRIC_EQUIVALENCE_CONTRACT,
        },
    },
    "challenge15.resource-override.v1": {
        "metric_equivalence": _TRAINING_METRIC_EQUIVALENCE_CONTRACT,
    },
    "challenge15.exact-evaluation-shard.v1": {
        "block_layout": {
            "carrier_block": "positive-int",
            "determinant_block": "positive-int",
            "quadrature_block": "positive-int",
        },
        "primitive_metrics": _EXACT_PRIMITIVE_METRICS_CONTRACT,
        "metric_equivalence": {
            "reference_sha256": "sha",
            "absolute_tolerance": "nonnegative-number",
            "maximum_difference": "nonnegative-number",
            "classification": ("enum", ("passed", "pending")),
            "ambiguous": "bool",
            "straddled_gates": (
                "list",
                (
                    "enum",
                    ("energy", "gap", "overlap", "singular_rank", "symmetry"),
                ),
            ),
            "passed": "bool",
        },
        "gate_metrics": _EXACT_GATE_CONTRACT,
    },
    "challenge15.coordinate-evaluation-shard.v1": {
        "sampler_configuration": {
            "chains": "positive-int",
            "draws": "positive-int",
            "burn_in": "nonnegative-int",
            "thinning": "positive-int",
            "proposal_kernel": "str",
            "frozen_proposal_widths": {
                "rigid": "positive-number",
                "local": "positive-number",
            },
        },
        "sector_diagnostics": {
            "L0": {
                "per_chain": [_CHAIN_DIAGNOSTIC_CONTRACT],
                "estimate": "number",
                "standard_error": "nonnegative-number",
                "tau_int": "positive-number",
                "effective_sample_size": "positive-number",
                "split_rhat": "positive-number",
                "autocorrelation_converged": "bool",
                "rigid_acceptance": "unit-number",
                "local_acceptance": "unit-number",
                "total_acceptance": "unit-number",
                "confidence_interval": {"low": "number", "high": "number"},
            },
            "L2": {
                "per_chain": [_CHAIN_DIAGNOSTIC_CONTRACT],
                "estimate": "number",
                "standard_error": "nonnegative-number",
                "tau_int": "positive-number",
                "effective_sample_size": "positive-number",
                "split_rhat": "positive-number",
                "autocorrelation_converged": "bool",
                "rigid_acceptance": "unit-number",
                "local_acceptance": "unit-number",
                "total_acceptance": "unit-number",
                "confidence_interval": {"low": "number", "high": "number"},
            },
        },
        "paired_gap_diagnostics": {
            **_STATISTIC_CONTRACT,
            "tau_int_e0": "positive-number",
            "tau_int_e2": "positive-number",
            "tau_int_gap": "positive-number",
            "variance_mc_e0": "nonnegative-number",
            "variance_mc_e2": "nonnegative-number",
            "variance_mc_gap": "nonnegative-number",
            "monte_carlo_covariance_e0_e2": "number",
            "optimizer_variance_e0": "nonnegative-number",
            "optimizer_variance_e2": "nonnegative-number",
            "optimizer_induced_covariance_e0_e2": "number",
            "variance_seed_mean_gap": "nonnegative-number",
            "uncertainty_status": ("enum", ("pending", "accepted")),
            "effective_sample_size": "positive-number",
            "split_rhat": "positive-number",
            "autocorrelation_converged": "bool",
            "within_seed_inputs": [
                {
                    "seed": "nonnegative-int",
                    "e0": "number",
                    "e2": "number",
                    "variance_mc_e0": "nonnegative-number",
                    "variance_mc_e2": "nonnegative-number",
                    "monte_carlo_covariance_e0_e2": "number",
                    "variance_mc_gap": "nonnegative-number",
                }
            ],
            "between_seed_inputs": {
                "paired_seed_ids": ["nonnegative-int"],
                "e0_seed_estimates": ["number"],
                "e2_seed_estimates": ["number"],
                "optimizer_variance_e0": "nonnegative-number",
                "optimizer_variance_e2": "nonnegative-number",
                "optimizer_covariance_e0_e2": "number",
                "paired_seed_count": "positive-int",
                "variance_seed_mean_gap": "nonnegative-number",
            },
        },
        "execution_validation": {
            "selected_layout": {
                "walker_microbatch": ("nullable", "positive-int"),
                "determinant_block": ("nullable", "positive-int"),
                "carrier_block": "positive-int",
                "quadrature_block": "positive-int",
            },
            "metric_equivalence": {
                "canonical_completed": "bool",
                "bitwise_equal": "bool",
                "classification": ("enum", ("passed", "pending")),
            },
        },
        "gate_metrics": _GATE_CONTRACT,
    },
    "challenge15.evaluation-receipt.v1": {
        "identity": {"stage": "str", "seed": "nonnegative-int", "rank": "positive-int"},
        "cache_counters": {"hits": "nonnegative-int", "misses": "nonnegative-int"},
        "compile_events": (
            "list",
            {"name": "str", "seconds": "nonnegative-number"},
        ),
        "selected_layout": {
            "walker_microbatch": ("nullable", "positive-int"),
            "determinant_block": ("nullable", "positive-int"),
            "carrier_block": "positive-int",
            "quadrature_block": "positive-int",
        },
        "metric_equivalence": {
            "canonical_completed": "bool",
            "bitwise_equal": "bool",
            "classification": ("enum", ("passed", "pending")),
        },
    },
    "challenge15.size-result.v1": {
        "coordinate_uncertainty_by_rank": [
            {
                "rank": "positive-int",
                "paired_seed_ids": ("fixed-list", (0, 1, 2, 3, 4)),
                "e0_seed_estimates": ["number"],
                "e2_seed_estimates": ["number"],
                "within_seed_inputs": [
                    {
                        "seed": "nonnegative-int",
                        "e0": "number",
                        "e2": "number",
                        "variance_mc_e0": "nonnegative-number",
                        "variance_mc_e2": "nonnegative-number",
                        "monte_carlo_covariance_e0_e2": "number",
                        "variance_mc_gap": "nonnegative-number",
                    }
                ],
                "optimizer_variance_e0": "nonnegative-number",
                "optimizer_variance_e2": "nonnegative-number",
                "optimizer_covariance_e0_e2": "number",
                "paired_seed_count": "positive-int",
                "variance_seed_mean_gap": "nonnegative-number",
                "uncertainty_status": ("enum", ("accepted",)),
            }
        ],
        "prerequisite": {
            "particles": ("nullable", "positive-int"),
            "terminal_selection_sha256": ("nullable", "sha"),
            "accepted": "bool",
        },
        "primitive_metrics": _PRIMITIVE_METRICS_CONTRACT,
        "seed_gate": {
            "passing_seeds": ["nonnegative-int"],
            "required_count": "positive-int",
            "passed": "bool",
        },
        "claim": {"statement": "str", "basis": "str"},
    },
    "challenge15.reduction-receipt.v1": {
        "cache_counters": {"hits": "nonnegative-int", "misses": "nonnegative-int"},
    },
    "challenge15.cross-size-manifest.v1": {
        "lineage": {
            "N6": {"size_result_sha256": "sha", "terminal_selection_sha256": "sha"},
            "N7": {"size_result_sha256": "sha", "terminal_selection_sha256": "sha"},
            "N8": {"size_result_sha256": "sha", "terminal_selection_sha256": "sha"},
        },
        "claim": {"statement": "str", "basis": "str"},
    },
    "challenge15.final-report.v1": {
        "size_summaries": {
            "N6": {"accepted": "bool", "size_result_sha256": "sha"},
            "N7": {"accepted": "bool", "size_result_sha256": "sha"},
            "N8": {"accepted": "bool", "size_result_sha256": "sha"},
        },
        "resource_summary": {
            "total_core_hours": "nonnegative-number",
            "total_gpu_hours": "nonnegative-number",
            "peak_rss_mib": "nonnegative-number",
        },
        "statistical_summary": {
            "minimum_effective_sample_size": "positive-number",
            "maximum_split_rhat": "positive-number",
            "all_intervals_contain_estimate": "bool",
        },
    },
}


def _validate_contract_value(spec: Any, value: Any, path: str) -> None:
    if isinstance(spec, dict):
        if not isinstance(value, Mapping) or set(value) != set(spec):
            raise ValueError(f"nested fields mismatch at {path}")
        for field, child in spec.items():
            _validate_contract_value(child, value[field], f"{path}.{field}")
        return
    if isinstance(spec, list):
        if not isinstance(value, list) or not value:
            raise ValueError(f"nested ordered list is invalid at {path}")
        for index, item in enumerate(value):
            _validate_contract_value(spec[0], item, f"{path}[{index}]")
        return
    if isinstance(spec, tuple):
        kind, argument = spec
        if kind == "nullable":
            if value is not None:
                _validate_contract_value(argument, value, path)
            return
        if kind == "list":
            if not isinstance(value, list):
                raise ValueError(f"nested ordered list is invalid at {path}")
            for index, item in enumerate(value):
                _validate_contract_value(
                    argument, item, f"{path}[{index}]"
                )
            return
        if kind == "enum":
            if value not in argument or (
                isinstance(value, bool) and not any(isinstance(x, bool) for x in argument)
            ):
                raise ValueError(f"nested enum is invalid at {path}")
            return
        if kind == "fixed-list":
            if value != list(argument):
                raise ValueError(f"nested ordered list is invalid at {path}")
            return
    if spec == "bool" and not isinstance(value, bool):
        raise ValueError(f"nested boolean is invalid at {path}")
    elif spec in {"positive-int", "nonnegative-int"}:
        minimum = 1 if spec == "positive-int" else 0
        _require_integer(value, path, minimum=minimum)
    elif spec in {"number", "positive-number", "nonnegative-number", "unit-number"}:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError(f"nested number is invalid at {path}")
        if spec == "positive-number" and value <= 0:
            raise ValueError(f"nested number is out of range at {path}")
        if spec == "nonnegative-number" and value < 0:
            raise ValueError(f"nested number is out of range at {path}")
        if spec == "unit-number" and not 0 <= value <= 1:
            raise ValueError(f"nested number is out of range at {path}")
    elif spec == "sha":
        _require_sha256(value, path)
    elif spec == "str" and (not isinstance(value, str) or not value):
        raise ValueError(f"nested string is invalid at {path}")


def contract_fixture(spec: Any) -> Any:
    if isinstance(spec, dict):
        return {field: contract_fixture(child) for field, child in spec.items()}
    if isinstance(spec, list):
        if spec == [["positive-number"]]:
            return [[1.0] * 32 for _ in range(2)]
        return [contract_fixture(spec[0])]
    if isinstance(spec, tuple):
        kind, argument = spec
        if kind == "nullable":
            return None
        if kind == "list":
            return []
        if kind == "fixed-list":
            return list(argument)
        return argument[0]
    return {
        "bool": False,
        "positive-int": 1,
        "nonnegative-int": 0,
        "number": 0.0,
        "positive-number": 1.0,
        "nonnegative-number": 0.0,
        "unit-number": 0.5,
        "sha": "a" * 64,
        "str": "value",
    }[spec]


def _validate_scientific_invariants(schema: str, payload: Mapping[str, Any]) -> None:
    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if {"estimate", "standard_error", "ci_low", "ci_high"} <= set(value):
                if not value["ci_low"] <= value["estimate"] <= value["ci_high"]:
                    raise ValueError("nested confidence interval excludes estimate")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    if schema == "challenge15.training-snapshot.v1":
        proposal = payload["proposal_state"]
        for name in ("local_widths", "rigid_widths"):
            widths = proposal[name]
            if len(widths) != 2 or any(len(row) != 32 for row in widths):
                raise ValueError("snapshot proposal widths must have exact shape [2,32]")
    if schema == "challenge15.production-oracle.v1":
        levels = payload["low_energy_scan"]["ordered_levels"]
        energies = [level["energy_ec"] for level in levels]
        if energies != sorted(energies):
            raise ValueError("nested low-energy levels are out of order")
    if schema == "challenge15.exact-evaluation-shard.v1":
        equivalence = payload["metric_equivalence"]
        straddled = equivalence["straddled_gates"]
        if straddled != sorted(set(straddled)):
            raise ValueError(
                "metric equivalence straddled gates are not unique and ordered"
            )
        if equivalence["ambiguous"] is not bool(straddled):
            raise ValueError("metric equivalence ambiguity is inconsistent")
        expected_classification = (
            "pending"
            if equivalence["ambiguous"]
            or equivalence["maximum_difference"]
            > equivalence["absolute_tolerance"]
            else "passed"
        )
        if equivalence["classification"] != expected_classification:
            raise ValueError("metric equivalence classification is inconsistent")
        if equivalence["passed"] and equivalence["classification"] != "passed":
            raise ValueError(
                "metric equivalence passed requires passed classification"
            )
    if schema == "challenge15.coordinate-evaluation-shard.v1":
        execution = payload["execution_validation"]
        equivalence = execution["metric_equivalence"]
        expected_equivalence = (
            "passed"
            if equivalence["canonical_completed"] and equivalence["bitwise_equal"]
            else "pending"
        )
        if equivalence["classification"] != expected_equivalence:
            raise ValueError("coordinate execution metric equivalence mismatch")
        for sector in ("L0", "L2"):
            diagnostic = payload["sector_diagnostics"][sector]
            chains = diagnostic["per_chain"]
            identities = [item["chain"] for item in chains]
            if identities != sorted(set(identities)):
                raise ValueError("nested chain identities are not unique and ordered")
            interval = diagnostic["confidence_interval"]
            if not interval["low"] <= diagnostic["estimate"] <= interval["high"]:
                raise ValueError("nested sector confidence interval excludes estimate")
            for item in chains:
                chain_interval = item["confidence_interval"]
                if not chain_interval["low"] <= item["estimate"] <= chain_interval["high"]:
                    raise ValueError("nested chain confidence interval excludes estimate")
        paired = payload["paired_gap_diagnostics"]
        seed_ids = [item["seed"] for item in paired["within_seed_inputs"]]
        if seed_ids != sorted(set(seed_ids)):
            raise ValueError("nested seed inputs are not unique and ordered")
        between = paired["between_seed_inputs"]
        count = between["paired_seed_count"]
        e0 = [item["e0"] for item in paired["within_seed_inputs"]]
        e2 = [item["e2"] for item in paired["within_seed_inputs"]]
        if (
            between["e0_seed_estimates"] != e0
            or between["e2_seed_estimates"] != e2
        ):
            raise ValueError(
                "duplicate seed arrays differ from ordered within-seed inputs"
            )
        paired_complete = (
            between["paired_seed_ids"] == seed_ids
            and len(seed_ids) == count
        )
        if paired["monte_carlo_covariance_e0_e2"] != 0:
            raise ValueError("final E0/E2 Monte Carlo covariance must be zero")
        if not math.isclose(
            paired["variance_mc_gap"],
            paired["variance_mc_e0"] + paired["variance_mc_e2"],
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError("paired Monte Carlo gap variance formula mismatch")
        for item in paired["within_seed_inputs"]:
            if item["monte_carlo_covariance_e0_e2"] != 0 or not math.isclose(
                item["variance_mc_gap"],
                item["variance_mc_e0"] + item["variance_mc_e2"],
                rel_tol=0.0,
                abs_tol=1e-15,
            ):
                raise ValueError("within-seed Monte Carlo covariance formula mismatch")
        for top, nested in (
            ("optimizer_variance_e0", "optimizer_variance_e0"),
            ("optimizer_variance_e2", "optimizer_variance_e2"),
            (
                "optimizer_induced_covariance_e0_e2",
                "optimizer_covariance_e0_e2",
            ),
            ("variance_seed_mean_gap", "variance_seed_mean_gap"),
        ):
            if paired[top] != between[nested]:
                raise ValueError("top-level optimizer covariance binding mismatch")
        accepted = paired["uncertainty_status"] == "accepted"
        if payload["gate_metrics"]["production_accepted"] and not accepted:
            raise ValueError("accepted result requires accepted paired covariance")
        if accepted:
            if not paired_complete or count < 2:
                raise ValueError("accepted paired covariance requires paired K>=2")
            mean0 = sum(e0) / count
            mean2 = sum(e2) / count
            s00 = sum((value - mean0) ** 2 for value in e0) / (count - 1)
            s22 = sum((value - mean2) ** 2 for value in e2) / (count - 1)
            s02 = sum(
                (value0 - mean0) * (value2 - mean2)
                for value0, value2 in zip(e0, e2, strict=True)
            ) / (count - 1)
            for actual, expected in (
                (between["optimizer_variance_e0"], s00),
                (between["optimizer_variance_e2"], s22),
                (between["optimizer_covariance_e0_e2"], s02),
            ):
                if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-15):
                    raise ValueError("unbiased optimizer covariance mismatch")
            expected_seed_variance = (s22 + s00 - 2 * s02) / count
            if not math.isclose(
                between["variance_seed_mean_gap"],
                expected_seed_variance,
                rel_tol=0.0,
                abs_tol=1e-15,
            ):
                raise ValueError("optimizer-induced gap variance formula mismatch")
    if schema == "challenge15.evaluation-receipt.v1":
        events = payload["compile_events"]
        if payload["compile_event_count"] != len(events) or not math.isclose(
            payload["compile_seconds"],
            sum(item["seconds"] for item in events),
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError("JAX compile event telemetry mismatch")
    if schema in {
        "challenge15.training-generation.v1",
        "challenge15.resource-override.v1",
    }:
        equivalence = (
            payload["training_metrics"]["metric_equivalence"]
            if schema == "challenge15.training-generation.v1"
            else payload["metric_equivalence"]
        )
        classification = equivalence["classification"]
        if (
            schema == "challenge15.resource-override.v1"
            and classification == "not-required"
        ):
            raise ValueError("resource override requires metric equivalence proof")
        pairs = (
            (
                equivalence["reference_prng_stream_sha256"],
                equivalence["candidate_prng_stream_sha256"],
            ),
            (
                equivalence["reference_sample_stream_sha256"],
                equivalence["candidate_sample_stream_sha256"],
            ),
            (
                equivalence["reference_accumulation_sha256"],
                equivalence["candidate_accumulation_sha256"],
            ),
            (
                equivalence["reference_metrics_sha256"],
                equivalence["candidate_metrics_sha256"],
            ),
        )
        if classification == "passed" and (
            equivalence["bitwise_equal"] is not True
            or any(reference is None or reference != candidate for reference, candidate in pairs)
        ):
            raise ValueError("passed training metric equivalence lacks bitwise evidence")
        if classification == "pending" and equivalence["bitwise_equal"] is True:
            raise ValueError("pending training metric equivalence cannot claim equality")
        if classification == "not-required" and (
            equivalence["canonical_layout"] != equivalence["selected_layout"]
            or equivalence["bitwise_equal"] is not None
            or any(value is not None for pair in pairs for value in pair)
        ):
            raise ValueError("non-OOM training metric equivalence is inconsistent")
    for metrics_field in ("primitive_metrics",):
        if metrics_field not in payload:
            continue
        span = payload[metrics_field]["projected_span"]
        for sector in ("L0", "L2"):
            values = span["singular_values_by_sector"][sector]
            if values != sorted(values, reverse=True):
                raise ValueError("nested projected singular values are out of order")
            rank = span["numerical_rank_by_sector"][sector]
            dimension = span["dim_m_l_by_sector"][sector]
            if rank > dimension:
                raise ValueError("nested projected rank exceeds multiplicity dimension")
            if span["completeness_claim_by_sector"][sector] and rank != dimension:
                raise ValueError("nested completeness claim is unsupported")


@dataclass(frozen=True, slots=True)
class SchemaContract:
    """Concrete recursive contract for one production payload schema."""

    schema: str
    exact_nested_objects: Mapping[tuple[str, ...], frozenset[str]] | None = None

    def __call__(self, payload: Mapping[str, Any]) -> None:
        _validate_payload_fields(self.schema, payload)
        _validate_schema_semantics(self.schema, payload)
        for field, spec in SCIENTIFIC_NESTED_CONTRACTS.get(self.schema, {}).items():
            _validate_contract_value(spec, payload[field], field)
        _validate_scientific_invariants(self.schema, payload)
        for path, fields in (self.exact_nested_objects or {}).items():
            value: Any = payload
            for component in path:
                if not isinstance(value, Mapping) or component not in value:
                    raise ValueError(f"{self.schema} missing nested field {'.'.join(path)}")
                value = value[component]
            if not isinstance(value, Mapping) or set(value) != set(fields):
                raise ValueError(
                    f"{self.schema} nested fields mismatch at {'.'.join(path)}"
                )


_RUNTIME_ROLE_FIELDS = frozenset(
    {"controller", "allowed_runtime_sha256", "deployment_receipt_sha256", "backend"}
)
_RANK_GROWTH_PRNG_FIELDS = frozenset({"algorithm", "key_sha256"})

# Deliberately explicit: adding a policy schema requires adding its contract here.
SCHEMA_VALIDATORS = {
    "challenge15.production-policy.v1": SchemaContract("challenge15.production-policy.v1"),
    "challenge15.source-manifest.v1": SchemaContract("challenge15.source-manifest.v1"),
    "challenge15.allowed-runtime.v1": SchemaContract("challenge15.allowed-runtime.v1"),
    "challenge15.runtime-attestation-set.v1": SchemaContract(
        "challenge15.runtime-attestation-set.v1",
        {
            ("roles", "training"): _RUNTIME_ROLE_FIELDS,
            ("roles", "coordinate"): _RUNTIME_ROLE_FIELDS,
            ("roles", "oracle"): _RUNTIME_ROLE_FIELDS,
            ("roles", "exact"): _RUNTIME_ROLE_FIELDS,
            ("roles", "reducer"): _RUNTIME_ROLE_FIELDS,
        },
    ),
    "challenge15.runtime-set-copies.v1": SchemaContract("challenge15.runtime-set-copies.v1"),
    "challenge15.runtime-set-publication-receipt.v1": SchemaContract("challenge15.runtime-set-publication-receipt.v1"),
    "challenge15.attestation-bootstrap-transfer.v1": SchemaContract("challenge15.attestation-bootstrap-transfer.v1"),
    "challenge15.cluster-profile.v1": SchemaContract("challenge15.cluster-profile.v1"),
    "challenge15.production-oracle.v1": SchemaContract("challenge15.production-oracle.v1"),
    "challenge15.chiral-response.v1": SchemaContract("challenge15.chiral-response.v1"),
    "challenge15.seed-owner.v1": SchemaContract("challenge15.seed-owner.v1"),
    "challenge15.rank-extension.v1": SchemaContract(
        "challenge15.rank-extension.v1",
        {("rank_growth_prng",): _RANK_GROWTH_PRNG_FIELDS},
    ),
    "challenge15.rank-extension-decision.v1": SchemaContract("challenge15.rank-extension-decision.v1"),
    "challenge15.training-attempt.v1": SchemaContract("challenge15.training-attempt.v1"),
    "challenge15.training-snapshot.v1": SchemaContract("challenge15.training-snapshot.v1"),
    "challenge15.training-generation.v1": SchemaContract("challenge15.training-generation.v1"),
    "challenge15.recovery-receipt.v1": SchemaContract("challenge15.recovery-receipt.v1"),
    "challenge15.resource-override.v1": SchemaContract("challenge15.resource-override.v1"),
    "challenge15.identity-map.v1": SchemaContract("challenge15.identity-map.v1"),
    "challenge15.submission-receipt.v1": SchemaContract("challenge15.submission-receipt.v1"),
    "challenge15.orchestration-state-key.v1": SchemaContract("challenge15.orchestration-state-key.v1"),
    "challenge15.orchestration-attempt-intent.v1": SchemaContract("challenge15.orchestration-attempt-intent.v1"),
    "challenge15.orchestration-transition.v1": SchemaContract("challenge15.orchestration-transition.v1"),
    "challenge15.orchestration-state-manifest.v1": SchemaContract("challenge15.orchestration-state-manifest.v1"),
    "challenge15.state-manifest-backup-receipt.v1": SchemaContract("challenge15.state-manifest-backup-receipt.v1"),
    "challenge15.output-promotion.v1": SchemaContract("challenge15.output-promotion.v1"),
    "challenge15.export-bundle.v1": SchemaContract("challenge15.export-bundle.v1"),
    "challenge15.import-bundle.v1": SchemaContract("challenge15.import-bundle.v1"),
    "challenge15.transfer-receipt.v1": SchemaContract("challenge15.transfer-receipt.v1"),
    "challenge15.dry-run-receipt.v1": SchemaContract("challenge15.dry-run-receipt.v1"),
    "challenge15.deployment-receipt.v1": SchemaContract("challenge15.deployment-receipt.v1"),
    "challenge15.exact-evaluation-shard.v1": SchemaContract("challenge15.exact-evaluation-shard.v1"),
    "challenge15.coordinate-evaluation-shard.v1": SchemaContract("challenge15.coordinate-evaluation-shard.v1"),
    "challenge15.evaluation-receipt.v1": SchemaContract("challenge15.evaluation-receipt.v1"),
    "challenge15.size-result.v1": SchemaContract("challenge15.size-result.v1"),
    "challenge15.reduction-receipt.v1": SchemaContract("challenge15.reduction-receipt.v1"),
    "challenge15.reduction-finalization.v1": SchemaContract("challenge15.reduction-finalization.v1"),
    "challenge15.terminal-selection.v1": SchemaContract("challenge15.terminal-selection.v1"),
    "challenge15.cross-size-manifest.v1": SchemaContract("challenge15.cross-size-manifest.v1"),
    "challenge15.final-report.v1": SchemaContract("challenge15.final-report.v1"),
    "challenge15.report-receipt.v1": SchemaContract("challenge15.report-receipt.v1"),
}
