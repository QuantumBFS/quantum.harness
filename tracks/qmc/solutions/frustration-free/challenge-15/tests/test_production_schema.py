from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import itertools
import json

import pytest

from challenge15.artifacts import publish_create_only
from challenge15.production_policy import ARTIFACT_SCHEMAS, policy_sha256, production_policy
from challenge15.production_schema import (
    SCHEMA_FIELDS,
    CONTEXT_REQUIRED_SCHEMAS,
    RECEIPT_CONTEXT_VALIDATOR_REGISTRY,
    PRODUCTION_VMC_CONFIG_FIELDS,
    SCIENTIFIC_NESTED_CONTRACTS,
    contract_fixture,
    canonical_json,
    SCHEMA_VALIDATORS,
    RankExtension,
    RankExtensionDecision,
    envelope_for,
    fixed_schedule_envelope,
    payload_sha256,
    validate_envelope,
    validate_canonical_path,
    validate_export_context,
    validate_import_context,
    validate_fixed_schedule_envelope,
    validate_receipt_context,
    validate_rank_extension,
    validate_rank_extension_decision,
)
from challenge15.provenance import execution_fingerprint


SHA = "a" * 64
RUNTIMES = {
    "training": {"qdeshell": "1" * 64},
    "coordinate": {"qdeshell": "2" * 64},
    "oracle": {"lasg02": "3" * 64},
    "exact": {"lasg02": "4" * 64},
    "reducer": {"lasg02": "5" * 64},
}


def _valid_chiral_response_payload():
    component_weights = {
        "-2": 0.2,
        "-1": 0.2,
        "0": 0.2,
        "1": 0.2,
        "2": 0.2,
    }
    payload = {
        "particles": 3,
        "orientation": 1,
        "initial_state": {
            "kind": "exact-ground",
            "coefficient_sha256": None,
            "estimator_scope": "exact-ED-initial-and-final-states",
            "rank": None,
            "seed": None,
            "checkpoint_sha256": None,
            "checkpoint_record_sha256": None,
            "generation_sha256": None,
            "parameter_sha256": None,
            "determinant_block": None,
            "exact_ground_overlap": None,
        },
        "configuration": {
            "mode": "oracle-reuse",
            "particles": 3,
            "oracle_sha256": "b" * 64,
            "generation_sha256": None,
            "checkpoint_sha256": None,
            "checkpoint_record_sha256": None,
            "parameter_sha256": None,
            "rank": None,
            "seed": None,
            "determinant_block": None,
        },
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
            "fixture_sha256": SHA,
            "fixture_schema": "challenge15.chiral-covariant-pair-fixture.v1",
            "normalization": "raw-LHYR-planar-Coulomb-E_C-resolution-eq-5.6",
            "minus_direction": "m_plus_2_to_m",
            "plus_direction": "m_to_m_plus_2",
            "plus_definition": "O_{+,M}=(-1)^M(O_{-,-M})†",
            "expected_channel": "-",
            "expected_local_frame_helicity": -2,
            "global_tensor_components": ["-2", "-1", "0", "1", "2"],
        },
        "channels": {
            "+": {
                "component_weights": dict(component_weights),
                "poles": [
                    {
                        "energy": 1.0,
                        "degeneracy": 1,
                        "member_indices": [0],
                        "member_weights": [0.25],
                        "weight": 0.25,
                        "fraction": 0.25,
                    },
                    {
                        "energy": 2.0,
                        "degeneracy": 1,
                        "member_indices": [1],
                        "member_weights": [0.75],
                        "weight": 0.75,
                        "fraction": 0.75,
                    },
                ],
                "spectral_weight": 1.0,
                "direct_sum_weight": 1.0,
                "recovered_fraction": 1.0,
                "lowest_pole_weight": 0.25,
                "pole_fraction": 0.25,
                "zero_source": False,
            },
            "-": {
                "component_weights": dict(component_weights),
                "poles": [
                    {
                        "energy": 1.0,
                        "degeneracy": 1,
                        "member_indices": [0],
                        "member_weights": [0.75],
                        "weight": 0.75,
                        "fraction": 0.75,
                    },
                    {
                        "energy": 2.0,
                        "degeneracy": 1,
                        "member_indices": [1],
                        "member_weights": [0.25],
                        "weight": 0.25,
                        "fraction": 0.25,
                    },
                ],
                "spectral_weight": 1.0,
                "direct_sum_weight": 1.0,
                "recovered_fraction": 1.0,
                "lowest_pole_weight": 0.75,
                "pole_fraction": 0.75,
                "zero_source": False,
            },
        },
        "delta_weight": 0.5,
        "contrast": 0.5,
        "contrast_floor": 1e-14,
        "diagnostics": {
            "tensor_commutator": {
                "residual_max": 0.0,
                "tolerance": 1e-10,
                "passed": True,
            },
            "adjoint": {
                "residual": 0.0,
                "tolerance": 1e-12,
                "passed": True,
            },
            "eigenpair": {
                "residual_max": 0.0,
                "tolerance": 1e-10,
                "passed": True,
            },
            "degeneracy": {
                "absolute_tolerance_E_C": 1e-10,
                "relative_tolerance": 1e-9,
            },
            "sum_rules_passed": True,
            "chirality_resolved": True,
        },
        "input_sha256": {
            "fixture": SHA,
            "oracle_artifact": "b" * 64,
            "oracle_cache": None,
            "nqs_generation": None,
            "nqs_checkpoint": None,
            "parameter": None,
            "configuration": "c" * 64,
        },
        "input_identities": {
            "oracle": {
                "identity_role": "oracle",
                "artifact_schema": "challenge15.cli-oracle.v1",
                "sha256": "b" * 64,
            },
            "generation": None,
            "checkpoint": None,
            "checkpoint_record": None,
            "parameter": None,
            "configuration": {
                "identity_role": "configuration",
                "artifact_schema": "challenge15.response-configuration.v1",
                "sha256": "c" * 64,
            },
        },
        "execution_fingerprint": execution_fingerprint(),
    }
    payload["input_sha256"]["configuration"] = payload_sha256(
        payload["configuration"]
    )
    payload["input_identities"]["configuration"]["sha256"] = payload[
        "input_sha256"
    ]["configuration"]
    return payload


def _fixture_value(field):
    if field.endswith("_sha256"):
        return SHA
    if field.endswith("_sha256s"):
        return []
    if field.endswith("_at_utc") or field.endswith("_utc"):
        return "2026-07-29T00:00:00Z"
    if field in {"particles"}:
        return 6
    if field in {"seed", "rank", "new_rank", "step", "attempt", "bytes", "candidate_count"}:
        return 1
    if field in {"previous_rank", "current_rank"}:
        return None
    if field == "runtime_attestations":
        return RUNTIMES
    if field == "base_configuration_sha256_by_size":
        return {"6": SHA, "7": SHA, "8": SHA}
    if field == "runtime_attestation_sets_by_size":
        return {"6": SHA, "7": SHA, "8": SHA}
    if field in {"input_sha256s", "output_sha256s", "transition_receipt_sha256s",
                 "completion_marker_sha256s", "attempt_intent_sha256s",
                 "output_promotion_sha256s", "expected_remote_output_sha256s",
                 "import_receipt_sha256s", "transfer_receipt_sha256s",
                 "scheduler_receipt_sha256s"}:
        return []
    if field in {"tasks", "members", "member_manifest", "packages", "wheel_sha256",
                 "decision_metrics", "proposal_state", "diagnostics", "training_metrics",
                 "scheduler_query", "scheduler_test", "cache_counters", "gate_metrics",
                 "primitive_metrics", "metric_equivalence", "sector_diagnostics",
                 "paired_gap_diagnostics", "sampler_configuration", "block_layout",
                 "sphere_spec", "physical_conventions", "coulomb_builder_diagnostics",
                 "sector_summaries", "low_energy_scan", "array_manifest",
                 "source_artifact_sha256", "lineage", "size_summaries",
                 "resource_summary", "statistical_summary", "generation_sha256_by_identity",
                 "exact_sha256_by_identity", "coordinate_sha256_by_identity",
                 "rank_transitions", "seed_gate", "prerequisite", "canonical_path_identities",
                 "parent_sha256s"}:
        return {}
    if field in {"expected_ranks", "expected_seeds", "rank_ladder", "seed_set",
                 "missing_identities", "failed_gates", "coordinate_uncertainty_by_rank",
                 "device_platforms",
                 "attestation_test_members", "expected_output_identities",
                 "create_only_namespace_identities", "expected_seed_set", "particles"}:
        return []
    if field in {"production_accepted", "production_accepted_n6_n8", "x64_enabled"}:
        return False
    if field in {"interpreter", "deployment_root", "destination", "source_root",
                 "destination_root", "partial_path", "final_path", "selected_reduction_path"}:
        return "/approved/value"
    if field == "controller":
        return "lasg02"
    if field in {"source_controller", "destination_controller", "cpu_controller"}:
        return "lasg02"
    if field == "gpu_controller":
        return "qdeshell"
    if field == "role":
        return "oracle"
    if field == "backend":
        return "cpu"
    if field in {
        "nodes", "ntasks", "cpus_per_task", "task_count", "array_concurrency",
        "compile_event_count",
    }:
        return 0
    return "value"


