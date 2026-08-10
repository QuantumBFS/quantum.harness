"""Restartable, provenance-bound command line interface for Challenge 15."""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, replace
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import jax
import numpy as np
import optax
from flax import serialization

from challenge15.artifacts import (
    publish_create_only,
    publish_json_atomic,
    verify_artifact,
)
from challenge15.model import (
    ModelConfig,
    ProjectedPfaffianNQS,
    embed_adam_state,
    embed_rank,
)
from challenge15.oracle import (
    evaluate_exact_nqs,
    oracle_cache_payload,
    oracle_from_cache_payload,
    quadrature_cache_info,
    solve_required_target_sectors_sparse,
    solve_target_sectors,
)
from challenge15.nqs_bridge import nqs_determinant_state
from challenge15.provenance import execution_fingerprint, validate_fingerprint
from challenge15.response_operator import build_response_family
from challenge15.spectral_response import (
    exact_chiral_spectrum,
    exact_chiral_spectrum_for_size,
    nqs_mixed_chiral_spectrum,
    validate_response_families,
)
from challenge15.generations import (
    VerifiedGeneration,
    claim_seed_root,
    create_rank_extension,
    create_rank_extension_decision as publish_rank_extension_decision,
    discover_unique_terminal_generation,
)
from challenge15.finalization import (
    create_rank_extension_decision as create_nonroot_rank_decision,
    finalize_reduction,
    select_terminal,
)
from challenge15.reducer import build_identity_map
from challenge15.production_schema import (
    SCHEMA_FIELDS,
    OrchestrationAttemptIntent,
    RankExtension,
    RankExtensionDecision,
    SeedOwner,
    canonical_json,
    attempt_correlation_id,
    envelope_for,
    payload_sha256,
    validate_envelope,
    validate_production_vmc_config_envelope,
)
from challenge15.production_policy import production_policy
from challenge15.production_vmc import (
    ProductionVMCConfig,
    evaluate_coordinates,
    train_rank,
)
from challenge15.spec import SphereSpec
from challenge15.train import (
    ENERGY_TOLERANCE_EC,
    GAP_RELATIVE_TOLERANCE,
    MINIMUM_PASSING_SEEDS,
    OVERLAP_CHANGE_TOLERANCE,
    REQUIRED_RANK_DOUBLINGS,
    REQUIRED_SEED_COUNT,
    RankConvergence,
    RankEvaluation,
    TrainConfig,
    analyze_rank_convergence,
    train_joint_sectors,
)


