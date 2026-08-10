from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import signal

import pytest

import challenge15.generations as generations_module
from challenge15.artifacts import publish_create_only, publish_production_envelope
from challenge15.generations import (
    PUBLISHER_SELECTOR_REGISTRY,
    SELECTOR_REQUIRED_CONSTRAINTS,
    claim_seed_root,
    create_rank_extension,
    create_rank_extension_decision,
    discover_unique_terminal_generation,
    publish_blob,
    publish_generation,
    publish_snapshot,
    publish_training_attempt,
    select_published,
)
from challenge15.production_policy import policy_sha256
from challenge15.production_schema import (
    RankExtension,
    RankExtensionDecision,
    OrchestrationAttemptIntent,
    SeedOwner,
    TrainingGeneration,
    TrainingAttempt,
    TrainingSnapshot,
    SCIENTIFIC_NESTED_CONTRACTS,
    canonical_json,
    contract_fixture,
    envelope_for,
    fixed_schedule_envelope,
    production_vmc_config_envelope,
    payload_sha256,
    attempt_correlation_id,
    validate_envelope,
)


SHA = "a" * 64
RUNTIMES = {
    "training": {"qdeshell": "1" * 64},
    "coordinate": {"qdeshell": "2" * 64},
    "oracle": {"lasg02": "3" * 64},
    "exact": {"lasg02": "4" * 64},
    "reducer": {"lasg02": "5" * 64},
}
BASE_CONFIG = {
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
BASE_SHA = payload_sha256(BASE_CONFIG)


def _kill_directory_publication(kind, root, payload, killpoint):
    os.environ["CHALLENGE15_PUBLICATION_KILLPOINT"] = killpoint
    if kind == "attempt":
        publish_training_attempt(Path(root), TrainingAttempt(**payload))
    elif kind == "generation":
        publish_generation(Path(root), TrainingGeneration(**payload))
    else:
        claim_seed_root(Path(root), SeedOwner(**payload))


def owner(seed: int = 0) -> SeedOwner:
    return SeedOwner(
        seed=seed,
        experiment_id="experiment",
        base_configuration_sha256=BASE_SHA,
        expected_seed_set=(0, 1, 2, 3, 4),
        owner_uuid="11111111-1111-4111-8111-111111111111",
        claimed_at_utc="2026-07-29T00:00:00Z",
        claim_host="host",
        claim_process="pid:1",
        claim_nonce_sha256=SHA,
        policy_sha256=policy_sha256(),
        source_manifest_sha256=SHA,
        runtime_attestations=RUNTIMES,
    )


def discover(seed_root: Path, expected_extensions):
    return discover_unique_terminal_generation(
        seed_root,
        expected_extensions,
        expected_policy_sha256=policy_sha256(),
        expected_source_manifest_sha256=SHA,
        expected_runtime_attestations=RUNTIMES,
        expected_base_configuration_sha256=BASE_SHA,
        expected_particles=6,
        expected_seed=0,
        expected_experiment_id="experiment",
        expected_canonical_root=seed_root,
    )


def decision(rank: int, parents=None) -> RankExtensionDecision:
    parents = parents or {}
    return RankExtensionDecision(
        policy_sha256=policy_sha256(),
        source_manifest_sha256=SHA,
        runtime_attestations=RUNTIMES,
        base_configuration_sha256=BASE_SHA,
        particles=6,
        seed=0,
        current_rank=None if rank == 1 else rank // 2,
        new_rank=rank,
        prior_expected_ranks_sha256=None if rank == 1 else parents.get("expected", "6" * 64),
        prior_reduction_sha256=None if rank == 1 else parents.get("reduction", "7" * 64),
        prior_finalization_sha256=None if rank == 1 else parents.get("finalization", "8" * 64),
        prior_import_receipt_sha256=None if rank == 1 else parents.get("import", "9" * 64),
        prior_transfer_receipt_sha256=None if rank == 1 else parents.get("transfer", "a" * 64),
        decision="train",
        reason="initial" if rank == 1 else "scheduled_initial_ladder",
        decision_metrics={},
    )


def extension(rank: int, parent=None, decision_sha: str | None = None) -> RankExtension:
    previous = None if parent is None else rank // 2
    reason = "initial" if parent is None else "scheduled_initial_ladder"
    return RankExtension(
        particles=6,
        seed=0,
        experiment_id="experiment",
        base_configuration_sha256=BASE_SHA,
        policy_sha256=policy_sha256(),
        source_manifest_sha256=SHA,
        runtime_attestations=RUNTIMES,
        expected_seed_set=(0, 1, 2, 3, 4),
        previous_rank=previous,
        new_rank=rank,
        parent_generation_sha256=None if parent is None else parent.payload_sha256,
        parent_parameter_sha256=None if parent is None else parent.payload["parameter_sha256"],
        parent_optimizer_state_sha256=(
            None if parent is None else parent.payload["optimizer_state_sha256"]
        ),
        rank_extension_decision_sha256=decision_sha or payload_sha256(decision(rank).to_payload()),
        embedding_algorithm="copy-old-append-zero-gates-v1",
        rank_growth_prng={"algorithm": "threefry2x32", "key_sha256": SHA},
        reason=reason,
        created_by_git_revision="revision",
    )


def publish_extension(seed_root: Path, rank: int, parent=None) -> Path:
    decisions = seed_root / "decisions"
    extensions = seed_root / "extensions"
    decisions.mkdir(exist_ok=True)
    extensions.mkdir(exist_ok=True)
    parents = {} if rank == 1 else _publish_decision_parents(seed_root)
    decision_path = create_rank_extension_decision(decisions, decision(rank, parents))
    return create_rank_extension(
        extensions,
        extension(rank, parent, decision_path.stem),
    )


def _publish_decision_parents(seed_root):
    directory = seed_root / "decision-parents"
    directory.mkdir(exist_ok=True)
    common = {
        "policy_sha256": policy_sha256(),
        "source_manifest_sha256": SHA,
        "runtime_attestations": RUNTIMES,
        "base_configuration_sha256": BASE_SHA,
        "particles": 6,
    }
    expected = hashlib.sha256(canonical_json([1])).hexdigest()
    payloads = {
        "reduction": (
            "challenge15.reduction-receipt.v1",
            {
                **common,
                "canonical_payload_sha256": SHA,
                "started_at_utc": "2026-07-29T00:00:00Z",
                "finished_at_utc": "2026-07-29T00:01:00Z",
                "hostname": "cpu",
                "slurm_job_id": "1",
                "devices": ["cpu"],
                "peak_rss_mib": 1.0,
                "stage_elapsed_seconds": 1.0,
                "cache_counters": contract_fixture(
                    SCIENTIFIC_NESTED_CONTRACTS[
                        "challenge15.reduction-receipt.v1"
                    ]["cache_counters"]
                ),
            },
        ),
        "import": (
            "challenge15.import-bundle.v1",
            {
                **common,
                "bundle_sha256": SHA,
                "destination_controller": "lasg02",
                "destination_root": "/approved/import",
                "member_manifest": {},
                "imported_artifact_sha256": SHA,
                "verified_at_utc": "2026-07-29T00:00:00Z",
            },
        ),
    }
    digests = {"expected": expected}
    for key, (schema, payload) in payloads.items():
        digest = payload_sha256(payload)
        publish_create_only(
            directory / f"{digest}.json",
            canonical_json(envelope_for(schema, payload)) + b"\n",
        )
        digests[key] = digest
    finalization = {
        **common,
        "expected_ranks": [1],
        "expected_ranks_sha256": expected,
        "selected_reduction_sha256": digests["reduction"],
        "selected_reduction_path": "/approved/reduction.json",
        "production_accepted": False,
        "finalized_at_utc": "2026-07-29T00:00:00Z",
        "finalized_by": "reducer",
    }
    transfer = {
        **common,
        "direction": "lasg02->qdeshell",
        "export_bundle_sha256": SHA,
        "import_bundle_sha256": digests["import"],
        "source_controller": "lasg02",
        "destination_controller": "qdeshell",
        "source_identity": "/approved/source",
        "destination_identity": "/approved/destination",
        "partial_path": "/approved/.partial",
        "final_path": "/approved/final",
        "bytes": 1,
        "attempt_intent_sha256": SHA,
        "correlation_id": SHA,
        "remote_claim_sha256": SHA,
        "started_at_utc": "2026-07-29T00:00:00Z",
        "verified_at_utc": "2026-07-29T00:01:00Z",
    }
    for key, schema, payload in (
        ("finalization", "challenge15.reduction-finalization.v1", finalization),
        ("transfer", "challenge15.transfer-receipt.v1", transfer),
    ):
        digest = payload_sha256(payload)
        publish_create_only(
            directory / f"{digest}.json",
            canonical_json(envelope_for(schema, payload)) + b"\n",
        )
        digests[key] = digest
    return digests


def generation(rank: int, extension_sha: str, parent=None) -> TrainingGeneration:
    return TrainingGeneration(
        policy_sha256=policy_sha256(),
        source_manifest_sha256=SHA,
        runtime_attestations=RUNTIMES,
        base_configuration_sha256=BASE_SHA,
        particles=6,
        seed=0,
        rank=rank,
        attempt_sha256=f"{rank:x}" * 64,
        extension_sha256=extension_sha,
        parent_generation_sha256=None if parent is None else parent,
        parent_parameter_sha256=None if parent is None else SHA,
        parent_optimizer_state_sha256=None if parent is None else "b" * 64,
        parameter_sha256=SHA,
        optimizer_state_sha256="b" * 64,
        terminal_snapshot_sha256="c" * 64,
        training_metrics=contract_fixture(
            SCIENTIFIC_NESTED_CONTRACTS[
                "challenge15.training-generation.v1"
            ]["training_metrics"]
        ),
    )


def publish_completed_generation(
    seed_root: Path,
    rank: int,
    extension_path: Path,
    parent=None,
    variant: str = "",
):
    suffix = f"-{variant}" if variant else ""
    parameter = publish_blob(seed_root, f"parameter-{rank}{suffix}".encode())
    optimizer = publish_blob(seed_root, f"optimizer-{rank}{suffix}".encode())
    walker = publish_blob(seed_root, f"walker-{rank}{suffix}".encode())
    amplitude = publish_blob(seed_root, f"amplitude-{rank}{suffix}".encode())
    prng = publish_blob(seed_root, f"prng-{rank}{suffix}".encode())
    owner_sha = next((seed_root / "owner").glob("*.json")).stem
    attempt = TrainingAttempt(
        seed=0,
        rank=rank,
        attempt_id=f"attempt-{rank}{suffix}",
        owner_sha256=owner_sha,
        extension_sha256=extension_path.stem,
        started_from_snapshot_sha256=None,
        resource_override=None,
        terminal_snapshot_sha256=None,
        status="running",
    )
    attempts_dir = seed_root / "attempts"
    before = set(attempts_dir.iterdir()) if attempts_dir.exists() else set()
    publish_training_attempt(seed_root, attempt)
    attempt_dir, = set(attempts_dir.iterdir()) - before
    snapshot = TrainingSnapshot(
        policy_sha256=policy_sha256(),
        source_manifest_sha256=SHA,
        runtime_attestations=RUNTIMES,
        base_configuration_sha256=BASE_SHA,
        particles=6,
        seed=0,
        rank=rank,
        attempt_id=attempt.attempt_id,
        step=100,
        parameter_sha256=parameter,
        optimizer_state_sha256=optimizer,
        walker_state_sha256=walker,
        log_amplitude_sha256=amplitude,
        prng_state_sha256=prng,
        proposal_state=contract_fixture(
            SCIENTIFIC_NESTED_CONTRACTS[
                "challenge15.training-snapshot.v1"
            ]["proposal_state"]
        ),
        diagnostics=contract_fixture(
            SCIENTIFIC_NESTED_CONTRACTS[
                "challenge15.training-snapshot.v1"
            ]["diagnostics"]
        ),
    )
    snapshot_sha = publish_snapshot(attempt_dir, snapshot)
    attempt_sha = publish_training_attempt(
        seed_root,
        replace(
            attempt,
            terminal_snapshot_sha256=snapshot_sha,
            status="complete",
        ),
    )
    item = generation(rank, extension_path.stem, None if parent is None else parent.payload_sha256)
    item = replace(
        item,
        attempt_sha256=attempt_sha,
        parent_parameter_sha256=None if parent is None else parent.payload["parameter_sha256"],
        parent_optimizer_state_sha256=(
            None if parent is None else parent.payload["optimizer_state_sha256"]
        ),
        parameter_sha256=parameter,
        optimizer_state_sha256=optimizer,
        terminal_snapshot_sha256=snapshot_sha,
    )
    return publish_generation(seed_root, item)


def test_claim_and_all_publications_are_create_only(tmp_path):
    seed_root = tmp_path / "seed=0"
    owner_path = claim_seed_root(seed_root, owner())
    assert owner_path.parent == seed_root / "owner"
    assert not owner_path.is_symlink()

    with pytest.raises(FileExistsError):
        claim_seed_root(seed_root, owner())

    extension_path = publish_extension(seed_root, 1)
    extensions = extension_path.parent
    ext = RankExtension(
        **validate_envelope(extension_path, "challenge15.rank-extension.v1")
    )
    assert extension_path.name == f"{payload_sha256(ext.to_payload())}.json"
    with pytest.raises(FileExistsError):
        create_rank_extension(
            extensions,
            RankExtension(**validate_envelope(extension_path, "challenge15.rank-extension.v1")),
        )

    publish_completed_generation(seed_root, 1, extension_path)
    attempt = next(
        item
        for item in (seed_root / "attempts").iterdir()
        if (item / "snapshots").is_dir()
    )
    snapshot_path = next((attempt / "snapshots").glob("*.json"))
    snapshot = TrainingSnapshot(**validate_envelope(snapshot_path, "challenge15.training-snapshot.v1"))
    with pytest.raises(FileExistsError):
        publish_snapshot(attempt, snapshot)


def test_discovery_validates_complete_unique_chain_and_ignores_snapshots(tmp_path):
    seed_root = tmp_path / "seed=0"
    claim_seed_root(seed_root, owner())
    first_path = publish_extension(seed_root, 1)
    first = publish_completed_generation(seed_root, 1, first_path)
    first_verified = discover(seed_root, [first_path.stem])
    assert first_verified.rank == 1
    assert first_verified.payload_sha256 == first

    second_path = publish_extension(seed_root, 2, first_verified)
    second = publish_completed_generation(seed_root, 2, second_path, first_verified)
    terminal = discover(
        seed_root, [first_path.stem, second_path.stem]
    )
    assert terminal.rank == 2
    assert terminal.payload_sha256 == second

    interrupted = seed_root / "attempts" / "interrupted" / "snapshots"
    interrupted.mkdir(parents=True)
    (interrupted / "partial").write_text("incomplete")
    assert discover(
        seed_root, [first_path.stem, second_path.stem]
    ).payload_sha256 == second


def test_discovery_rejects_forks_tampering_staleness_and_symlinks(tmp_path):
    seed_root = tmp_path / "seed=0"
    claim_seed_root(seed_root, owner())
    ext_path = publish_extension(seed_root, 1)
    generation_sha = publish_completed_generation(seed_root, 1, ext_path)

    manifest = seed_root / "generations" / generation_sha / "manifest.json"
    document = json.loads(manifest.read_text())
    document["payload"]["source_manifest_sha256"] = "0" * 64
    manifest.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="SHA256|canonical"):
        discover(seed_root, [ext_path.stem])

    symlink_root = tmp_path / "linked"
    symlink_root.symlink_to(seed_root, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        discover(symlink_root, [ext_path.stem])


def test_discovery_rejects_undeclared_and_duplicate_rank_candidates(tmp_path):
    seed_root = tmp_path / "seed=0"
    claim_seed_root(seed_root, owner())
    ext_path = publish_extension(seed_root, 1)
    publish_completed_generation(seed_root, 1, ext_path)
    publish_completed_generation(seed_root, 1, ext_path, variant="fork")
    with pytest.raises(ValueError, match="duplicate rank|multiple|fork"):
        discover(seed_root, [ext_path.stem])


def test_extension_filename_must_match_payload_hash(tmp_path):
    seed_root = tmp_path / "seed=0"
    claim_seed_root(seed_root, owner())
    extensions_dir = seed_root / "extensions"
    extensions_dir.mkdir()
    ext = extension(1)
    wrong = extensions_dir / f"{'0' * 64}.json"
    wrong.write_bytes(canonical_json(envelope_for("challenge15.rank-extension.v1", ext)) + b"\n")

    with pytest.raises(ValueError, match="filename"):
        discover(seed_root, ["0" * 64])


def _intent(namespace: Path) -> OrchestrationAttemptIntent:
    initial = OrchestrationAttemptIntent(
        state_key_sha256=SHA,
        transition_identity_sha256="b" * 64,
        attempt=1,
        action_kind="rank-extension",
        correlation_id="0" * 64,
        source_controller=None,
        destination_controller="qdeshell",
        script_sha256="c" * 64,
        canonical_argv_sha256="d" * 64,
        input_sha256s=("e" * 64,),
        profile_sha256="f" * 64,
        deployment_receipt_sha256="1" * 64,
        runtime_set_sha256="2" * 64,
        source_manifest_sha256=SHA,
        policy_sha256=policy_sha256(),
        base_configuration_sha256=BASE_SHA,
        particles=6,
        seed=0,
        rank=1,
        parent_sha256s={
            "parent_generation_sha256": None,
            "parent_parameter_sha256": None,
            "parent_optimizer_state_sha256": None,
        },
        expected_output_identities=(
            {
                "output_schema": "challenge15.rank-extension.v1",
                "particles": 6,
                "seed": 0,
                "experiment_id": "experiment",
                "base_configuration_sha256": BASE_SHA,
                "policy_sha256": policy_sha256(),
                "source_manifest_sha256": SHA,
                "runtime_attestations": RUNTIMES,
                "previous_rank": None,
                "new_rank": 1,
                "parent_generation_sha256": None,
                "parent_parameter_sha256": None,
                "parent_optimizer_state_sha256": None,
                "rank_extension_decision_sha256": payload_sha256(
                    decision(1).to_payload()
                ),
                "rank_growth_prng": {
                    "algorithm": "threefry2x32",
                    "key_sha256": SHA,
                },
            },
        ),
        create_only_namespace_identities=(str(namespace.absolute()),),
        scheduler_job_name=None,
        scheduler_comment=None,
        remote_claim_path_identity=None,
        created_at_utc="2026-07-29T00:00:00Z",
    )
    return replace(initial, correlation_id=attempt_correlation_id(initial))


def test_intent_bounded_selector_adopts_one_and_rejects_multiple_or_tampered(tmp_path):
    namespace = tmp_path / "extensions"
    namespace.mkdir()
    intent = _intent(namespace)
    assert select_published(intent, namespace) is None

    decisions = tmp_path / "decisions"
    decisions.mkdir()
    decision_path = create_rank_extension_decision(decisions, decision(1))
    first = extension(1, decision_sha=decision_path.stem)
    first_path = create_rank_extension(namespace, first)
    selected = select_published(intent, namespace)
    assert selected is not None
    assert selected.path == first_path

    second = replace(first, created_by_git_revision="different")
    create_rank_extension(namespace, second)
    with pytest.raises(ValueError, match="multiple"):
        select_published(intent, namespace)

    first_path.write_text(first_path.read_text().replace('"seed":0', '"seed":4'))
    with pytest.raises(ValueError, match="SHA256"):
        select_published(intent, namespace)


def test_extension_publication_requires_and_binds_stored_decision(tmp_path):
    seed_root = tmp_path / "seed=0"
    claim_seed_root(seed_root, owner())
    extensions = seed_root / "extensions"
    extensions.mkdir()
    ext = extension(1)

    with pytest.raises(ValueError, match="decision"):
        create_rank_extension(extensions, ext)

    decisions = seed_root / "decisions"
    decisions.mkdir()
    decision_path = create_rank_extension_decision(decisions, decision(1))
    bound = replace(ext, rank_extension_decision_sha256=decision_path.stem)
    assert create_rank_extension(extensions, bound).is_file()


def test_snapshot_requires_matching_running_attempt_owner_and_extension(tmp_path):
    seed_root = tmp_path / "seed=0"
    claim_seed_root(seed_root, owner())
    extension_path = publish_extension(seed_root, 1)
    owner_sha = next((seed_root / "owner").glob("*.json")).stem
    attempt = TrainingAttempt(
        seed=0,
        rank=1,
        attempt_id="attempt",
        owner_sha256=owner_sha,
        extension_sha256=extension_path.stem,
        started_from_snapshot_sha256=None,
        resource_override=None,
        terminal_snapshot_sha256=None,
        status="running",
    )
    publish_training_attempt(seed_root, attempt)
    attempt_dir = next((seed_root / "attempts").iterdir())
    blob = publish_blob(seed_root, b"state")
    snapshot = TrainingSnapshot(
        policy_sha256=policy_sha256(),
        source_manifest_sha256=SHA,
        runtime_attestations=RUNTIMES,
        base_configuration_sha256=BASE_SHA,
        particles=6,
        seed=0,
        rank=1,
        attempt_id="wrong-attempt",
        step=1,
        parameter_sha256=blob,
        optimizer_state_sha256=blob,
        walker_state_sha256=blob,
        log_amplitude_sha256=blob,
        prng_state_sha256=blob,
        proposal_state=contract_fixture(
            SCIENTIFIC_NESTED_CONTRACTS[
                "challenge15.training-snapshot.v1"
            ]["proposal_state"]
        ),
        diagnostics=contract_fixture(
            SCIENTIFIC_NESTED_CONTRACTS[
                "challenge15.training-snapshot.v1"
            ]["diagnostics"]
        ),
    )

    with pytest.raises(ValueError, match="attempt"):
        publish_snapshot(attempt_dir, snapshot)


def test_generation_requires_completed_attempt_terminal_snapshot_and_blobs(tmp_path):
    seed_root = tmp_path / "seed=0"
    claim_seed_root(seed_root, owner())
    extension_path = publish_extension(seed_root, 1)

    with pytest.raises(ValueError, match="attempt"):
        publish_generation(seed_root, generation(1, extension_path.stem))


def test_selector_registry_is_exhaustive_and_schema_cannot_be_overridden(tmp_path):
    assert set(PUBLISHER_SELECTOR_REGISTRY) == {
        "challenge15.seed-owner.v1",
        "challenge15.rank-extension.v1",
        "challenge15.training-attempt.v1",
        "challenge15.training-snapshot.v1",
        "challenge15.training-generation.v1",
        "challenge15.coordinate-evaluation-shard.v1",
        "challenge15.exact-evaluation-shard.v1",
        "challenge15.size-result.v1",
        "challenge15.reduction-receipt.v1",
        "challenge15.export-bundle.v1",
        "challenge15.import-bundle.v1",
        "challenge15.transfer-receipt.v1",
        "challenge15.reduction-finalization.v1",
        "challenge15.terminal-selection.v1",
    }
    assert set(PUBLISHER_SELECTOR_REGISTRY) == set(SELECTOR_REQUIRED_CONSTRAINTS)
    assert all(SELECTOR_REQUIRED_CONSTRAINTS.values())
    namespace = tmp_path / "extensions"
    namespace.mkdir()
    intent = _intent(namespace)
    with pytest.raises(ValueError, match="override"):
        select_published(
            intent,
            namespace,
            output_schema="challenge15.seed-owner.v1",
        )


def test_selector_rejects_unmatched_intent_constraint(tmp_path):
    namespace = tmp_path / "extensions"
    namespace.mkdir()
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    decision_path = create_rank_extension_decision(decisions, decision(1))
    create_rank_extension(
        namespace,
        extension(1, decision_sha=decision_path.stem),
    )
    intent = _intent(namespace)
    identities = list(intent.expected_output_identities)
    identities[0] = {**identities[0], "owner_sha256": "f" * 64}
    broken = replace(intent, expected_output_identities=tuple(identities))
    broken = replace(broken, correlation_id=attempt_correlation_id(broken))

    with pytest.raises(ValueError, match="constraint"):
        select_published(broken, namespace)


def test_selector_treats_valid_wrong_identity_candidate_as_tamper(tmp_path):
    namespace = tmp_path / "extensions"
    namespace.mkdir()
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    decision_path = create_rank_extension_decision(decisions, decision(1))
    create_rank_extension(namespace, extension(1, decision_sha=decision_path.stem))
    intent = _intent(namespace)
    identities = list(intent.expected_output_identities)
    identities[0] = {**identities[0], "seed": 4}
    broken = replace(intent, expected_output_identities=tuple(identities))
    broken = replace(broken, correlation_id=attempt_correlation_id(broken))

    with pytest.raises(ValueError, match="tamper"):
        select_published(broken, namespace)


def test_selector_rejects_multiple_declared_namespaces(tmp_path):
    namespace = tmp_path / "extensions"
    namespace.mkdir()
    intent = _intent(namespace)
    broken = replace(
        intent,
        create_only_namespace_identities=(
            str(namespace.absolute()),
            str((tmp_path / "other").absolute()),
        ),
    )
    broken = replace(broken, correlation_id=attempt_correlation_id(broken))
    with pytest.raises(ValueError, match="exactly one"):
        select_published(broken, namespace)


def test_seed_claim_rename_failure_leaves_only_external_staging(
    tmp_path, monkeypatch
):
    seed_root = tmp_path / "seed=0"

    def fail_rename(*_args, **_kwargs):
        raise OSError("injected seed rename")

    original = generations_module._rename_noreplace
    monkeypatch.setattr(generations_module, "_rename_noreplace", fail_rename)
    with pytest.raises(OSError, match="seed rename"):
        claim_seed_root(seed_root, owner())

    assert not seed_root.exists()
    staging = tmp_path / ".challenge15-staging"
    assert staging.is_dir()
    assert len(tuple(path for path in staging.iterdir() if path.name != ".publication.lock")) == 1
    monkeypatch.setattr(generations_module, "_rename_noreplace", original)
    recovered = claim_seed_root(seed_root, owner())
    assert recovered.is_file()
    assert not tuple(path for path in staging.iterdir() if path.name != ".publication.lock")


def test_attempt_directory_failure_never_stages_inside_attempt_namespace(
    tmp_path, monkeypatch
):
    seed_root = tmp_path / "seed=0"
    claim_seed_root(seed_root, owner())
    extension_path = publish_extension(seed_root, 1)
    owner_sha = next((seed_root / "owner").glob("*.json")).stem
    attempt = TrainingAttempt(
        seed=0,
        rank=1,
        attempt_id="attempt",
        owner_sha256=owner_sha,
        extension_sha256=extension_path.stem,
        started_from_snapshot_sha256=None,
        resource_override=None,
        terminal_snapshot_sha256=None,
        status="running",
    )

    def fail_rename(*_args, **_kwargs):
        raise OSError("injected attempt rename")

    monkeypatch.setattr(generations_module, "_rename_noreplace", fail_rename)
    with pytest.raises(OSError, match="attempt rename"):
        publish_training_attempt(seed_root, attempt)

    assert not tuple((seed_root / "attempts").iterdir())
    assert len(tuple((seed_root / ".staging").iterdir())) == 1


def test_seed_replacement_inode_is_quarantined_not_published(tmp_path, monkeypatch):
    seed_root = tmp_path / "seed=0"
    original = generations_module._rename_noreplace
    replaced = False

    def replace_source(directory_fd, source, destination, destination_fd=None):
        nonlocal replaced
        if not replaced and destination == seed_root.name:
            replaced = True
            os.rename(source, f".owned.{source}", src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            os.mkdir(source, 0o700, dir_fd=directory_fd)
        return original(directory_fd, source, destination, destination_fd)

    monkeypatch.setattr(generations_module, "_rename_noreplace", replace_source)
    with pytest.raises(ValueError, match="inode mismatch"):
        claim_seed_root(seed_root, owner())
    assert not seed_root.exists()
    assert any(
        path.name.startswith(".rejected.seed=0")
        for path in (tmp_path / ".challenge15-staging").iterdir()
    )


@pytest.mark.parametrize("mutation", ["runtime", "prng"])
def test_selector_rejects_rehashed_wrong_provenance_as_tamper(tmp_path, mutation):
    namespace = tmp_path / "extensions"
    namespace.mkdir()
    candidate = extension(1)
    if mutation == "runtime":
        runtime = {role: dict(value) for role, value in RUNTIMES.items()}
        runtime["training"]["qdeshell"] = "f" * 64
        candidate = replace(candidate, runtime_attestations=runtime)
    else:
        candidate = replace(
            candidate,
            rank_growth_prng={
                "algorithm": "threefry2x32",
                "key_sha256": "f" * 64,
            },
        )
    digest = payload_sha256(candidate.to_payload())
    publish_production_envelope(
        namespace / f"{digest}.json",
        "challenge15.rank-extension.v1",
        candidate,
    )

    with pytest.raises(ValueError, match="tamper"):
        select_published(_intent(namespace), namespace)


def test_resource_override_loads_schedule_and_binds_failed_attempt(tmp_path):
    seed_root = tmp_path / "seed=0"
    claim_seed_root(seed_root, owner())
    extension_path = publish_extension(seed_root, 1)
    owner_sha = next((seed_root / "owner").glob("*.json")).stem
    failed = TrainingAttempt(
        seed=0,
        rank=1,
        attempt_id="failed",
        owner_sha256=owner_sha,
        extension_sha256=extension_path.stem,
        started_from_snapshot_sha256=None,
        resource_override=None,
        terminal_snapshot_sha256=None,
        status="failed",
    )
    failed_sha = publish_training_attempt(seed_root, failed)
    schedule = {
        **BASE_CONFIG,
        "policy_sha256": policy_sha256(),
        "source_manifest_sha256": SHA,
        "runtime_attestations": RUNTIMES,
        "particles": 6,
        "base_configuration_sha256": BASE_SHA,
        "seed": 0,
        "rank": 1,
        "owner_sha256": owner_sha,
        "extension_sha256": extension_path.stem,
        "schedule_version": "fixed-v1",
    }
    schedule_digest = payload_sha256(schedule)
    configurations = seed_root / "base-configurations"
    configurations.mkdir()
    publish_create_only(
        configurations / f"{BASE_SHA}.json",
        canonical_json(production_vmc_config_envelope(BASE_CONFIG)) + b"\n",
    )
    schedules = seed_root / "schedules"
    schedules.mkdir()
    publish_create_only(
        schedules / f"{schedule_digest}.json",
        canonical_json(fixed_schedule_envelope(schedule)) + b"\n",
    )
    override_payload = {
        "policy_sha256": policy_sha256(),
        "source_manifest_sha256": SHA,
        "runtime_attestations": RUNTIMES,
        "base_configuration_sha256": BASE_SHA,
        "particles": 6,
        "seed": 0,
        "rank": 1,
        "extension_sha256": extension_path.stem,
        "attempt_sha256": failed_sha,
        "reason": "oom",
        "walker_microbatch": 1,
        "carrier_block": 1,
        "quadrature_block": 1,
        "fixed_schedule_sha256": schedule_digest,
        "metric_equivalence": contract_fixture(
            SCIENTIFIC_NESTED_CONTRACTS[
                "challenge15.resource-override.v1"
            ]["metric_equivalence"]
        ),
    }
    override_payload["metric_equivalence"]["classification"] = "pending"
    override_path = tmp_path / "override.json"
    override_digest = payload_sha256(override_payload)
    publish_production_envelope(
        override_path,
        "challenge15.resource-override.v1",
        override_payload,
    )
    retry = TrainingAttempt(
        seed=0,
        rank=1,
        attempt_id="retry",
        owner_sha256=owner_sha,
        extension_sha256=extension_path.stem,
        started_from_snapshot_sha256=None,
        resource_override={
            "path": str(override_path.absolute()),
            "payload_sha256": override_digest,
        },
        terminal_snapshot_sha256=None,
        status="running",
    )
    assert publish_training_attempt(seed_root, retry)

    wrong_schedule = {**schedule, "source_manifest_sha256": "f" * 64}
    wrong_digest = payload_sha256(wrong_schedule)
    publish_create_only(
        schedules / f"{wrong_digest}.json",
        canonical_json(fixed_schedule_envelope(wrong_schedule)) + b"\n",
    )
    wrong_override = {
        **override_payload,
        "fixed_schedule_sha256": wrong_digest,
    }
    wrong_override_path = tmp_path / "wrong-override.json"
    publish_production_envelope(
        wrong_override_path,
        "challenge15.resource-override.v1",
        wrong_override,
    )
    with pytest.raises(ValueError, match="schedule source"):
        publish_training_attempt(
            seed_root,
            replace(
                retry,
                attempt_id="wrong-schedule",
                resource_override={
                    "path": str(wrong_override_path.absolute()),
                    "payload_sha256": payload_sha256(wrong_override),
                },
            ),
        )

    tampered = json.loads((schedules / f"{schedule_digest}.json").read_text())
    tampered["payload"]["draws_per_update"] += 1
    (schedules / f"{schedule_digest}.json").write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="schedule"):
        publish_training_attempt(seed_root, replace(retry, attempt_id="retry-2"))


@pytest.mark.parametrize("boundary,published", [("before-rename", False), ("after-rename", True)])
def test_sigkill_seed_publication_has_atomic_visibility(tmp_path, boundary, published):
    seed_root = tmp_path / "seed=0"
    process = multiprocessing.get_context("spawn").Process(
        target=_kill_directory_publication,
        args=("seed", seed_root, owner().to_payload(), f"seed-{boundary}"),
    )
    process.start()
    process.join(timeout=10)
    assert process.exitcode == -signal.SIGKILL
    assert seed_root.exists() is published
    if published:
        assert next((seed_root / "owner").glob("*.json"))
    else:
        assert claim_seed_root(seed_root, owner()).is_file()


@pytest.mark.parametrize("kind", ["attempt", "generation"])
@pytest.mark.parametrize("boundary,published", [("before-rename", False), ("after-rename", True)])
def test_sigkill_directory_publishers_have_atomic_visibility(
    tmp_path, kind, boundary, published
):
    seed_root = tmp_path / "seed=0"
    claim_seed_root(seed_root, owner())
    extension_path = publish_extension(seed_root, 1)
    if kind == "attempt":
        owner_sha = next((seed_root / "owner").glob("*.json")).stem
        value = TrainingAttempt(
            seed=0,
            rank=1,
            attempt_id="kill",
            owner_sha256=owner_sha,
            extension_sha256=extension_path.stem,
            started_from_snapshot_sha256=None,
            resource_override=None,
            terminal_snapshot_sha256=None,
            status="running",
        )
        namespace = seed_root / "attempts"
    else:
        generation_sha = publish_completed_generation(seed_root, 1, extension_path)
        generation_path = seed_root / "generations" / generation_sha / "manifest.json"
        value = TrainingGeneration(
            **validate_envelope(
                generation_path, "challenge15.training-generation.v1"
            )
        )
        shutil.rmtree(generation_path.parent)
        namespace = seed_root / "generations"
    process = multiprocessing.get_context("spawn").Process(
        target=_kill_directory_publication,
        args=(kind, seed_root, value.to_payload(), f"{kind}-{boundary}"),
    )
    process.start()
    process.join(timeout=10)
    assert process.exitcode == -signal.SIGKILL
    canonical = tuple(namespace.iterdir())
    assert bool(canonical) is published
    if not published:
        if kind == "attempt":
            publish_training_attempt(seed_root, value)
        else:
            publish_generation(seed_root, value)