def _valid_schema_fixture(schema):
    if schema == "challenge15.production-policy.v1":
        return production_policy()
    if schema == "challenge15.chiral-response.v1":
        return _valid_chiral_response_payload()
    payload = {field: _fixture_value(field) for field in SCHEMA_FIELDS[schema]}
    if "policy_sha256" in payload:
        payload["policy_sha256"] = policy_sha256()
    if schema == "challenge15.allowed-runtime.v1":
        payload.update(
            role="oracle",
            controller="lasg02",
            backend="cpu",
            attestation_test_members=[
                {"nodeid": "test::node", "test_file_sha256": SHA, "result_sha256": SHA}
            ],
        )
    elif schema == "challenge15.runtime-attestation-set.v1":
        payload["particles"] = 6
        payload["roles"] = {
            role: {
                "controller": "qdeshell" if role in {"training", "coordinate"} else "lasg02",
                "allowed_runtime_sha256": f"{index + 1:x}" * 64,
                "deployment_receipt_sha256": f"{index + 6:x}" * 64,
                "backend": "gpu" if role in {"training", "coordinate"} else "cpu",
            }
            for index, role in enumerate(("training", "coordinate", "oracle", "exact", "reducer"))
        }
    elif schema == "challenge15.rank-extension.v1":
        return root_extension().to_payload()
    elif schema == "challenge15.rank-extension-decision.v1":
        return root_decision().to_payload()
    elif schema == "challenge15.seed-owner.v1":
        payload.update(
            seed=0,
            expected_seed_set=[0, 1, 2, 3, 4],
            runtime_attestations=RUNTIMES,
            policy_sha256=policy_sha256(),
        )
    elif schema == "challenge15.identity-map.v1":
        payload.update(task_count=0, tasks=[], particles=6, runtime_attestations=RUNTIMES,
                       policy_sha256=policy_sha256())
    elif schema == "challenge15.training-attempt.v1":
        payload.update(
            seed=0,
            rank=1,
            started_from_snapshot_sha256=None,
            resource_override=None,
            terminal_snapshot_sha256=SHA,
            status="complete",
        )
    elif schema == "challenge15.training-generation.v1":
        payload.update(
            policy_sha256=policy_sha256(),
            runtime_attestations=RUNTIMES,
            particles=6,
            seed=0,
            rank=1,
            parent_generation_sha256=None,
            parent_parameter_sha256=None,
            parent_optimizer_state_sha256=None,
        )
    elif schema == "challenge15.resource-override.v1":
        payload.update(
            policy_sha256=policy_sha256(),
            runtime_attestations=RUNTIMES,
            particles=6,
            seed=0,
            rank=1,
            walker_microbatch=1,
            carrier_block=1,
            quadrature_block=1,
        )
    elif {"policy_sha256", "runtime_attestations", "particles"} <= set(payload):
        payload.update(policy_sha256=policy_sha256(), runtime_attestations=RUNTIMES, particles=6)
    if schema in {"challenge15.cross-size-manifest.v1", "challenge15.final-report.v1",
                  "challenge15.report-receipt.v1"}:
        payload["particles"] = [6, 7, 8]
    for field in SCIENTIFIC_NESTED_CONTRACTS.get(schema, {}):
        payload[field] = contract_fixture(
            SCIENTIFIC_NESTED_CONTRACTS[schema][field]
        )
    if schema == "challenge15.resource-override.v1":
        payload["metric_equivalence"]["classification"] = "pending"
    if schema == "challenge15.coordinate-evaluation-shard.v1":
        payload["execution_validation"]["metric_equivalence"] = {
            "canonical_completed": True,
            "bitwise_equal": True,
            "classification": "passed",
        }
    if schema == "challenge15.evaluation-receipt.v1":
        payload["compile_events"] = [
            {
                "name": "/jax/core/compile/backend_compile_duration",
                "seconds": 0.0,
            }
        ]
        payload["compile_event_count"] = len(payload["compile_events"])
        payload["compile_seconds"] = sum(
            item["seconds"] for item in payload["compile_events"]
        )
    return payload


SCHEMA_FIXTURE_REGISTRY = {
    schema: (lambda schema=schema: _valid_schema_fixture(schema))
    for schema in ARTIFACT_SCHEMAS
}


def root_decision() -> RankExtensionDecision:
    return RankExtensionDecision(
        policy_sha256=policy_sha256(),
        source_manifest_sha256=SHA,
        runtime_attestations=RUNTIMES,
        base_configuration_sha256=SHA,
        particles=6,
        seed=0,
        current_rank=None,
        new_rank=1,
        prior_expected_ranks_sha256=None,
        prior_reduction_sha256=None,
        prior_finalization_sha256=None,
        prior_import_receipt_sha256=None,
        prior_transfer_receipt_sha256=None,
        decision="train",
        reason="initial",
        decision_metrics={},
    )


def root_extension() -> RankExtension:
    return RankExtension(
        particles=6,
        seed=0,
        experiment_id="experiment",
        base_configuration_sha256=SHA,
        policy_sha256=policy_sha256(),
        source_manifest_sha256=SHA,
        runtime_attestations=RUNTIMES,
        expected_seed_set=(0, 1, 2, 3, 4),
        previous_rank=None,
        new_rank=1,
        parent_generation_sha256=None,
        parent_parameter_sha256=None,
        parent_optimizer_state_sha256=None,
        rank_extension_decision_sha256=payload_sha256(root_decision().to_payload()),
        embedding_algorithm="copy-old-append-zero-gates-v1",
        rank_growth_prng={"algorithm": "threefry2x32", "key_sha256": SHA},
        reason="initial",
        created_by_git_revision="revision",
    )


def test_inventory_has_exact_envelope_fields_for_every_schema():
    for schema in ARTIFACT_SCHEMAS:
        assert schema

    envelope = envelope_for("challenge15.rank-extension.v1", root_extension())
    assert set(envelope) == {"schema", "payload", "payload_sha256"}
    assert "schema" not in envelope["payload"]
    assert validate_envelope(envelope, "challenge15.rank-extension.v1") == envelope["payload"]


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda value: value["payload"].update(extra=True), "fields"),
        (lambda value: value["payload"].update(schema="nested"), "schema"),
        (lambda value: value.update(extra=True), "envelope"),
        (lambda value: value.update(payload_sha256="0" * 64), "SHA256"),
    ],
)
def test_envelopes_fail_closed_on_extra_nested_or_tampered_fields(mutate, match):
    envelope = envelope_for("challenge15.rank-extension.v1", root_extension())
    mutate(envelope)

    with pytest.raises(ValueError, match=match):
        validate_envelope(envelope, "challenge15.rank-extension.v1")


def test_duplicate_json_keys_are_rejected():
    document = (
        '{"schema":"challenge15.rank-extension.v1",'
        '"schema":"challenge15.rank-extension.v1","payload":{},'
        '"payload_sha256":"' + "0" * 64 + '"}'
    )
    with pytest.raises(ValueError, match="duplicate"):
        validate_envelope(document, "challenge15.rank-extension.v1")


