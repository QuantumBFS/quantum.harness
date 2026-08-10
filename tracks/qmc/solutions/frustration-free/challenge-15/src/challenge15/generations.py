"""Append-only seed ownership, rank extension, snapshot, and generation trees."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import fcntl
import os
from pathlib import Path
import stat
import signal
from typing import Any, Mapping, Sequence
import uuid

from .artifacts import (
    _fsync_directory,
    _fsync_directory_fd,
    _open_directory_fd,
    _reject_symlink_components,
    _rename_noreplace,
    publish_production_envelope,
)
from .production_schema import (
    OrchestrationAttemptIntent,
    RankExtension,
    RankExtensionDecision,
    SeedOwner,
    TrainingAttempt,
    TrainingGeneration,
    TrainingSnapshot,
    payload_sha256,
    validate_envelope,
    validate_fixed_schedule_envelope,
    validate_production_vmc_config_envelope,
    validate_rank_extension,
    validate_rank_extension_decision,
    validate_orchestration_attempt_intent,
    validate_seed_owner,
    validate_training_generation,
    validate_training_snapshot,
)


@dataclass(frozen=True, slots=True)
class VerifiedGeneration:
    path: Path
    payload_sha256: str
    payload: Mapping[str, Any]

    @property
    def rank(self) -> int:
        return int(self.payload["rank"])


@dataclass(frozen=True, slots=True)
class ValidatedCandidate:
    path: Path
    schema: str
    payload_sha256: str
    payload: Mapping[str, Any]


def _publication_killpoint(name: str) -> None:
    if os.environ.get("CHALLENGE15_PUBLICATION_KILLPOINT") == name:
        os.kill(os.getpid(), signal.SIGKILL)


PUBLISHER_SELECTOR_REGISTRY = {
    "challenge15.seed-owner.v1": "content-addressed-files",
    "challenge15.rank-extension.v1": "content-addressed-files",
    "challenge15.training-attempt.v1": "attempt-manifest",
    "challenge15.training-snapshot.v1": "step-content-addressed-files",
    "challenge15.training-generation.v1": "generation-manifests",
    "challenge15.coordinate-evaluation-shard.v1": "content-addressed-files",
    "challenge15.exact-evaluation-shard.v1": "content-addressed-files",
    "challenge15.size-result.v1": "content-addressed-files",
    "challenge15.reduction-receipt.v1": "content-addressed-files",
    "challenge15.export-bundle.v1": "content-addressed-files",
    "challenge15.import-bundle.v1": "content-addressed-files",
    "challenge15.transfer-receipt.v1": "content-addressed-files",
    "challenge15.reduction-finalization.v1": "content-addressed-files",
    "challenge15.terminal-selection.v1": "content-addressed-files",
}

SELECTOR_REQUIRED_CONSTRAINTS = {
    "challenge15.seed-owner.v1": {
        "seed", "experiment_id", "base_configuration_sha256", "policy_sha256",
        "source_manifest_sha256", "runtime_attestations",
    },
    "challenge15.rank-extension.v1": {
        "particles", "seed", "experiment_id", "base_configuration_sha256",
        "policy_sha256", "source_manifest_sha256", "runtime_attestations",
        "previous_rank", "new_rank", "parent_generation_sha256",
        "parent_parameter_sha256", "parent_optimizer_state_sha256",
        "rank_extension_decision_sha256", "rank_growth_prng",
    },
    "challenge15.training-attempt.v1": {
        "seed", "rank", "attempt_id", "owner_sha256", "extension_sha256",
        "started_from_snapshot_sha256", "resource_override",
        "terminal_snapshot_sha256",
    },
    "challenge15.training-snapshot.v1": {
        "seed", "rank", "attempt_id", "step", "parameter_sha256",
        "optimizer_state_sha256", "walker_state_sha256",
        "log_amplitude_sha256", "prng_state_sha256", "policy_sha256",
        "source_manifest_sha256", "runtime_attestations",
        "base_configuration_sha256", "particles",
    },
    "challenge15.training-generation.v1": {
        "seed", "rank", "attempt_sha256", "extension_sha256",
        "parent_generation_sha256", "parent_parameter_sha256",
        "parent_optimizer_state_sha256", "parameter_sha256",
        "optimizer_state_sha256", "terminal_snapshot_sha256",
        "policy_sha256", "source_manifest_sha256", "runtime_attestations",
        "base_configuration_sha256", "particles",
    },
    "challenge15.coordinate-evaluation-shard.v1": {
        "seed", "rank", "generation_sha256", "parameter_sha256",
        "evaluation_prng_sha256", "policy_sha256", "source_manifest_sha256",
        "runtime_attestations", "base_configuration_sha256", "particles",
    },
    "challenge15.exact-evaluation-shard.v1": {
        "seed", "rank", "generation_sha256", "oracle_sha256",
        "parameter_sha256", "policy_sha256", "source_manifest_sha256",
        "runtime_attestations", "base_configuration_sha256", "particles",
    },
    "challenge15.size-result.v1": {
        "expected_ranks", "expected_seeds", "oracle_sha256",
        "generation_sha256_by_identity", "exact_sha256_by_identity",
        "coordinate_sha256_by_identity", "coordinate_uncertainty_by_rank",
        "prerequisite", "policy_sha256",
        "source_manifest_sha256", "runtime_attestations",
        "base_configuration_sha256", "particles",
    },
    "challenge15.reduction-receipt.v1": {
        "canonical_payload_sha256", "policy_sha256",
        "source_manifest_sha256", "runtime_attestations",
        "base_configuration_sha256", "particles",
    },
    "challenge15.export-bundle.v1": {
        "bundle_role", "source_controller", "source_root",
        "source_artifact_sha256", "member_manifest", "sha256sums_sha256",
        "bundle_sha256", "policy_sha256", "source_manifest_sha256",
        "runtime_attestations", "base_configuration_sha256", "particles",
    },
    "challenge15.import-bundle.v1": {
        "bundle_sha256", "destination_controller", "destination_root",
        "member_manifest", "imported_artifact_sha256", "policy_sha256",
        "source_manifest_sha256", "runtime_attestations",
        "base_configuration_sha256", "particles",
    },
    "challenge15.transfer-receipt.v1": {
        "direction", "export_bundle_sha256", "import_bundle_sha256",
        "source_controller", "destination_controller", "source_identity",
        "destination_identity", "partial_path", "final_path", "bytes",
        "attempt_intent_sha256", "correlation_id", "remote_claim_sha256",
        "policy_sha256", "source_manifest_sha256", "runtime_attestations",
        "base_configuration_sha256", "particles",
    },
    "challenge15.reduction-finalization.v1": {
        "expected_ranks", "expected_ranks_sha256",
        "selected_reduction_sha256", "selected_reduction_path",
        "production_accepted", "policy_sha256", "source_manifest_sha256",
        "runtime_attestations", "base_configuration_sha256", "particles",
    },
    "challenge15.terminal-selection.v1": {
        "selected_expected_ranks_sha256", "selected_finalization_sha256",
        "selected_reduction_sha256", "production_accepted",
        "policy_sha256", "source_manifest_sha256", "runtime_attestations",
        "base_configuration_sha256", "particles",
    },
}

if set(PUBLISHER_SELECTOR_REGISTRY) != set(SELECTOR_REQUIRED_CONSTRAINTS):
    raise RuntimeError("selector registry and required constraints differ")


def claim_seed_root(path: Path, owner: SeedOwner) -> Path:
    """Claim a permanent seed root exactly once."""

    seed_root = Path(path)
    validate_seed_owner(owner)
    _reject_symlink_components(seed_root)
    if not seed_root.parent.is_dir():
        raise FileNotFoundError(f"seed root parent does not exist: {seed_root.parent}")
    staging_root = seed_root.parent / ".challenge15-staging"
    staging_root.mkdir(mode=0o700, exist_ok=True)
    _require_regular_directory(staging_root, "seed staging")
    os.chmod(staging_root, 0o700)
    staging_fd = _open_directory_fd(staging_root)
    lock_fd = os.open(
        ".publication.lock",
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=staging_fd,
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        return _claim_seed_root_locked(seed_root, owner, staging_root)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
        os.close(staging_fd)


def _claim_seed_root_locked(
    seed_root: Path,
    owner: SeedOwner,
    staging_root: Path,
) -> Path:
    recovered = _recover_staged_seed_claim(staging_root, seed_root, owner)
    if recovered is not None:
        return recovered
    staging_name = f"{seed_root.name}.{owner.owner_uuid}.{uuid.uuid4().hex}"
    staged_seed = staging_root / staging_name
    staged_seed.mkdir()
    try:
        _fsync_directory(staging_root)
        owner_dir = staged_seed / "owner"
        owner_dir.mkdir()
        _fsync_directory(staged_seed)
        digest = payload_sha256(owner.to_payload())
        owner_path = owner_dir / f"{digest}.json"
        publish_production_envelope(
            owner_path,
            "challenge15.seed-owner.v1",
            owner,
        )
        staged_fd = _open_directory_fd(staged_seed)
        _fsync_directory_fd(staged_fd)
        retained = os.fstat(staged_fd)
        staging_fd = _open_directory_fd(staging_root)
        parent_fd = _open_directory_fd(seed_root.parent)
        try:
            current = os.stat(staging_name, dir_fd=staging_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (retained.st_dev, retained.st_ino):
                raise ValueError("seed staging source inode changed")
            _publication_killpoint("seed-before-rename")
            _rename_noreplace(
                staging_fd,
                staging_name,
                seed_root.name,
                parent_fd,
            )
            _publication_killpoint("seed-after-rename")
            published = os.stat(
                seed_root.name, dir_fd=parent_fd, follow_symlinks=False
            )
            if (published.st_dev, published.st_ino) != (
                retained.st_dev,
                retained.st_ino,
            ):
                _rename_noreplace(
                    parent_fd,
                    seed_root.name,
                    f".rejected.{seed_root.name}.{uuid.uuid4().hex}",
                    staging_fd,
                )
                raise ValueError("published seed inode mismatch")
            _fsync_directory_fd(staging_fd)
            _fsync_directory_fd(parent_fd)
        finally:
            os.close(staged_fd)
            os.close(staging_fd)
            os.close(parent_fd)
        return seed_root / "owner" / f"{digest}.json"
    except BaseException:
        # Staging is deliberately retained. It is outside canonical namespaces
        # and may only be reclaimed by inode-bound recovery.
        _fsync_directory(seed_root.parent)
        raise


def _recover_staged_seed_claim(
    staging_root: Path,
    seed_root: Path,
    owner: SeedOwner,
) -> Path | None:
    candidates = sorted(staging_root.glob(f"{seed_root.name}.*"))
    if not candidates:
        return None
    valid: list[tuple[Path, Path, tuple[int, int]]] = []
    for candidate in candidates:
        metadata = os.lstat(candidate)
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise ValueError("occupied seed staging candidate is tamper evidence")
        owner_dir = candidate / "owner"
        files = tuple(owner_dir.glob("*.json")) if owner_dir.is_dir() else ()
        if len(files) != 1:
            raise ValueError("occupied seed staging candidate is tamper evidence")
        payload = validate_envelope(files[0], "challenge15.seed-owner.v1")
        if payload != owner.to_payload() or files[0].stem != payload_sha256(payload):
            raise ValueError("occupied seed staging candidate is tamper evidence")
        valid.append((candidate, files[0], (metadata.st_dev, metadata.st_ino)))
    if len(valid) != 1:
        raise ValueError("multiple recoverable seed staging candidates")
    candidate, owner_path, retained = valid[0]
    staging_fd = _open_directory_fd(staging_root)
    parent_fd = _open_directory_fd(seed_root.parent)
    try:
        current = os.stat(candidate.name, dir_fd=staging_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != retained:
            raise ValueError("recoverable seed staging inode changed")
        _rename_noreplace(
            staging_fd,
            candidate.name,
            seed_root.name,
            parent_fd,
        )
        published = os.stat(seed_root.name, dir_fd=parent_fd, follow_symlinks=False)
        if (published.st_dev, published.st_ino) != retained:
            raise ValueError("recovered seed inode mismatch")
        _fsync_directory_fd(staging_fd)
        _fsync_directory_fd(parent_fd)
    finally:
        os.close(staging_fd)
        os.close(parent_fd)
    return seed_root / "owner" / owner_path.name


def create_rank_extension(output_dir: Path, extension: RankExtension) -> Path:
    """Publish an extension under its canonical payload-derived filename."""

    directory = Path(output_dir)
    _require_regular_directory(directory, "rank extension output")
    decision = _read_decision(directory.parent, extension.rank_extension_decision_sha256)
    _validate_decision_parents(directory.parent, decision)
    validate_rank_extension(extension, decision)
    digest = payload_sha256(extension.to_payload())
    destination = directory / f"{digest}.json"
    publish_production_envelope(
        destination,
        "challenge15.rank-extension.v1",
        extension,
    )
    return destination


def create_rank_extension_decision(
    output_dir: Path,
    decision: RankExtensionDecision,
) -> Path:
    """Publish one immutable decision before its matching extension."""

    directory = Path(output_dir)
    _require_regular_directory(directory, "rank extension decision output")
    validate_rank_extension_decision(decision)
    digest = payload_sha256(decision.to_payload())
    destination = directory / f"{digest}.json"
    publish_production_envelope(
        destination,
        "challenge15.rank-extension-decision.v1",
        decision,
    )
    return destination


def publish_blob(seed_root: Path, data: bytes) -> str:
    """Publish one content-addressed binary blob beneath a claimed seed root."""

    root = _require_claimed_seed_root(seed_root)
    blobs = _ensure_child_directory(root, "blobs")
    digest = hashlib.sha256(data).hexdigest()
    from .artifacts import publish_create_only

    publish_create_only(blobs / digest, data)
    return digest


def publish_training_attempt(seed_root: Path, attempt: TrainingAttempt) -> str:
    """Create deterministic attempt metadata without starting VMC."""

    root = _require_claimed_seed_root(seed_root)
    owner_payload, owner_sha = _read_unique_owner(root)
    extension = _read_extension(root, attempt.extension_sha256)
    if attempt.seed != owner_payload["seed"] or attempt.seed != extension.seed:
        raise ValueError("training attempt seed does not match owner/extension")
    if attempt.rank != extension.new_rank:
        raise ValueError("training attempt rank does not match extension")
    if attempt.owner_sha256 != owner_sha:
        raise ValueError("training attempt owner SHA256 mismatch")
    if attempt.status not in {"created", "running", "failed", "complete"}:
        raise ValueError("training attempt status is invalid")
    for label, digest in (
        ("owner", attempt.owner_sha256),
        ("extension", attempt.extension_sha256),
    ):
        _require_sha(digest, label)
    if attempt.started_from_snapshot_sha256 is not None:
        snapshot, _ = _read_snapshot_by_sha(
            root, attempt.started_from_snapshot_sha256
        )
        if snapshot["seed"] != attempt.seed or snapshot["rank"] != attempt.rank:
            raise ValueError("attempt starting snapshot identity mismatch")
        for field in (
            "policy_sha256",
            "source_manifest_sha256",
            "runtime_attestations",
            "base_configuration_sha256",
            "particles",
        ):
            if snapshot[field] != extension.to_payload()[field]:
                raise ValueError(f"attempt starting snapshot {field} mismatch")
    if attempt.resource_override is not None:
        if not isinstance(attempt.resource_override, Mapping) or set(
            attempt.resource_override
        ) != {"path", "payload_sha256"}:
            raise ValueError("resource override reference fields mismatch")
        override_path = Path(str(attempt.resource_override["path"]))
        if not override_path.is_absolute() or override_path.is_symlink():
            raise ValueError("resource override path is not canonical")
        override = validate_envelope(
            override_path,
            "challenge15.resource-override.v1",
        )
        if payload_sha256(override) != attempt.resource_override["payload_sha256"]:
            raise ValueError("resource override SHA256 mismatch")
        for field, expected in (
            ("seed", attempt.seed),
            ("rank", attempt.rank),
            ("extension_sha256", attempt.extension_sha256),
            ("base_configuration_sha256", extension.base_configuration_sha256),
        ):
            if override[field] != expected:
                raise ValueError(f"resource override {field} mismatch")
        if override["reason"] != "oom":
            raise ValueError("resource override reason must be oom")
        prior_attempt, _ = _read_attempt_by_sha(
            root, str(override["attempt_sha256"])
        )
        if prior_attempt["status"] != "failed":
            raise ValueError("resource override parent attempt is not failed")
        for field in ("seed", "rank", "extension_sha256"):
            if prior_attempt[field] != override[field]:
                raise ValueError(f"resource override attempt {field} mismatch")
        schedule_digest = str(override["fixed_schedule_sha256"])
        _require_sha(schedule_digest, "fixed schedule")
        schedule_path = root / "schedules" / f"{schedule_digest}.json"
        schedule = validate_fixed_schedule_envelope(schedule_path)
        if payload_sha256(schedule) != schedule_digest:
            raise ValueError("fixed schedule content hash mismatch")
        expected_schedule = {
            "policy_sha256": extension.policy_sha256,
            "source_manifest_sha256": extension.source_manifest_sha256,
            "runtime_attestations": extension.runtime_attestations,
            "base_configuration_sha256": extension.base_configuration_sha256,
            "particles": extension.particles,
            "seed": attempt.seed,
            "rank": attempt.rank,
            "owner_sha256": attempt.owner_sha256,
            "extension_sha256": attempt.extension_sha256,
        }
        for field, expected in expected_schedule.items():
            if schedule[field] != expected:
                raise ValueError(f"fixed schedule {field} lineage mismatch")
        config_path = (
            root
            / "base-configurations"
            / f"{schedule['base_configuration_sha256']}.json"
        )
        config = validate_production_vmc_config_envelope(config_path)
        if payload_sha256(config) != schedule["base_configuration_sha256"]:
            raise ValueError("production VMC config content hash mismatch")
        frozen_fields = (
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
        )
        for field in frozen_fields:
            if schedule[field] != config[field]:
                raise ValueError(f"fixed schedule/config {field} mismatch")
    if attempt.status == "complete":
        attempts = root / "attempts"
        running = replace(
            attempt,
            terminal_snapshot_sha256=None,
            status="running",
        )
        running_dir = attempts / _attempt_identity(running.to_payload())
        running_path = running_dir / "attempt.json"
        if not running_path.is_file():
            raise ValueError("completed attempt requires one immutable running attempt")
        running_payload = validate_envelope(
            running_path, "challenge15.training-attempt.v1"
        )
        if running_payload != running.to_payload():
            raise ValueError("completed attempt running identity mismatch")
        snapshots = running_dir / "snapshots"
        terminal = str(attempt.terminal_snapshot_sha256)
        matches = tuple(snapshots.glob(f"*-{terminal}.json")) if snapshots.is_dir() else ()
        if len(matches) != 1:
            raise ValueError("completed attempt requires a terminal snapshot")
    attempt_identity = _attempt_identity(attempt.to_payload())
    attempts = _ensure_child_directory(root, "attempts")
    digest = _publish_envelope_directory(
        attempts,
        attempt_identity,
        "attempt.json",
        "challenge15.training-attempt.v1",
        attempt,
        staging_parent=root / ".staging",
    )
    return digest


def publish_snapshot(attempt: Path, snapshot: TrainingSnapshot) -> str:
    """Publish one immutable checkpoint beneath an existing attempt."""

    attempt_dir = Path(attempt)
    _require_regular_directory(attempt_dir, "training attempt")
    if attempt_dir.parent.name != "attempts":
        raise ValueError("snapshot attempt path is outside the seed attempts namespace")
    seed_root = attempt_dir.parent.parent
    owner_payload, owner_sha = _read_unique_owner(_require_claimed_seed_root(seed_root))
    attempt_payload = validate_envelope(
        attempt_dir / "attempt.json",
        "challenge15.training-attempt.v1",
    )
    if attempt_payload["status"] != "running":
        raise ValueError("snapshots must bind an immutable running attempt")
    if attempt_dir.name != _attempt_identity(attempt_payload):
        raise ValueError("snapshot attempt directory identity mismatch")
    extension = _read_extension(seed_root, str(attempt_payload["extension_sha256"]))
    if attempt_payload["owner_sha256"] != owner_sha:
        raise ValueError("snapshot attempt owner does not match seed owner")
    if (
        snapshot.attempt_id != attempt_payload["attempt_id"]
        or snapshot.seed != attempt_payload["seed"]
        or snapshot.rank != attempt_payload["rank"]
    ):
        raise ValueError("snapshot identity does not match training attempt")
    if snapshot.seed != owner_payload["seed"] or snapshot.rank != extension.new_rank:
        raise ValueError("snapshot does not match owner and extension")
    for field in (
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
        "base_configuration_sha256",
        "particles",
    ):
        if snapshot.to_payload()[field] != extension.to_payload()[field]:
            raise ValueError(f"snapshot {field} does not match extension")
    validate_training_snapshot(snapshot)
    for digest in (
        snapshot.parameter_sha256,
        snapshot.optimizer_state_sha256,
        snapshot.walker_state_sha256,
        snapshot.log_amplitude_sha256,
        snapshot.prng_state_sha256,
    ):
        _validate_blob(seed_root, digest)
    snapshots = attempt_dir / "snapshots"
    if snapshots.exists():
        _require_regular_directory(snapshots, "snapshot")
    else:
        snapshots.mkdir()
        _fsync_directory(attempt_dir)
    digest = payload_sha256(snapshot.to_payload())
    publish_production_envelope(
        snapshots / f"{snapshot.step}-{digest}.json",
        "challenge15.training-snapshot.v1",
        snapshot,
    )
    return digest


def publish_generation(seed_root: Path, generation: TrainingGeneration) -> str:
    """Publish one terminal training generation, without running VMC."""

    root = _require_claimed_seed_root(seed_root)
    owner_payload, _ = _read_unique_owner(root)
    validate_training_generation(generation)
    extension = _read_extension(root, generation.extension_sha256)
    _validate_generation_against_extension(generation.to_payload(), extension, owner_payload)
    _validate_generation_artifacts(root, generation.to_payload())
    generations = _ensure_child_directory(root, "generations")
    digest = payload_sha256(generation.to_payload())
    _publish_envelope_directory(
        generations,
        digest,
        "manifest.json",
        "challenge15.training-generation.v1",
        generation,
        staging_parent=root / ".staging",
    )
    return digest


def discover_unique_terminal_generation(
    seed_root: Path,
    expected_extensions: Sequence[str],
    *,
    expected_policy_sha256: str,
    expected_source_manifest_sha256: str,
    expected_runtime_attestations: Mapping[str, Mapping[str, str]],
    expected_base_configuration_sha256: str,
    expected_particles: int,
    expected_seed: int,
    expected_experiment_id: str,
    expected_canonical_root: Path,
) -> VerifiedGeneration:
    """Validate the entire declared generation chain and return its sole tip."""

    root = _require_claimed_seed_root(seed_root)
    if root.absolute() != Path(expected_canonical_root).absolute():
        raise ValueError("seed root canonical identity mismatch")
    owner_payload, _ = _read_unique_owner(root)
    expected_identity = {
        "policy_sha256": expected_policy_sha256,
        "source_manifest_sha256": expected_source_manifest_sha256,
        "runtime_attestations": {
            role: dict(controllers)
            for role, controllers in expected_runtime_attestations.items()
        },
        "base_configuration_sha256": expected_base_configuration_sha256,
        "seed": expected_seed,
        "experiment_id": expected_experiment_id,
    }
    for field, expected_value in expected_identity.items():
        if owner_payload[field] != expected_value:
            raise ValueError(f"seed owner has stale expected {field}")
    expected = tuple(expected_extensions)
    if len(set(expected)) != len(expected):
        raise ValueError("expected extensions contain duplicates")
    for digest in expected:
        _require_sha(digest, "expected extension")
    extensions = [_read_extension(root, digest) for digest in expected]
    if any(extension.particles != expected_particles for extension in extensions):
        raise ValueError("extension particles mismatch expected identity")
    _validate_complete_extension_namespace(root, expected)
    _validate_extension_chain(extensions, expected, owner_payload)

    generations_dir = root / "generations"
    if not generations_dir.exists():
        if expected:
            raise ValueError("declared extensions have omitted generations")
        raise ValueError("generation tree has no root")
    _require_regular_directory(generations_dir, "generations")
    manifest_paths: list[Path] = []
    for child in sorted(generations_dir.iterdir()):
        _reject_symlink_components(child)
        if not child.is_dir() or not _is_sha(child.name):
            raise ValueError("generation namespace contains a malformed object")
        members = sorted(child.iterdir())
        if members != [child / "manifest.json"]:
            raise ValueError("generation directory is malformed")
        manifest_paths.append(child / "manifest.json")
    discovered: list[VerifiedGeneration] = []
    for manifest in manifest_paths:
        _reject_symlink_components(manifest)
        if not manifest.parent.is_dir() or manifest.parent.parent != generations_dir:
            raise ValueError("generation manifest path is outside its exact namespace")
        payload = validate_envelope(manifest, "challenge15.training-generation.v1")
        computed = payload_sha256(payload)
        if manifest.parent.name != computed:
            raise ValueError("generation directory name does not match payload SHA256")
        generation = _generation_from_payload(payload)
        validate_training_generation(generation)
        extension = _read_extension(root, generation.extension_sha256)
        _validate_generation_against_extension(payload, extension, owner_payload)
        _validate_generation_artifacts(root, payload)
        discovered.append(
            VerifiedGeneration(
                path=manifest,
                payload_sha256=computed,
                payload=payload,
            )
        )

    by_extension: dict[str, list[VerifiedGeneration]] = {}
    by_rank: dict[int, list[VerifiedGeneration]] = {}
    for item in discovered:
        by_extension.setdefault(str(item.payload["extension_sha256"]), []).append(item)
        by_rank.setdefault(item.rank, []).append(item)
    if set(by_extension) != set(expected):
        raise ValueError("generation tree contains an undeclared extension")
    if any(len(items) != 1 for items in by_extension.values()):
        raise ValueError("generation tree has multiple candidates for one extension")
    if any(len(items) != 1 for items in by_rank.values()):
        raise ValueError("generation tree has a duplicate rank or fork")
    if len(discovered) != len(expected):
        raise ValueError("generation tree has omitted or undeclared generations")

    ordered: list[VerifiedGeneration] = []
    previous: VerifiedGeneration | None = None
    for extension in extensions:
        item = by_extension[payload_sha256(extension.to_payload())][0]
        expected_parent = None if previous is None else previous.payload_sha256
        if item.payload["parent_generation_sha256"] != expected_parent:
            raise ValueError("generation parent mismatch or fork")
        if previous is not None:
            if item.payload["parent_parameter_sha256"] != previous.payload["parameter_sha256"]:
                raise ValueError("generation parent parameter mismatch")
            if (
                item.payload["parent_optimizer_state_sha256"]
                != previous.payload["optimizer_state_sha256"]
            ):
                raise ValueError("generation parent optimizer mismatch")
        ordered.append(item)
        previous = item
    if not ordered:
        raise ValueError("generation tree has no root")
    return ordered[-1]


def select_published(
    intent: OrchestrationAttemptIntent | Mapping[str, Any],
    create_only_namespace: Path,
    *,
    output_schema: str | None = None,
) -> ValidatedCandidate | None:
    """Select zero or one intent-bounded candidate; reject tampering/ambiguity."""

    if isinstance(intent, OrchestrationAttemptIntent):
        validate_orchestration_attempt_intent(intent)
        payload = intent.to_payload()
    else:
        payload = dict(intent)
        validate_envelope(
            {
                "schema": "challenge15.orchestration-attempt-intent.v1",
                "payload": payload,
                "payload_sha256": payload_sha256(payload),
            },
            "challenge15.orchestration-attempt-intent.v1",
        )
    namespace = Path(create_only_namespace)
    _require_regular_directory(namespace, "create-only selector namespace")
    identity = str(namespace.absolute())
    declared = payload.get("create_only_namespace_identities")
    if not isinstance(declared, (list, tuple)) or len(declared) != 1:
        raise ValueError("attempt intent must declare exactly one permitted namespace")
    if not any(
        item == identity or (isinstance(item, str) and item.endswith(f":{identity}"))
        for item in declared
    ):
        raise ValueError("selector namespace is not declared by attempt intent")
    schemas = {
        item.get("output_schema")
        for item in payload.get("expected_output_identities", ())
        if isinstance(item, Mapping) and isinstance(item.get("output_schema"), str)
    }
    if len(schemas) != 1:
        raise ValueError("attempt intent must declare exactly one output schema")
    schema = schemas.pop()
    if output_schema is not None and output_schema != schema:
        raise ValueError("output schema cannot override attempt intent")
    if schema not in PUBLISHER_SELECTOR_REGISTRY:
        raise ValueError("attempt intent output schema has no registered selector")
    for output_identity in payload["expected_output_identities"]:
        required = SELECTOR_REQUIRED_CONSTRAINTS[schema]
        missing = required - set(output_identity)
        if missing:
            raise ValueError(
                f"attempt intent omits required selector constraints: {sorted(missing)}"
            )
    candidates = _candidate_paths(namespace, schema, payload)
    valid: list[ValidatedCandidate] = []
    for path in candidates:
        _reject_symlink_components(path)
        candidate_payload = validate_envelope(path, schema)
        digest = payload_sha256(candidate_payload)
        _validate_candidate_filename(path, schema, digest)
        _validate_candidate_identity(candidate_payload, payload)
        valid.append(
            ValidatedCandidate(
                path=path,
                schema=schema,
                payload_sha256=digest,
                payload=candidate_payload,
            )
        )
    if len(valid) > 1:
        raise ValueError("multiple valid candidates occupy the intent namespace")
    return valid[0] if valid else None


def _candidate_paths(
    namespace: Path,
    schema: str,
    intent: Mapping[str, Any],
) -> list[Path]:
    selector = PUBLISHER_SELECTOR_REGISTRY[schema]
    if selector == "generation-manifests":
        return sorted(namespace.glob("*/manifest.json"))
    if selector == "step-content-addressed-files":
        rank = intent.get("rank")
        expected = intent.get("expected_output_identities", ())
        steps = {
            item.get("step")
            for item in expected
            if isinstance(item, Mapping) and isinstance(item.get("step"), int)
        }
        if len(steps) != 1:
            raise ValueError("snapshot selector intent must fix one update")
        step = steps.pop()
        if rank is None:
            raise ValueError("snapshot selector intent must fix rank")
        return sorted(namespace.glob(f"{step}-*.json"))
    if selector == "attempt-manifest":
        candidate = namespace / "attempt.json"
        return [candidate] if candidate.exists() else []
    return sorted(namespace.glob("*.json"))


def _validate_candidate_filename(path: Path, schema: str, digest: str) -> None:
    if schema == "challenge15.training-generation.v1":
        if path.name != "manifest.json" or path.parent.name != digest:
            raise ValueError("candidate generation path does not match payload hash")
    elif schema == "challenge15.training-attempt.v1":
        if path.name != "attempt.json":
            raise ValueError("candidate attempt path is invalid")
    elif schema == "challenge15.training-snapshot.v1":
        if not path.name.endswith(f"-{digest}.json"):
            raise ValueError("candidate snapshot filename does not match payload hash")
    elif path.name != f"{digest}.json":
        raise ValueError("candidate filename does not match payload hash")


def _validate_candidate_identity(
    candidate: Mapping[str, Any],
    intent: Mapping[str, Any],
) -> bool:
    expected_outputs = intent.get("expected_output_identities", ())
    matching = 0
    for identity in expected_outputs:
        if not isinstance(identity, Mapping):
            raise ValueError("attempt intent output identity is malformed")
        requested = {
            key: value
            for key, value in identity.items()
            if key not in {"output_schema", "namespace"}
        }
        missing = set(requested) - set(candidate)
        if missing:
            raise ValueError(
                f"candidate cannot satisfy intent constraint fields: {sorted(missing)}"
            )
        constraints = requested
        if all(candidate[key] == value for key, value in constraints.items()):
            matching += 1
    if matching == 0:
        raise ValueError("occupied candidate identity is tamper evidence")
    if matching != 1:
        raise ValueError("candidate matches multiple intended output identities")

    direct = (
        "policy_sha256",
        "source_manifest_sha256",
        "base_configuration_sha256",
        "particles",
        "seed",
        "rank",
    )
    for field in direct:
        expected = intent.get(field)
        if expected is not None and field in candidate and candidate[field] != expected:
            raise ValueError(f"candidate {field} does not match attempt intent")
    parents = intent.get("parent_sha256s", {})
    if isinstance(parents, Mapping):
        for field, expected in parents.items():
            if field in candidate and candidate[field] != expected:
                raise ValueError(f"candidate parent {field} does not match attempt intent")
    return True


def _validate_extension_chain(
    extensions: Sequence[RankExtension],
    expected: Sequence[str],
    owner: Mapping[str, Any],
) -> None:
    previous: RankExtension | None = None
    for index, (extension, digest) in enumerate(zip(extensions, expected, strict=True)):
        if payload_sha256(extension.to_payload()) != digest:
            raise ValueError("extension filename does not match payload SHA256")
        validate_rank_extension(extension)
        for field in (
            "seed",
            "experiment_id",
            "base_configuration_sha256",
            "policy_sha256",
            "source_manifest_sha256",
            "runtime_attestations",
            "expected_seed_set",
        ):
            extension_value = extension.to_payload()[field]
            owner_value = owner[field]
            if extension_value != owner_value:
                raise ValueError(f"extension {field} does not match seed owner")
        expected_previous = None if index == 0 else extensions[index - 1].new_rank
        if extension.previous_rank != expected_previous:
            raise ValueError("extension chain has a rank gap or wrong parent rank")
        if previous is not None and extension.new_rank != 2 * previous.new_rank:
            raise ValueError("extension chain skipped a required doubling")
        previous = extension


def _validate_generation_against_extension(
    generation: Mapping[str, Any],
    extension: RankExtension,
    owner: Mapping[str, Any],
) -> None:
    extension_payload = extension.to_payload()
    bindings = (
        "particles",
        "seed",
        "base_configuration_sha256",
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
    )
    for field in bindings:
        if generation[field] != extension_payload[field]:
            raise ValueError(f"generation {field} does not match extension")
    if generation["rank"] != extension.new_rank:
        raise ValueError("generation rank does not match extension")
    if generation["extension_sha256"] != payload_sha256(extension_payload):
        raise ValueError("generation extension SHA256 mismatch")
    if generation["parent_generation_sha256"] != extension.parent_generation_sha256:
        raise ValueError("generation parent generation mismatch")
    if generation["parent_parameter_sha256"] != extension.parent_parameter_sha256:
        raise ValueError("generation parent parameter mismatch")
    if (
        generation["parent_optimizer_state_sha256"]
        != extension.parent_optimizer_state_sha256
    ):
        raise ValueError("generation parent optimizer mismatch")
    if generation["seed"] != owner["seed"]:
        raise ValueError("generation seed does not match owner")


def _read_unique_owner(root: Path) -> tuple[Mapping[str, Any], str]:
    owner_dir = root / "owner"
    _require_regular_directory(owner_dir, "seed owner")
    entries = sorted(owner_dir.iterdir())
    if len(entries) != 1 or entries[0].suffix != ".json":
        raise ValueError("seed root must contain exactly one owner")
    path = entries[0]
    _reject_symlink_components(path)
    payload = validate_envelope(path, "challenge15.seed-owner.v1")
    digest = payload_sha256(payload)
    if path.name != f"{digest}.json":
        raise ValueError("owner filename does not match payload SHA256")
    owner = SeedOwner(
        **{
            **payload,
            "expected_seed_set": tuple(payload["expected_seed_set"]),
        }
    )
    validate_seed_owner(owner)
    return payload, digest


def _read_extension(root: Path, digest: str) -> RankExtension:
    _require_sha(digest, "extension")
    path = root / "extensions" / f"{digest}.json"
    _reject_symlink_components(path)
    if not path.is_file():
        raise ValueError(f"declared extension is missing: {digest}")
    payload = validate_envelope(path, "challenge15.rank-extension.v1")
    computed = payload_sha256(payload)
    if path.name != f"{computed}.json" or computed != digest:
        raise ValueError("extension filename does not match payload SHA256")
    extension = RankExtension(
        **{
            **payload,
            "expected_seed_set": tuple(payload["expected_seed_set"]),
        }
    )
    decision = _read_decision(root, extension.rank_extension_decision_sha256)
    validate_rank_extension(extension, decision)
    return extension


def _read_decision(root: Path, digest: str | None) -> RankExtensionDecision:
    _require_sha(digest, "rank extension decision")
    path = root / "decisions" / f"{digest}.json"
    _reject_symlink_components(path)
    if not path.is_file():
        raise ValueError("rank extension decision is missing")
    payload = validate_envelope(path, "challenge15.rank-extension-decision.v1")
    computed = payload_sha256(payload)
    if computed != digest or path.name != f"{computed}.json":
        raise ValueError("rank extension decision filename does not match payload SHA256")
    decision = RankExtensionDecision(**payload)
    validate_rank_extension_decision(decision)
    return decision


def _validate_decision_parents(
    root: Path,
    decision: RankExtensionDecision,
) -> None:
    if decision.current_rank is None:
        return
    directory = root / "decision-parents"
    _require_regular_directory(directory, "decision parents")
    references = (
        (
            "prior_reduction_sha256",
            decision.prior_reduction_sha256,
            "challenge15.reduction-receipt.v1",
        ),
        (
            "prior_finalization_sha256",
            decision.prior_finalization_sha256,
            "challenge15.reduction-finalization.v1",
        ),
        (
            "prior_import_receipt_sha256",
            decision.prior_import_receipt_sha256,
            "challenge15.import-bundle.v1",
        ),
        (
            "prior_transfer_receipt_sha256",
            decision.prior_transfer_receipt_sha256,
            "challenge15.transfer-receipt.v1",
        ),
    )
    loaded: dict[str, Mapping[str, Any]] = {}
    for field, digest, schema in references:
        assert digest is not None
        path = directory / f"{digest}.json"
        payload = validate_envelope(path, schema)
        if payload_sha256(payload) != digest:
            raise ValueError(f"rank decision {field} content mismatch")
        loaded[field] = payload
    baseline = loaded["prior_reduction_sha256"]
    for field, payload in loaded.items():
        for common_field in (
            "policy_sha256",
            "source_manifest_sha256",
            "runtime_attestations",
            "base_configuration_sha256",
            "particles",
        ):
            if payload[common_field] != baseline[common_field]:
                raise ValueError(f"rank decision parent {field} provenance mismatch")
    finalization = loaded["prior_finalization_sha256"]
    if (
        finalization["selected_reduction_sha256"]
        != decision.prior_reduction_sha256
        or finalization["expected_ranks_sha256"]
        != decision.prior_expected_ranks_sha256
    ):
        raise ValueError("rank decision finalization lineage mismatch")
    transfer = loaded["prior_transfer_receipt_sha256"]
    if transfer["import_bundle_sha256"] != decision.prior_import_receipt_sha256:
        raise ValueError("rank decision transfer/import lineage mismatch")


def _validate_generation_artifacts(
    root: Path,
    generation: Mapping[str, Any],
) -> None:
    attempt_payload, attempt_dir = _read_attempt_by_sha(
        root, str(generation["attempt_sha256"])
    )
    if attempt_payload["status"] != "complete":
        raise ValueError("generation requires a completed training attempt")
    if (
        attempt_payload["seed"] != generation["seed"]
        or attempt_payload["rank"] != generation["rank"]
        or attempt_payload["extension_sha256"] != generation["extension_sha256"]
    ):
        raise ValueError("generation attempt identity mismatch")
    digest = str(generation["terminal_snapshot_sha256"])
    if attempt_payload["terminal_snapshot_sha256"] != digest:
        raise ValueError("generation attempt does not bind terminal snapshot")
    snapshot, snapshot_path = _read_snapshot_by_sha(root, digest)
    running_attempt = validate_envelope(
        snapshot_path.parent.parent / "attempt.json",
        "challenge15.training-attempt.v1",
    )
    if running_attempt["status"] != "running":
        raise ValueError("terminal snapshot does not bind a running attempt")
    if payload_sha256(snapshot) != digest:
        raise ValueError("generation terminal snapshot SHA256 mismatch")
    for field in (
        "seed",
        "rank",
        "parameter_sha256",
        "optimizer_state_sha256",
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
        "base_configuration_sha256",
        "particles",
    ):
        if snapshot[field] != generation[field]:
            raise ValueError(f"generation terminal snapshot {field} mismatch")
    if snapshot["attempt_id"] != attempt_payload["attempt_id"]:
        raise ValueError("generation terminal snapshot attempt mismatch")
    for field in (
        "parameter_sha256",
        "optimizer_state_sha256",
        "walker_state_sha256",
        "log_amplitude_sha256",
        "prng_state_sha256",
    ):
        _validate_blob(root, str(snapshot[field]))


def _read_attempt_by_sha(
    root: Path,
    expected_sha256: str,
) -> tuple[Mapping[str, Any], Path]:
    _require_sha(expected_sha256, "attempt")
    attempts = root / "attempts"
    try:
        _require_regular_directory(attempts, "attempts")
    except FileNotFoundError as exc:
        raise ValueError("generation attempt is missing") from exc
    matches: list[tuple[Mapping[str, Any], Path]] = []
    for attempt_dir in sorted(attempts.iterdir()):
        _require_regular_directory(attempt_dir, "attempt")
        path = attempt_dir / "attempt.json"
        if not path.is_file():
            continue
        payload = validate_envelope(path, "challenge15.training-attempt.v1")
        if attempt_dir.name != _attempt_identity(payload):
            raise ValueError("attempt directory identity mismatch")
        if payload_sha256(payload) == expected_sha256:
            matches.append((payload, attempt_dir))
    if len(matches) != 1:
        raise ValueError("generation attempt is missing or ambiguous")
    return matches[0]


def _read_snapshot_by_sha(
    root: Path,
    expected_sha256: str,
) -> tuple[Mapping[str, Any], Path]:
    _require_sha(expected_sha256, "snapshot")
    attempts = root / "attempts"
    _require_regular_directory(attempts, "attempts")
    matches: list[tuple[Mapping[str, Any], Path]] = []
    for attempt_dir in sorted(attempts.iterdir()):
        snapshots = attempt_dir / "snapshots"
        if not snapshots.is_dir():
            continue
        for path in sorted(snapshots.glob(f"*-{expected_sha256}.json")):
            payload = validate_envelope(path, "challenge15.training-snapshot.v1")
            if payload_sha256(payload) == expected_sha256:
                matches.append((payload, path))
    if len(matches) != 1:
        raise ValueError("starting snapshot is missing or ambiguous")
    return matches[0]


def _validate_blob(root: Path, digest: str) -> None:
    _require_sha(digest, "blob")
    path = root / "blobs" / digest
    _reject_symlink_components(path)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("referenced blob is missing or tampered")


def _attempt_identity(attempt: Mapping[str, Any]) -> str:
    return payload_sha256(
        {
            "seed": attempt["seed"],
            "rank": attempt["rank"],
            "attempt_id": attempt["attempt_id"],
            "owner_sha256": attempt["owner_sha256"],
            "extension_sha256": attempt["extension_sha256"],
            "status": attempt["status"],
        }
    )


def _validate_complete_extension_namespace(
    root: Path,
    expected: Sequence[str],
) -> None:
    directory = root / "extensions"
    _require_regular_directory(directory, "extensions")
    entries = sorted(directory.iterdir())
    actual: list[str] = []
    for path in entries:
        _reject_symlink_components(path)
        if not path.is_file() or path.suffix != ".json" or not _is_sha(path.stem):
            raise ValueError("extension namespace contains a malformed object")
        payload = validate_envelope(path, "challenge15.rank-extension.v1")
        computed = payload_sha256(payload)
        if path.stem != computed:
            raise ValueError("extension filename does not match payload SHA256")
        actual.append(computed)
    if set(actual) != set(expected) or len(actual) != len(expected):
        raise ValueError("extension namespace has omitted or undeclared extensions")


def _generation_from_payload(payload: Mapping[str, Any]) -> TrainingGeneration:
    return TrainingGeneration(**payload)


def _require_claimed_seed_root(path: Path) -> Path:
    root = Path(path)
    _require_regular_directory(root, "seed root")
    _read_unique_owner(root)
    return root


def _ensure_child_directory(root: Path, name: str) -> Path:
    child = root / name
    if child.exists():
        _require_regular_directory(child, name)
    else:
        child.mkdir()
        _fsync_directory(root)
    return child


def _publish_envelope_directory(
    parent: Path,
    final_name: str,
    envelope_name: str,
    schema: str,
    payload: Any,
    *,
    staging_parent: Path,
) -> str:
    parent_fd = _open_directory_fd(parent)
    staging_parent.mkdir(exist_ok=True)
    _require_regular_directory(staging_parent, "artifact staging")
    staging_parent_fd = _open_directory_fd(staging_parent)
    staging_name = f".{final_name}.partial.{uuid.uuid4().hex}"
    published = False
    try:
        os.mkdir(staging_name, 0o700, dir_fd=staging_parent_fd)
        _fsync_directory_fd(staging_parent_fd)
        staging = staging_parent / staging_name
        digest = publish_production_envelope(
            staging / envelope_name,
            schema,
            payload,
        )
        staging_fd = _open_directory_fd(staging)
        _fsync_directory_fd(staging_fd)
        retained = os.fstat(staging_fd)
        current = os.stat(
            staging_name, dir_fd=staging_parent_fd, follow_symlinks=False
        )
        if (current.st_dev, current.st_ino) != (retained.st_dev, retained.st_ino):
            raise ValueError("directory publication staging inode changed")
        kind = "attempt" if schema == "challenge15.training-attempt.v1" else "generation"
        _publication_killpoint(f"{kind}-before-rename")
        _rename_noreplace(
            staging_parent_fd,
            staging_name,
            final_name,
            parent_fd,
        )
        _publication_killpoint(f"{kind}-after-rename")
        final = os.stat(final_name, dir_fd=parent_fd, follow_symlinks=False)
        if (final.st_dev, final.st_ino) != (retained.st_dev, retained.st_ino):
            _rename_noreplace(
                parent_fd,
                final_name,
                f".rejected.{final_name}.{uuid.uuid4().hex}",
                staging_parent_fd,
            )
            raise ValueError("directory publication final inode mismatch")
        published = True
        _fsync_directory_fd(staging_parent_fd)
        _fsync_directory_fd(parent_fd)
        return digest
    finally:
        # Never recursively remove a name after a failure: another process may
        # have replaced it. Stale staging is outside canonical discovery.
        if "staging_fd" in locals():
            os.close(staging_fd)
        os.close(staging_parent_fd)
        os.close(parent_fd)


def _require_regular_directory(path: Path, label: str) -> None:
    _reject_symlink_components(path)
    try:
        mode = path.stat().st_mode
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"{label} directory does not exist: {path}") from exc
    if not stat.S_ISDIR(mode):
        raise ValueError(f"{label} path is not a directory")


def _require_sha(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA256")


def _is_sha(value: str) -> bool:
    try:
        _require_sha(value, "identity")
    except ValueError:
        return False
    return True