def configuration_sha256(configuration: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        configuration,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_compatible_checkpoint(
    path: Path | str, configuration: Mapping[str, Any]
) -> dict[str, Any]:
    return _validate_checkpoint(
        path,
        expected_configuration=configuration,
        allowed_schemas={"challenge15.train-checkpoint.v1"},
    )


def _checkpoint_coverage(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    configuration = checkpoint.get("configuration")
    if not isinstance(configuration, Mapping):
        raise ValueError("checkpoint training configuration must be an object")
    expected = _expected_record_identities(configuration)
    present = _record_identities(checkpoint.get("records"), expected)
    missing = sorted(expected - present)
    return {
        "expected": [list(identity) for identity in sorted(expected)],
        "present": [list(identity) for identity in sorted(present)],
        "missing": [list(identity) for identity in missing],
        "passed": not missing,
    }


def _validate_checkpoint(
    path: Path | str,
    *,
    expected_configuration: Mapping[str, Any] | None = None,
    allowed_schemas: set[str] | None = None,
) -> dict[str, Any]:
    payload = verify_artifact(path)
    schemas = allowed_schemas or {
        "challenge15.train-checkpoint.v1",
        "challenge15.train-result.v1",
    }
    if payload.get("schema") not in schemas:
        raise ValueError("artifact is not an allowed Challenge 15 train checkpoint")
    configuration = payload.get("configuration")
    if not isinstance(configuration, dict):
        raise ValueError("checkpoint training configuration must be an object")
    stored_digest = payload.get("configuration_sha256")
    if stored_digest != configuration_sha256(configuration):
        raise ValueError("stored configuration SHA256 does not match configuration")
    if expected_configuration is not None:
        expected = dict(expected_configuration)
        if configuration != expected or stored_digest != configuration_sha256(expected):
            raise ValueError("incompatible resume configuration")
    current_fingerprint = execution_fingerprint()
    validate_fingerprint(
        payload.get("execution_fingerprint"),
        current=current_fingerprint,
        context="checkpoint",
    )
    _validate_training_configuration(configuration)
    coverage = _checkpoint_coverage(payload)
    records = payload.get("records")
    assert isinstance(records, list)
    present = {tuple(identity) for identity in coverage["present"]}
    completed = _completed_identities(payload.get("completed"))
    if completed != present:
        raise ValueError("checkpoint completed records are inconsistent with coverage")

    spec = SphereSpec(int(configuration["particles"]))
    restored: dict[tuple[int, int], tuple[Any, Any]] = {}
    for record in records:
        identity = (record["rank"], record["seed"])
        if record.get("shared_parameter_tree") is not True:
            raise ValueError("checkpoint record does not contain one shared parameter tree")
        validate_fingerprint(
            record.get("execution_fingerprint"),
            current=current_fingerprint,
            context="checkpoint record",
        )
        if record.get("execution_fingerprint") != payload.get(
            "execution_fingerprint"
        ):
            raise ValueError("checkpoint record execution fingerprint differs from parent")
        parameters = _restore_parameters(spec, configuration, record)
        optimizer_state = _restore_optimizer_state(
            configuration, record, parameters
        )
        if len(record.get("steps", ())) != int(configuration["steps"]):
            raise ValueError("checkpoint record has stale training-step diagnostics")
        restored[identity] = (parameters, optimizer_state)

    ranks = list(configuration["ranks"])
    for identity, (parameters, _optimizer_state) in restored.items():
        rank, seed = identity
        rank_index = ranks.index(rank)
        record = _record_by_identity(records, identity)
        if rank_index == 0:
            if any(
                record.get(field) is not None
                for field in (
                    "nested_from_rank",
                    "parent_parameter_sha256",
                    "rank_growth_prng",
                    "initial_parameter_sha256",
                )
            ):
                raise ValueError("first-rank checkpoint lineage is invalid")
            continue
        lower_rank = ranks[rank_index - 1]
        parent_identity = (lower_rank, seed)
        if parent_identity not in restored:
            raise ValueError("checkpoint lineage parent is missing")
        parent_record = _record_by_identity(records, parent_identity)
        if (
            record.get("nested_from_rank") != lower_rank
            or record.get("parent_parameter_sha256")
            != parent_record.get("parameter_sha256")
        ):
            raise ValueError("checkpoint lineage metadata is invalid")
        growth_key = jax.random.fold_in(jax.random.key(seed), rank)
        expected_key = [
            int(value)
            for value in np.asarray(jax.random.key_data(growth_key)).reshape(-1)
        ]
        if record.get("rank_growth_prng") != expected_key:
            raise ValueError("checkpoint lineage PRNG is invalid")
        expanded = embed_rank(
            restored[parent_identity][0],
            lower_rank,
            rank,
            key=growth_key,
        )
        expanded_digest = hashlib.sha256(
            serialization.to_bytes(expanded)
        ).hexdigest()
        if record.get("initial_parameter_sha256") != expanded_digest:
            raise ValueError("checkpoint lineage initial-parameter hash is invalid")
        if jax.tree.structure(parameters) != jax.tree.structure(expanded):
            raise ValueError("checkpoint lineage parameter structure is invalid")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        return int(arguments.handler(arguments))
    except (OSError, TypeError, ValueError, RuntimeError, FloatingPointError) as exc:
        parser.error(str(exc))
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m challenge15.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    oracle = commands.add_parser("oracle")
    _common_config(oracle)
    oracle.add_argument("--particles", type=int)
    oracle.add_argument("--output")
    oracle.add_argument("--policy")
    oracle.add_argument("--source-manifest")
    oracle.add_argument("--runtime-attestations")
    oracle.add_argument("--output-dir")
    oracle.add_argument("--create-only", action="store_true")
    oracle.set_defaults(handler=_oracle_command)

    train = commands.add_parser("train")
    _common_config(train)
    train.add_argument("--particles", type=int)
    train.add_argument("--ranks")
    train.add_argument("--seeds")
    train.add_argument("--steps", type=int)
    train.add_argument("--output", required=True)
    train.add_argument("--resume", action="store_true")
    train.set_defaults(handler=_train_command)

    evaluate = commands.add_parser("evaluate")
    _common_config(evaluate)
    evaluate.add_argument("--checkpoint")
    evaluate.add_argument("--oracle")
    evaluate.add_argument("--prerequisite")
    evaluate.add_argument("--output", required=True)
    evaluate.set_defaults(handler=_evaluate_command)

    response = commands.add_parser("response")
    source = response.add_mutually_exclusive_group(required=True)
    source.add_argument("--particles", type=int)
    source.add_argument("--oracle")
    response.add_argument("--generation")
    response.add_argument("--checkpoint")
    response.add_argument("--rank", type=int)
    response.add_argument("--seed", type=int)
    response.add_argument("--output", required=True)
    response.set_defaults(handler=_response_command)

    verify = commands.add_parser("verify")
    _common_config(verify)
    verify.add_argument("--artifact")
    verify.set_defaults(handler=_verify_command)

    report = commands.add_parser("report")
    _common_config(report)
    report.add_argument("--evaluation")
    report.add_argument("--output")
    for field in (
        "cross-size-manifest",
        "policy",
        "source-manifest",
        "runtime-attestation-set-n6",
        "runtime-attestation-set-n7",
        "runtime-attestation-set-n8",
        "n8-provisional-finalization",
        "n8-reduction",
        "n8-import-receipt",
        "n8-transfer-receipt",
        "output-dir",
        "receipt-dir",
    ):
        report.add_argument(f"--{field}")
    report.add_argument("--create-only", action="store_true")
    report.set_defaults(handler=_report_command)

    manifest = commands.add_parser("manifest")
    manifest.add_argument("--n6")
    manifest.add_argument("--n7")
    manifest.add_argument("--n8")
    manifest.add_argument("--output", required=True)
    manifest.set_defaults(handler=_manifest_command)

    vmc_train = commands.add_parser("vmc-train")
    vmc_train.add_argument("--base-config", required=True)
    vmc_train.add_argument("--extension", required=True)
    _production_provenance(vmc_train)
    vmc_train.add_argument("--owner", required=True)
    vmc_train.add_argument("--resource-override")
    vmc_train.add_argument("--destination", required=True)
    vmc_train.add_argument("--create-only", action="store_true", required=True)
    vmc_train.set_defaults(handler=_production_vmc_train_command)

    coordinate = commands.add_parser("coordinate-shard")
    coordinate.add_argument("--base-config", required=True)
    coordinate.add_argument("--generation", required=True)
    _production_provenance(coordinate)
    coordinate.add_argument("--destination", required=True)
    coordinate.add_argument("--receipt-dir", required=True)
    coordinate.add_argument("--create-only", action="store_true", required=True)
    coordinate.set_defaults(handler=_coordinate_shard_command)

    _add_production_contracts(commands)
    return parser


def _required(parser: argparse.ArgumentParser, *names: str) -> None:
    for name in names:
        parser.add_argument(f"--{name.replace('_', '-')}", required=True)


def _production_provenance(parser: argparse.ArgumentParser) -> None:
    _required(parser, "policy", "source_manifest", "runtime_attestations")


def _contract(
    commands: argparse._SubParsersAction,
    name: str,
    required: Sequence[str],
    *,
    choices: Mapping[str, Sequence[str]] | None = None,
    integers: Sequence[str] = (),
    flags: Sequence[str] = (),
    handler=None,
) -> argparse.ArgumentParser:
    parser = commands.add_parser(name)
    for field in required:
        keyword = f"--{field.replace('_', '-')}"
        options: dict[str, Any] = {"required": True}
        if choices and field in choices:
            options["choices"] = choices[field]
        if field in integers:
            options["type"] = int
        parser.add_argument(keyword, **options)
    for field in flags:
        parser.add_argument(
            f"--{field.replace('_', '-')}", action="store_true", required=True
        )
    if handler is None:
        raise RuntimeError(f"production command {name!r} has no execution handler")
    parser.set_defaults(handler=handler)
    return parser


def _add_production_contracts(commands: argparse._SubParsersAction) -> None:
    roles = ("training", "coordinate", "oracle", "exact", "reducer")
    controllers = ("qdeshell", "lasg02", "wuzh02")
    parser = _contract(commands, "policy", ("output",), flags=("create_only",), handler=_policy_command)
    parser = _contract(
        commands,
        "source-manifest",
        ("root", "policy", "output"),
        flags=("require_clean",),
        handler=_source_manifest_command,
    )
    _contract(
        commands,
        "verify-execution-inputs",
        ("source_manifest", "runtime_set", "role", "controller"),
        choices={"role": roles, "controller": controllers},
        handler=_verify_execution_inputs_command,
    )
    _contract(
        commands,
        "runtime-attest",
        (
            "role", "controller", "profile", "wheelhouse", "source_manifest",
            "policy", "expected_backend", "output_dir",
        ),
        choices={
            "role": roles,
            "controller": controllers,
            "profile": ("cpu", "cuda12"),
            "expected_backend": ("cpu", "gpu"),
        },
        flags=("create_only",),
        handler=_runtime_attest_command,
    )
    _contract(
        commands,
        "runtime-attestation-set",
        (
            "particles", "training_controller", "training",
            "coordinate_controller", "coordinate", "oracle_controller", "oracle",
            "exact_controller", "exact", "reducer_controller", "reducer", "output_dir",
        ),
        integers=("particles",),
        flags=("create_only",),
        handler=_runtime_attestation_set_command,
    )
    _contract(
        commands,
        "runtime-set-verify-copies",
        (
            "runtime_set_local", "runtime_set_local_sha256", "cpu_runtime_set_remote",
            "cpu_runtime_set_receipt", "gpu_runtime_set_remote",
            "gpu_runtime_set_receipt", "cpu_controller", "gpu_controller",
            "cpu_deployment_receipt", "gpu_deployment_receipt",
            "source_manifest", "policy",
        ),
        choices={"cpu_controller": ("lasg02", "wuzh02"), "gpu_controller": ("qdeshell",)},
        handler=_runtime_set_verify_copies_command,
    )
    _contract(
        commands,
        "runtime-set-remote-digest",
        ("runtime_set", "source_manifest_sha256", "policy_sha256"),
        handler=_runtime_set_remote_digest_command,
    )
    _contract(
        commands,
        "runtime-set-copy",
        ("manifest", "field"),
        choices={"field": (
            "local_path", "local_sha256", "cpu_remote_path", "cpu_receipt",
            "gpu_remote_path", "gpu_receipt",
        )},
        handler=_manifest_field_command,
    )
    _contract(
        commands,
        "runtime-set-publication-receipt",
        (
            "controller", "deployment_receipt", "controller_local_path",
            "runtime_set_sha256", "source_manifest", "policy", "output_dir",
        ),
        flags=("create_only",),
        handler=_runtime_set_publication_receipt_command,
    )
    intent = _contract(
        commands,
        "orchestration-attempt-intent",
        (
            "state_key", "transition_identity", "attempt", "action_kind",
            "source_controller", "destination_controller", "script",
            "canonical_argv_sha256", "input_sha256", "profile",
            "deployment_receipt", "runtime_set_sha256", "source_manifest",
            "policy", "base_config", "expected_output_identity",
            "create_only_namespace", "remote_claim_root", "output_dir",
        ),
        choices={"action_kind": ("slurm", "transfer", "backup", "local")},
        integers=("attempt",),
        flags=("create_only",),
        handler=_orchestration_attempt_intent_command,
    )
    for field in ("particles", "seed", "rank"):
        intent.add_argument(f"--{field}", type=int)
    intent.add_argument("--parent-sha256", action="append", default=[])
    _contract(
        commands,
        "claim-seed",
        (
            "particles", "seed", "base_config", "policy", "source_manifest",
            "runtime_attestations", "destination", "owner_uuid",
        ),
        integers=("particles", "seed"),
        flags=("create_only",),
        handler=_claim_seed_command,
    )
    _contract(
        commands,
        "rank-extension",
        (
            "particles", "seed", "base_config", "policy", "source_manifest",
            "runtime_attestations", "reason", "decision", "output_dir",
        ),
        integers=("particles", "seed"),
        flags=("create_only",),
        handler=_rank_extension_command,
    ).add_argument("--parent-generation")
    decision_parser = _contract(
        commands,
        "rank-extension-decision",
        (
            "seed", "current_rank", "new_rank", "base_config", "reason",
            "policy", "source_manifest", "runtime_attestations", "output_dir",
        ),
        integers=("seed", "new_rank"),
        flags=("create_only",),
        handler=_rank_extension_decision_command,
    )
    for field in (
        "prior_reduction",
        "prior_finalization",
        "prior_import_receipt",
        "prior_transfer_receipt",
    ):
        decision_parser.add_argument(f"--{field.replace('_', '-')}")
    _contract(
        commands,
        "identity-map",
        (
            "stage", "particles", "expected_ranks", "expected_seeds",
            "array_concurrency", "input_root", "output_dir",
        ),
        integers=("particles", "array_concurrency"),
        flags=("create_only",),
        handler=_identity_map_command,
    )
    _contract(
        commands,
        "identity-map-count",
        ("identity_map",),
        handler=_identity_map_count_command,
    )
    _contract(
        commands,
        "identity-map-task",
        ("identity_map", "task_id", "stage"),
        integers=("task_id",),
        handler=_identity_map_task_command,
    )
    _contract(
        commands,
        "discover-generation",
        (
            "seed_root", "extension_root", "expected_ranks", "policy",
            "source_manifest", "runtime_attestations",
        ),
        flags=("print_manifest",),
        handler=_discover_generation_command,
    )
    _contract(
        commands,
        "resource-override",
        (
            "extension", "attempt", "reason", "walker_microbatch",
            "carrier_block", "quadrature_block", "output_dir",
        ),
        choices={"reason": ("oom",)},
        integers=("walker_microbatch", "carrier_block", "quadrature_block"),
        flags=("create_only",),
        handler=_resource_override_command,
    )
    _contract(
        commands,
        "exact-shard",
        (
            "oracle", "generation", "policy", "source_manifest",
            "runtime_attestations", "destination", "receipt_dir",
            "determinant_block", "carrier_block", "quadrature_block",
        ),
        integers=("determinant_block", "carrier_block", "quadrature_block"),
        flags=("create_only",),
        handler=_exact_shard_command,
    )
    _contract(
        commands,
        "cumulative-reducer-identity-map",
        (
            "particles", "expected_ranks", "new_rank", "expected_seeds",
            "new_coordinate_root", "new_exact_root", "output_dir",
        ),
        integers=("particles", "new_rank"),
        flags=("create_only",),
        handler=_cumulative_reducer_identity_map_command,
    ).add_argument("--previous-cycle-receipt")
    _contract(
        commands,
        "cycle-ranks",
        ("previous_cycle_receipt", "new_rank"),
        integers=("new_rank",),
        flags=("print_tsv",),
        handler=_cycle_ranks_command,
    )
    _contract(
        commands,
        "accepted-terminal-identity-map",
        (
            "terminal_selection", "provisional_finalization", "reduction",
            "runtime_attestation_set", "output_dir",
        ),
        flags=("create_only",),
        handler=_accepted_terminal_identity_map_command,
    )
    _contract(
        commands,
        "runtime-set-identity-map",
        ("runtime_attestation_set", "output_dir"),
        flags=("create_only",),
        handler=_runtime_set_identity_map_command,
    )
    reduce_size_parser = _contract(
        commands,
        "reduce-size",
        (
            "particles", "expected_ranks", "expected_seeds", "identity_map",
            "oracle", "training_root", "exact_root", "coordinate_root",
            "policy", "source_manifest", "runtime_attestations",
            "output_dir", "receipt_dir",
        ),
        integers=("particles",),
        flags=("create_only",),
        handler=_reduce_size_command,
    )
    reduce_size_parser.add_argument("--prerequisite-terminal-selection")
    _contract(
        commands,
        "finalize-reduction",
        (
            "reduction", "policy", "source_manifest", "reduction_sha256",
            "runtime_attestations", "output_dir",
        ),
        flags=("create_only",),
        handler=_finalize_reduction_command,
    )
    _contract(
        commands,
        "finalization-status",
        ("finalization",),
        flags=("print",),
        handler=_finalization_status_command,
    )
    _contract(
        commands,
        "select-terminal",
        (
            "finalization", "policy", "source_manifest",
            "runtime_attestations", "output_dir",
        ),
        flags=("create_only",),
        handler=_select_terminal_command,
    )
    _contract(
        commands,
        "validate-prerequisite",
        (
            "particles", "terminal_selection", "terminal_selection_sha256",
            "policy", "source_manifest", "runtime_attestations",
        ),
        integers=("particles",),
        handler=_validate_prerequisite_command,
    )
    _contract(
        commands,
        "export-bundle",
        (
            "bundle_role", "source_controller", "source_root", "artifacts_from",
            "policy", "source_manifest", "runtime_attestations", "output_dir",
        ),
        flags=("create_only",),
        handler=_export_bundle_command,
    )
    _contract(
        commands,
        "import-bundle",
        (
            "bundle", "destination_controller", "destination_root", "profile",
            "output_dir",
        ),
        flags=("create_only",),
        handler=_import_bundle_command,
    )
    _contract(
        commands,
        "import-member",
        ("import", "kind"),
        flags=("print_path",),
        handler=_import_member_command,
    )
    _contract(
        commands,
        "transfer-import",
        ("receipt",),
        flags=("print_path",),
        handler=_transfer_import_command,
    )
    _contract(
        commands,
        "orchestration-output",
        ("transition_receipt", "field"),
        handler=_orchestration_output_command,
    )
    _contract(
        commands,
        "output-promotion",
        (
            "state_key", "transition_intent", "canonical_output",
            "expected_identity", "publisher", "controller", "output_dir",
        ),
        flags=("create_only",),
        handler=_output_promotion_command,
    )
    _contract(
        commands,
        "select-published",
        (
            "transition_intent", "publisher", "create_only_namespace",
            "promotion_output_dir", "print",
        ),
        choices={"print": ("none", "path")},
        handler=_select_published_command,
    )
    _contract(
        commands,
        "terminal-member",
        ("terminal_selection", "kind"),
        choices={"kind": ("provisional-finalization", "reduction")},
        flags=("print_path",),
        handler=_terminal_member_command,
    )
    _contract(
        commands,
        "verify-transfer",
        (
            "export", "import", "receipt", "policy", "source_manifest",
            "runtime_attestations",
        ),
        handler=_verify_transfer_command,
    )
    _contract(
        commands,
        "transfer-receipt",
        (
            "export", "import", "source_controller", "destination_controller",
            "policy", "source_manifest", "runtime_attestations", "output_dir",
        ),
        flags=("create_only",),
        handler=_transfer_receipt_command,
    )
    _contract(
        commands,
        "bootstrap-export",
        (
            "allowed_runtime", "source_manifest", "policy",
            "source_deployment_receipt", "destination_deployment_receipt",
            "source_controller", "destination_controller", "output_dir",
        ),
        flags=("create_only",),
        handler=_bootstrap_export_command,
    )
    _contract(
        commands,
        "bootstrap-import",
        (
            "bundle", "allowed_runtime_sha256", "source_manifest", "policy",
            "source_deployment_receipt", "destination_deployment_receipt",
            "output_dir",
        ),
        flags=("create_only",),
        handler=_bootstrap_import_command,
    )
    _contract(
        commands,
        "reduce-cross-size",
        (
            "n6_terminal_selection", "n7_terminal_selection", "n8_terminal_selection",
            "runtime_attestation_set_n6", "runtime_attestation_set_n7",
            "runtime_attestation_set_n8", "n8_provisional_finalization",
            "n8_reduction", "n8_import_receipt", "n8_transfer_receipt",
            "policy", "source_manifest", "output_dir", "receipt_dir",
        ),
        flags=("create_only",),
        handler=_reduce_cross_size_command,
    )
    _contract(
        commands,
        "production-orchestrate-size",
        (
            "particles", "rank_ladder", "seeds", "base_config", "policy",
            "source_manifest", "runtime_set_local", "runtime_set_local_sha256",
            "cpu_runtime_set_remote", "cpu_runtime_set_receipt",
            "gpu_runtime_set_remote", "gpu_runtime_set_receipt", "cpu_controller",
            "gpu_controller", "cpu_profile", "gpu_profile",
            "cpu_deployment_receipt", "gpu_deployment_receipt",
            "cpu_results_root", "gpu_results_root", "state_root_base",
            "state_backup_uri", "transition_action_manifest",
        ),
        choices={"cpu_controller": ("lasg02", "wuzh02"), "gpu_controller": ("qdeshell",)},
        integers=("particles",),
        flags=("create_only",),
        handler=_production_orchestrate_size_command,
    ).add_argument("--state-mirror-root")
    production = commands.choices["production-orchestrate-size"]
    production.add_argument("--prerequisite-terminal-selection")


def _manifest_field_command(arguments: argparse.Namespace) -> int:
    document = json.loads(Path(arguments.manifest).read_text(encoding="utf-8"))
    payload = document.get("payload")
    if not isinstance(payload, Mapping) or arguments.field not in payload:
        raise ValueError("runtime-set copy manifest field is missing")
    value = payload[arguments.field]
    if not isinstance(value, (str, int)):
        raise ValueError("runtime-set copy field is not scalar")
    print(value)
    return 0


def _publish_content_addressed(
    output_dir: Path | str, schema: str, payload: Mapping[str, Any]
) -> Path:
    digest = payload_sha256(payload)
    destination = Path(output_dir) / f"{digest}.json"
    _write_create_only(destination, envelope_for(schema, payload))
    print(destination.absolute())
    return destination


def _verify_execution_inputs_command(arguments: argparse.Namespace) -> int:
    source_path = Path(arguments.source_manifest)
    source = validate_envelope(
        source_path, "challenge15.source-manifest.v1"
    )
    runtime_path = Path(arguments.runtime_set)
    runtime_set = validate_envelope(
        runtime_path, "challenge15.runtime-attestation-set.v1"
    )
    root = Path.cwd().resolve()
    for relative, expected in source["members"].items():
        candidate = root / relative
        if not candidate.is_file() or candidate.is_symlink():
            raise ValueError(f"source manifest member is missing: {relative}")
        if _file_sha256(candidate) != expected:
            raise ValueError(f"source manifest member SHA256 mismatch: {relative}")
    role_entry = runtime_set["roles"][arguments.role]
    if role_entry["controller"] != arguments.controller:
        raise ValueError("runtime-set role/controller mismatch")
    digest = role_entry["allowed_runtime_sha256"]
    candidates = (
        runtime_path.parent / "allowed-runtimes" / f"{digest}.json",
        runtime_path.parent / f"{digest}.json",
    )
    matches = [path for path in candidates if path.is_file()]
    if len(matches) != 1:
        raise ValueError("controller-local allowed-runtime envelope is missing")
    runtime = validate_envelope(matches[0], "challenge15.allowed-runtime.v1")
    if (
        payload_sha256(runtime) != digest
        or runtime["role"] != arguments.role
        or runtime["controller"] != arguments.controller
        or runtime["source_manifest_sha256"] != payload_sha256(source)
    ):
        raise ValueError("allowed-runtime provenance mismatch")
    results = runtime_path.parent / "attestation-results"
    for member in runtime["attestation_test_members"]:
        test_relative = str(member["nodeid"]).split("::", 1)[0]
        test_path = root / test_relative
        if _file_sha256(test_path) != member["test_file_sha256"]:
            raise ValueError("attested test member hash mismatch")
        result = results / str(member["result_sha256"])
        if not result.is_file() or _file_sha256(result) != member["result_sha256"]:
            raise ValueError("attested test-result digest mismatch")
    return 0


def _runtime_attestation_commands(
    *,
    wheelhouse: Path,
    environment: Path,
    requirements: Path,
) -> tuple[tuple[str, ...], ...]:
    interpreter = str(environment / "bin" / "python")
    tests = (
        "tests/test_runtime_candidate.py",
        "tests/test_jax_04_compat.py",
        "tests/test_batched_model.py",
        "tests/test_production_vmc.py",
        "tests/test_coordinate_evaluation.py",
    )
    return (
        (sys.executable, "-m", "venv", str(environment)),
        (
            interpreter,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--require-hashes",
            "--only-binary=:all:",
            "--find-links",
            str(wheelhouse),
            "-r",
            str(requirements),
        ),
        (interpreter, "-m", "pytest", "-m", "production", *tests, "-q"),
    )


def _runtime_attest_command(arguments: argparse.Namespace) -> int:
    role = arguments.role
    controller = arguments.controller
    expected_gpu = role in {"training", "coordinate"}
    if expected_gpu != (controller == "qdeshell"):
        raise ValueError("runtime role/controller mismatch")
    if (arguments.profile == "cuda12") != expected_gpu:
        raise ValueError("runtime profile role mismatch")
    if (arguments.expected_backend == "gpu") != expected_gpu:
        raise ValueError("runtime backend role mismatch")
    wheelhouse = Path(arguments.wheelhouse).resolve(strict=True)
    source = validate_envelope(
        Path(arguments.source_manifest), "challenge15.source-manifest.v1"
    )
    policy = validate_envelope(
        Path(arguments.policy), "challenge15.production-policy.v1"
    )
    root = Path(__file__).resolve().parents[2]
    environment = Path(arguments.output_dir) / (
        f".attestation-env-{role}-{controller}-{time.time_ns()}"
    )
    requirements = root / "production" / "runtime" / arguments.profile / "requirements.txt"
    commands = _runtime_attestation_commands(
        wheelhouse=wheelhouse,
        environment=environment,
        requirements=requirements,
    )
    subprocess.run(commands[0], check=True, cwd=root)
    subprocess.run(commands[1], check=True, cwd=root)
    tests = (
        "tests/test_runtime_candidate.py",
        "tests/test_jax_04_compat.py",
        "tests/test_batched_model.py",
        "tests/test_production_vmc.py",
        "tests/test_coordinate_evaluation.py",
    )
    report = Path(arguments.output_dir) / (
        f".pytest-{role}-{controller}-{time.time_ns()}.txt"
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        commands[2],
        cwd=root,
        capture_output=True,
        text=True,
    )
    report.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise ValueError("production runtime attestation pytest gate failed")
    report_sha = _file_sha256(report)
    result_blob = (
        Path(arguments.output_dir) / "attestation-results" / report_sha
    )
    result_blob.parent.mkdir(parents=True, exist_ok=True)
    with result_blob.open("xb") as stream:
        stream.write(report.read_bytes())
        stream.flush()
        import os

        os.fsync(stream.fileno())
    if _file_sha256(result_blob) != report_sha:
        raise ValueError("attestation result publication mismatch")
    test_members = [
        {
            "nodeid": path,
            "test_file_sha256": _file_sha256(root / path),
            "result_sha256": report_sha,
        }
        for path in tests
    ]
    wheel_hashes = {
        path.name: _file_sha256(path)
        for path in sorted(wheelhouse.iterdir())
        if path.is_file() and path.suffix == ".whl"
    }
    probe = json.loads(
        subprocess.run(
            [
                str(environment / "bin" / "python"),
                "-c",
                (
                    "import importlib.metadata as m,json,platform,jax;"
                    "names=('jax','jaxlib','flax','optax','numpy','scipy','sympy','h5py','pytest');"
                    "print(json.dumps({'python_version':platform.python_version(),"
                    "'packages':{n:m.version(n) for n in names},"
                    "'backend':jax.default_backend(),'x64':bool(jax.config.x64_enabled),"
                    "'devices':sorted({d.platform for d in jax.devices()})}))"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    if probe["backend"] != arguments.expected_backend:
        raise ValueError("attested runtime backend mismatch")
    payload = {
        "profile": arguments.profile,
        "role": role,
        "controller": controller,
        "python_version": probe["python_version"],
        "python_abi": "cp312",
        "platform_tag": "manylinux2014_x86_64",
        "minimum_glibc": "2.17",
        "packages": probe["packages"],
        "wheel_sha256": wheel_hashes,
        "source_manifest_sha256": payload_sha256(source),
        "policy_sha256": payload_sha256(policy),
        "backend": probe["backend"],
        "x64_enabled": probe["x64"],
        "device_platforms": probe["devices"],
        "cuda_driver": (
            platform.platform() if expected_gpu else None
        ),
        "smoke_payload_sha256": report_sha,
        "attestation_test_members": test_members,
        "attested_hostname_class": controller,
        "attested_at_utc": (
            __import__("datetime").datetime.now(__import__("datetime").UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        ),
    }
    _publish_content_addressed(
        Path(arguments.output_dir) / "allowed-runtimes",
        "challenge15.allowed-runtime.v1",
        payload,
    )
    return 0


def _runtime_attestation_set_command(arguments: argparse.Namespace) -> int:
    entries = {}
    for role in ("training", "coordinate", "oracle", "exact", "reducer"):
        controller = getattr(arguments, f"{role}_controller")
        runtime_path = Path(getattr(arguments, role))
        runtime = validate_envelope(runtime_path, "challenge15.allowed-runtime.v1")
        if runtime["role"] != role or runtime["controller"] != controller:
            raise ValueError(f"{role} allowed-runtime role/controller mismatch")
        deployment_path = runtime_path.parent / "deployment-receipt.json"
        if not deployment_path.exists():
            raise ValueError(f"{role} deployment receipt is missing")
        deployment = validate_envelope(
            deployment_path, "challenge15.deployment-receipt.v1"
        )
        entries[role] = {
            "controller": controller,
            "allowed_runtime_sha256": payload_sha256(runtime),
            "deployment_receipt_sha256": payload_sha256(deployment),
            "backend": runtime["backend"],
        }
    payload = {
        "set_name": f"N={arguments.particles}",
        "particles": arguments.particles,
        "roles": entries,
    }
    _publish_content_addressed(
        arguments.output_dir, "challenge15.runtime-attestation-set.v1", payload
    )
    return 0


def _runtime_set_verify_copies_command(arguments: argparse.Namespace) -> int:
    local_path = Path(arguments.runtime_set_local)
    if _file_sha256(local_path) != arguments.runtime_set_local_sha256:
        raise ValueError("local runtime-set explicit SHA256 mismatch")
    local = validate_envelope(local_path, "challenge15.runtime-attestation-set.v1")
    local_payload_sha = payload_sha256(local)
    role_map_sha = payload_sha256(local["roles"])
    source_sha = _envelope_payload_digest(arguments.source_manifest)
    policy_sha = _envelope_payload_digest(arguments.policy)
    if (
        local["source_manifest_sha256"] != source_sha
        or local["policy_sha256"] != policy_sha
    ):
        raise ValueError("local runtime-set source/policy mismatch")
    for label, remote, receipt_path, deployment_path, controller in (
        (
            "CPU",
            arguments.cpu_runtime_set_remote,
            arguments.cpu_runtime_set_receipt,
            arguments.cpu_deployment_receipt,
            arguments.cpu_controller,
        ),
        (
            "GPU",
            arguments.gpu_runtime_set_remote,
            arguments.gpu_runtime_set_receipt,
            arguments.gpu_deployment_receipt,
            arguments.gpu_controller,
        ),
    ):
        receipt = validate_envelope(
            Path(receipt_path),
            "challenge15.runtime-set-publication-receipt.v1",
        )
        deployment = validate_envelope(
            Path(deployment_path), "challenge15.deployment-receipt.v1"
        )
        if (
            receipt["controller"] != controller
            or receipt["controller_local_path_identity"] != f"{controller}:{remote}"
            or receipt["payload_sha256"] != local_payload_sha
            or receipt["role_map_sha256"] != role_map_sha
            or receipt["source_manifest_sha256"] != source_sha
            or receipt["policy_sha256"] != policy_sha
            or receipt["deployment_receipt_sha256"] != payload_sha256(deployment)
        ):
            raise ValueError(f"{label} runtime-set copy/receipt mismatch")
        _verify_remote_runtime_copy(
            controller=controller,
            remote_path=remote,
            deployment=deployment,
            expected_byte_sha256=arguments.runtime_set_local_sha256,
            expected_payload_sha256=local_payload_sha,
            expected_role_map_sha256=role_map_sha,
            expected_source_sha256=source_sha,
            expected_policy_sha256=policy_sha,
        )
    return 0


def _verify_remote_runtime_copy(
    *,
    controller: str,
    remote_path: str,
    deployment: Mapping[str, Any],
    expected_byte_sha256: str,
    expected_payload_sha256: str,
    expected_role_map_sha256: str,
    expected_source_sha256: str,
    expected_policy_sha256: str,
) -> None:
    if not Path(remote_path).is_absolute():
        raise ValueError("controller-local runtime-set path must be absolute")
    interpreter = str(deployment["interpreter"])
    root = Path(str(deployment["deployment_root"]))
    if not Path(interpreter).is_absolute() or (
        Path(interpreter) != root and root not in Path(interpreter).parents
    ):
        raise ValueError("remote runtime verifier interpreter is not deployment-bound")
    completed = subprocess.run(
        [
            "ssh",
            controller,
            interpreter,
            "-m",
            "challenge15.cli",
            "runtime-set-remote-digest",
            "--runtime-set",
            remote_path,
            "--source-manifest-sha256",
            expected_source_sha256,
            "--policy-sha256",
            expected_policy_sha256,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        evidence = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("remote runtime verifier returned malformed evidence") from exc
    expected = {
        "byte_sha256": expected_byte_sha256,
        "payload_sha256": expected_payload_sha256,
        "role_map_sha256": expected_role_map_sha256,
        "source_manifest_sha256": expected_source_sha256,
        "policy_sha256": expected_policy_sha256,
    }
    if evidence != expected:
        raise ValueError("controller-local runtime-set remote evidence mismatch")


def _runtime_set_remote_digest_command(arguments: argparse.Namespace) -> int:
    path = Path(arguments.runtime_set)
    runtime = validate_envelope(
        path, "challenge15.runtime-attestation-set.v1"
    )
    if (
        runtime["source_manifest_sha256"] != arguments.source_manifest_sha256
        or runtime["policy_sha256"] != arguments.policy_sha256
    ):
        raise ValueError("remote runtime-set source/policy mismatch")
    print(
        json.dumps(
            {
                "byte_sha256": _file_sha256(path),
                "payload_sha256": payload_sha256(runtime),
                "role_map_sha256": payload_sha256(runtime["roles"]),
                "source_manifest_sha256": runtime["source_manifest_sha256"],
                "policy_sha256": runtime["policy_sha256"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


def _runtime_set_publication_receipt_command(arguments: argparse.Namespace) -> int:
    deployment = validate_envelope(
        Path(arguments.deployment_receipt), "challenge15.deployment-receipt.v1"
    )
    runtime = validate_envelope(
        Path(arguments.controller_local_path),
        "challenge15.runtime-attestation-set.v1",
    )
    source = validate_envelope(
        Path(arguments.source_manifest), "challenge15.source-manifest.v1"
    )
    policy = validate_envelope(
        Path(arguments.policy), "challenge15.production-policy.v1"
    )
    if payload_sha256(runtime) != arguments.runtime_set_sha256:
        raise ValueError("runtime-set publication SHA256 mismatch")
    payload = {
        "controller": arguments.controller,
        "deployment_receipt_sha256": payload_sha256(deployment),
        "controller_local_path_identity": (
            f"{arguments.controller}:{Path(arguments.controller_local_path).absolute()}"
        ),
        "payload_sha256": payload_sha256(runtime),
        "role_map_sha256": payload_sha256(runtime["roles"]),
        "source_manifest_sha256": payload_sha256(source),
        "policy_sha256": payload_sha256(policy),
        "published_at_utc": (
            __import__("datetime").datetime.now(__import__("datetime").UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        ),
    }
    _publish_content_addressed(
        arguments.output_dir,
        "challenge15.runtime-set-publication-receipt.v1",
        payload,
    )
    return 0


def _identity_map_count_command(arguments: argparse.Namespace) -> int:
    payload = validate_envelope(
        Path(arguments.identity_map), "challenge15.identity-map.v1"
    )
    task_count = payload["task_count"]
    tasks = payload["tasks"]
    if not isinstance(task_count, int) or task_count < 1 or len(tasks) != task_count:
        raise ValueError("identity map task count is inconsistent")
    print(task_count)
    return 0


def _identity_map_task_command(arguments: argparse.Namespace) -> int:
    from challenge15.orchestrator import resolve_array_identity

    task = resolve_array_identity(
        Path(arguments.identity_map),
        arguments.task_id,
        expected_stage=arguments.stage,
    )
    print(canonical_json(task).decode("utf-8"))
    return 0


def _identity_map_command(arguments: argparse.Namespace) -> int:
    ranks = tuple(_integer_list(arguments.expected_ranks, "expected-ranks"))
    seeds = tuple(_integer_list(arguments.expected_seeds, "expected-seeds"))
    if seeds != (0, 1, 2, 3, 4):
        raise ValueError("identity map requires seeds 0,1,2,3,4")
    root = Path(arguments.input_root).absolute()
    inputs: dict[tuple[int, int], str] = {}
    input_paths: dict[tuple[int, int], str] = {}
    common: dict[str, Any] | None = None
    for rank in ranks:
        for seed in seeds:
            path = root / f"rank={rank}" / f"seed={seed}.json"
            payload = validate_envelope(path)
            candidate_common = {
                field: payload[field]
                for field in (
                    "policy_sha256",
                    "source_manifest_sha256",
                    "runtime_attestations",
                    "base_configuration_sha256",
                    "particles",
                )
            }
            if common is None:
                common = candidate_common
            elif candidate_common != common:
                raise ValueError("identity-map inputs have unequal provenance")
            inputs[(rank, seed)] = payload_sha256(payload)
            input_paths[(rank, seed)] = str(path.resolve(strict=True))
    assert common is not None
    if common["particles"] != arguments.particles:
        raise ValueError("identity-map particle mismatch")
    identity = build_identity_map(
        stage=arguments.stage,
        expected_ranks=ranks,
        input_sha256_by_identity=inputs,
        input_path_by_identity=input_paths,
        array_concurrency=arguments.array_concurrency,
        policy_sha256=common["policy_sha256"],
        source_manifest_sha256=common["source_manifest_sha256"],
        runtime_attestations=common["runtime_attestations"],
        base_configuration_sha256=common["base_configuration_sha256"],
        particles=arguments.particles,
    )
    _publish_content_addressed(
        arguments.output_dir, "challenge15.identity-map.v1", identity
    )
    return 0


def _discover_generation_command(arguments: argparse.Namespace) -> int:
    seed_root = Path(arguments.seed_root).absolute()
    extension_root = Path(arguments.extension_root).absolute()
    if extension_root != seed_root / "extensions":
        raise ValueError("extension root is not local to seed root")
    extensions = tuple(
        path.stem
        for path in sorted(extension_root.glob("*.json"))
        if path.is_file() and not path.is_symlink()
    )
    expected_ranks = tuple(
        _integer_list(arguments.expected_ranks, "expected-ranks")
    )
    if len(extensions) != len(expected_ranks):
        raise ValueError("extension count does not match expected ranks")
    payloads = [
        validate_envelope(
            extension_root / f"{digest}.json",
            "challenge15.rank-extension.v1",
        )
        for digest in extensions
    ]
    ranks = tuple(sorted(int(payload["new_rank"]) for payload in payloads))
    if ranks != expected_ranks:
        raise ValueError("extensions do not match expected ranks")
    owner_paths = tuple((seed_root / "owner").glob("*.json"))
    if len(owner_paths) != 1:
        raise ValueError("seed root does not have a unique owner")
    owner = validate_envelope(owner_paths[0], "challenge15.seed-owner.v1")
    first = payloads[0]
    runtime = validate_envelope(
        Path(arguments.runtime_attestations),
        "challenge15.runtime-attestation-set.v1",
    )
    generation = discover_unique_terminal_generation(
        seed_root,
        extensions,
        expected_policy_sha256=_envelope_payload_digest(arguments.policy),
        expected_source_manifest_sha256=_envelope_payload_digest(
            arguments.source_manifest
        ),
        expected_runtime_attestations=_runtime_role_map(runtime),
        expected_base_configuration_sha256=first[
            "base_configuration_sha256"
        ],
        expected_particles=int(first["particles"]),
        expected_seed=int(first["seed"]),
        expected_experiment_id=str(owner["experiment_id"]),
        expected_canonical_root=seed_root,
    )
    print(generation.path)
    return 0


def _finalization_status_command(arguments: argparse.Namespace) -> int:
    payload = validate_envelope(
        Path(arguments.finalization), "challenge15.reduction-finalization.v1"
    )
    print("accepted" if payload["production_accepted"] else "pending")
    return 0


def _runtime_role_map(runtime_set: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    return {
        role: {
            str(item["controller"]): str(item["allowed_runtime_sha256"])
        }
        for role, item in runtime_set["roles"].items()
    }


def _verify_production_bindings(
    payload: Mapping[str, Any],
    *,
    policy_path: str,
    source_path: str,
    runtime_path: str,
) -> None:
    policy = validate_envelope(
        Path(policy_path), "challenge15.production-policy.v1"
    )
    source = validate_envelope(
        Path(source_path), "challenge15.source-manifest.v1"
    )
    runtime = validate_envelope(
        Path(runtime_path), "challenge15.runtime-attestation-set.v1"
    )
    if payload["policy_sha256"] != payload_sha256(policy):
        raise ValueError("artifact policy SHA256 mismatch")
    if payload["source_manifest_sha256"] != payload_sha256(source):
        raise ValueError("artifact source-manifest SHA256 mismatch")
    if payload["runtime_attestations"] != _runtime_role_map(runtime):
        raise ValueError("artifact runtime-attestation role map mismatch")


def _finalize_reduction_command(arguments: argparse.Namespace) -> int:
    reduction_path = Path(arguments.reduction).absolute()
    reduction = validate_envelope(
        reduction_path, "challenge15.size-result.v1"
    )
    if payload_sha256(reduction) != arguments.reduction_sha256:
        raise ValueError("explicit reduction SHA256 mismatch")
    _verify_production_bindings(
        reduction,
        policy_path=arguments.policy,
        source_path=arguments.source_manifest,
        runtime_path=arguments.runtime_attestations,
    )
    print(finalize_reduction(reduction_path, Path(arguments.output_dir)))
    return 0


def _select_terminal_command(arguments: argparse.Namespace) -> int:
    provisional = validate_envelope(
        Path(arguments.finalization),
        "challenge15.reduction-finalization.v1",
    )
    _verify_production_bindings(
        provisional,
        policy_path=arguments.policy,
        source_path=arguments.source_manifest,
        runtime_path=arguments.runtime_attestations,
    )
    selected = select_terminal(
        Path(arguments.finalization), Path(arguments.output_dir)
    )
    members = selected.parent / "members"
    members.mkdir()
    finalization_path = Path(arguments.finalization).absolute()
    publish_create_only(
        members / f"{payload_sha256(provisional)}.json",
        finalization_path.read_bytes(),
    )
    reduction_path = Path(str(provisional["selected_reduction_path"]))
    publish_create_only(
        members / f"{provisional['selected_reduction_sha256']}.json",
        reduction_path.read_bytes(),
    )
    print(selected)
    return 0


def _validate_prerequisite_command(arguments: argparse.Namespace) -> int:
    path = Path(arguments.terminal_selection).absolute()
    terminal = validate_envelope(path, "challenge15.terminal-selection.v1")
    if payload_sha256(terminal) != arguments.terminal_selection_sha256:
        raise ValueError("terminal-selection explicit SHA256 mismatch")
    if (
        terminal["particles"] != arguments.particles
        or terminal["production_accepted"] is not True
    ):
        raise ValueError("prerequisite terminal selection is not accepted")
    _verify_production_bindings(
        terminal,
        policy_path=arguments.policy,
        source_path=arguments.source_manifest,
        runtime_path=arguments.runtime_attestations,
    )
    finalization_path = (
        path.parent
        / "members"
        / f"{terminal['selected_finalization_sha256']}.json"
    )
    provisional = validate_envelope(
        finalization_path, "challenge15.reduction-finalization.v1"
    )
    if payload_sha256(provisional) != terminal["selected_finalization_sha256"]:
        raise ValueError("prerequisite selected finalization mismatch")
    reduction_path = Path(str(provisional["selected_reduction_path"]))
    reduction = validate_envelope(reduction_path, "challenge15.size-result.v1")
    if (
        payload_sha256(reduction) != terminal["selected_reduction_sha256"]
        or reduction["production_accepted"] is not True
    ):
        raise ValueError("prerequisite canonical reduction mismatch")
    return 0


def _orchestration_output_command(arguments: argparse.Namespace) -> int:
    payload = validate_envelope(Path(arguments.transition_receipt))
    if arguments.field not in payload:
        raise ValueError("transition output field is missing")
    value = payload[arguments.field]
    print(
        value
        if isinstance(value, (str, int, float))
        else canonical_json(value).decode("utf-8")
    )
    return 0


def _import_member_command(arguments: argparse.Namespace) -> int:
    imported = validate_envelope(
        Path(getattr(arguments, "import")), "challenge15.import-bundle.v1"
    )
    manifest = imported["member_manifest"]
    matches = [
        relative
        for relative in manifest
        if Path(relative).name == arguments.kind
        or Path(relative).stem == arguments.kind
        or relative.startswith(f"{arguments.kind}/")
    ]
    if len(matches) != 1:
        raise ValueError("import member kind is missing or ambiguous")
    path = Path(str(imported["destination_root"])) / "members" / matches[0]
    if not path.is_file() or _file_sha256(path) != manifest[matches[0]]:
        raise ValueError("import member path/hash mismatch")
    print(path.absolute())
    return 0


def _transfer_import_command(arguments: argparse.Namespace) -> int:
    receipt = validate_envelope(
        Path(arguments.receipt), "challenge15.transfer-receipt.v1"
    )
    path = Path(str(receipt["final_path"]))
    if not path.is_absolute() or not path.exists():
        raise ValueError("transfer destination is not local and complete")
    print(path)
    return 0


def _terminal_member_command(arguments: argparse.Namespace) -> int:
    terminal_path = Path(arguments.terminal_selection).absolute()
    terminal = validate_envelope(
        terminal_path, "challenge15.terminal-selection.v1"
    )
    digest = (
        terminal["selected_finalization_sha256"]
        if arguments.kind == "provisional-finalization"
        else terminal["selected_reduction_sha256"]
    )
    path = terminal_path.parent / "members" / f"{digest}.json"
    payload = validate_envelope(
        path,
        (
            "challenge15.reduction-finalization.v1"
            if arguments.kind == "provisional-finalization"
            else "challenge15.size-result.v1"
        ),
    )
    if payload_sha256(payload) != digest:
        raise ValueError("terminal member payload mismatch")
    print(path)
    return 0


def _envelope_payload_digest(path: Path | str) -> str:
    return payload_sha256(validate_envelope(Path(path)))


def _orchestration_attempt_intent_command(arguments: argparse.Namespace) -> int:
    state_key = validate_envelope(
        Path(arguments.state_key), "challenge15.orchestration-state-key.v1"
    )
    transition = validate_envelope(Path(arguments.transition_identity))
    expected_identity = json.loads(arguments.expected_output_identity)
    if not isinstance(expected_identity, Mapping):
        raise ValueError("expected output identity must be a JSON object")
    script_sha = _file_sha256(Path(arguments.script))
    profile_sha = _envelope_payload_digest(arguments.profile)
    deployment_sha = _envelope_payload_digest(arguments.deployment_receipt)
    source_sha = _envelope_payload_digest(arguments.source_manifest)
    policy_sha = _envelope_payload_digest(arguments.policy)
    base_sha = payload_sha256(
        validate_production_vmc_config_envelope(Path(arguments.base_config))
    )
    correlation_seed = OrchestrationAttemptIntent(
        state_key_sha256=payload_sha256(state_key),
        transition_identity_sha256=payload_sha256(transition),
        attempt=arguments.attempt,
        action_kind=arguments.action_kind,
        correlation_id="0" * 64,
        source_controller=arguments.source_controller,
        destination_controller=arguments.destination_controller,
        script_sha256=script_sha,
        canonical_argv_sha256=arguments.canonical_argv_sha256,
        input_sha256s=(arguments.input_sha256,),
        profile_sha256=profile_sha,
        deployment_receipt_sha256=deployment_sha,
        runtime_set_sha256=arguments.runtime_set_sha256,
        source_manifest_sha256=source_sha,
        policy_sha256=policy_sha,
        base_configuration_sha256=base_sha,
        particles=arguments.particles,
        seed=arguments.seed,
        rank=arguments.rank,
        parent_sha256s={
            f"parent-{index}": value
            for index, value in enumerate(arguments.parent_sha256)
        },
        expected_output_identities=(dict(expected_identity),),
        create_only_namespace_identities=(
            str(Path(arguments.create_only_namespace).absolute()),
        ),
        scheduler_job_name=None,
        scheduler_comment=None,
        remote_claim_path_identity=str(
            Path(arguments.remote_claim_root).absolute()
        ),
        created_at_utc=(
            __import__("datetime").datetime.now(__import__("datetime").UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        ),
    )
    correlation = attempt_correlation_id(correlation_seed)
    intent = replace(
        correlation_seed,
        correlation_id=correlation,
        scheduler_job_name=(
            f"c15-{correlation[:24]}"
            if arguments.action_kind == "slurm"
            else None
        ),
        scheduler_comment=(
            correlation if arguments.action_kind == "slurm" else None
        ),
    )
    _publish_content_addressed(
        arguments.output_dir,
        "challenge15.orchestration-attempt-intent.v1",
        intent.to_payload(),
    )
    return 0


def _claim_seed_command(arguments: argparse.Namespace) -> int:
    base = validate_production_vmc_config_envelope(Path(arguments.base_config))
    policy = validate_envelope(
        Path(arguments.policy), "challenge15.production-policy.v1"
    )
    source = validate_envelope(
        Path(arguments.source_manifest), "challenge15.source-manifest.v1"
    )
    runtime = validate_envelope(
        Path(arguments.runtime_attestations),
        "challenge15.runtime-attestation-set.v1",
    )
    common = {
        "particles": arguments.particles,
        "seed": arguments.seed,
        "base": payload_sha256(base),
        "policy": payload_sha256(policy),
        "source": payload_sha256(source),
        "runtime": payload_sha256(runtime),
    }
    now = (
        __import__("datetime").datetime.now(__import__("datetime").UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    owner = SeedOwner(
        seed=arguments.seed,
        experiment_id=payload_sha256(common),
        base_configuration_sha256=payload_sha256(base),
        expected_seed_set=(0, 1, 2, 3, 4),
        owner_uuid=arguments.owner_uuid,
        claimed_at_utc=now,
        claim_host=platform.node(),
        claim_process=str(__import__("os").getpid()),
        claim_nonce_sha256=payload_sha256(
            {"owner_uuid": arguments.owner_uuid, "claimed_at_utc": now}
        ),
        policy_sha256=payload_sha256(policy),
        source_manifest_sha256=payload_sha256(source),
        runtime_attestations=_runtime_role_map(runtime),
    )
    print(claim_seed_root(Path(arguments.destination), owner))
    return 0


def _rank_extension_decision_command(arguments: argparse.Namespace) -> int:
    runtime = validate_envelope(
        Path(arguments.runtime_attestations),
        "challenge15.runtime-attestation-set.v1",
    )
    current = (
        None if arguments.current_rank == "none" else int(arguments.current_rank)
    )
    if current is None:
        if arguments.new_rank != 1 or arguments.reason != "initial":
            raise ValueError("root rank decision must be none -> 1 with reason initial")
        if any(
            getattr(arguments, field)
            for field in (
                "prior_reduction",
                "prior_finalization",
                "prior_import_receipt",
                "prior_transfer_receipt",
            )
        ):
            raise ValueError("root rank decision forbids prior-cycle inputs")
        decision = RankExtensionDecision(
            policy_sha256=_envelope_payload_digest(arguments.policy),
            source_manifest_sha256=_envelope_payload_digest(
                arguments.source_manifest
            ),
            runtime_attestations=_runtime_role_map(runtime),
            base_configuration_sha256=payload_sha256(
                validate_production_vmc_config_envelope(
                    Path(arguments.base_config)
                )
            ),
            particles=int(runtime["particles"]),
            seed=arguments.seed,
            current_rank=None,
            new_rank=1,
            prior_expected_ranks_sha256=None,
            prior_reduction_sha256=None,
            prior_finalization_sha256=None,
            prior_import_receipt_sha256=None,
            prior_transfer_receipt_sha256=None,
            decision="train",
            reason="initial",
            decision_metrics={"prior_production_accepted": None},
        )
        Path(arguments.output_dir).mkdir(parents=True, exist_ok=False)
        print(
            publish_rank_extension_decision(
                Path(arguments.output_dir), decision
            )
        )
        return 0
    required = (
        arguments.prior_reduction,
        arguments.prior_finalization,
        arguments.prior_import_receipt,
        arguments.prior_transfer_receipt,
    )
    if any(value is None for value in required):
        raise ValueError("non-root rank decision requires every prior-cycle input")
    output = create_nonroot_rank_decision(
        Path(arguments.prior_finalization),
        arguments.seed,
        arguments.new_rank,
        Path(arguments.output_dir),
        prior_import_receipt=Path(arguments.prior_import_receipt),
        prior_transfer_receipt=Path(arguments.prior_transfer_receipt),
    )
    payload = validate_envelope(
        output, "challenge15.rank-extension-decision.v1"
    )
    if (
        payload["current_rank"] != current
        or payload["prior_reduction_sha256"]
        != _envelope_payload_digest(arguments.prior_reduction)
        or payload["reason"] != arguments.reason
    ):
        raise ValueError("non-root rank decision lineage mismatch")
    _verify_production_bindings(
        payload,
        policy_path=arguments.policy,
        source_path=arguments.source_manifest,
        runtime_path=arguments.runtime_attestations,
    )
    print(output)
    return 0


def _rank_extension_command(arguments: argparse.Namespace) -> int:
    decision_path = Path(arguments.decision).absolute()
    decision = validate_envelope(
        decision_path, "challenge15.rank-extension-decision.v1"
    )
    if (
        decision["particles"] != arguments.particles
        or decision["seed"] != arguments.seed
        or decision["reason"] != arguments.reason
    ):
        raise ValueError("rank extension decision identity mismatch")
    _verify_production_bindings(
        decision,
        policy_path=arguments.policy,
        source_path=arguments.source_manifest,
        runtime_path=arguments.runtime_attestations,
    )
    base = validate_production_vmc_config_envelope(Path(arguments.base_config))
    if payload_sha256(base) != decision["base_configuration_sha256"]:
        raise ValueError("rank extension base configuration mismatch")
    output = Path(arguments.output_dir)
    seed_root = output.parent
    owner_paths = tuple((seed_root / "owner").glob("*.json"))
    if len(owner_paths) != 1:
        raise ValueError("rank extension requires unique seed owner")
    owner = validate_envelope(owner_paths[0], "challenge15.seed-owner.v1")
    parent_path = (
        None
        if arguments.parent_generation is None
        else Path(arguments.parent_generation).absolute()
    )
    if decision["current_rank"] is None:
        if parent_path is not None:
            raise ValueError("root extension forbids parent generation")
        parent_digest = parent_parameter = parent_optimizer = None
    else:
        if parent_path is None:
            raise ValueError("non-root extension requires parent generation")
        parent = validate_envelope(
            parent_path, "challenge15.training-generation.v1"
        )
        parent_digest = payload_sha256(parent)
        parent_parameter = parent["parameter_sha256"]
        parent_optimizer = parent["optimizer_state_sha256"]
        if (
            parent["rank"] != decision["current_rank"]
            or parent["seed"] != arguments.seed
        ):
            raise ValueError("rank extension parent identity mismatch")
    source = validate_envelope(
        Path(arguments.source_manifest), "challenge15.source-manifest.v1"
    )
    extension = RankExtension(
        particles=arguments.particles,
        seed=arguments.seed,
        experiment_id=owner["experiment_id"],
        base_configuration_sha256=payload_sha256(base),
        policy_sha256=decision["policy_sha256"],
        source_manifest_sha256=decision["source_manifest_sha256"],
        runtime_attestations=decision["runtime_attestations"],
        expected_seed_set=(0, 1, 2, 3, 4),
        previous_rank=decision["current_rank"],
        new_rank=decision["new_rank"],
        parent_generation_sha256=parent_digest,
        parent_parameter_sha256=parent_parameter,
        parent_optimizer_state_sha256=parent_optimizer,
        rank_extension_decision_sha256=payload_sha256(decision),
        embedding_algorithm="copy-old-append-zero-gates-v1",
        rank_growth_prng={
            "algorithm": "threefry2x32",
            "key_sha256": payload_sha256(
                {
                    "seed": arguments.seed,
                    "new_rank": decision["new_rank"],
                    "base_configuration_sha256": payload_sha256(base),
                }
            ),
        },
        reason=arguments.reason,
        created_by_git_revision=source["git_revision"],
    )
    print(create_rank_extension(output, extension))
    return 0


def _now_utc() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _resource_override_command(arguments: argparse.Namespace) -> int:
    extension = validate_envelope(
        Path(arguments.extension), "challenge15.rank-extension.v1"
    )
    payload = {
        **{
            field: extension[field]
            for field in (
                "policy_sha256", "source_manifest_sha256", "runtime_attestations",
                "base_configuration_sha256", "particles", "seed",
            )
        },
        "rank": extension["new_rank"],
        "extension_sha256": payload_sha256(extension),
        "attempt_sha256": payload_sha256(
            {"extension_sha256": payload_sha256(extension), "attempt": arguments.attempt}
        ),
        "reason": arguments.reason,
        "walker_microbatch": arguments.walker_microbatch,
        "carrier_block": arguments.carrier_block,
        "quadrature_block": arguments.quadrature_block,
        "fixed_schedule_sha256": extension["base_configuration_sha256"],
        "metric_equivalence": {
            "canonical_layout": {
                "walker_microbatch": arguments.walker_microbatch,
                "carrier_block": arguments.carrier_block,
                "quadrature_block": arguments.quadrature_block,
            },
            "selected_layout": {
                "walker_microbatch": arguments.walker_microbatch,
                "carrier_block": arguments.carrier_block,
                "quadrature_block": arguments.quadrature_block,
            },
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
        },
    }
    _publish_content_addressed(
        arguments.output_dir, "challenge15.resource-override.v1", payload
    )
    return 0


def _exact_shard_command(arguments: argparse.Namespace) -> int:
    """Validate the exact immutable shard identity before the numerical kernel."""
    oracle = validate_envelope(
        Path(arguments.oracle), "challenge15.production-oracle.v1"
    )
    generation = validate_envelope(
        Path(arguments.generation), "challenge15.training-generation.v1"
    )
    _verify_production_bindings(
        generation,
        policy_path=arguments.policy,
        source_path=arguments.source_manifest,
        runtime_path=arguments.runtime_attestations,
    )
    for field in (
        "policy_sha256", "source_manifest_sha256", "runtime_attestations",
        "base_configuration_sha256", "particles",
    ):
        if generation[field] != oracle[field]:
            raise ValueError(f"exact shard has stale {field}")
    # The production oracle arrays are immutable sidecar members.  Keep the
    # expensive evaluator behind a small injectable loader so execution tests
    # can use a fake kernel without running physics.
    from challenge15.exact_eval import evaluate_exact_shard_from_envelopes

    output = evaluate_exact_shard_from_envelopes(
        Path(arguments.oracle),
        Path(arguments.generation),
        determinant_block=arguments.determinant_block,
        carrier_block=arguments.carrier_block,
        quadrature_block=arguments.quadrature_block,
        destination=Path(arguments.destination),
    )
    print(output)
    return 0


def _identity_inputs(
    root: Path, ranks: Sequence[int]
) -> tuple[dict[tuple[int, int], str], dict[tuple[int, int], str]]:
    result: dict[tuple[int, int], str] = {}
    paths: dict[tuple[int, int], str] = {}
    for rank in ranks:
        for seed in range(5):
            candidates = sorted((root / f"rank={rank}").glob(f"seed={seed}*.json"))
            if len(candidates) != 1:
                raise ValueError(
                    f"identity input must be unique for rank={rank},seed={seed}"
                )
            result[(rank, seed)] = _envelope_payload_digest(candidates[0])
            paths[(rank, seed)] = str(candidates[0].resolve(strict=True))
    return result, paths


def _publish_identity_map(
    *, stage: str, particles: int, ranks: Sequence[int], input_root: Path,
    output_dir: str, concurrency: int, common: Mapping[str, Any],
) -> None:
    inputs, paths = _identity_inputs(input_root, ranks)
    payload = build_identity_map(
        stage=stage,
        expected_ranks=ranks,
        input_sha256_by_identity=inputs,
        input_path_by_identity=paths,
        array_concurrency=concurrency,
        particles=particles,
        **common,
    )
    _publish_content_addressed(
        output_dir, "challenge15.identity-map.v1", payload
    )


def _cumulative_reducer_identity_map_command(arguments: argparse.Namespace) -> int:
    ranks = tuple(_integer_list(arguments.expected_ranks, "expected-ranks"))
    if arguments.new_rank not in ranks or ranks[-1] != arguments.new_rank:
        raise ValueError("new rank must terminate expected ranks")
    roots = (Path(arguments.new_coordinate_root), Path(arguments.new_exact_root))
    first = next((p for root in roots for p in sorted(root.rglob("*.json"))), None)
    if first is None:
        raise ValueError("cumulative reducer inputs are empty")
    sample = validate_envelope(first)
    common = {
        field: sample[field]
        for field in (
            "policy_sha256", "source_manifest_sha256", "runtime_attestations",
            "base_configuration_sha256",
        )
    }
    _publish_identity_map(
        stage="reduction", particles=arguments.particles, ranks=ranks,
        input_root=Path(arguments.new_exact_root), output_dir=arguments.output_dir,
        concurrency=1, common=common,
    )
    return 0


def _cycle_ranks_command(arguments: argparse.Namespace) -> int:
    previous: list[int] = []
    if arguments.previous_cycle_receipt:
        payload = validate_envelope(Path(arguments.previous_cycle_receipt))
        previous = list(payload.get("expected_ranks", ()))
    ranks = [*previous, arguments.new_rank]
    if ranks != [1, 2, 4, 8][: len(ranks)]:
        raise ValueError("cycle ranks are not consecutive immutable doublings")
    if arguments.print_tsv:
        print("\t".join(str(rank) for rank in ranks))
    return 0


def _accepted_terminal_identity_map_command(arguments: argparse.Namespace) -> int:
    from challenge15.reducer import expected_ranks_sha256

    terminal = validate_envelope(
        Path(arguments.terminal_selection), "challenge15.terminal-selection.v1"
    )
    if terminal["production_accepted"] is not True:
        raise ValueError("accepted-terminal map requires accepted selection")
    common = {
        field: terminal[field]
        for field in (
            "policy_sha256", "source_manifest_sha256", "runtime_attestations",
            "base_configuration_sha256",
        )
    }
    reduction = validate_envelope(
        Path(arguments.reduction), "challenge15.size-result.v1"
    )
    finalization = validate_envelope(
        Path(arguments.provisional_finalization),
        "challenge15.reduction-finalization.v1",
    )
    runtime_set = validate_envelope(
        Path(arguments.runtime_attestation_set),
        "challenge15.runtime-attestation-set.v1",
    )
    ranks = list(reduction["expected_ranks"])
    if (
        expected_ranks_sha256(ranks) != terminal["selected_expected_ranks_sha256"]
        or payload_sha256(reduction) != terminal["selected_reduction_sha256"]
        or payload_sha256(finalization) != terminal["selected_finalization_sha256"]
        or _runtime_role_map(runtime_set) != terminal["runtime_attestations"]
        or runtime_set["source_manifest_sha256"] != terminal["source_manifest_sha256"]
        or runtime_set["policy_sha256"] != terminal["policy_sha256"]
        or runtime_set["base_configuration_sha256"]
        != terminal["base_configuration_sha256"]
    ):
        raise ValueError("accepted-terminal identity map lineage mismatch")
    # This map is a single accepted object, not a Slurm five-seed map.
    payload = {
        **common, "particles": terminal["particles"], "stage": "accepted-terminal",
        "expected_ranks": ranks,
        "expected_ranks_sha256": expected_ranks_sha256(ranks),
        "expected_seeds": [], "task_count": 0, "tasks": [], "array_concurrency": 1,
    }
    _publish_content_addressed(
        arguments.output_dir, "challenge15.identity-map.v1", payload
    )
    return 0


def _runtime_set_identity_map_command(arguments: argparse.Namespace) -> int:
    runtime = validate_envelope(
        Path(arguments.runtime_attestation_set),
        "challenge15.runtime-attestation-set.v1",
    )
    payload = {
        "policy_sha256": runtime["policy_sha256"],
        "source_manifest_sha256": runtime["source_manifest_sha256"],
        "runtime_attestations": _runtime_role_map(runtime),
        "base_configuration_sha256": runtime["base_configuration_sha256"],
        "particles": runtime["particles"],
        "stage": "runtime-set", "expected_ranks": [],
        "expected_ranks_sha256": payload_sha256([]), "expected_seeds": [],
        "task_count": 0, "tasks": [], "array_concurrency": 1,
    }
    _publish_content_addressed(
        arguments.output_dir, "challenge15.identity-map.v1", payload
    )
    return 0


def _paths_with_schema(root: Path, schema: str) -> list[Path]:
    result = []
    for path in sorted(root.rglob("*.json")):
        try:
            validate_envelope(path, schema)
        except ValueError:
            continue
        result.append(path)
    return result


def _reduce_size_command(arguments: argparse.Namespace) -> int:
    from challenge15.reducer import publish_reduction, reduce_size

    ranks = tuple(_integer_list(arguments.expected_ranks, "expected-ranks"))
    if tuple(_integer_list(arguments.expected_seeds, "expected-seeds")) != tuple(range(5)):
        raise ValueError("reduction requires exactly seeds 0..4")
    result = reduce_size(
        ranks,
        Path(arguments.identity_map),
        Path(arguments.oracle),
        sorted({
            path.parent.parent
            for path in _paths_with_schema(
                Path(arguments.training_root), "challenge15.training-generation.v1"
            )
        }),
        _paths_with_schema(Path(arguments.exact_root), "challenge15.exact-evaluation-shard.v1"),
        _paths_with_schema(
            Path(arguments.coordinate_root), "challenge15.coordinate-evaluation-shard.v1"
        ),
        (
            None
            if arguments.prerequisite_terminal_selection is None
            else Path(arguments.prerequisite_terminal_selection)
        ),
    )
    published = publish_reduction(
        result, Path(arguments.output_dir), Path(arguments.receipt_dir)
    )
    print(
        f"{_envelope_payload_digest(published.payload_path)}"
        f"\t{published.payload_path.resolve(strict=True)}"
    )
    return 0


def _artifact_paths(value: str) -> list[Path]:
    path = Path(value)
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.is_file() and not p.is_symlink())
    return [Path(item) for item in value.split(",")]


def _export_bundle_command(arguments: argparse.Namespace) -> int:
    from challenge15.transfers import file_sha256, write_sha256sums

    source_root = Path(arguments.source_root).resolve(strict=True)
    artifacts = _artifact_paths(arguments.artifacts_from)
    if not artifacts:
        raise ValueError("export bundle has no artifacts")
    members = {
        path.resolve().relative_to(source_root).as_posix(): file_sha256(path)
        for path in artifacts
        if path.resolve().is_relative_to(source_root)
    }
    if len(members) != len(artifacts):
        raise ValueError("export artifacts are duplicated or outside source root")
    first = validate_envelope(artifacts[0])
    _verify_production_bindings(
        first, policy_path=arguments.policy, source_path=arguments.source_manifest,
        runtime_path=arguments.runtime_attestations,
    )
    bundle_sha = payload_sha256(dict(sorted(members.items())))
    root = Path(arguments.output_dir) / bundle_sha
    member_root = root / "members"
    member_root.mkdir(parents=True, exist_ok=False)
    for path in artifacts:
        publish_create_only(
            member_root / path.resolve().relative_to(source_root), path.read_bytes()
        )
    sums = write_sha256sums(member_root)
    payload = {
        **{
            field: first[field]
            for field in (
                "policy_sha256", "source_manifest_sha256", "runtime_attestations",
                "base_configuration_sha256", "particles",
            )
        },
        "bundle_role": arguments.bundle_role,
        "source_controller": arguments.source_controller,
        "source_root": str(source_root),
        "source_artifact_sha256": payload_sha256(first),
        "member_manifest": dict(sorted(members.items())),
        "sha256sums_sha256": _file_sha256(sums),
        "bundle_sha256": bundle_sha,
        "created_at_utc": _now_utc(),
    }
    _write_create_only(root / "export.json", envelope_for(
        "challenge15.export-bundle.v1", payload
    ))
    print(root)
    return 0


def _import_bundle_command(arguments: argparse.Namespace) -> int:
    from challenge15.transfers import verify_export_bundle

    bundle = Path(arguments.bundle).resolve(strict=True)
    exported = validate_envelope(
        bundle / "export.json", "challenge15.export-bundle.v1"
    )
    verify_export_bundle(bundle, exported)
    profile = validate_envelope(
        Path(arguments.profile), "challenge15.cluster-profile.v1"
    )
    destination = Path(arguments.destination_root).absolute()
    approved = Path(profile["approved_results_root"])
    if destination != approved and approved not in destination.parents:
        raise ValueError("import destination is outside profile-approved root")
    if arguments.destination_controller != profile["controller"]:
        raise ValueError("import destination controller/profile mismatch")
    payload = {
        **{
            field: exported[field]
            for field in (
                "policy_sha256", "source_manifest_sha256", "runtime_attestations",
                "base_configuration_sha256", "particles", "bundle_sha256",
                "member_manifest",
            )
        },
        "destination_controller": arguments.destination_controller,
        "destination_root": str(destination),
        "imported_artifact_sha256": exported["source_artifact_sha256"],
        "verified_at_utc": _now_utc(),
    }
    _publish_content_addressed(
        arguments.output_dir, "challenge15.import-bundle.v1", payload
    )
    return 0


def _output_promotion_command(arguments: argparse.Namespace) -> int:
    state_key = validate_envelope(
        Path(arguments.state_key), "challenge15.orchestration-state-key.v1"
    )
    intent = validate_envelope(
        Path(arguments.transition_intent),
        "challenge15.orchestration-attempt-intent.v1",
    )
    output_path = Path(arguments.canonical_output).absolute()
    output = validate_envelope(output_path)
    expected = json.loads(arguments.expected_identity)
    if intent["destination_controller"] != arguments.controller:
        raise ValueError("promotion controller is not intent-bound")
    if any(output.get(key) != value for key, value in expected.items()):
        raise ValueError("promoted output identity mismatch")
    payload = {
        "state_key_sha256": payload_sha256(state_key),
        "transition_identity_sha256": intent["transition_identity_sha256"],
        "output_schema": json.loads(output_path.read_text())["schema"],
        "output_payload_sha256": payload_sha256(output),
        "output_absolute_path_identity": str(output_path),
        "producer_intent_sha256": payload_sha256(intent),
        "selector_kind": arguments.publisher,
        "selector_namespace_identity": str(output_path.parent),
        "candidate_computed_sha256": payload_sha256(output),
        "candidate_count": 1,
        "promoted_at_utc": _now_utc(),
    }
    _publish_content_addressed(
        arguments.output_dir, "challenge15.output-promotion.v1", payload
    )
    return 0


def _select_published_command(arguments: argparse.Namespace) -> int:
    from challenge15.orchestrator import recover_before_act

    intent = validate_envelope(
        Path(arguments.transition_intent),
        "challenge15.orchestration-attempt-intent.v1",
    )
    permitted = {Path(item).absolute() for item in intent["create_only_namespace_identities"]}
    namespace = Path(arguments.create_only_namespace).absolute()
    if namespace not in permitted:
        raise ValueError("selector namespace is not permitted by intent")
    identity = intent["expected_output_identities"][0]
    schema = str(identity.pop("schema"))
    recovered = recover_before_act(
        namespace, expected_schema=schema, expected_identity=identity
    )
    if arguments.print == "path" and recovered.path is not None:
        print(recovered.path)
    return 0


def _verify_transfer_command(arguments: argparse.Namespace) -> int:
    from challenge15.transfers import verify_export_bundle

    exported = validate_envelope(
        Path(arguments.export), "challenge15.export-bundle.v1"
    )
    imported = validate_envelope(
        Path(getattr(arguments, "import")), "challenge15.import-bundle.v1"
    )
    receipt = validate_envelope(
        Path(arguments.receipt), "challenge15.transfer-receipt.v1"
    )
    _verify_production_bindings(
        exported, policy_path=arguments.policy, source_path=arguments.source_manifest,
        runtime_path=arguments.runtime_attestations,
    )
    verify_export_bundle(Path(arguments.export).parent, exported)
    if (
        receipt["export_bundle_sha256"] != payload_sha256(exported)
        or receipt["import_bundle_sha256"] != payload_sha256(imported)
        or imported["member_manifest"] != exported["member_manifest"]
    ):
        raise ValueError("transfer receipt lineage mismatch")
    return 0


def _transfer_receipt_command(arguments: argparse.Namespace) -> int:
    exported = validate_envelope(Path(arguments.export), "challenge15.export-bundle.v1")
    imported = validate_envelope(
        Path(getattr(arguments, "import")), "challenge15.import-bundle.v1"
    )
    if imported["member_manifest"] != exported["member_manifest"]:
        raise ValueError("transfer member manifest mismatch")
    payload = {
        **{
            field: exported[field]
            for field in (
                "policy_sha256", "source_manifest_sha256", "runtime_attestations",
                "base_configuration_sha256", "particles",
            )
        },
        "direction": f"{arguments.source_controller}->{arguments.destination_controller}",
        "export_bundle_sha256": payload_sha256(exported),
        "import_bundle_sha256": payload_sha256(imported),
        "source_controller": arguments.source_controller,
        "destination_controller": arguments.destination_controller,
        "source_identity": f"{arguments.source_controller}:{exported['source_root']}",
        "destination_identity": (
            f"{arguments.destination_controller}:{imported['destination_root']}"
        ),
        "partial_path": str(Path(imported["destination_root"]).with_name(".complete")),
        "final_path": imported["destination_root"],
        "bytes": sum(Path(arguments.export).parent.joinpath("members", name).stat().st_size
                     for name in exported["member_manifest"]),
        "attempt_intent_sha256": payload_sha256(
            {"export": payload_sha256(exported), "import": payload_sha256(imported)}
        ),
        "correlation_id": payload_sha256(imported),
        "remote_claim_sha256": payload_sha256(exported),
        "started_at_utc": exported["created_at_utc"],
        "verified_at_utc": imported["verified_at_utc"],
    }
    _publish_content_addressed(
        arguments.output_dir, "challenge15.transfer-receipt.v1", payload
    )
    return 0


def _bootstrap_export_command(arguments: argparse.Namespace) -> int:
    runtime = validate_envelope(
        Path(arguments.allowed_runtime), "challenge15.allowed-runtime.v1"
    )
    payload = {
        "source_controller": arguments.source_controller,
        "destination_controller": arguments.destination_controller,
        "role": runtime["role"],
        "allowed_runtime_sha256": payload_sha256(runtime),
        "source_manifest_sha256": _envelope_payload_digest(arguments.source_manifest),
        "policy_sha256": _envelope_payload_digest(arguments.policy),
        "source_deployment_receipt_sha256": _envelope_payload_digest(
            arguments.source_deployment_receipt
        ),
        "destination_deployment_receipt_sha256": _envelope_payload_digest(
            arguments.destination_deployment_receipt
        ),
        "export_bundle_sha256": payload_sha256(runtime),
        "import_bundle_sha256": "0" * 64,
        "verified_at_utc": _now_utc(),
    }
    _publish_content_addressed(
        arguments.output_dir,
        "challenge15.attestation-bootstrap-transfer.v1",
        payload,
    )
    return 0


def _bootstrap_import_command(arguments: argparse.Namespace) -> int:
    exported = validate_envelope(Path(arguments.bundle))
    if (
        exported["allowed_runtime_sha256"] != arguments.allowed_runtime_sha256
        or exported["source_manifest_sha256"]
        != _envelope_payload_digest(arguments.source_manifest)
        or exported["policy_sha256"] != _envelope_payload_digest(arguments.policy)
        or exported["source_deployment_receipt_sha256"]
        != _envelope_payload_digest(arguments.source_deployment_receipt)
        or exported["destination_deployment_receipt_sha256"]
        != _envelope_payload_digest(arguments.destination_deployment_receipt)
    ):
        raise ValueError("bootstrap allowed-runtime mismatch")
    payload = {
        **exported,
        "import_bundle_sha256": payload_sha256(
            {"bundle": payload_sha256(exported), "destination": arguments.output_dir}
        ),
        "verified_at_utc": _now_utc(),
    }
    _publish_content_addressed(
        arguments.output_dir,
        "challenge15.attestation-bootstrap-transfer.v1",
        payload,
    )
    return 0


def _reduce_cross_size_command(arguments: argparse.Namespace) -> int:
    terminals = [
        validate_envelope(
            Path(getattr(arguments, f"n{n}_terminal_selection")),
            "challenge15.terminal-selection.v1",
        )
        for n in (6, 7, 8)
    ]
    if [item["particles"] for item in terminals] != [6, 7, 8] or not all(
        item["production_accepted"] for item in terminals
    ):
        raise ValueError("cross-size reduction requires accepted N=6,7,8 terminals")
    terminal_paths = [
        Path(getattr(arguments, f"n{n}_terminal_selection")).absolute()
        for n in (6, 7, 8)
    ]
    reductions = [
        validate_envelope(
            path.parent / "members" / f"{terminal['selected_reduction_sha256']}.json",
            "challenge15.size-result.v1",
        )
        for path, terminal in zip(terminal_paths, terminals, strict=True)
    ]
    runtime_paths = [
        getattr(arguments, f"runtime_attestation_set_n{n}") for n in (6, 7, 8)
    ]
    runtimes = [
        validate_envelope(Path(path), "challenge15.runtime-attestation-set.v1")
        for path in runtime_paths
    ]
    n8_finalization = validate_envelope(
        Path(arguments.n8_provisional_finalization),
        "challenge15.reduction-finalization.v1",
    )
    n8_reduction = validate_envelope(
        Path(arguments.n8_reduction), "challenge15.size-result.v1"
    )
    n8_import = validate_envelope(
        Path(arguments.n8_import_receipt), "challenge15.import-bundle.v1"
    )
    n8_transfer = validate_envelope(
        Path(arguments.n8_transfer_receipt), "challenge15.transfer-receipt.v1"
    )
    if (
        n8_finalization["selected_reduction_sha256"] != payload_sha256(n8_reduction)
        or n8_transfer["import_bundle_sha256"] != payload_sha256(n8_import)
    ):
        raise ValueError("cross-size N=8 finalization/transport lineage mismatch")
    payload = {
        "policy_sha256": _envelope_payload_digest(arguments.policy),
        "source_manifest_sha256": _envelope_payload_digest(arguments.source_manifest),
        "n6_sha256": payload_sha256(reductions[0]),
        "n7_sha256": payload_sha256(reductions[1]),
        "n8_sha256": payload_sha256(reductions[2]),
        "n6_terminal_selection_sha256": payload_sha256(terminals[0]),
        "n7_terminal_selection_sha256": payload_sha256(terminals[1]),
        "n8_terminal_selection_sha256": payload_sha256(terminals[2]),
        "particles": [6, 7, 8],
        "base_configuration_sha256_by_size": {
            str(n): terminal["base_configuration_sha256"]
            for n, terminal in zip((6, 7, 8), terminals, strict=True)
        },
        "runtime_attestation_sets_by_size": {
            str(n): payload_sha256(runtime)
            for n, runtime in zip((6, 7, 8), runtimes, strict=True)
        },
        "lineage": {
            f"N{n}": {
                "size_result_sha256": payload_sha256(reduction),
                "terminal_selection_sha256": payload_sha256(terminal),
            }
            for n, reduction, terminal in zip(
                (6, 7, 8), reductions, terminals, strict=True
            )
        },
        "production_accepted_n6_n8": True,
        "claim": {
            "statement": "finite-size lowest-L=2 sector gaps for N=6-8",
            "basis": (
                "accepted terminal reductions with bound N=8 finalization, "
                f"import {payload_sha256(n8_import)}, and transfer "
                f"{payload_sha256(n8_transfer)}"
            ),
        },
    }
    _publish_content_addressed(
        arguments.output_dir, "challenge15.cross-size-manifest.v1", payload
    )
    return 0


def _common_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config")


def _write_create_only(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_json(document) + b"\n"
    try:
        descriptor = path.open("xb")
    except FileExistsError as exc:
        raise ValueError(f"create-only output already exists: {path}") from exc
    with descriptor:
        descriptor.write(data)
        descriptor.flush()
        import os

        os.fsync(descriptor.fileno())


def _policy_command(arguments: argparse.Namespace) -> int:
    _write_create_only(
        Path(arguments.output),
        envelope_for("challenge15.production-policy.v1", production_policy()),
    )
    return 0


def _source_manifest_command(arguments: argparse.Namespace) -> int:
    root = Path(arguments.root).resolve(strict=True)
    if arguments.require_clean:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if status:
            raise ValueError("source manifest requires a clean tracked tree")
    policy_payload = validate_envelope(
        Path(arguments.policy), "challenge15.production-policy.v1"
    )
    includes = (
        "src/**/*.py",
        "production/**/*.py",
        "production/**/*.json",
        "production/**/*.sh",
        "production/**/*.sbatch",
        "production/runtime/**/*.txt",
        "production/runtime/**/*.in",
        "tests/**/*.py",
        "pyproject.toml",
        "uv.lock",
    )
    members: dict[str, str] = {}
    for pattern in includes:
        for path in root.glob(pattern):
            if path.is_file() and not path.is_symlink():
                members[path.relative_to(root).as_posix()] = _file_sha256(path)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    payload = {
        "git_revision": revision,
        "members": dict(sorted(members.items())),
        "policy_sha256": payload_sha256(policy_payload),
    }
    _write_create_only(
        Path(arguments.output),
        envelope_for("challenge15.source-manifest.v1", payload),
    )
    return 0


def _production_orchestrate_size_command(arguments: argparse.Namespace) -> int:
    from challenge15.orchestrator import RANK_LADDER, SEEDS, validate_backup_uri

    ranks = tuple(_integer_list(arguments.rank_ladder, "rank-ladder"))
    seeds = tuple(_integer_list(arguments.seeds, "seeds"))
    if ranks != RANK_LADDER or seeds != SEEDS:
        raise ValueError("production rank ladder and seeds are immutable")
    prerequisite = arguments.prerequisite_terminal_selection
    if arguments.particles == 6 and prerequisite is not None:
        raise ValueError("N=6 must omit prerequisite terminal selection")
    if arguments.particles in {7, 8} and prerequisite is None:
        raise ValueError("N=7/N=8 require prerequisite terminal selection")
    if arguments.particles not in {6, 7, 8}:
        raise ValueError("production particles must be N=6,7,8")
    validate_backup_uri(arguments.state_backup_uri)
    if arguments.cpu_controller == "wuzh02":
        from challenge15.cluster_profile import load_profile

        profile = load_profile(arguments.cpu_profile)
        profile.require_role("oracle")
        profile.require_role("exact")
        profile.require_role("reducer")
        if profile.controller != "wuzh02" or not profile.contains_result(
            arguments.cpu_results_root
        ):
            raise ValueError("WUZH02 audited profile/root mismatch")
        deployment = validate_envelope(
            Path(arguments.cpu_deployment_receipt),
            "challenge15.deployment-receipt.v1",
        )
        runtime = validate_envelope(
            Path(arguments.cpu_runtime_set_remote),
            "challenge15.runtime-attestation-set.v1",
        )
        if deployment["profile_sha256"] != profile.sha256:
            raise ValueError("WUZH02 deployment attestation is not profile-bound")
        for role in ("oracle", "exact", "reducer"):
            entry = runtime["roles"][role]
            if (
                entry["controller"] != "wuzh02"
                or entry["deployment_receipt_sha256"] != payload_sha256(deployment)
            ):
                raise ValueError("WUZH02 runtime capacity/attestation mismatch")
    root = Path(__file__).resolve().parents[2]
    script = root / "production" / "orchestrate" / "submit_size.py"
    fields = (
        "particles",
        "rank_ladder",
        "seeds",
        "base_config",
        "policy",
        "source_manifest",
        "runtime_set_local",
        "runtime_set_local_sha256",
        "cpu_runtime_set_remote",
        "cpu_runtime_set_receipt",
        "gpu_runtime_set_remote",
        "gpu_runtime_set_receipt",
        "cpu_controller",
        "gpu_controller",
        "cpu_profile",
        "gpu_profile",
        "cpu_deployment_receipt",
        "gpu_deployment_receipt",
        "cpu_results_root",
        "gpu_results_root",
        "state_root_base",
        "state_backup_uri",
    )
    command = [sys.executable, str(script)]
    for field in fields:
        command.extend(
            [f"--{field.replace('_', '-')}", str(getattr(arguments, field))]
        )
    if prerequisite:
        command.extend(["--prerequisite-terminal-selection", prerequisite])
    if arguments.state_mirror_root:
        command.extend(["--state-mirror-root", arguments.state_mirror_root])
    command.append("--create-only")
    return subprocess.run(command, cwd=root, check=True).returncode


def _production_vmc_config(path: Path | str) -> ProductionVMCConfig:
    payload = validate_production_vmc_config_envelope(Path(path))
    schedule_version = payload.pop("schedule_version")
    if schedule_version != "fixed-v1":
        raise ValueError("production VMC schedule version mismatch")
    return ProductionVMCConfig(**payload)


def _production_vmc_train_command(arguments: argparse.Namespace) -> int:
    extension = RankExtension(
        **validate_envelope(
            Path(arguments.extension), "challenge15.rank-extension.v1"
        )
    )
    owner = SeedOwner(
        **validate_envelope(Path(arguments.owner), "challenge15.seed-owner.v1")
    )
    train_rank(
        _production_vmc_config(arguments.base_config),
        extension,
        Path(arguments.destination),
        owner,
    )
    return 0


def _coordinate_shard_command(arguments: argparse.Namespace) -> int:
    path = Path(arguments.generation)
    config = _production_vmc_config(arguments.base_config)
    payload = validate_envelope(path, "challenge15.training-generation.v1")
    root = path.parents[2]
    if (
        path.name != "manifest.json"
        or path.parent.parent.name != "generations"
        or path.parent.name != payload_sha256(payload)
    ):
        raise ValueError("generation path is not canonical")
    owner_paths = tuple((root / "owner").glob("*.json"))
    if len(owner_paths) != 1:
        raise ValueError("generation root must contain one owner")
    owner = validate_envelope(owner_paths[0], "challenge15.seed-owner.v1")
    extension_dir = root / "extensions"
    if not extension_dir.is_dir() or extension_dir.is_symlink():
        raise ValueError("generation extension namespace is invalid")
    extension_sha256s = tuple(
        item.stem
        for item in sorted(extension_dir.iterdir())
        if item.is_file() and not item.is_symlink() and item.suffix == ".json"
    )
    generation = discover_unique_terminal_generation(
        root,
        extension_sha256s,
        expected_policy_sha256=str(payload["policy_sha256"]),
        expected_source_manifest_sha256=str(payload["source_manifest_sha256"]),
        expected_runtime_attestations=payload["runtime_attestations"],
        expected_base_configuration_sha256=config.base_configuration_sha256,
        expected_particles=int(payload["particles"]),
        expected_seed=int(payload["seed"]),
        expected_experiment_id=str(owner["experiment_id"]),
        expected_canonical_root=root,
    )
    if generation.path.absolute() != path.absolute():
        raise ValueError("generation path is not the unique terminal generation")
    evaluate_coordinates(
        config,
        generation,
        Path(arguments.destination),
    )
    return 0


def _load_response_oracle(path: Path):
    """Verify and restore one CLI oracle cache without solving."""

    artifact = verify_artifact(path)
    configuration = artifact.get("configuration")
    if not isinstance(configuration, Mapping):
        raise ValueError("response oracle configuration is missing")
    particles = configuration.get("particles")
    if isinstance(particles, bool) or not isinstance(particles, int):
        raise ValueError("response oracle particle number is invalid")
    return _load_cached_oracle(path, SphereSpec(particles), execution_fingerprint())


def _load_response_generation(
    path: Path,
    *,
    rank: int,
    seed: int,
    parameter_sha256: str,
) -> Mapping[str, Any]:
    """Verify a production generation and bind it to the selected checkpoint."""

    generation = validate_envelope(path, "challenge15.training-generation.v1")
    if (
        generation["rank"] != rank
        or generation["seed"] != seed
        or generation["parameter_sha256"] != parameter_sha256
    ):
        raise ValueError("generation identity does not match checkpoint selection")
    return generation


def _response_families(spec: SphereSpec):
    families = {
        helicity: build_response_family(spec, helicity)
        for helicity in ("+", "-")
    }
    validate_response_families(spec, families)
    return families


def _response_spectrum_from_oracle(oracle):
    families = _response_families(oracle.spec)
    return exact_chiral_spectrum(oracle, families)


def _response_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _verify_response_artifact(path: Path) -> dict[str, Any]:
    payload = verify_artifact(path)
    validate_envelope(
        envelope_for("challenge15.chiral-response.v1", payload),
        "challenge15.chiral-response.v1",
    )
    return payload


def _response_payload(
    spectrum,
    *,
    configuration: Mapping[str, Any],
    initial_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    fixture = (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "fixtures"
        / "chiral_covariant_pair_large_q.json"
    )
    fixture_digest = _file_sha256(fixture)
    channels: dict[str, Any] = {}
    for helicity in ("+", "-"):
        channel = spectrum.channels[helicity]
        channels[helicity] = {
            "component_weights": {
                str(component): float(channel.component_weights[component])
                for component in range(-2, 3)
            },
            "poles": [
                {
                    "energy": float(pole.energy),
                    "degeneracy": int(pole.degeneracy),
                    "member_indices": [int(value) for value in pole.member_indices],
                    "member_weights": [
                        float(value) for value in pole.member_weights
                    ],
                    "weight": float(pole.weight),
                    "fraction": (
                        float(pole.weight / channel.total_weight)
                        if channel.total_weight > 0.0
                        else 0.0
                    ),
                }
                for pole in channel.poles
            ],
            "spectral_weight": float(channel.total_weight),
            "direct_sum_weight": float(channel.direct_sum_weight),
            "recovered_fraction": float(channel.recovered_fraction),
            "lowest_pole_weight": float(channel.lowest_weight),
            "pole_fraction": float(channel.pole_fraction),
            "zero_source": all(
                channel.component_weights[component] == 0.0
                for component in range(-2, 3)
            ),
        }

    exact_initial = initial_metadata is None
    tensor_residual = float(spectrum.tensor_commutator_residual_max)
    adjoint_residual = float(spectrum.adjoint_residual)
    eigenpair_residual = float(spectrum.eigenpair_residual_max)
    sum_rules_passed = all(
        channel["recovered_fraction"] >= 0.99
        for channel in channels.values()
    )
    diagnostics_passed = (
        tensor_residual <= 1e-10
        and adjoint_residual <= 1e-12
        and eigenpair_residual <= 1e-10
        and float(spectrum.reversal_residual_max) <= 1e-12
    )
    chirality_resolved = (
        spectrum.contrast is not None
        and float(spectrum.delta_weight) > 0.0
        and sum_rules_passed
        and diagnostics_passed
    )
    if not diagnostics_passed or not sum_rules_passed or not chirality_resolved:
        raise RuntimeError("chiral response gates failed")

    oracle_digest = configuration["oracle_sha256"]
    generation_digest = configuration["generation_sha256"]
    checkpoint_digest = configuration["checkpoint_sha256"]
    parameter_digest = configuration["parameter_sha256"]
    checkpoint_record_digest = configuration["checkpoint_record_sha256"]
    payload = {
        "particles": int(spectrum.particles),
        "orientation": int(spectrum.orientation),
        "initial_state": {
            "kind": "exact-ground" if exact_initial else "nqs-determinant",
            "coefficient_sha256": (
                None
                if exact_initial
                else str(spectrum.initial_coefficient_sha256)
            ),
            "estimator_scope": (
                "exact-ED-initial-and-final-states"
                if exact_initial
                else "exact-finite-Hilbert-contraction-with-exact-ED-L2-finals"
            ),
            "rank": None if exact_initial else initial_metadata["rank"],
            "seed": None if exact_initial else initial_metadata["seed"],
            "checkpoint_sha256": checkpoint_digest,
            "checkpoint_record_sha256": checkpoint_record_digest,
            "generation_sha256": generation_digest,
            "parameter_sha256": parameter_digest,
            "determinant_block": (
                None if exact_initial else initial_metadata["determinant_block"]
            ),
            "exact_ground_overlap": (
                None if exact_initial else initial_metadata["exact_ground_overlap"]
            ),
        },
        "configuration": dict(configuration),
        "physical_conventions": {
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
        },
        "source": {
            "fixture_sha256": fixture_digest,
            "fixture_schema": "challenge15.chiral-covariant-pair-fixture.v1",
            "normalization": "raw-LHYR-planar-Coulomb-E_C-resolution-eq-5.6",
            "minus_direction": "m_plus_2_to_m",
            "plus_direction": "m_to_m_plus_2",
            "plus_definition": "O_{+,M}=(-1)^M(O_{-,-M})†",
            "expected_channel": "-",
            "expected_local_frame_helicity": -2,
            "global_tensor_components": ["-2", "-1", "0", "1", "2"],
        },
        "channels": channels,
        "delta_weight": float(spectrum.delta_weight),
        "contrast": (
            None if spectrum.contrast is None else float(spectrum.contrast)
        ),
        "contrast_floor": float(spectrum.contrast_floor),
        "diagnostics": {
            "tensor_commutator": {
                "residual_max": tensor_residual,
                "tolerance": 1e-10,
                "passed": tensor_residual <= 1e-10,
            },
            "adjoint": {
                "residual": adjoint_residual,
                "tolerance": 1e-12,
                "passed": adjoint_residual <= 1e-12,
            },
            "eigenpair": {
                "residual_max": eigenpair_residual,
                "tolerance": 1e-10,
                "passed": eigenpair_residual <= 1e-10,
            },
            "degeneracy": {
                "absolute_tolerance_E_C": 1e-10,
                "relative_tolerance": 1e-9,
            },
            "sum_rules_passed": sum_rules_passed,
            "chirality_resolved": chirality_resolved,
        },
        "input_sha256": {
            "fixture": fixture_digest,
            "oracle_artifact": (
                None
                if configuration["mode"] == "exact-size"
                else oracle_digest
            ),
            "oracle_cache": (
                oracle_digest
                if configuration["mode"] == "exact-size"
                else None
            ),
            "nqs_generation": generation_digest,
            "nqs_checkpoint": checkpoint_digest,
            "parameter": parameter_digest,
            "configuration": payload_sha256(configuration),
        },
        "input_identities": {
            "oracle": {
                "identity_role": "oracle",
                "artifact_schema": (
                    "challenge15.oracle-cache.v2"
                    if configuration["mode"] == "exact-size"
                    else "challenge15.cli-oracle.v1"
                ),
                "sha256": oracle_digest,
            },
            "generation": (
                None
                if generation_digest is None
                else {
                    "identity_role": "generation",
                    "artifact_schema": "challenge15.training-generation.v1",
                    "sha256": generation_digest,
                }
            ),
            "checkpoint": (
                None
                if checkpoint_digest is None
                else {
                    "identity_role": "checkpoint",
                    "artifact_schema": "challenge15.train-checkpoint.v1",
                    "sha256": checkpoint_digest,
                }
            ),
            "checkpoint_record": (
                None
                if checkpoint_record_digest is None
                else {
                    "identity_role": "checkpoint_record",
                    "artifact_schema": "challenge15.train-checkpoint-record.v1",
                    "sha256": checkpoint_record_digest,
                }
            ),
            "parameter": (
                None
                if parameter_digest is None
                else {
                    "identity_role": "parameter",
                    "artifact_schema": "challenge15.parameter-blob.v1",
                    "sha256": parameter_digest,
                }
            ),
            "configuration": {
                "identity_role": "configuration",
                "artifact_schema": "challenge15.response-configuration.v1",
                "sha256": payload_sha256(configuration),
            },
        },
        "execution_fingerprint": execution_fingerprint(),
    }
    validate_envelope(
        envelope_for("challenge15.chiral-response.v1", payload),
        "challenge15.chiral-response.v1",
    )
    return payload


def _response_command(arguments: argparse.Namespace) -> int:
    triplet = (arguments.checkpoint, arguments.rank, arguments.seed)
    if any(value is not None for value in triplet) and not all(
        value is not None for value in triplet
    ):
        raise ValueError("--checkpoint, --rank, and --seed must be supplied together")
    if arguments.particles is not None and not 2 <= arguments.particles <= 8:
        raise ValueError("exact chiral response requires 2 <= particles <= 8")
    if arguments.particles is not None and arguments.checkpoint is not None:
        raise ValueError("checkpoint response requires --oracle")
    if (arguments.generation is None) != (arguments.checkpoint is None):
        raise ValueError("--generation is required exactly with --checkpoint")

    oracle_path = None if arguments.oracle is None else Path(arguments.oracle)
    generation_path = (
        None if arguments.generation is None else Path(arguments.generation)
    )
    checkpoint_path = (
        None if arguments.checkpoint is None else Path(arguments.checkpoint)
    )
    initial_metadata: dict[str, Any] | None = None
    if oracle_path is None:
        spectrum = exact_chiral_spectrum_for_size(arguments.particles)
        oracle_digest = spectrum.oracle_cache_sha256
        if oracle_digest is None:
            raise ValueError("exact response did not bind solved oracle cache bytes")
        configuration = {
            "mode": "exact-size",
            "particles": arguments.particles,
            "oracle_sha256": oracle_digest,
            "generation_sha256": None,
            "checkpoint_sha256": None,
            "checkpoint_record_sha256": None,
            "parameter_sha256": None,
            "rank": None,
            "seed": None,
            "determinant_block": None,
        }
    else:
        oracle = _load_response_oracle(oracle_path)
        oracle_digest = _file_sha256(oracle_path)
        if checkpoint_path is None:
            spectrum = _response_spectrum_from_oracle(oracle)
            configuration = {
                "mode": "oracle-reuse",
                "particles": oracle.spec.particles,
                "oracle_sha256": oracle_digest,
                "generation_sha256": None,
                "checkpoint_sha256": None,
                "checkpoint_record_sha256": None,
                "parameter_sha256": None,
                "rank": None,
                "seed": None,
                "determinant_block": None,
            }
        else:
            assert generation_path is not None
            checkpoint = _validate_checkpoint(checkpoint_path)
            checkpoint_configuration = checkpoint["configuration"]
            if int(checkpoint_configuration["particles"]) != oracle.spec.particles:
                raise ValueError("checkpoint and oracle particle numbers differ")
            record = _checkpoint_record(
                checkpoint, rank=arguments.rank, seed=arguments.seed
            )
            parameter_digest = record["parameter_sha256"]
            _load_response_generation(
                generation_path,
                rank=arguments.rank,
                seed=arguments.seed,
                parameter_sha256=parameter_digest,
            )
            parameters = _restore_parameters(
                oracle.spec, checkpoint_configuration, record
            )
            initial = nqs_determinant_state(
                oracle.spec,
                parameters,
                oracle,
                target_l=0,
                determinant_block=256,
            )
            families = _response_families(oracle.spec)
            spectrum = nqs_mixed_chiral_spectrum(oracle, families, initial)
            generation_digest = _file_sha256(generation_path)
            checkpoint_digest = _file_sha256(checkpoint_path)
            checkpoint_record_digest = payload_sha256(record)
            overlap = float(
                abs(
                    np.vdot(
                        oracle.exact_sector(0).isometry
                        @ oracle.exact_sector(0).eigenvectors[:, 0],
                        initial.coefficients,
                    )
                )
                ** 2
            )
            configuration = {
                "mode": "mixed",
                "particles": oracle.spec.particles,
                "oracle_sha256": oracle_digest,
                "generation_sha256": generation_digest,
                "checkpoint_sha256": checkpoint_digest,
                "checkpoint_record_sha256": checkpoint_record_digest,
                "parameter_sha256": parameter_digest,
                "rank": arguments.rank,
                "seed": arguments.seed,
                "determinant_block": 256,
            }
            initial_metadata = {
                "rank": arguments.rank,
                "seed": arguments.seed,
                "determinant_block": 256,
                "exact_ground_overlap": overlap,
            }

    payload = _response_payload(
        spectrum,
        configuration=configuration,
        initial_metadata=initial_metadata,
    )
    destination = Path(arguments.output) / "response.json"
    publish_json_atomic(
        destination,
        payload,
        validator=_verify_response_artifact,
    )
    return 0


def _oracle_command(arguments: argparse.Namespace) -> int:
    command_start = time.perf_counter()
    config, input_provenance = _configuration(
        arguments, ("particles",), required=("particles",)
    )
    if int(config["particles"]) >= 6 or arguments.output_dir is not None:
        required = {
            "policy": arguments.policy,
            "source-manifest": arguments.source_manifest,
            "runtime-attestations": arguments.runtime_attestations,
            "output-dir": arguments.output_dir,
        }
        missing = [name for name, value in required.items() if not value]
        if missing or arguments.create_only is not True:
            raise ValueError(
                "production oracle requires "
                + ", ".join(f"--{name}" for name in (*missing, "create-only"))
            )
        arguments.output = arguments.output_dir
    if not arguments.output:
        raise ValueError("oracle requires --output")
    spec = SphereSpec(int(config["particles"]))
    solve_start = time.perf_counter()
    result = (
        solve_required_target_sectors_sparse(spec)
        if spec.particles >= 6
        else solve_target_sectors(spec)
    )
    solve_elapsed = time.perf_counter() - solve_start
    payload = {
        "schema": "challenge15.cli-oracle.v1",
        "command": "oracle",
        "configuration": config,
        "configuration_sha256": configuration_sha256(config),
        "code_provenance": _code_provenance(),
        "runtime_provenance": _runtime_provenance(),
        "input_provenance": input_provenance,
        "execution_fingerprint": execution_fingerprint(),
        "oracle": result.to_payload(),
        "oracle_cache": oracle_cache_payload(result),
        "telemetry": _telemetry(
            command_start,
            stages=[
                {
                    "stage": (
                        "sparse_required_target_solve"
                        if spec.particles >= 6
                        else "dense_small_n_oracle"
                    ),
                    "elapsed_wall_seconds": solve_elapsed,
                }
            ],
            determinant_blocks=0,
        ),
    }
    destination = Path(arguments.output) / "result.json"
    publish_json_atomic(destination, payload)
    verify_artifact(destination)
    return 0


def _train_command(arguments: argparse.Namespace) -> int:
    command_start = time.perf_counter()
    training_stages: list[dict[str, Any]] = []
    config, input_provenance = _configuration(
        arguments, ("particles", "ranks", "seeds", "steps"), required=("particles",)
    )
    config.setdefault("ranks", [1])
    config.setdefault("seeds", [0])
    config.setdefault("steps", 1)
    config["ranks"] = _integer_list(config["ranks"], "ranks")
    config["seeds"] = _integer_list(config["seeds"], "seeds")
    _validate_training_configuration(config)
    if any(rank <= 0 for rank in config["ranks"]):
        raise ValueError("ranks must be positive")
    if any(
        upper != 2 * lower
        for lower, upper in zip(config["ranks"], config["ranks"][1:])
    ):
        raise ValueError("ranks must form a nested doubling sequence")
    output = Path(arguments.output)
    checkpoint_path = output / "checkpoint.json"
    digest = configuration_sha256(config)
    current_fingerprint = execution_fingerprint()
    if arguments.resume:
        if not checkpoint_path.exists():
            raise ValueError("resume requested but checkpoint does not exist")
        checkpoint = load_compatible_checkpoint(checkpoint_path, config)
    else:
        if checkpoint_path.exists():
            raise ValueError("checkpoint exists; pass --resume or choose a new output")
        checkpoint = {
            "schema": "challenge15.train-checkpoint.v1",
            "configuration": config,
            "configuration_sha256": digest,
            "completed": [],
            "records": [],
            "code_provenance": _code_provenance(),
            "runtime_provenance": _runtime_provenance(),
            "input_provenance": input_provenance,
            "execution_fingerprint": current_fingerprint,
            "telemetry": _telemetry(command_start, stages=[], determinant_blocks=0),
        }
    training_stages = list(checkpoint.get("telemetry", {}).get("stages", []))
    completed = {
        tuple(identity) for identity in _checkpoint_coverage(checkpoint)["present"]
    }
    spec = SphereSpec(int(config["particles"]))
    for seed in config["seeds"]:
        for rank_index, rank in enumerate(config["ranks"]):
            identity = (int(rank), int(seed))
            if identity in completed:
                continue
            train_config = _train_config(config, rank=int(rank), seed=int(seed))
            nested_from_rank = None
            parent_parameter_sha256 = None
            rank_growth_prng = None
            initial_parameter_sha256 = None
            initial_parameters = None
            initial_optimizer_state = None
            if rank_index:
                lower_rank = int(config["ranks"][rank_index - 1])
                parent = _checkpoint_record(
                    checkpoint, rank=lower_rank, seed=int(seed)
                )
                lower_parameters = _restore_parameters(spec, config, parent)
                lower_optimizer_state = _restore_optimizer_state(
                    config, parent, lower_parameters
                )
                growth_key = jax.random.fold_in(
                    jax.random.key(int(seed)), int(rank)
                )
                initial_parameters = embed_rank(
                    lower_parameters,
                    lower_rank,
                    int(rank),
                    key=growth_key,
                )
                initial_optimizer_state = embed_adam_state(
                    lower_optimizer_state,
                    initial_parameters,
                    old_rank=lower_rank,
                    new_rank=int(rank),
                )
                nested_from_rank = lower_rank
                parent_parameter_sha256 = parent["parameter_sha256"]
                rank_growth_prng = [
                    int(value)
                    for value in np.asarray(jax.random.key_data(growth_key)).reshape(-1)
                ]
                initial_parameter_sha256 = hashlib.sha256(
                    serialization.to_bytes(initial_parameters)
                ).hexdigest()
            stage_start = time.perf_counter()
            result = train_joint_sectors(
                spec,
                train_config,
                initial_parameters=initial_parameters,
                initial_optimizer_state=initial_optimizer_state,
            )
            training_stages.append(
                {
                    "stage": "joint_sector_training",
                    "rank": int(rank),
                    "seed": int(seed),
                    "elapsed_wall_seconds": time.perf_counter() - stage_start,
                }
            )
            parameter_bytes = serialization.to_bytes(result.shared_parameters)
            optimizer_bytes = serialization.to_bytes(result.optimizer_state)
            checkpoint["records"].append(
                {
                    "rank": int(rank),
                    "seed": int(seed),
                    "shared_parameter_tree": True,
                    "execution_fingerprint": current_fingerprint,
                    "nested_from_rank": nested_from_rank,
                    "parent_parameter_sha256": parent_parameter_sha256,
                    "rank_growth_prng": rank_growth_prng,
                    "initial_parameter_sha256": initial_parameter_sha256,
                    "parameter_sha256": result.parameter_sha256,
                    "parameters_base64": base64.b64encode(parameter_bytes).decode("ascii"),
                    "optimizer_state_sha256": hashlib.sha256(
                        optimizer_bytes
                    ).hexdigest(),
                    "optimizer_state_base64": base64.b64encode(
                        optimizer_bytes
                    ).decode("ascii"),
                    "steps": [asdict(step) for step in result.steps],
                    "prng_provenance": [
                        [name, list(key)] for name, key in result.prng_provenance
                    ],
                }
            )
            checkpoint["completed"].append([int(rank), int(seed)])
            checkpoint["telemetry"] = _telemetry(
                command_start,
                stages=training_stages,
                determinant_blocks=0,
            )
            completed.add(identity)
            publish_json_atomic(checkpoint_path, checkpoint)
            _validate_checkpoint(
                checkpoint_path,
                expected_configuration=config,
                allowed_schemas={"challenge15.train-checkpoint.v1"},
            )
    final = dict(checkpoint)
    final["schema"] = "challenge15.train-result.v1"
    final["production_accepted"] = False
    final["acceptance_status"] = "pending exact evaluation and all production gates"
    result_path = output / "result.json"
    publish_json_atomic(result_path, final)
    verify_artifact(result_path)
    return 0


def _evaluate_command(arguments: argparse.Namespace) -> int:
    command_start = time.perf_counter()
    evaluation_stages: list[dict[str, Any]] = []
    config, input_provenance = _configuration(
        arguments,
        ("checkpoint", "oracle", "prerequisite"),
        required=("checkpoint",),
    )
    checkpoint_path = Path(config["checkpoint"])
    checkpoint = _validate_checkpoint(checkpoint_path)
    coverage = _checkpoint_coverage(checkpoint)
    train_config = checkpoint["configuration"]
    spec = SphereSpec(int(train_config["particles"]))
    current_fingerprint = execution_fingerprint()
    prerequisite = _validate_size_prerequisite(
        spec.particles,
        Path(config["prerequisite"]) if config.get("prerequisite") else None,
        current_fingerprint,
    )
    if config.get("oracle"):
        oracle_start = time.perf_counter()
        oracle_path = Path(config["oracle"])
        oracle = _load_cached_oracle(
            oracle_path, spec, current_fingerprint
        )
        input_provenance["oracle_sha256"] = _file_sha256(oracle_path)
        oracle_cache_telemetry = {"hits": len(checkpoint["records"]), "misses": 1}
        evaluation_stages.append(
            {
                "stage": "load_verified_oracle_cache",
                "elapsed_wall_seconds": time.perf_counter() - oracle_start,
            }
        )
    else:
        if spec.particles >= 6:
            raise ValueError("N=6-8 evaluation requires a verified cached oracle")
        oracle = solve_target_sectors(spec)
        oracle_cache_telemetry = {"hits": 0, "misses": 1}
    evaluations = []
    quadrature_before = quadrature_cache_info()
    for record in checkpoint["records"]:
        record_start = time.perf_counter()
        parameters = _restore_parameters(spec, train_config, record)
        metrics = evaluate_exact_nqs(spec, parameters, oracle)
        gap = metrics.energy_l2 - metrics.energy_l0
        energy_limit = min(1e-4, 0.01 * oracle.gap)
        gates = {
            "finite_positive_norms": bool(
                np.isfinite(metrics.norm_l0)
                and np.isfinite(metrics.norm_l2)
                and metrics.norm_l0 > 0
                and metrics.norm_l2 > 0
            ),
            "energy_l0": abs(metrics.energy_l0 - oracle.energy_l0) <= energy_limit,
            "energy_l2": abs(metrics.energy_l2 - oracle.energy_l2) <= energy_limit,
            "gap": abs(gap - oracle.gap) <= 0.01 * oracle.gap,
            "overlap_l0": metrics.overlap_l0 >= 0.99,
            "overlap_l2": metrics.overlap_l2 >= 0.99,
            "quadrature_l0": (
                metrics.quadrature_coefficient_relative_change_l0 <= 1e-11
                and metrics.quadrature_energy_relative_change_l0 <= 1e-11
            ),
            "quadrature_l2": (
                metrics.quadrature_coefficient_relative_change_l2 <= 1e-11
                and metrics.quadrature_energy_relative_change_l2 <= 1e-11
            ),
            "exact_l0": metrics.l2_residual_l0 <= 1e-10,
            "exact_l2": metrics.l2_residual_l2 <= 1e-10,
        }
        evaluations.append(
            {
                "rank": record["rank"],
                "seed": record["seed"],
                "execution_fingerprint": current_fingerprint,
                "parameter_sha256": record["parameter_sha256"],
                "optimizer_state_sha256": record["optimizer_state_sha256"],
                "energy_l0": metrics.energy_l0,
                "energy_l2": metrics.energy_l2,
                "norm_l0": metrics.norm_l0,
                "norm_l2": metrics.norm_l2,
                "finite_size_l2_gap": gap,
                "h_lll_variance_l0": metrics.h_variance_l0,
                "h_lll_variance_l2": metrics.h_variance_l2,
                "bare_potential_sampling_variance": None,
                "overlap_l0": metrics.overlap_l0,
                "overlap_l2": metrics.overlap_l2,
                "l2_residual_l0": metrics.l2_residual_l0,
                "l2_residual_l2": metrics.l2_residual_l2,
                "quadrature_coefficient_change_l0": (
                    metrics.quadrature_coefficient_relative_change_l0
                ),
                "quadrature_coefficient_change_l2": (
                    metrics.quadrature_coefficient_relative_change_l2
                ),
                "quadrature_energy_change_l0": (
                    metrics.quadrature_energy_relative_change_l0
                ),
                "quadrature_energy_change_l2": (
                    metrics.quadrature_energy_relative_change_l2
                ),
                "projected_span_rank_l0": metrics.projected_span_rank_l0,
                "projected_span_rank_l2": metrics.projected_span_rank_l2,
                "determinant_blocks": (
                    (oracle.m_zero_dimension + 255) // 256
                )
                * int(record["rank"])
                * sum(
                    order[1]
                    for order in (
                        *metrics.quadrature_orders_l0,
                        *metrics.quadrature_orders_l2,
                    )
                ),
                "gates": gates,
                "accepted": all(gates.values()),
            }
        )
        evaluation_stages.append(
            {
                "stage": "exact_record_evaluation",
                "rank": int(record["rank"]),
                "seed": int(record["seed"]),
                "elapsed_wall_seconds": time.perf_counter() - record_start,
            }
        )
    if coverage["passed"]:
        rank_records = _rank_records(evaluations, train_config["ranks"])
        convergence = analyze_rank_convergence(rank_records)
        paired_seed_gate = _paired_seed_transition_gate(
            evaluations, train_config["ranks"]
        )
        if convergence.accepted and not paired_seed_gate["passed"]:
            convergence = RankConvergence(
                False,
                convergence.transitions,
                "one or more paired seeds fail rank-transition gates",
            )
    else:
        convergence = RankConvergence(
            False, (), "checkpoint exact coverage is incomplete"
        )
        paired_seed_gate = {
            "passed": False,
            "per_seed": [],
            "reason": "checkpoint exact coverage is incomplete",
        }
    seed_count = len(set(train_config["seeds"]))
    quadrature_after = quadrature_cache_info()
    passing_seeds = len(
        {
            item["seed"]
            for item in evaluations
            if item["rank"] == train_config["ranks"][-1] and item["accepted"]
        }
    )
    production_accepted = _production_acceptance(
        coverage,
        convergence,
        configured_seed_count=seed_count,
        passing_seed_count=passing_seeds,
    )
    seed_gate = {
        "required": REQUIRED_SEED_COUNT,
        "passing_required": MINIMUM_PASSING_SEEDS,
        "provided": seed_count,
        "passing": passing_seeds,
        "passed": (
            seed_count >= REQUIRED_SEED_COUNT
            and passing_seeds >= MINIMUM_PASSING_SEEDS
        ),
    }
    payload = {
        "schema": "challenge15.exact-evaluation.v1",
        "command": "evaluate",
        "configuration": config,
        "configuration_sha256": configuration_sha256(config),
        "particles": spec.particles,
        "code_provenance": _code_provenance(),
        "runtime_provenance": _runtime_provenance(),
        "input_provenance": {
            **input_provenance,
            "checkpoint_sha256": _file_sha256(checkpoint_path),
        },
        "execution_fingerprint": current_fingerprint,
        "size_prerequisite": prerequisite,
        "oracle_summary": {
            "energy_l0": oracle.energy_l0,
            "energy_l2": oracle.energy_l2,
            "finite_size_l2_gap": oracle.gap,
        },
        "cache_telemetry": {
            "oracle": oracle_cache_telemetry,
            "rotated_carrier_quadrature": {
                "hits": quadrature_after["hits"] - quadrature_before["hits"],
                "misses": quadrature_after["misses"]
                - quadrature_before["misses"],
                "entries": quadrature_after["entries"],
            },
        },
        "telemetry": _telemetry(
            command_start,
            stages=evaluation_stages,
            determinant_blocks=sum(
                item["determinant_blocks"] for item in evaluations
            ),
        ),
        "stochastic_vmc_reporting": {
            "applicable": False,
            "elapsed_wall_seconds": None,
            "peak_rss_mib": None,
            "effective_sample_size": None,
            "split_rhat": None,
            "confidence_interval_95": None,
            "within_seed_variation": None,
            "between_seed_variation": None,
            "ess_per_device_hour": None,
        },
        "evaluations": evaluations,
        "rank_convergence": asdict(convergence),
        "paired_seed_transition_gate": paired_seed_gate,
        "seed_gate": seed_gate,
        "coverage_gate": coverage,
        "acceptance_thresholds": _acceptance_thresholds(),
        "production_accepted": production_accepted,
        "pending_work": (
            []
            if production_accepted
            else _failed_gates(
                {
                    "coverage_gate": coverage,
                    "rank_convergence": asdict(convergence),
                    "paired_seed_transition_gate": paired_seed_gate,
                    "seed_gate": seed_gate,
                    "evaluations": evaluations,
                }
            )
        ),
        "claim": (
            "finite-size lowest-L=2 sector gap"
            if production_accepted
            else "pending; no system or rank accepted"
        ),
        "chiral_graviton_claim": False,
    }
    destination = Path(arguments.output) / "evaluation.json"
    publish_json_atomic(destination, payload)
    verify_artifact(destination)
    return 0


def _load_cached_oracle(
    path: Path,
    spec: SphereSpec,
    current_fingerprint: Mapping[str, Any],
):
    artifact = verify_artifact(path)
    if artifact.get("schema") != "challenge15.cli-oracle.v1":
        raise ValueError("oracle input is not a verified CLI oracle artifact")
    if artifact.get("configuration_sha256") != configuration_sha256(
        artifact.get("configuration", {})
    ):
        raise ValueError("oracle configuration SHA256 mismatch")
    validate_fingerprint(
        artifact.get("execution_fingerprint"),
        current=dict(current_fingerprint),
        context="oracle",
    )
    if int(artifact["configuration"]["particles"]) != spec.particles:
        raise ValueError("oracle particle number does not match checkpoint")
    result = oracle_from_cache_payload(artifact.get("oracle_cache", {}))
    cached_summary = artifact["oracle_cache"]["summary"]
    published_summary = artifact.get("oracle", {})
    cached_without_hashes = {
        key: value for key, value in cached_summary.items() if key != "array_hashes"
    }
    published_without_hashes = {
        key: value for key, value in published_summary.items() if key != "array_hashes"
    }
    published_hashes = published_summary.get("array_hashes", {})
    if (
        result.spec != spec
        or cached_without_hashes != published_without_hashes
        or any(
            published_hashes.get(name) != digest
            for name, digest in cached_summary["array_hashes"].items()
        )
    ):
        raise ValueError("oracle cache and summary are inconsistent")
    return result


def _verify_command(arguments: argparse.Namespace) -> int:
    config, _ = _configuration(arguments, ("artifact",), required=("artifact",))
    path = Path(config["artifact"])
    payload = verify_artifact(path)
    if payload.get("schema") in {
        "challenge15.train-checkpoint.v1",
        "challenge15.train-result.v1",
    }:
        payload = _validate_checkpoint(path)
    elif payload.get("schema") == "challenge15.exact-evaluation.v1":
        _validate_evaluation_artifact(path)
    elif payload.get("schema") == "challenge15.cli-oracle.v1":
        config = payload.get("configuration", {})
        _load_cached_oracle(
            path,
            SphereSpec(int(config["particles"])),
            execution_fingerprint(),
        )
    elif set(payload) == set(
        SCHEMA_FIELDS["challenge15.chiral-response.v1"]
    ):
        validate_envelope(
            envelope_for("challenge15.chiral-response.v1", payload),
            "challenge15.chiral-response.v1",
        )
    elif payload.get("schema") == "challenge15.cross-size-manifest.v1":
        _validate_cross_size_manifest(payload)
    for relative, expected in payload.get("manifest", {}).items():
        candidate = path.parent / relative
        if _file_sha256(candidate) != expected:
            raise ValueError(f"manifest SHA256 mismatch: {relative}")
    return 0


def _validate_size_prerequisite(
    particles: int,
    prerequisite_path: Path | None,
    current_fingerprint: Mapping[str, Any],
) -> dict[str, Any] | None:
    if particles <= 6:
        if prerequisite_path is not None:
            raise ValueError("N=6 must not declare a size prerequisite")
        return None
    required_particles = particles - 1
    if prerequisite_path is None:
        raise ValueError(f"N={particles} requires an accepted N={required_particles} prerequisite")
    prerequisite, accepted = _validate_evaluation_artifact(prerequisite_path)
    if prerequisite.get("particles") != required_particles:
        raise ValueError("size prerequisite particle number is invalid")
    if not accepted or prerequisite.get("production_accepted") is not True:
        raise ValueError("size prerequisite is not production accepted")
    if prerequisite.get("execution_fingerprint") != current_fingerprint:
        raise ValueError("size prerequisite execution fingerprint is stale")
    return {
        "particles": required_particles,
        "path": str(prerequisite_path.resolve()),
        "sha256": _file_sha256(prerequisite_path),
        "execution_fingerprint_digest": current_fingerprint["digest"],
        "production_accepted": True,
    }


def _manifest_command(arguments: argparse.Namespace) -> int:
    current = execution_fingerprint()
    links: dict[str, Any] = {}
    evaluations: dict[int, Mapping[str, Any]] = {}
    pending: list[int] = []
    for particles in (6, 7, 8):
        value = getattr(arguments, f"n{particles}")
        if value is None:
            pending.append(particles)
            continue
        path = Path(value)
        evaluation, accepted = _validate_evaluation_artifact(path)
        if evaluation.get("particles") != particles:
            raise ValueError(f"N={particles} manifest link has the wrong particle number")
        if not accepted or evaluation.get("production_accepted") is not True:
            raise ValueError(f"N={particles} manifest link is not production accepted")
        if evaluation.get("execution_fingerprint") != current:
            raise ValueError(f"N={particles} manifest link has a stale fingerprint")
        links[f"N={particles}"] = {
            "particles": particles,
            "path": str(path.resolve()),
            "sha256": _file_sha256(path),
            "execution_fingerprint_digest": current["digest"],
        }
        evaluations[particles] = evaluation
    _validate_manifest_lineage(links, evaluations)
    accepted_all = not pending and len(links) == 3
    payload = {
        "schema": "challenge15.cross-size-manifest.v1",
        "command": "manifest",
        "execution_fingerprint": current,
        "links": links,
        "pending_sizes": pending,
        "production_accepted_n6_n8": accepted_all,
        "claim": (
            "Passing all linked gates would establish the finite-size lowest-L=2 "
            "sector gaps for N=6-8; this is not a chiral-graviton claim."
            if accepted_all
            else "N=6-8 production acceptance is pending; no aggregate claim is permitted."
        ),
        "chiral_graviton_claim": False,
    }
    destination = Path(arguments.output) / "manifest.json"
    publish_json_atomic(destination, payload)
    verify_artifact(destination)
    return 0


def _validate_cross_size_manifest(payload: Mapping[str, Any]) -> None:
    current = execution_fingerprint()
    validate_fingerprint(
        payload.get("execution_fingerprint"),
        current=current,
        context="cross-size manifest",
    )
    links = payload.get("links", {})
    if not isinstance(links, dict):
        raise ValueError("cross-size manifest links must be an object")
    linked_sizes: set[int] = set()
    evaluations: dict[int, Mapping[str, Any]] = {}
    for name, link in links.items():
        particles = int(name.removeprefix("N="))
        if particles not in (6, 7, 8):
            raise ValueError("cross-size manifest contains an unexpected size")
        path = Path(link["path"])
        if _file_sha256(path) != link.get("sha256"):
            raise ValueError("cross-size manifest linked artifact SHA256 mismatch")
        evaluation, accepted = _validate_evaluation_artifact(path)
        if (
            link.get("particles") != particles
            or evaluation.get("particles") != particles
            or not accepted
            or evaluation.get("production_accepted") is not True
        ):
            raise ValueError("cross-size manifest linked evaluation is invalid")
        if link.get("execution_fingerprint_digest") != current["digest"]:
            raise ValueError("cross-size manifest linked fingerprint is stale")
        linked_sizes.add(particles)
        evaluations[particles] = evaluation
    _validate_manifest_lineage(links, evaluations)
    expected_pending = sorted({6, 7, 8} - linked_sizes)
    if payload.get("pending_sizes") != expected_pending:
        raise ValueError("cross-size manifest pending sizes are inconsistent")
    expected_accepted = not expected_pending
    if payload.get("production_accepted_n6_n8") is not expected_accepted:
        raise ValueError("cross-size manifest aggregate acceptance is inconsistent")


def _validate_manifest_lineage(
    links: Mapping[str, Mapping[str, Any]],
    evaluations: Mapping[int, Mapping[str, Any]],
) -> None:
    """Require each linked accepted child to name the exact linked parent."""

    if 6 in evaluations and evaluations[6].get("size_prerequisite") is not None:
        raise ValueError("cross-size manifest N=6 lineage is invalid")
    for child in (7, 8):
        if child not in evaluations:
            continue
        parent = child - 1
        parent_link = links.get(f"N={parent}")
        if parent_link is None or parent not in evaluations:
            raise ValueError(
                f"cross-size manifest N={child} lineage omits linked N={parent}"
            )
        prerequisite = evaluations[child].get("size_prerequisite")
        if (
            not isinstance(prerequisite, Mapping)
            or prerequisite.get("particles") != parent
            or prerequisite.get("sha256") != parent_link.get("sha256")
        ):
            raise ValueError(
                f"cross-size manifest N={child} lineage does not match linked N={parent}"
            )


def _report_command(arguments: argparse.Namespace) -> int:
    config, input_provenance = _configuration(
        arguments, ("evaluation",), required=("evaluation",)
    )
    evaluation_path = Path(config["evaluation"])
    evaluation, accepted = _validate_evaluation_artifact(evaluation_path)
    statement = (
        "Passing all gates would establish the finite-size lowest-L=2 sector gap. "
        "It is not called a chiral graviton until the separate metric-response "
        "acceptance plan is completed."
        if accepted
        else "Production acceptance remains pending; no rank/system is accepted."
    )
    payload = {
        "schema": "challenge15.core-report.v1",
        "command": "report",
        "configuration": config,
        "configuration_sha256": configuration_sha256(config),
        "code_provenance": _code_provenance(),
        "runtime_provenance": _runtime_provenance(),
        "input_provenance": {
            **input_provenance,
            "evaluation_sha256": _file_sha256(evaluation_path),
        },
        "execution_fingerprint": execution_fingerprint(),
        "production_accepted": accepted,
        "statement": statement,
        "finite_size_l2_gap": evaluation.get("oracle_summary", {}).get(
            "finite_size_l2_gap"
        ),
        "telemetry": evaluation.get("telemetry"),
        "cache_telemetry": evaluation.get("cache_telemetry"),
        "stochastic_vmc_reporting": evaluation.get("stochastic_vmc_reporting"),
        "chiral_graviton_claim": False,
        "failed_gates": _failed_gates(evaluation),
    }
    destination = Path(arguments.output) / "report.json"
    publish_json_atomic(destination, payload)
    verify_artifact(destination)
    return 0


def _configuration(
    arguments: argparse.Namespace,
    names: Sequence[str],
    *,
    required: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    config: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    if arguments.config:
        path = Path(arguments.config)
        config = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("configuration JSON must contain an object")
        provenance["configuration_path_sha256"] = _file_sha256(path)
    else:
        provenance["configuration_path_sha256"] = None
    for name in names:
        value = getattr(arguments, name, None)
        if value is not None:
            config[name] = value
    for name in required:
        if name not in config:
            raise ValueError(f"missing required configuration field: {name}")
    return config, provenance


def _integer_list(value: Any, name: str) -> list[int]:
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError(f"{name} must be a JSON list or comma-separated string")
    try:
        result = [int(item) for item in values]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain integers") from exc
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _validate_training_configuration(configuration: Mapping[str, Any]) -> None:
    required = {"particles", "ranks", "seeds", "steps"}
    missing = required - set(configuration)
    if missing:
        raise ValueError(
            "checkpoint training configuration is missing "
            + ", ".join(sorted(missing))
        )
    forbidden_acceptance_overrides = {
        "energy_tolerance",
        "gap_relative_tolerance",
        "overlap_tolerance",
        "required_rank_doublings",
        "required_seeds",
        "minimum_passing_seeds",
    }
    supplied_overrides = forbidden_acceptance_overrides & set(configuration)
    if supplied_overrides:
        raise ValueError(
            "acceptance constants are immutable; remove "
            + ", ".join(sorted(supplied_overrides))
        )
    ranks = _integer_list(configuration["ranks"], "ranks")
    seeds = _integer_list(configuration["seeds"], "seeds")
    if len(ranks) != len(set(ranks)) or any(rank <= 0 for rank in ranks):
        raise ValueError("checkpoint ranks must be unique and positive")
    if any(
        upper != 2 * lower for lower, upper in zip(ranks, ranks[1:])
    ):
        raise ValueError("checkpoint ranks must form a nested doubling sequence")
    if len(seeds) != len(set(seeds)):
        raise ValueError("checkpoint seeds must be unique")
    _train_config(configuration, rank=ranks[0], seed=seeds[0])


def _expected_record_identities(
    configuration: Mapping[str, Any],
) -> set[tuple[int, int]]:
    ranks = _integer_list(configuration.get("ranks"), "ranks")
    seeds = _integer_list(configuration.get("seeds"), "seeds")
    return {(rank, seed) for rank in ranks for seed in seeds}


def _record_identities(
    records: Any, expected: set[tuple[int, int]]
) -> set[tuple[int, int]]:
    if not isinstance(records, list):
        raise ValueError("checkpoint records must be a list")
    identities: set[tuple[int, int]] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("checkpoint records must be objects")
        rank = record.get("rank")
        seed = record.get("seed")
        if (
            isinstance(rank, bool)
            or not isinstance(rank, int)
            or isinstance(seed, bool)
            or not isinstance(seed, int)
        ):
            raise ValueError("checkpoint record rank and seed must be integers")
        identity = (rank, seed)
        if identity not in expected:
            raise ValueError(f"unexpected checkpoint record: {identity}")
        if identity in identities:
            raise ValueError(f"duplicate checkpoint record: {identity}")
        identities.add(identity)
    return identities


def _completed_identities(completed: Any) -> set[tuple[int, int]]:
    if not isinstance(completed, list):
        raise ValueError("checkpoint completed records must be a list")
    identities: set[tuple[int, int]] = set()
    for item in completed:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in item)
        ):
            raise ValueError("checkpoint completed records are malformed")
        identity = (item[0], item[1])
        if identity in identities:
            raise ValueError("checkpoint completed records contain duplicates")
        identities.add(identity)
    return identities


def _record_by_identity(records, identity):
    for record in records:
        if (record["rank"], record["seed"]) == identity:
            return record
    raise ValueError(f"checkpoint lineage record is missing: {identity}")


def _train_config(config: Mapping[str, Any], *, rank: int, seed: int) -> TrainConfig:
    names = set(TrainConfig.__dataclass_fields__) - {"rank", "seed"}
    kwargs = {name: config[name] for name in names if name in config}
    return TrainConfig(rank=rank, seed=seed, **kwargs)


def _restore_parameters(spec: SphereSpec, config: Mapping[str, Any], record):
    train_config = _train_config(
        config, rank=int(record["rank"]), seed=int(record["seed"])
    )
    model = ProjectedPfaffianNQS(
        ModelConfig(
            rank=train_config.rank,
            hidden_width=train_config.hidden_width,
            depth=train_config.depth,
            token_width=train_config.token_width,
            fourier_order=train_config.fourier_order,
            block_size=train_config.projection_block_size,
        )
    )
    point = np.ones((spec.particles, 2), dtype=np.complex128)
    point /= np.linalg.norm(point, axis=1, keepdims=True)
    template = model.init(jax.random.key(train_config.seed), spec, point, target_l=0)[
        "params"
    ]
    encoded = base64.b64decode(record["parameters_base64"], validate=True)
    if hashlib.sha256(encoded).hexdigest() != record["parameter_sha256"]:
        raise ValueError("checkpoint parameter SHA256 mismatch")
    return serialization.from_bytes(template, encoded)


def _restore_optimizer_state(config, record, parameters):
    train_config = _train_config(
        config, rank=int(record["rank"]), seed=int(record["seed"])
    )
    template = optax.adam(train_config.learning_rate).init(parameters)
    encoded = base64.b64decode(record["optimizer_state_base64"], validate=True)
    if hashlib.sha256(encoded).hexdigest() != record["optimizer_state_sha256"]:
        raise ValueError("checkpoint optimizer-state SHA256 mismatch")
    return serialization.from_bytes(template, encoded)


def _checkpoint_record(checkpoint, *, rank: int, seed: int):
    matches = [
        record
        for record in checkpoint["records"]
        if record["rank"] == rank and record["seed"] == seed
    ]
    if len(matches) != 1:
        raise ValueError("nested resume is missing its unique parent checkpoint")
    return matches[0]


def _rank_records(evaluations: list[dict[str, Any]], ranks: list[int]):
    by_rank = {
        rank: sorted(
            (item for item in evaluations if item["rank"] == rank),
            key=lambda item: item["seed"],
        )
        for rank in ranks
    }
    seed_sets = [
        {item["seed"] for item in by_rank[rank]}
        for rank in ranks
    ]
    if not seed_sets or any(seeds != seed_sets[0] for seeds in seed_sets[1:]):
        raise ValueError("exact adjacent ranks require identical paired seed sets")
    records = []
    for rank in ranks:
        current = by_rank[rank]
        if not current:
            raise ValueError(f"rank {rank} has no evaluations")
        records.append(
            RankEvaluation(
                rank=rank,
                energy_l0=float(np.mean([item["energy_l0"] for item in current])),
                energy_l2=float(np.mean([item["energy_l2"] for item in current])),
                sigma_diff_l0=0.0,
                sigma_diff_l2=0.0,
                sigma_diff_gap=0.0,
                overlap_l0=float(np.mean([item["overlap_l0"] for item in current])),
                overlap_l2=float(np.mean([item["overlap_l2"] for item in current])),
            )
        )
    return records


def _paired_seed_transition_gate(
    evaluations: list[dict[str, Any]], ranks: list[int]
) -> dict[str, Any]:
    seeds = sorted({item["seed"] for item in evaluations})
    per_seed = []
    for seed in seeds:
        records = [
            RankEvaluation(
                rank=rank,
                energy_l0=float(
                    next(
                        item["energy_l0"]
                        for item in evaluations
                        if item["rank"] == rank and item["seed"] == seed
                    )
                ),
                energy_l2=float(
                    next(
                        item["energy_l2"]
                        for item in evaluations
                        if item["rank"] == rank and item["seed"] == seed
                    )
                ),
                sigma_diff_l0=0.0,
                sigma_diff_l2=0.0,
                sigma_diff_gap=0.0,
                overlap_l0=float(
                    next(
                        item["overlap_l0"]
                        for item in evaluations
                        if item["rank"] == rank and item["seed"] == seed
                    )
                ),
                overlap_l2=float(
                    next(
                        item["overlap_l2"]
                        for item in evaluations
                        if item["rank"] == rank and item["seed"] == seed
                    )
                ),
            )
            for rank in ranks
        ]
        result = analyze_rank_convergence(records)
        per_seed.append(
            {
                "seed": seed,
                "accepted": result.accepted,
                "transitions": [asdict(item) for item in result.transitions],
                "reason": result.reason,
            }
        )
    return {
        "passed": bool(per_seed) and all(item["accepted"] for item in per_seed),
        "per_seed": per_seed,
        "reason": (
            "every paired seed passes both rank transitions"
            if per_seed and all(item["accepted"] for item in per_seed)
            else "one or more paired seeds fail rank-transition gates"
        ),
    }


def _failed_gates(evaluation: Mapping[str, Any]) -> list[str]:
    failed = []
    if not evaluation.get("coverage_gate", {}).get("passed", False):
        failed.append("checkpoint_coverage")
    if not evaluation.get("rank_convergence", {}).get("accepted", False):
        failed.append("rank_convergence")
    if not evaluation.get("paired_seed_transition_gate", {}).get("passed", False):
        failed.append("paired_seed_transition_gate")
    if not evaluation.get("seed_gate", {}).get("passed", False):
        failed.append("seed_gate")
    for item in evaluation.get("evaluations", []):
        for name, passed in item.get("gates", {}).items():
            if not passed:
                failed.append(f"rank={item['rank']},seed={item['seed']}:{name}")
    return failed


def _acceptance_thresholds() -> dict[str, Any]:
    return {
        "energy_absolute_ec": 1e-4,
        "energy_fraction_of_gap": 0.01,
        "gap_relative": 0.01,
        "overlap_minimum": 0.99,
        "quadrature_relative": 1e-11,
        "l2_residual": 1e-10,
        "rank_energy_ec": ENERGY_TOLERANCE_EC,
        "rank_gap_relative": GAP_RELATIVE_TOLERANCE,
        "rank_overlap_change": OVERLAP_CHANGE_TOLERANCE,
        "required_rank_doublings": REQUIRED_RANK_DOUBLINGS,
        "required_seed_count": REQUIRED_SEED_COUNT,
        "minimum_passing_seeds": MINIMUM_PASSING_SEEDS,
    }


def _evaluation_record_gates(
    item: Mapping[str, Any], oracle: Mapping[str, Any]
) -> dict[str, bool]:
    gap_reference = float(oracle["finite_size_l2_gap"])
    energy_limit = min(1e-4, 0.01 * gap_reference)
    return {
        "finite_positive_norms": bool(
            np.isfinite(item["norm_l0"])
            and np.isfinite(item["norm_l2"])
            and item["norm_l0"] > 0
            and item["norm_l2"] > 0
        ),
        "energy_l0": abs(item["energy_l0"] - oracle["energy_l0"])
        <= energy_limit,
        "energy_l2": abs(item["energy_l2"] - oracle["energy_l2"])
        <= energy_limit,
        "gap": abs(item["finite_size_l2_gap"] - gap_reference)
        <= 0.01 * gap_reference,
        "overlap_l0": item["overlap_l0"] >= 0.99,
        "overlap_l2": item["overlap_l2"] >= 0.99,
        "quadrature_l0": (
            item["quadrature_coefficient_change_l0"] <= 1e-11
            and item["quadrature_energy_change_l0"] <= 1e-11
        ),
        "quadrature_l2": (
            item["quadrature_coefficient_change_l2"] <= 1e-11
            and item["quadrature_energy_change_l2"] <= 1e-11
        ),
        "exact_l0": item["l2_residual_l0"] <= 1e-10,
        "exact_l2": item["l2_residual_l2"] <= 1e-10,
    }


def _validate_stochastic_reporting(
    reporting: Any,
    *,
    mode: str,
) -> None:
    fields = {
        "applicable",
        "elapsed_wall_seconds",
        "peak_rss_mib",
        "effective_sample_size",
        "split_rhat",
        "confidence_interval_95",
        "within_seed_variation",
        "between_seed_variation",
        "ess_per_device_hour",
    }
    if not isinstance(reporting, dict) or set(reporting) != fields:
        raise ValueError("stochastic reporting fields are incomplete or unexpected")
    if mode == "exact":
        if reporting["applicable"] is not False or any(
            reporting[name] is not None for name in fields - {"applicable"}
        ):
            raise ValueError(
                "exact evaluation forbids stochastic reporting values"
            )
        return
    if mode != "stochastic" or reporting["applicable"] is not True:
        raise ValueError("stochastic reporting mode/applicability is invalid")
    positive_fields = (
        "elapsed_wall_seconds",
        "peak_rss_mib",
        "effective_sample_size",
        "split_rhat",
        "ess_per_device_hour",
    )
    nonnegative_fields = ("within_seed_variation", "between_seed_variation")
    if any(
        not isinstance(reporting[name], (int, float))
        or not np.isfinite(reporting[name])
        or reporting[name] <= 0
        for name in positive_fields
    ):
        raise ValueError("stochastic reporting positive metrics are invalid")
    if any(
        not isinstance(reporting[name], (int, float))
        or not np.isfinite(reporting[name])
        or reporting[name] < 0
        for name in nonnegative_fields
    ):
        raise ValueError("stochastic reporting variation metrics are invalid")
    interval = reporting["confidence_interval_95"]
    if (
        not isinstance(interval, list)
        or len(interval) != 2
        or any(
            not isinstance(value, (int, float)) or not np.isfinite(value)
            for value in interval
        )
        or interval[0] > interval[1]
    ):
        raise ValueError("stochastic reporting confidence interval is invalid")


def _validate_evaluation_artifact(path: Path) -> tuple[dict[str, Any], bool]:
    evaluation = verify_artifact(path)
    return _validate_evaluation_payload(evaluation)


def _validate_evaluation_payload(
    evaluation: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    if evaluation.get("schema") != "challenge15.exact-evaluation.v1":
        raise ValueError("input is not an exact evaluation artifact")
    if evaluation.get("configuration_sha256") != configuration_sha256(
        evaluation.get("configuration", {})
    ):
        raise ValueError("evaluation configuration SHA256 mismatch")
    current = execution_fingerprint()
    validate_fingerprint(
        evaluation.get("execution_fingerprint"),
        current=current,
        context="evaluation",
    )
    if evaluation.get("acceptance_thresholds") != _acceptance_thresholds():
        raise ValueError("evaluation acceptance thresholds are not immutable")
    _validate_stochastic_reporting(
        evaluation.get("stochastic_vmc_reporting"),
        mode="exact",
    )

    checkpoint_path = Path(evaluation["configuration"]["checkpoint"])
    if evaluation.get("input_provenance", {}).get(
        "checkpoint_sha256"
    ) != _file_sha256(checkpoint_path):
        raise ValueError("evaluation checkpoint SHA256 mismatch")
    checkpoint = _validate_checkpoint(checkpoint_path)
    if checkpoint.get("execution_fingerprint") != evaluation.get(
        "execution_fingerprint"
    ):
        raise ValueError("evaluation and checkpoint execution fingerprints differ")
    particles = int(checkpoint["configuration"]["particles"])
    if evaluation.get("particles") != particles:
        raise ValueError("evaluation particle number is inconsistent")
    prerequisite_value = evaluation["configuration"].get("prerequisite")
    prerequisite = _validate_size_prerequisite(
        particles,
        Path(prerequisite_value) if prerequisite_value else None,
        current,
    )
    if evaluation.get("size_prerequisite") != prerequisite:
        raise ValueError("evaluation size prerequisite lineage is inconsistent")
    oracle_value = evaluation["configuration"].get("oracle")
    if oracle_value:
        oracle_path = Path(oracle_value)
        oracle = _load_cached_oracle(
            oracle_path, SphereSpec(particles), current
        )
        if evaluation.get("input_provenance", {}).get(
            "oracle_sha256"
        ) != _file_sha256(oracle_path):
            raise ValueError("evaluation oracle SHA256 mismatch")
        if evaluation.get("oracle_summary") != {
            "energy_l0": oracle.energy_l0,
            "energy_l2": oracle.energy_l2,
            "finite_size_l2_gap": oracle.gap,
        }:
            raise ValueError("evaluation oracle summary is inconsistent")
    elif particles >= 6:
        raise ValueError("production evaluation is missing a cached oracle")
    coverage = _checkpoint_coverage(checkpoint)
    if evaluation.get("coverage_gate") != coverage:
        raise ValueError("evaluation coverage aggregate is inconsistent")

    records = evaluation.get("evaluations")
    if not isinstance(records, list):
        raise ValueError("evaluation records must be a list")
    identities = [(item.get("rank"), item.get("seed")) for item in records]
    checkpoint_identities = [
        (item["rank"], item["seed"]) for item in checkpoint["records"]
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("evaluation contains duplicate rank/seed records")
    if set(identities) != set(checkpoint_identities):
        raise ValueError("evaluation records do not match checkpoint state coverage")
    for item in records:
        parent_record = _record_by_identity(
            checkpoint["records"], (item["rank"], item["seed"])
        )
        if (
            item.get("parameter_sha256") != parent_record["parameter_sha256"]
            or item.get("optimizer_state_sha256")
            != parent_record["optimizer_state_sha256"]
        ):
            raise ValueError("evaluation record state hashes are inconsistent")
        validate_fingerprint(
            item.get("execution_fingerprint"),
            current=current,
            context="evaluation record",
        )
        if item.get("execution_fingerprint") != evaluation.get(
            "execution_fingerprint"
        ):
            raise ValueError("evaluation record execution fingerprint differs")
        recomputed_gates = _evaluation_record_gates(
            item, evaluation["oracle_summary"]
        )
        if item.get("gates") != recomputed_gates:
            raise ValueError("evaluation individual gate aggregate is inconsistent")
        if item.get("accepted") is not all(recomputed_gates.values()):
            raise ValueError("evaluation record acceptance is inconsistent")

    train_config = checkpoint["configuration"]
    if coverage["passed"]:
        convergence = analyze_rank_convergence(
            _rank_records(records, train_config["ranks"])
        )
        paired_seed_gate = _paired_seed_transition_gate(
            records, train_config["ranks"]
        )
        if convergence.accepted and not paired_seed_gate["passed"]:
            convergence = RankConvergence(
                False,
                convergence.transitions,
                "one or more paired seeds fail rank-transition gates",
            )
    else:
        convergence = RankConvergence(
            False, (), "checkpoint exact coverage is incomplete"
        )
        paired_seed_gate = {
            "passed": False,
            "per_seed": [],
            "reason": "checkpoint exact coverage is incomplete",
        }
    if evaluation.get("paired_seed_transition_gate") != paired_seed_gate:
        raise ValueError("evaluation paired-seed transition aggregate is inconsistent")
    recomputed_convergence = json.loads(
        json.dumps(asdict(convergence), allow_nan=False)
    )
    if evaluation.get("rank_convergence") != recomputed_convergence:
        raise ValueError("evaluation rank convergence aggregate is inconsistent")
    seed_count = len(set(train_config["seeds"]))
    passing = len(
        {
            item["seed"]
            for item in records
            if item["rank"] == train_config["ranks"][-1] and item["accepted"]
        }
    )
    expected_seed_gate = {
        "required": REQUIRED_SEED_COUNT,
        "passing_required": MINIMUM_PASSING_SEEDS,
        "provided": seed_count,
        "passing": passing,
        "passed": seed_count >= REQUIRED_SEED_COUNT
        and passing >= MINIMUM_PASSING_SEEDS,
    }
    if evaluation.get("seed_gate") != expected_seed_gate:
        raise ValueError("evaluation seed aggregate is inconsistent")
    accepted = _production_acceptance(
        coverage,
        convergence,
        configured_seed_count=seed_count,
        passing_seed_count=passing,
    )
    if evaluation.get("production_accepted") is not accepted:
        raise ValueError("evaluation production acceptance is inconsistent")
    expected_pending = (
        []
        if accepted
        else _failed_gates(
            {
                "coverage_gate": coverage,
                "rank_convergence": recomputed_convergence,
                "paired_seed_transition_gate": paired_seed_gate,
                "seed_gate": expected_seed_gate,
                "evaluations": records,
            }
        )
    )
    if evaluation.get("pending_work") != expected_pending:
        raise ValueError("evaluation pending work is inconsistent")
    return evaluation, accepted


def _reported_acceptance(evaluation: Mapping[str, Any]) -> bool:
    return _validate_evaluation_payload(dict(evaluation))[1]


def _production_acceptance(
    coverage: Mapping[str, Any],
    convergence: RankConvergence,
    *,
    configured_seed_count: int,
    passing_seed_count: int,
) -> bool:
    return bool(
        coverage.get("passed") is True
        and convergence.accepted
        and configured_seed_count >= REQUIRED_SEED_COUNT
        and passing_seed_count >= MINIMUM_PASSING_SEEDS
    )


def _code_provenance() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    source_hashes = {
        path.relative_to(root).as_posix(): _file_sha256(path)
        for path in sorted((root / "src" / "challenge15").glob("*.py"))
    }
    return {
        "git_revision": completed.stdout.strip(),
        "source_hashes": source_hashes,
    }


def _runtime_provenance() -> dict[str, Any]:
    packages = {}
    for name in ("jax", "flax", "optax", "numpy", "scipy"):
        packages[name] = metadata.version(name)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "jax_enable_x64": bool(jax.config.x64_enabled),
        "jax_backend": jax.default_backend(),
    }


def _telemetry(
    command_start: float,
    *,
    stages: list[dict[str, Any]],
    determinant_blocks: int,
) -> dict[str, Any]:
    maximum_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mib = float(maximum_rss) / 1024.0
    return {
        "elapsed_wall_seconds": time.perf_counter() - command_start,
        "peak_rss_mib": rss_mib,
        "stages": stages,
        "cache_hits": sum(
            int(stage.get("cache_hits", 0)) for stage in stages
        ),
        "cache_misses": sum(
            int(stage.get("cache_misses", 0)) for stage in stages
        ),
        "determinant_blocks": int(determinant_blocks),
        "backend": jax.default_backend(),
        "devices": [str(device) for device in jax.devices()],
    }


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    sys.exit(main())