def test_root_decision_is_exact_and_extension_requires_its_hash():
    decision = root_decision()
    validate_rank_extension_decision(decision)
    validate_rank_extension(root_extension(), decision)

    with pytest.raises(ValueError, match="rank extension decision"):
        validate_rank_extension(
            replace(root_extension(), rank_extension_decision_sha256=None),
            decision,
        )
    with pytest.raises(ValueError, match="decision SHA256"):
        validate_rank_extension(
            replace(root_extension(), rank_extension_decision_sha256="0" * 64),
            decision,
        )


def test_nonroot_extension_requires_both_parent_state_hashes():
    decision = replace(
        root_decision(),
        current_rank=1,
        new_rank=2,
        prior_expected_ranks_sha256=SHA,
        prior_reduction_sha256=SHA,
        prior_finalization_sha256=SHA,
        prior_import_receipt_sha256=SHA,
        prior_transfer_receipt_sha256=SHA,
        reason="scheduled_initial_ladder",
    )
    extension = replace(
        root_extension(),
        previous_rank=1,
        new_rank=2,
        parent_generation_sha256=SHA,
        parent_parameter_sha256=SHA,
        parent_optimizer_state_sha256=SHA,
        rank_extension_decision_sha256=payload_sha256(decision.to_payload()),
        reason="scheduled_initial_ladder",
    )
    validate_rank_extension(extension, decision)

    with pytest.raises(ValueError, match="parent optimizer"):
        validate_rank_extension(replace(extension, parent_optimizer_state_sha256=None), decision)
    with pytest.raises(ValueError, match="parent parameter"):
        validate_rank_extension(replace(extension, parent_parameter_sha256=None), decision)


def test_runtime_attestations_are_role_and_controller_bound():
    broken = dict(RUNTIMES)
    broken["training"] = {"lasg02": broken["training"]["qdeshell"]}

    with pytest.raises(ValueError, match="controller"):
        validate_rank_extension(replace(root_extension(), runtime_attestations=broken))


def test_every_schema_has_a_specific_recursive_validator():
    assert set(SCHEMA_VALIDATORS) == set(ARTIFACT_SCHEMAS)
    assert CONTEXT_REQUIRED_SCHEMAS == frozenset(RECEIPT_CONTEXT_VALIDATOR_REGISTRY)
    assert all(callable(validator) for validator in SCHEMA_VALIDATORS.values())


def test_canonical_json_rejects_non_string_map_keys_instead_of_stringifying():
    broken = root_extension().to_payload()
    broken["rank_growth_prng"] = {1: "forbidden"}

    with pytest.raises(ValueError, match="string"):
        envelope_for("challenge15.rank-extension.v1", broken)


def test_stored_envelope_bytes_must_be_exact_canonical_form():
    envelope = envelope_for("challenge15.rank-extension.v1", root_extension())
    noncanonical = json.dumps(envelope, indent=2).encode()

    with pytest.raises(ValueError, match="canonical"):
        validate_envelope(noncanonical, "challenge15.rank-extension.v1")


@pytest.mark.parametrize(
    "field",
    ["seed", "particles", "new_rank"],
)
def test_boolean_is_never_accepted_as_an_integer(field):
    broken = replace(root_extension(), **{field: True})
    with pytest.raises(ValueError, match="integer"):
        validate_rank_extension(broken)


def test_canonical_path_must_remain_under_approved_root_without_symlinks(tmp_path):
    approved = tmp_path / "approved"
    approved.mkdir()
    deployment = approved / "deployment"
    deployment.mkdir()
    interpreter = deployment / "bin"
    interpreter.mkdir()
    python = interpreter / "python"
    python.write_bytes(b"python")

    assert validate_canonical_path(python, (approved,)) == python
    with pytest.raises(ValueError, match="approved root"):
        validate_canonical_path(tmp_path / "outside", (approved,))

    linked = approved / "linked"
    linked.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        validate_canonical_path(linked / "python", (approved,))


@pytest.mark.parametrize("schema", ARTIFACT_SCHEMAS)
def test_schema_fixture_registry_has_one_valid_payload_per_schema(schema):
    payload = SCHEMA_FIXTURE_REGISTRY[schema]()
    envelope = envelope_for(schema, payload)
    assert validate_envelope(envelope, schema) == payload


@pytest.mark.parametrize("schema", ARTIFACT_SCHEMAS)
def test_every_schema_rejects_each_missing_or_extra_top_level_field(schema):
    payload = SCHEMA_FIXTURE_REGISTRY[schema]()
    for field in tuple(payload):
        broken = dict(payload)
        broken.pop(field)
        with pytest.raises(ValueError, match="fields"):
            envelope_for(schema, broken)
    with pytest.raises(ValueError, match="fields"):
        envelope_for(schema, {**payload, "unknown_field": None})


def test_chiral_response_valid_minimal_payload_is_registered():
    payload = _valid_chiral_response_payload()
    envelope = envelope_for("challenge15.chiral-response.v1", payload)
    assert validate_envelope(envelope, "challenge15.chiral-response.v1") == payload


@pytest.mark.parametrize(
    "path",
    [
        ("physical_conventions", "spatial_geometry"),
        ("physical_conventions", "spatial_metric_varied"),
        ("physical_conventions", "area_varied"),
        ("physical_conventions", "chord_coulomb_varied"),
        ("physical_conventions", "response_source"),
        ("physical_conventions", "curved_sphere_effective_mass_claim"),
        ("physical_conventions", "landau_level_derivative_used"),
        ("source", "fixture_sha256"),
        ("source", "fixture_schema"),
        ("source", "normalization"),
        ("source", "minus_direction"),
        ("source", "plus_direction"),
        ("source", "plus_definition"),
        ("source", "expected_channel"),
        ("source", "expected_local_frame_helicity"),
        ("source", "global_tensor_components"),
        ("channels", "+"),
        ("channels", "-"),
        ("diagnostics", "tensor_commutator"),
        ("diagnostics", "adjoint"),
        ("diagnostics", "eigenpair"),
        ("diagnostics", "degeneracy"),
        ("diagnostics", "sum_rules_passed"),
        ("diagnostics", "chirality_resolved"),
    ],
)
def test_chiral_response_rejects_deleted_required_nested_fields(path):
    payload = _valid_chiral_response_payload()
    _at_path(payload, path[:-1]).pop(path[-1])
    with pytest.raises(ValueError):
        envelope_for("challenge15.chiral-response.v1", payload)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["physical_conventions"].__setitem__(
            "spatial_metric_varied", True
        ),
        lambda value: value["physical_conventions"].__setitem__(
            "spatial_metric_varied", 0
        ),
        lambda value: value["source"].__setitem__(
            "expected_local_frame_helicity", -2.0
        ),
        lambda value: value["source"].__setitem__("minus_direction", "reverse"),
        lambda value: value["source"].__setitem__(
            "global_tensor_components", ["-2", "-1", "0", "1"]
        ),
        lambda value: value["channels"].__setitem__("other", value["channels"]["+"]),
        lambda value: value["channels"]["+"]["component_weights"].__setitem__("3", 0.0),
        lambda value: value["channels"]["+"]["component_weights"].__setitem__("-2", -1.0),
        lambda value: value["channels"]["+"]["component_weights"].__setitem__("-2", True),
        lambda value: value["channels"]["+"]["component_weights"].__setitem__("-2", 1),
        lambda value: value.__setitem__("particles", 3.0),
        lambda value: value.__setitem__("orientation", True),
        lambda value: value["channels"]["+"].__setitem__("spectral_weight", 1),
        lambda value: value["channels"]["+"].__setitem__("recovered_fraction", 1),
        lambda value: value.__setitem__("delta_weight", 0),
        lambda value: value.__setitem__("contrast", 0),
        lambda value: value["diagnostics"]["adjoint"].__setitem__("residual", 0),
        lambda value: value["channels"]["+"]["component_weights"].__setitem__(
            "-2", float("inf")
        ),
        lambda value: value["channels"]["+"].__setitem__("recovered_fraction", 0.98),
        lambda value: value["channels"]["+"].__setitem__("pole_fraction", 1.1),
        lambda value: value["channels"]["+"].__setitem__("spectral_weight", 1.1),
        lambda value: value.__setitem__("delta_weight", 0.4),
        lambda value: value.__setitem__("contrast", 0.4),
        lambda value: value["diagnostics"]["adjoint"].__setitem__("passed", False),
        lambda value: value["diagnostics"]["tensor_commutator"].__setitem__(
            "tolerance", 1e-9
        ),
        lambda value: value["input_sha256"].__setitem__("fixture", "bad"),
        lambda value: value["input_sha256"].__setitem__(
            "oracle_cache", "d" * 64
        ),
        lambda value: value["initial_state"].__setitem__("kind", "nqs-determinant"),
    ],
)
def test_chiral_response_rejects_convention_numeric_hash_and_derived_tampering(
    mutate,
):
    payload = _valid_chiral_response_payload()
    mutate(payload)
    with pytest.raises((TypeError, ValueError)):
        envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_contrast_is_null_exactly_below_floor():
    payload = _valid_chiral_response_payload()
    for helicity in ("+", "-"):
        _make_chiral_channel_zero(payload, helicity)
    assert envelope_for("challenge15.chiral-response.v1", payload)

    payload["contrast"] = 0.0
    with pytest.raises(ValueError, match="contrast"):
        envelope_for("challenge15.chiral-response.v1", payload)


def _make_chiral_channel_zero(payload, helicity):
    channel = payload["channels"][helicity]
    channel["component_weights"] = {
        component: 0.0 for component in ("-2", "-1", "0", "1", "2")
    }
    channel["poles"] = []
    channel["spectral_weight"] = 0.0
    channel["direct_sum_weight"] = 0.0
    channel["recovered_fraction"] = 1.0
    channel["lowest_pole_weight"] = 0.0
    channel["pole_fraction"] = 0.0
    channel["zero_source"] = True
    minus = payload["channels"]["-"]["lowest_pole_weight"]
    plus = payload["channels"]["+"]["lowest_pole_weight"]
    payload["delta_weight"] = minus - plus
    denominator = minus + plus
    payload["contrast"] = (
        payload["delta_weight"] / denominator
        if denominator >= payload["contrast_floor"]
        else None
    )
    payload["diagnostics"]["chirality_resolved"] = (
        payload["contrast"] is not None and payload["delta_weight"] > 0.0
    )


def test_chiral_response_zero_source_old_shape_rejects_nonzero_spectrum():
    payload = _valid_chiral_response_payload()
    payload["diagnostics"].pop("chirality_resolved")
    for channel in payload["channels"].values():
        channel.pop("poles")
        channel.pop("zero_source")
    channel = payload["channels"]["+"]
    channel["component_weights"] = {
        component: 0.0 for component in ("-2", "-1", "0", "1", "2")
    }
    channel["direct_sum_weight"] = 0.0
    channel["recovered_fraction"] = 1.0
    with pytest.raises(ValueError):
        envelope_for("challenge15.chiral-response.v1", payload)


@pytest.mark.parametrize("helicity", ["+", "-"])
@pytest.mark.parametrize(
    "mutation",
    [
        "spectral",
        "lowest",
        "component-weight",
        "direct-and-spectrum",
        "grouped-pole",
        "grouped-fraction",
        "member-weight",
        "recovered-fraction",
        "pole-fraction",
        "zero-source-diagnostic",
    ],
)
def test_chiral_response_zero_source_rejects_nonzero_or_inconsistent_channel(
    helicity,
    mutation,
):
    payload = _valid_chiral_response_payload()
    _make_chiral_channel_zero(payload, helicity)
    channel = payload["channels"][helicity]
    if mutation == "spectral":
        channel["spectral_weight"] = 5e-13
    elif mutation == "lowest":
        channel["lowest_pole_weight"] = 5e-13
    elif mutation == "component-weight":
        channel["component_weights"]["0"] = 5e-13
    elif mutation == "direct-and-spectrum":
        channel["direct_sum_weight"] = 5e-13
        channel["poles"] = [
            {
                "energy": 1.0,
                "degeneracy": 1,
                "member_indices": [0],
                "member_weights": [5e-13],
                "weight": 5e-13,
                "fraction": 1.0,
            }
        ]
        channel["spectral_weight"] = 5e-13
        channel["lowest_pole_weight"] = 5e-13
        channel["pole_fraction"] = 1.0
        channel["zero_source"] = False
    elif mutation == "grouped-pole":
        channel["poles"] = [
            {
                "energy": 1.0,
                "degeneracy": 1,
                "member_indices": [0],
                "member_weights": [5e-13],
                "weight": 5e-13,
                "fraction": 0.0,
            }
        ]
    elif mutation == "grouped-fraction":
        channel["poles"] = [
            {
                "energy": 1.0,
                "degeneracy": 1,
                "member_indices": [0],
                "member_weights": [0.0],
                "weight": 0.0,
                "fraction": 5e-13,
            }
        ]
    elif mutation == "member-weight":
        channel["poles"] = [
            {
                "energy": 1.0,
                "degeneracy": 1,
                "member_indices": [0],
                "member_weights": [5e-13],
                "weight": 0.0,
                "fraction": 0.0,
            }
        ]
    elif mutation == "recovered-fraction":
        channel["recovered_fraction"] = 1.0 + 5e-13
    elif mutation == "pole-fraction":
        channel["pole_fraction"] = 5e-13
    else:
        channel["zero_source"] = False
    with pytest.raises(ValueError, match="zero|source|pole|spectral|recovered"):
        envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_tiny_positive_source_uses_normal_ratio_logic():
    payload = _valid_chiral_response_payload()
    _make_chiral_channel_zero(payload, "+")
    channel = payload["channels"]["+"]
    channel["component_weights"]["0"] = 5e-13
    channel["direct_sum_weight"] = 5e-13
    channel["poles"] = [
        {
            "energy": 1.0,
            "degeneracy": 1,
            "member_indices": [0],
            "member_weights": [5e-13],
            "weight": 5e-13,
            "fraction": 1.0,
        }
    ]
    channel["spectral_weight"] = 5e-13
    channel["lowest_pole_weight"] = 5e-13
    channel["pole_fraction"] = 1.0
    channel["zero_source"] = False
    minus = payload["channels"]["-"]["lowest_pole_weight"]
    payload["delta_weight"] = minus - 5e-13
    payload["contrast"] = payload["delta_weight"] / (minus + 5e-13)
    payload["diagnostics"]["chirality_resolved"] = True

    assert envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_negative_zero_is_consistently_zero():
    payload = _valid_chiral_response_payload()
    for helicity in ("+", "-"):
        _make_chiral_channel_zero(payload, helicity)
        channel = payload["channels"][helicity]
        channel["component_weights"] = {
            component: -0.0 for component in ("-2", "-1", "0", "1", "2")
        }
        channel["poles"] = [
            {
                "energy": -0.0,
                "degeneracy": 1,
                "member_indices": [0],
                "member_weights": [-0.0],
                "weight": -0.0,
                "fraction": -0.0,
            }
        ]
        channel["spectral_weight"] = -0.0
        channel["direct_sum_weight"] = -0.0
        channel["lowest_pole_weight"] = -0.0
        channel["pole_fraction"] = -0.0
    payload["delta_weight"] = -0.0

    assert envelope_for("challenge15.chiral-response.v1", payload)
    assert payload["contrast"] is None
    assert payload["diagnostics"]["chirality_resolved"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("delta_weight", 5e-13),
        ("delta_weight", -5e-13),
        ("contrast", 0.0),
        ("chirality_resolved", True),
    ],
)
def test_chiral_response_both_zero_rejects_tolerance_sized_top_level_claims(
    field,
    value,
):
    payload = _valid_chiral_response_payload()
    for helicity in ("+", "-"):
        _make_chiral_channel_zero(payload, helicity)
    if field == "chirality_resolved":
        payload["diagnostics"][field] = value
    else:
        payload[field] = value

    with pytest.raises(ValueError, match="delta|contrast|chirality|zero"):
        envelope_for("challenge15.chiral-response.v1", payload)


@pytest.mark.parametrize("zero_helicities", [("+",), ("-",), ("+", "-")])
def test_chiral_response_accepts_identically_zero_channels_with_consistent_scalars(
    zero_helicities,
):
    payload = _valid_chiral_response_payload()
    for helicity in zero_helicities:
        _make_chiral_channel_zero(payload, helicity)

    envelope = envelope_for("challenge15.chiral-response.v1", payload)
    assert validate_envelope(envelope, "challenge15.chiral-response.v1") == payload
    for helicity in zero_helicities:
        assert payload["channels"][helicity]["zero_source"] is True
        assert payload["channels"][helicity]["poles"] == []
    if zero_helicities == ("+", "-"):
        assert payload["delta_weight"] == 0.0
        assert payload["contrast"] is None
        assert payload["diagnostics"]["chirality_resolved"] is False


@pytest.mark.parametrize(
    "path",
    [
        ("initial_state",),
        ("configuration",),
        ("physical_conventions",),
        ("source",),
        ("channels", "+"),
        ("channels", "+", "component_weights"),
        ("diagnostics",),
        ("diagnostics", "adjoint"),
        ("input_sha256",),
        ("input_identities",),
        ("input_identities", "oracle"),
        ("execution_fingerprint",),
    ],
)
def test_chiral_response_rejects_extra_fields_in_every_nested_object(path):
    payload = _valid_chiral_response_payload()
    _at_path(payload, path)["unknown"] = None
    with pytest.raises(ValueError):
        envelope_for("challenge15.chiral-response.v1", payload)


@pytest.mark.parametrize(
    "field",
    [
        "fixture",
        "oracle_artifact",
        "configuration",
        "nqs_generation",
        "nqs_checkpoint",
        "parameter",
    ],
)
def test_chiral_response_rejects_every_malformed_input_hash(field):
    payload = _valid_chiral_response_payload()
    if field.startswith("nqs_"):
        payload["initial_state"] = {
            "kind": "nqs-determinant",
            "coefficient_sha256": "d" * 64,
            "estimator_scope": (
                "exact-finite-Hilbert-contraction-with-exact-ED-L2-finals"
            ),
            "rank": 2,
            "seed": 7,
            "checkpoint_sha256": "f" * 64,
            "checkpoint_record_sha256": "1" * 64,
            "generation_sha256": "e" * 64,
            "parameter_sha256": "a" * 64,
            "determinant_block": 256,
            "exact_ground_overlap": 0.9,
        }
        payload["configuration"] = {
            "mode": "mixed",
            "particles": 3,
            "oracle_sha256": "b" * 64,
            "generation_sha256": "e" * 64,
            "checkpoint_sha256": "f" * 64,
            "checkpoint_record_sha256": "1" * 64,
            "parameter_sha256": "a" * 64,
            "rank": 2,
            "seed": 7,
            "determinant_block": 256,
        }
        payload["input_sha256"]["nqs_generation"] = "e" * 64
        payload["input_sha256"]["nqs_checkpoint"] = "f" * 64
        payload["input_sha256"]["parameter"] = "a" * 64
        payload["input_sha256"]["configuration"] = payload_sha256(
            payload["configuration"]
        )
    payload["input_sha256"][field] = "BAD"
    with pytest.raises(ValueError, match="SHA256"):
        envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_rejects_tampered_execution_fingerprint():
    payload = _valid_chiral_response_payload()
    payload["execution_fingerprint"]["digest"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_rejects_numeric_contrast_below_floor():
    payload = _valid_chiral_response_payload()
    for helicity, lowest in (("+", 1e-16), ("-", 2e-16)):
        channel = payload["channels"][helicity]
        channel["poles"][0]["member_weights"] = [lowest]
        channel["poles"][0]["weight"] = lowest
        channel["poles"][0]["fraction"] = lowest
        channel["poles"][1]["member_weights"] = [1.0 - lowest]
        channel["poles"][1]["weight"] = 1.0 - lowest
        channel["poles"][1]["fraction"] = 1.0 - lowest
        channel["lowest_pole_weight"] = lowest
        channel["pole_fraction"] = lowest
    payload["delta_weight"] = 1e-16
    payload["contrast"] = 1.0 / 3.0
    payload["diagnostics"]["chirality_resolved"] = True
    with pytest.raises(ValueError, match="contrast"):
        envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_mixed_payload_uses_strict_json():
    payload = _mixed_chiral_response_payload()
    assert envelope_for("challenge15.chiral-response.v1", payload)

    payload["channels"]["-"]["component_weights"]["0"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_rejects_duplicated_generation_checkpoint_digest():
    payload = _mixed_chiral_response_payload()
    payload["initial_state"]["checkpoint_sha256"] = "e" * 64
    payload["configuration"]["checkpoint_sha256"] = "e" * 64
    payload["input_sha256"]["nqs_checkpoint"] = "e" * 64
    payload["input_identities"]["checkpoint"]["sha256"] = "e" * 64
    payload["input_sha256"]["configuration"] = payload_sha256(
        payload["configuration"]
    )
    payload["input_identities"]["configuration"]["sha256"] = payload[
        "input_sha256"
    ]["configuration"]
    with pytest.raises(ValueError, match="distinct"):
        envelope_for("challenge15.chiral-response.v1", payload)


def _mixed_chiral_response_payload():
    payload = _valid_chiral_response_payload()
    payload["initial_state"] = {
        "kind": "nqs-determinant",
        "coefficient_sha256": "d" * 64,
        "estimator_scope": (
            "exact-finite-Hilbert-contraction-with-exact-ED-L2-finals"
        ),
        "rank": 2,
        "seed": 7,
        "checkpoint_sha256": "f" * 64,
        "checkpoint_record_sha256": "1" * 64,
        "generation_sha256": "e" * 64,
        "parameter_sha256": "a" * 64,
        "determinant_block": 256,
        "exact_ground_overlap": 0.9,
    }
    payload["configuration"] = {
        "mode": "mixed",
        "particles": 3,
        "oracle_sha256": "b" * 64,
        "generation_sha256": "e" * 64,
        "checkpoint_sha256": "f" * 64,
        "checkpoint_record_sha256": "1" * 64,
        "parameter_sha256": "a" * 64,
        "rank": 2,
        "seed": 7,
        "determinant_block": 256,
    }
    payload["input_sha256"].update(
        {
            "nqs_generation": "e" * 64,
            "nqs_checkpoint": "f" * 64,
            "parameter": "a" * 64,
            "configuration": payload_sha256(payload["configuration"]),
        }
    )
    payload["input_identities"].update(
        {
            "generation": {
                "identity_role": "generation",
                "artifact_schema": "challenge15.training-generation.v1",
                "sha256": "e" * 64,
            },
            "checkpoint": {
                "identity_role": "checkpoint",
                "artifact_schema": "challenge15.train-checkpoint.v1",
                "sha256": "f" * 64,
            },
            "checkpoint_record": {
                "identity_role": "checkpoint_record",
                "artifact_schema": "challenge15.train-checkpoint-record.v1",
                "sha256": "1" * 64,
            },
            "parameter": {
                "identity_role": "parameter",
                "artifact_schema": "challenge15.parameter-blob.v1",
                "sha256": "a" * 64,
            },
        }
    )
    payload["input_identities"]["configuration"]["sha256"] = payload[
        "input_sha256"
    ]["configuration"]
    return payload


_RESPONSE_IDENTITY_ROLES = (
    "oracle",
    "generation",
    "checkpoint",
    "checkpoint_record",
    "parameter",
    "configuration",
)


def _response_role_digest(payload, role):
    if role == "oracle":
        return payload["input_sha256"]["oracle_artifact"]
    if role == "generation":
        return payload["input_sha256"]["nqs_generation"]
    if role == "checkpoint":
        return payload["input_sha256"]["nqs_checkpoint"]
    if role == "checkpoint_record":
        return payload["initial_state"]["checkpoint_record_sha256"]
    if role == "parameter":
        return payload["input_sha256"]["parameter"]
    return payload["input_sha256"]["configuration"]


def _substitute_response_role(payload, role, digest):
    if role == "oracle":
        payload["input_sha256"]["oracle_artifact"] = digest
        payload["configuration"]["oracle_sha256"] = digest
    elif role == "generation":
        payload["input_sha256"]["nqs_generation"] = digest
        payload["configuration"]["generation_sha256"] = digest
        payload["initial_state"]["generation_sha256"] = digest
    elif role == "checkpoint":
        payload["input_sha256"]["nqs_checkpoint"] = digest
        payload["configuration"]["checkpoint_sha256"] = digest
        payload["initial_state"]["checkpoint_sha256"] = digest
    elif role == "checkpoint_record":
        payload["configuration"]["checkpoint_record_sha256"] = digest
        payload["initial_state"]["checkpoint_record_sha256"] = digest
    elif role == "parameter":
        payload["input_sha256"]["parameter"] = digest
        payload["configuration"]["parameter_sha256"] = digest
        payload["initial_state"]["parameter_sha256"] = digest
    else:
        payload["input_sha256"]["configuration"] = digest


@pytest.mark.parametrize(
    "source_role,target_role",
    tuple(itertools.permutations(_RESPONSE_IDENTITY_ROLES, 2)),
)
def test_chiral_response_rejects_every_role_digest_substitution(
    source_role,
    target_role,
):
    payload = _mixed_chiral_response_payload()
    source_digest = _response_role_digest(payload, source_role)
    _substitute_response_role(payload, target_role, source_digest)
    payload["input_identities"][target_role] = deepcopy(
        payload["input_identities"][source_role]
    )
    if target_role != "configuration":
        payload["input_sha256"]["configuration"] = payload_sha256(
            payload["configuration"]
        )
        payload["input_identities"]["configuration"]["sha256"] = payload[
            "input_sha256"
        ]["configuration"]

    with pytest.raises(ValueError):
        envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_rejects_consistent_multi_role_substitution():
    payload = _mixed_chiral_response_payload()
    oracle_digest = _response_role_digest(payload, "oracle")
    for role in ("generation", "checkpoint", "checkpoint_record", "parameter"):
        _substitute_response_role(payload, role, oracle_digest)
        payload["input_identities"][role] = {
            "identity_role": role,
            "artifact_schema": payload["input_identities"][role][
                "artifact_schema"
            ],
            "sha256": oracle_digest,
        }
    payload["input_sha256"]["configuration"] = payload_sha256(
        payload["configuration"]
    )
    payload["input_identities"]["configuration"]["sha256"] = payload[
        "input_sha256"
    ]["configuration"]

    with pytest.raises(ValueError, match="distinct"):
        envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_accepts_pairwise_distinct_mixed_role_identities():
    payload = _mixed_chiral_response_payload()
    assert envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_exact_oracle_and_configuration_must_be_distinct():
    payload = _valid_chiral_response_payload()
    payload["input_sha256"]["oracle_artifact"] = payload["input_sha256"][
        "oracle_cache"
    ]
    payload["input_sha256"]["oracle_cache"] = None
    payload["configuration"]["mode"] = "oracle-reuse"
    payload["configuration"]["oracle_sha256"] = payload["input_sha256"][
        "oracle_artifact"
    ]
    payload["input_identities"]["oracle"]["artifact_schema"] = (
        "challenge15.cli-oracle.v1"
    )
    payload["input_sha256"]["configuration"] = payload["input_sha256"][
        "oracle_artifact"
    ]
    payload["input_identities"]["configuration"]["sha256"] = payload[
        "input_sha256"
    ]["configuration"]

    with pytest.raises(ValueError, match="configuration"):
        envelope_for("challenge15.chiral-response.v1", payload)


def test_chiral_response_exact_cache_typed_identity_matches_payload_version():
    payload = _valid_chiral_response_payload()
    payload["input_sha256"]["oracle_cache"] = payload["input_sha256"][
        "oracle_artifact"
    ]
    payload["input_sha256"]["oracle_artifact"] = None
    payload["configuration"]["mode"] = "exact-size"
    payload["input_identities"]["oracle"]["artifact_schema"] = (
        "challenge15.oracle-cache.v2"
    )
    payload["input_sha256"]["configuration"] = payload_sha256(
        payload["configuration"]
    )
    payload["input_identities"]["configuration"]["sha256"] = payload[
        "input_sha256"
    ]["configuration"]
    assert envelope_for("challenge15.chiral-response.v1", payload)

    payload["input_identities"]["oracle"]["artifact_schema"] = (
        "challenge15.oracle-cache.v1"
    )
    with pytest.raises(ValueError, match="oracle typed identity"):
        envelope_for("challenge15.chiral-response.v1", payload)


@pytest.mark.parametrize(
    "field",
    [
        "rank",
        "seed",
        "checkpoint_sha256",
        "checkpoint_record_sha256",
        "generation_sha256",
        "parameter_sha256",
        "determinant_block",
    ],
)
def test_chiral_response_mixed_metadata_must_match_published_configuration(field):
    payload = _mixed_chiral_response_payload()
    envelope_for("challenge15.chiral-response.v1", payload)

    value = payload["initial_state"][field]
    payload["initial_state"][field] = value + 1 if isinstance(value, int) else "9" * 64
    with pytest.raises(ValueError, match="metadata|identity"):
        envelope_for("challenge15.chiral-response.v1", payload)


def test_nested_contract_rejects_every_missing_or_unknown_rank_prng_field():
    payload = root_extension().to_payload()
    for field in ("algorithm", "key_sha256"):
        broken = deepcopy(payload)
        broken["rank_growth_prng"].pop(field)
        with pytest.raises(ValueError, match="nested fields"):
            envelope_for("challenge15.rank-extension.v1", broken)
    broken = deepcopy(payload)
    broken["rank_growth_prng"]["unknown"] = True
    with pytest.raises(ValueError, match="nested fields"):
        envelope_for("challenge15.rank-extension.v1", broken)


@pytest.mark.parametrize(
    "schema,field",
    [
        (schema, field)
        for schema, fields in SCIENTIFIC_NESTED_CONTRACTS.items()
        for field in fields
    ],
)
def test_every_scientific_nested_object_rejects_missing_and_unknown_fields(
    schema, field
):
    payload = SCHEMA_FIXTURE_REGISTRY[schema]()
    nested = payload[field]
    target = nested[0] if isinstance(nested, list) else nested
    assert isinstance(target, dict) and target
    first = next(iter(target))
    missing = deepcopy(payload)
    missing_target = missing[field][0] if isinstance(nested, list) else missing[field]
    missing_target.pop(first)
    with pytest.raises(ValueError, match="nested"):
        envelope_for(schema, missing)
    extra = deepcopy(payload)
    extra_target = extra[field][0] if isinstance(nested, list) else extra[field]
    extra_target["unknown"] = None
    with pytest.raises(ValueError, match="nested"):
        envelope_for(schema, extra)


def _object_paths(value, path=()):
    if isinstance(value, dict):
        yield path
        for key, child in value.items():
            yield from _object_paths(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _object_paths(child, path + (index,))


def _at_path(value, path):
    for component in path:
        value = value[component]
    return value


def _leaf_specs(spec, path=()):
    if isinstance(spec, dict):
        for field, child in spec.items():
            yield from _leaf_specs(child, path + (field,))
    elif isinstance(spec, list):
        yield from _leaf_specs(spec[0], path + (0,))
    else:
        yield path, spec


def _invalid_contract_leaf(spec):
    if isinstance(spec, tuple):
        return object() if spec[0] == "nullable" else "__invalid__"
    if spec == "bool":
        return 1
    if spec in {"positive-int", "nonnegative-int"}:
        return True
    if spec in {"number", "positive-number", "nonnegative-number", "unit-number"}:
        return float("nan")
    if spec == "sha":
        return "bad"
    return ""


@pytest.mark.parametrize("schema", sorted(SCIENTIFIC_NESTED_CONTRACTS))
def test_every_recursive_scientific_object_rejects_each_field_mutation(schema):
    payload = SCHEMA_FIXTURE_REGISTRY[schema]()
    for root_field in SCIENTIFIC_NESTED_CONTRACTS[schema]:
        for path in _object_paths(payload[root_field]):
            target = _at_path(payload[root_field], path)
            for field in tuple(target):
                broken = deepcopy(payload)
                _at_path(broken[root_field], path).pop(field)
                with pytest.raises(ValueError, match="nested"):
                    envelope_for(schema, broken)
            broken = deepcopy(payload)
            _at_path(broken[root_field], path)["unknown"] = None
            with pytest.raises(ValueError, match="nested"):
                envelope_for(schema, broken)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["gate_metrics"].__setitem__("finite", 1),
        lambda payload: payload["primitive_metrics"]["gap"].__setitem__("ci_low", 1.0),
        lambda payload: payload["primitive_metrics"]["projected_span"][
            "singular_values_by_sector"
        ].__setitem__("L0", [0.1, 0.2]),
        lambda payload: payload["primitive_metrics"]["projected_span"][
            "numerical_rank_by_sector"
        ].__setitem__("L0", 2),
        lambda payload: (
            payload["primitive_metrics"]["projected_span"][
                "completeness_claim_by_sector"
            ].__setitem__("L0", True),
            payload["primitive_metrics"]["projected_span"][
                "dim_m_l_by_sector"
            ].__setitem__("L0", 1),
        ),
    ],
)
def test_scientific_contract_rejects_type_range_order_and_cross_invariants(mutate):
    payload = SCHEMA_FIXTURE_REGISTRY["challenge15.exact-evaluation-shard.v1"]()
    mutate(payload)
    with pytest.raises(ValueError, match="nested"):
        envelope_for("challenge15.exact-evaluation-shard.v1", payload)


def test_exact_shard_contract_defers_cross_rank_acceptance():
    payload = SCHEMA_FIXTURE_REGISTRY[
        "challenge15.exact-evaluation-shard.v1"
    ]()

    assert "rank_converged" not in payload["gate_metrics"]
    assert "production_accepted" not in payload["gate_metrics"]
    assert envelope_for("challenge15.exact-evaluation-shard.v1", payload)


def test_exact_shard_ambiguity_cannot_be_validated_as_passed():
    schema = "challenge15.exact-evaluation-shard.v1"
    payload = SCHEMA_FIXTURE_REGISTRY[schema]()
    payload["metric_equivalence"] = {
        "reference_sha256": SHA,
        "absolute_tolerance": 2e-11,
        "maximum_difference": 1e-13,
        "classification": "pending",
        "ambiguous": True,
        "straddled_gates": ["overlap"],
        "passed": False,
    }

    encoded = envelope_for(schema, payload)
    assert validate_envelope(encoded, schema) == payload

    mutations = (
        {"classification": "passed"},
        {"passed": True},
        {"ambiguous": False},
        {"straddled_gates": []},
    )
    for mutation in mutations:
        broken = deepcopy(payload)
        broken["metric_equivalence"].update(mutation)
        with pytest.raises(ValueError, match="equivalence|ambiguous|passed"):
            envelope_for(schema, broken)


def test_coordinate_diagnostic_rejects_mutation_of_every_leaf():
    schema = "challenge15.coordinate-evaluation-shard.v1"
    for root, spec in SCIENTIFIC_NESTED_CONTRACTS[schema].items():
        for path, leaf_spec in _leaf_specs(spec):
            payload = SCHEMA_FIXTURE_REGISTRY[schema]()
            parent = _at_path(payload[root], path[:-1])
            parent[path[-1]] = _invalid_contract_leaf(leaf_spec)
            with pytest.raises((TypeError, ValueError)):
                envelope_for(schema, payload)


@pytest.mark.parametrize(
    "mutation",
    ["mc-covariance", "mc-variance", "within-seed", "optimizer-variance"],
)
def test_paired_gap_enforces_exact_covariance_formulas(mutation):
    schema = "challenge15.coordinate-evaluation-shard.v1"
    payload = SCHEMA_FIXTURE_REGISTRY[schema]()
    paired = payload["paired_gap_diagnostics"]
    if mutation == "mc-covariance":
        paired["monte_carlo_covariance_e0_e2"] = 1e-3
    elif mutation == "mc-variance":
        paired["variance_mc_gap"] = 1e-3
    elif mutation == "within-seed":
        paired["within_seed_inputs"][0]["monte_carlo_covariance_e0_e2"] = 1e-3
    else:
        paired["between_seed_inputs"]["variance_seed_mean_gap"] = 1e-3
    with pytest.raises(ValueError, match="covariance|variance"):
        envelope_for(schema, payload)


def _accepted_paired_gap_payload():
    schema = "challenge15.coordinate-evaluation-shard.v1"
    payload = SCHEMA_FIXTURE_REGISTRY[schema]()
    paired = payload["paired_gap_diagnostics"]
    second = deepcopy(paired["within_seed_inputs"][0])
    second["seed"] = 1
    paired["within_seed_inputs"].append(second)
    paired["within_seed_inputs"][0].update({"e0": 1.0, "e2": 2.0})
    paired["within_seed_inputs"][1].update({"e0": 3.0, "e2": 6.0})
    between = paired["between_seed_inputs"]
    between.update(
        {
            "paired_seed_ids": [0, 1],
            "e0_seed_estimates": [1.0, 3.0],
            "e2_seed_estimates": [2.0, 6.0],
            "optimizer_variance_e0": 2.0,
            "optimizer_variance_e2": 8.0,
            "optimizer_covariance_e0_e2": 4.0,
            "paired_seed_count": 2,
            "variance_seed_mean_gap": 1.0,
        }
    )
    paired.update(
        {
            "optimizer_variance_e0": 2.0,
            "optimizer_variance_e2": 8.0,
            "optimizer_induced_covariance_e0_e2": 4.0,
            "variance_seed_mean_gap": 1.0,
            "uncertainty_status": "accepted",
        }
    )
    payload["gate_metrics"]["production_accepted"] = True
    return payload


def test_accepted_paired_gap_recomputes_unbiased_covariance_exactly():
    payload = _accepted_paired_gap_payload()
    assert envelope_for("challenge15.coordinate-evaluation-shard.v1", payload)
    for field in (
        "optimizer_variance_e0",
        "optimizer_variance_e2",
        "optimizer_covariance_e0_e2",
        "variance_seed_mean_gap",
    ):
        broken = deepcopy(payload)
        broken["paired_gap_diagnostics"]["between_seed_inputs"][field] += 0.25
        with pytest.raises(ValueError, match="covariance|variance"):
            envelope_for("challenge15.coordinate-evaluation-shard.v1", broken)


@pytest.mark.parametrize("field", ("e0_seed_estimates", "e2_seed_estimates"))
def test_accepted_paired_gap_rejects_duplicate_array_substitution(field):
    payload = _accepted_paired_gap_payload()
    payload["paired_gap_diagnostics"]["between_seed_inputs"][field][0] += 0.5
    with pytest.raises(ValueError, match="within-seed|duplicate|paired"):
        envelope_for("challenge15.coordinate-evaluation-shard.v1", payload)


def test_paired_gap_k1_or_unpaired_is_pending_and_not_accepted():
    schema = "challenge15.coordinate-evaluation-shard.v1"
    payload = SCHEMA_FIXTURE_REGISTRY[schema]()
    assert envelope_for(schema, payload)
    payload["paired_gap_diagnostics"]["uncertainty_status"] = "accepted"
    payload["gate_metrics"]["production_accepted"] = True
    with pytest.raises(ValueError, match="K>=2|paired"):
        envelope_for(schema, payload)
    unpaired = SCHEMA_FIXTURE_REGISTRY[schema]()
    unpaired["paired_gap_diagnostics"]["between_seed_inputs"][
        "paired_seed_ids"
    ] = [1]
    assert envelope_for(schema, unpaired)
    unpaired["paired_gap_diagnostics"]["uncertainty_status"] = "accepted"
    with pytest.raises(ValueError, match="paired K>=2"):
        envelope_for(schema, unpaired)


def test_export_and_import_context_recompute_manifest_and_bundle_bytes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    destination = tmp_path / "destination"
    destination.mkdir()
    destination_members = destination / "members"
    destination_members.mkdir()
    member = b"member-bytes"
    (source / "member.bin").write_bytes(member)
    (destination_members / "member.bin").write_bytes(member)
    bundle = tmp_path / "bundle.tar"
    bundle.write_bytes(b"bundle-bytes")
    imported_bundle = destination / "imported.tar"
    imported_bundle.write_bytes(bundle.read_bytes())
    member_sha = hashlib.sha256(member).hexdigest()
    bundle_sha = hashlib.sha256(bundle.read_bytes()).hexdigest()
    manifest = {"member.bin": member_sha}
    sums_sha = hashlib.sha256(f"{member_sha}  member.bin\n".encode()).hexdigest()
    common = {
        "policy_sha256": policy_sha256(),
        "source_manifest_sha256": SHA,
        "runtime_attestations": RUNTIMES,
        "base_configuration_sha256": SHA,
        "particles": 6,
    }
    exported = {
        **common,
        "bundle_role": "evaluation",
        "source_controller": "lasg02",
        "source_root": str(source),
        "source_artifact_sha256": member_sha,
        "member_manifest": manifest,
        "sha256sums_sha256": sums_sha,
        "bundle_sha256": bundle_sha,
        "created_at_utc": "2026-07-29T00:00:00Z",
    }
    imported = {
        **common,
        "bundle_sha256": bundle_sha,
        "destination_controller": "qdeshell",
        "destination_root": str(destination),
        "member_manifest": manifest,
        "imported_artifact_sha256": member_sha,
        "verified_at_utc": "2026-07-29T00:01:00Z",
    }
    export_context = {
        "approved_roots": (tmp_path,),
        "source_controller": "lasg02",
        "bundle_role": "evaluation",
        "bundle_path": bundle,
        "source_artifact_sha256": member_sha,
    }
    import_context = {
        "approved_roots": (tmp_path,),
        "destination_controller": "qdeshell",
        "bundle_path": imported_bundle,
        "member_root": destination_members,
        "imported_artifact_sha256": member_sha,
    }
    assert validate_export_context(exported, export_context) == len(bundle.read_bytes())
    assert validate_import_context(imported, import_context) == len(imported_bundle.read_bytes())

    (destination_members / "member.bin").write_bytes(member + b"extra")
    with pytest.raises(ValueError, match="manifest"):
        validate_import_context(imported, import_context)

    (destination_members / "member.bin").write_bytes(member)
    intent = {"correlation_id": "correlation"}
    transfer = {
        **common,
        "direction": "lasg02->qdeshell",
        "export_bundle_sha256": payload_sha256(exported),
        "import_bundle_sha256": payload_sha256(imported),
        "source_controller": "lasg02",
        "destination_controller": "qdeshell",
        "source_identity": str(bundle),
        "destination_identity": str(imported_bundle),
        "partial_path": str(destination / "partial"),
        "final_path": str(imported_bundle),
        "bytes": len(bundle.read_bytes()),
        "attempt_intent_sha256": payload_sha256(intent),
        "correlation_id": "correlation",
        "remote_claim_sha256": SHA,
        "started_at_utc": "2026-07-29T00:00:00Z",
        "verified_at_utc": "2026-07-29T00:01:00Z",
    }
    transfer_context = {
        "export_bundle": exported,
        "import_bundle": imported,
        "export_context": export_context,
        "import_context": import_context,
        "approved_source_roots": (tmp_path,),
        "approved_destination_roots": (tmp_path,),
        "attempt_intent": intent,
        "remote_claim_sha256": SHA,
        "source_identity": str(bundle),
        "destination_identity": str(imported_bundle),
        "partial_path": str(destination / "partial"),
        "final_path": str(imported_bundle),
        "bytes": len(bundle.read_bytes()),
    }
    validate_receipt_context(
        "challenge15.transfer-receipt.v1", transfer, transfer_context
    )
    imported_bundle.write_bytes(imported_bundle.read_bytes() + b"extra")
    with pytest.raises(ValueError, match="bundle payload hash|byte count"):
        validate_receipt_context(
            "challenge15.transfer-receipt.v1", transfer, transfer_context
        )


def test_fixed_schedule_exact_fields_types_ranges_and_canonical_hash():
    payload = {
        "policy_sha256": policy_sha256(),
        "source_manifest_sha256": SHA,
        "runtime_attestations": RUNTIMES,
        "base_configuration_sha256": SHA,
        "particles": 6,
        "seed": 0,
        "rank": 1,
        "owner_sha256": SHA,
        "extension_sha256": SHA,
        "schedule_version": "fixed-v1",
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
    }
    envelope = fixed_schedule_envelope(payload)
    assert validate_fixed_schedule_envelope(envelope) == payload
    for field in payload:
        broken = dict(payload)
        broken.pop(field)
        with pytest.raises(ValueError, match="fields"):
            fixed_schedule_envelope(broken)
    with pytest.raises(ValueError, match="fields"):
        fixed_schedule_envelope({**payload, "unknown": None})
    for field, value in (
        ("chains_per_sector", True),
        ("walkers_per_chain", 31),
        ("checkpoint_interval_steps", 10001),
        ("weight_l0", 0.6),
        ("learning_rate", 0.0),
    ):
        with pytest.raises(ValueError):
            fixed_schedule_envelope({**payload, field: value})
    assert PRODUCTION_VMC_CONFIG_FIELDS == frozenset(
        {
            "optimizer", "learning_rate", "steps", "weight_l0",
            "weight_l2", "chains_per_sector", "walkers_per_chain",
            "pilot_sweeps", "burn_in_sweeps", "draws_per_update",
            "thinning_sweeps", "reequilibration_sweeps_after_update",
            "refresh_log_amplitudes_after_update", "checkpoint_interval_steps",
            "final_evaluation_chains_per_sector",
            "final_evaluation_burn_in_sweeps",
            "final_evaluation_draws_per_chain",
            "final_evaluation_thinning_sweeps",
                "schedule_version",
        }
    )
    assert not {
        "walker_microbatch", "carrier_block", "quadrature_block"
    } & PRODUCTION_VMC_CONFIG_FIELDS


def test_evaluation_receipt_reloads_shard_and_rejects_substitution(tmp_path):
    schema = "challenge15.coordinate-evaluation-shard.v1"
    shard = SCHEMA_FIXTURE_REGISTRY[schema]()
    digest = payload_sha256(shard)
    path = tmp_path / f"{digest}.json"
    publish_create_only(
        path,
        canonical_json(envelope_for(schema, shard)) + b"\n",
    )
    receipt = SCHEMA_FIXTURE_REGISTRY["challenge15.evaluation-receipt.v1"]()
    receipt.update(
        {
            field: shard[field]
            for field in (
                "policy_sha256",
                "source_manifest_sha256",
                "runtime_attestations",
                "base_configuration_sha256",
                "particles",
            )
        }
    )
    receipt.update(
        shard_sha256=digest,
        stage="coordinate",
        identity={
            "stage": "coordinate",
            "seed": shard["seed"],
            "rank": shard["rank"],
        },
        controller="qdeshell",
        telemetry_invocation_sha256=payload_sha256(
            {
                "stage": "coordinate",
                "shard_sha256": digest,
                "started_at_utc": receipt["started_at_utc"],
            }
        ),
        metric_equivalence={
            "canonical_completed": True,
            "bitwise_equal": True,
            "classification": "passed",
        },
    )
    context = {
        "approved_roots": (tmp_path,),
        "shard_path": path,
        "shard_schema": schema,
    }
    validate_receipt_context(
        "challenge15.evaluation-receipt.v1", receipt, context
    )
    for mutation in (
        {"source_manifest_sha256": "f" * 64},
        {"stage": "exact"},
        {"identity": {**receipt["identity"], "seed": shard["seed"] + 1}},
        {"identity": {**receipt["identity"], "rank": shard["rank"] + 1}},
        {"controller": "lasg02"},
    ):
        with pytest.raises(ValueError, match="evaluation"):
            validate_receipt_context(
                "challenge15.evaluation-receipt.v1",
                {**receipt, **mutation},
                context,
            )
    replacement = {**shard, "evaluation_prng_sha256": "f" * 64}
    path.write_bytes(canonical_json(envelope_for(schema, replacement)) + b"\n")
    with pytest.raises(ValueError, match="shard"):
        validate_receipt_context(
            "challenge15.evaluation-receipt.v1", receipt, context
        )
