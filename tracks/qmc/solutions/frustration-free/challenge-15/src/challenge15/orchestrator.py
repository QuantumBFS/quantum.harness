"""Durable local production orchestration state.

The module owns identities and restart metadata.  External actions are always
performed by submit-once/transfer-once wrappers using persisted intents.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import socket
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse
from datetime import UTC, datetime

from .production_schema import canonical_json


RANK_LADDER = (1, 2, 4, 8)
SEEDS = (0, 1, 2, 3, 4)
TRANSITION_STATES = (
    "VERIFY_INPUTS",
    "VERIFY_RUNTIME_SET_COPIES",
    "ENSURE_ORACLE",
    "CLAIM_SEEDS",
    "PREPARE_RANK",
    "TRAIN_RANK",
    "COORDINATE_EVALUATE",
    "EXPORT_GPU_IDENTITY_MAP",
    "TRANSFER_GPU_TO_CPU",
    "IMPORT_GPU_RESULTS",
    "EXACT_EVALUATE",
    "REDUCE_EXACT_INPUTS",
    "PROVISIONAL_FINALIZE",
    "CLASSIFY_FINALIZATION",
    "DECIDE_EXTENSION",
    "SELECT_TERMINAL",
    "EXPORT_ACCEPTED_TERMINAL",
    "STOP_ACCEPTED",
    "STOP_PENDING",
    "HARD_FAIL",
)


@dataclass(frozen=True)
class OrchestrationInputs:
    particles: int
    rank_ladder: tuple[int, ...]
    seeds: tuple[int, ...]
    base_configuration_sha256: str
    policy_sha256: str
    source_manifest_sha256: str
    source_revision: str
    runtime_set_local_sha256: str
    runtime_set_local_path: str
    cpu_runtime_set_remote_sha256: str
    cpu_runtime_set_remote_path: str
    cpu_runtime_set_receipt_sha256: str
    gpu_runtime_set_remote_sha256: str
    gpu_runtime_set_remote_path: str
    gpu_runtime_set_receipt_sha256: str
    prerequisite_terminal_selection_sha256: str | None
    cpu_controller: str
    gpu_controller: str
    cpu_profile_sha256: str
    gpu_profile_sha256: str
    cpu_deployment_receipt_sha256: str
    gpu_deployment_receipt_sha256: str
    cpu_results_root: str
    gpu_results_root: str
    state_root_base: str
    state_backup_uri: str
    state_mirror_root: str | None
    transition_action_manifest_sha256: str = "0" * 64


@dataclass(frozen=True)
class PublishedStateKey:
    payload: dict[str, Any]
    sha256: str
    run_root: Path


@dataclass(frozen=True)
class CycleOutcome:
    new_rank: int
    expected_ranks: tuple[int, ...]
    previous_expected_ranks: tuple[int, ...]
    parent_sha256: str | None
    outcome_sha256: str
    status: str = "pending"


@dataclass(frozen=True)
class RecoveryDecision:
    published: bool
    path: Path | None
    computed_sha256: str | None


@dataclass(frozen=True)
class OrchestrationOutcome:
    state: str
    visited_ranks: tuple[int, ...]
    cycle_inputs: tuple[tuple[int, tuple[int, ...]], ...]
    transition_names: tuple[str, ...]
    terminal_selection: str | None


@dataclass(frozen=True)
class TransitionEvidence:
    input_sha256s: tuple[str, ...]
    output_sha256s: tuple[str, ...]
    outcome: str
    output_promotion_sha256s: tuple[str, ...] = ()
    import_receipt_sha256s: tuple[str, ...] = ()
    transfer_receipt_sha256s: tuple[str, ...] = ()
    scheduler_receipt_sha256s: tuple[str, ...] = ()
    attempt_intent_sha256s: tuple[str, ...] = ()
    expected_remote_output_sha256s: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransitionStep:
    state: str
    recover: Callable[[], TransitionEvidence | None]
    act: Callable[[], TransitionEvidence]


def orchestrate_rank_outcomes(
    rank_outcomes: Mapping[int, str],
) -> OrchestrationOutcome:
    """Pure transition classifier used by the durable execution driver."""
    transitions = [
        "VERIFY_INPUTS",
        "VERIFY_RUNTIME_SET_COPIES",
        "ENSURE_ORACLE",
        "CLAIM_SEEDS",
    ]
    visited: list[int] = []
    cycle_inputs: list[tuple[int, tuple[int, ...]]] = []
    for rank in RANK_LADDER:
        visited.append(rank)
        previous = rank_trace(rank)
        cycle_inputs.append((rank, previous))
        transitions.extend(
            (
                "PREPARE_RANK",
                "TRAIN_RANK",
                "COORDINATE_EVALUATE",
                "EXPORT_GPU_IDENTITY_MAP",
                "TRANSFER_GPU_TO_CPU",
                "IMPORT_GPU_RESULTS",
                "EXACT_EVALUATE",
                "REDUCE_EXACT_INPUTS",
                "PROVISIONAL_FINALIZE",
                "CLASSIFY_FINALIZATION",
            )
        )
        status = rank_outcomes.get(rank)
        if status == "accepted":
            transitions.extend(
                ("SELECT_TERMINAL", "EXPORT_ACCEPTED_TERMINAL", "STOP_ACCEPTED")
            )
            return OrchestrationOutcome(
                state="STOP_ACCEPTED",
                visited_ranks=tuple(visited),
                cycle_inputs=tuple(cycle_inputs),
                transition_names=tuple(transitions),
                terminal_selection=f"rank={rank}:accepted",
            )
        if status != "pending":
            transitions.append("HARD_FAIL")
            return OrchestrationOutcome(
                state="HARD_FAIL",
                visited_ranks=tuple(visited),
                cycle_inputs=tuple(cycle_inputs),
                transition_names=tuple(transitions),
                terminal_selection=None,
            )
        if rank != RANK_LADDER[-1]:
            transitions.append("DECIDE_EXTENSION")
    transitions.append("STOP_PENDING")
    return OrchestrationOutcome(
        state="STOP_PENDING",
        visited_ranks=tuple(visited),
        cycle_inputs=tuple(cycle_inputs),
        transition_names=tuple(transitions),
        terminal_selection=None,
    )


class DurableStateStore:
    """Append-only local transition receipts and exclusive completion markers."""

    def __init__(self, root: Path | str, *, state_key: str | None = None):
        self.root = _reject_symlink_ancestors(Path(root), "durable state store")
        self.state_key = state_key or hashlib.sha256(
            str(self.root.absolute()).encode()
        ).hexdigest()
        self.transitions = self.root / "transitions"
        self.markers = self.root / "completion-markers"
        self.backup_checkpoints = self.root / "backup-checkpoints"
        self.transitions.mkdir(parents=True, exist_ok=True)
        self.markers.mkdir(parents=True, exist_ok=True)
        self.backup_checkpoints.mkdir(parents=True, exist_ok=True)
        _fsync_directory(self.root)

    def complete_transition(
        self,
        *,
        state: str,
        attempt: int,
        input_sha256s: tuple[str, ...],
        output_sha256s: tuple[str, ...],
        outcome: str,
        output_promotion_sha256s: tuple[str, ...] = (),
        import_receipt_sha256s: tuple[str, ...] = (),
        transfer_receipt_sha256s: tuple[str, ...] = (),
        scheduler_receipt_sha256s: tuple[str, ...] = (),
    ) -> Path:
        if state.split(".", 1)[0] not in TRANSITION_STATES or "/" in state:
            raise ValueError("unknown orchestration transition state")
        payload = {
            "state_key": self.state_key,
            "state": state,
            "attempt": attempt,
            "input_sha256s": list(input_sha256s),
            "output_sha256s": list(output_sha256s),
            "output_promotion_sha256s": list(output_promotion_sha256s),
            "import_receipt_sha256s": list(import_receipt_sha256s),
            "transfer_receipt_sha256s": list(transfer_receipt_sha256s),
            "scheduler_receipt_sha256s": list(scheduler_receipt_sha256s),
            "outcome": outcome,
            "created_at_utc": datetime.now(UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z"),
        }
        digest = hashlib.sha256(canonical_json(payload)).hexdigest()
        state_root = self.transitions / state
        state_root.mkdir(exist_ok=True)
        receipt = state_root / f"{digest}.json"
        marker = self.markers / f"{state}.json"
        if marker.exists():
            existing = json.loads(marker.read_text(encoding="utf-8"))
            existing_path = Path(existing["receipt"])
            if existing.get("receipt_sha256") == digest and existing_path == receipt:
                return receipt
            raise ValueError("conflicting completion marker")
        document = {
            "schema": "challenge15.orchestration-transition.v1",
            "payload": payload,
            "payload_sha256": digest,
        }
        _exclusive_bytes(receipt, canonical_json(document) + b"\n")
        _fsync_directory(state_root)
        marker_payload = {"receipt": str(receipt), "receipt_sha256": digest}
        try:
            _exclusive_bytes(marker, canonical_json(marker_payload) + b"\n")
            _fsync_directory(self.markers)
        except FileExistsError as exc:
            raise ValueError("conflicting completion marker") from exc
        return receipt

    def completed_receipt(self, state: str) -> Path | None:
        marker = self.markers / f"{state}.json"
        if not marker.exists():
            return None
        payload = json.loads(marker.read_text(encoding="utf-8"))
        receipt = Path(payload["receipt"])
        document = json.loads(receipt.read_text(encoding="utf-8"))
        computed = hashlib.sha256(canonical_json(document["payload"])).hexdigest()
        if (
            computed != payload["receipt_sha256"]
            or document.get("payload_sha256") != computed
            or document.get("schema") != "challenge15.orchestration-transition.v1"
        ):
            raise ValueError("corrupt completion marker or transition receipt")
        return receipt

    def completed_backup(self, transition_receipt: Path) -> Path | None:
        digest = json.loads(
            transition_receipt.read_text(encoding="utf-8")
        )["payload_sha256"]
        checkpoint = self.backup_checkpoints / f"{digest}.json"
        if not checkpoint.exists():
            return None
        payload = json.loads(checkpoint.read_text(encoding="utf-8"))
        manifest = Path(payload["manifest"])
        receipt = Path(payload["backup_receipt"])
        if (
            not manifest.is_file()
            or not receipt.is_file()
            or hashlib.sha256(manifest.read_bytes()).hexdigest()
            != payload["manifest_file_sha256"]
            or hashlib.sha256(receipt.read_bytes()).hexdigest()
            != payload["backup_receipt_file_sha256"]
        ):
            raise ValueError("state-manifest backup checkpoint is corrupt")
        return receipt

    def record_backup(
        self, transition_receipt: Path, manifest: Path, backup_receipt: Path
    ) -> None:
        digest = json.loads(
            transition_receipt.read_text(encoding="utf-8")
        )["payload_sha256"]
        checkpoint = self.backup_checkpoints / f"{digest}.json"
        payload = {
            "manifest": str(manifest),
            "manifest_file_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "backup_receipt": str(backup_receipt),
            "backup_receipt_file_sha256": hashlib.sha256(
                backup_receipt.read_bytes()
            ).hexdigest(),
        }
        data = canonical_json(payload) + b"\n"
        if checkpoint.exists():
            if checkpoint.read_bytes() != data:
                raise ValueError("conflicting state-manifest backup checkpoint")
            return
        _exclusive_bytes(checkpoint, data)
        _fsync_directory(self.backup_checkpoints)

    def publish_state_manifest(
        self,
        *,
        source_revision: str,
        backup_uri: str,
        mirror_root: str | None,
        attempt_intent_sha256s: Sequence[str] = (),
        output_promotion_sha256s: Sequence[str] = (),
        expected_remote_output_sha256s: Sequence[str] = (),
    ) -> Path:
        manifests = self.root / "state-manifests"
        manifests.mkdir(exist_ok=True)
        transition_receipts = sorted(self.transitions.glob("*/*.json"))
        markers = sorted(self.markers.glob("*.json"))
        previous = sorted(
            manifests.glob("*.json"),
            key=lambda path: json.loads(path.read_text(encoding="utf-8"))["payload"][
                "created_at_utc"
            ],
        )
        payload = {
            "state_key_sha256": self.state_key,
            "source_revision": source_revision,
            "transition_receipt_sha256s": [
                json.loads(path.read_text(encoding="utf-8"))["payload_sha256"]
                for path in transition_receipts
            ],
            "completion_marker_sha256s": [
                hashlib.sha256(path.read_bytes()).hexdigest() for path in markers
            ],
            "attempt_intent_sha256s": list(attempt_intent_sha256s),
            "output_promotion_sha256s": list(output_promotion_sha256s),
            "expected_remote_output_sha256s": list(expected_remote_output_sha256s),
            "previous_state_manifest_sha256": (
                None
                if not previous
                else json.loads(previous[-1].read_text(encoding="utf-8"))[
                    "payload_sha256"
                ]
            ),
            "backup_uri_identity": backup_uri,
            "mirror_root_identity": mirror_root,
            "created_at_utc": datetime.now(UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z"),
        }
        digest = hashlib.sha256(canonical_json(payload)).hexdigest()
        destination = manifests / f"{digest}.json"
        if destination.exists():
            return destination
        document = {
            "schema": "challenge15.orchestration-state-manifest.v1",
            "payload": payload,
            "payload_sha256": digest,
        }
        _exclusive_bytes(destination, canonical_json(document) + b"\n")
        _fsync_directory(manifests)
        return destination


def run_transition_driver(
    store: DurableStateStore,
    steps: Sequence[TransitionStep],
    *,
    source_revision: str,
    backup_uri: str,
    mirror_root: str | None,
    backup: Callable[[Path], Path],
) -> tuple[Path, ...]:
    """Recover-before-act, mark, manifest and remotely back up every step."""
    completed: list[Path] = []
    intents: list[str] = []
    promotions: list[str] = []
    remote_outputs: list[str] = []
    for step in steps:
        marker_receipt = store.completed_receipt(step.state)
        if marker_receipt is not None:
            marker_document = json.loads(marker_receipt.read_text(encoding="utf-8"))
            marker_evidence = marker_document["payload"]
            recovered = step.recover()
            if recovered is None or (
                list(recovered.input_sha256s) != marker_evidence["input_sha256s"]
                or list(recovered.output_sha256s)
                != marker_evidence["output_sha256s"]
                or recovered.outcome != marker_evidence["outcome"]
                or list(recovered.output_promotion_sha256s)
                != marker_evidence["output_promotion_sha256s"]
                or list(recovered.import_receipt_sha256s)
                != marker_evidence["import_receipt_sha256s"]
                or list(recovered.transfer_receipt_sha256s)
                != marker_evidence["transfer_receipt_sha256s"]
                or list(recovered.scheduler_receipt_sha256s)
                != marker_evidence["scheduler_receipt_sha256s"]
            ):
                raise ValueError(
                    "completion marker does not match rebuilt transition evidence"
                )
            if store.completed_backup(marker_receipt) is not None:
                completed.append(marker_receipt)
                continue
            manifest = store.publish_state_manifest(
                source_revision=source_revision,
                backup_uri=backup_uri,
                mirror_root=mirror_root,
                attempt_intent_sha256s=intents,
                output_promotion_sha256s=marker_evidence[
                    "output_promotion_sha256s"
                ],
                expected_remote_output_sha256s=remote_outputs,
            )
            backup_receipt = backup(manifest)
            if not backup_receipt.is_file():
                raise ValueError("state-manifest backup did not publish a receipt")
            store.record_backup(marker_receipt, manifest, backup_receipt)
            completed.append(marker_receipt)
            continue
        evidence = step.recover()
        if evidence is None:
            evidence = step.act()
        receipt = store.complete_transition(
            state=step.state,
            attempt=1,
            input_sha256s=evidence.input_sha256s,
            output_sha256s=evidence.output_sha256s,
            outcome=evidence.outcome,
            output_promotion_sha256s=evidence.output_promotion_sha256s,
            import_receipt_sha256s=evidence.import_receipt_sha256s,
            transfer_receipt_sha256s=evidence.transfer_receipt_sha256s,
            scheduler_receipt_sha256s=evidence.scheduler_receipt_sha256s,
        )
        intents.extend(evidence.attempt_intent_sha256s)
        promotions.extend(evidence.output_promotion_sha256s)
        remote_outputs.extend(evidence.expected_remote_output_sha256s)
        manifest = store.publish_state_manifest(
            source_revision=source_revision,
            backup_uri=backup_uri,
            mirror_root=mirror_root,
            attempt_intent_sha256s=intents,
            output_promotion_sha256s=promotions,
            expected_remote_output_sha256s=remote_outputs,
        )
        backup_receipt = backup(manifest)
        if not backup_receipt.is_file():
            raise ValueError("state-manifest backup did not publish a receipt")
        store.record_backup(receipt, manifest, backup_receipt)
        completed.append(receipt)
    return tuple(completed)


_RANK_CYCLE_STATES = (
    "PREPARE_RANK",
    "TRAIN_RANK",
    "COORDINATE_EVALUATE",
    "EXPORT_GPU_IDENTITY_MAP",
    "TRANSFER_GPU_TO_CPU",
    "IMPORT_GPU_RESULTS",
    "EXACT_EVALUATE",
    "REDUCE_EXACT_INPUTS",
    "PROVISIONAL_FINALIZE",
    "CLASSIFY_FINALIZATION",
)


def run_task7b_driver(
    store: DurableStateStore,
    executor: Any,
    *,
    rank_ladder: Sequence[int],
    source_revision: str,
    backup_uri: str,
    mirror_root: str | None,
    backup: Callable[[Path], Path],
) -> tuple[Path, ...]:
    """Execute the complete Task 7B branch graph through external actions."""

    def execute(states: Sequence[str], rank: int | None) -> tuple[Path, ...]:
        steps = tuple(
            TransitionStep(
                state if rank is None else f"{state}.rank-{rank}",
                lambda state=state: executor.recover(state, rank),
                lambda state=state: executor.act(state, rank),
            )
            for state in states
        )
        return run_transition_driver(
            store,
            steps,
            source_revision=source_revision,
            backup_uri=backup_uri,
            mirror_root=mirror_root,
            backup=backup,
        )

    receipts = list(
        execute(
            (
                "VERIFY_INPUTS",
                "VERIFY_RUNTIME_SET_COPIES",
                "ENSURE_ORACLE",
                "CLAIM_SEEDS",
            ),
            None,
        )
    )
    ranks = tuple(rank_ladder)
    if ranks != RANK_LADDER:
        raise ValueError("Task 7B rank ladder must be exactly 1,2,4,8")
    for index, rank in enumerate(ranks):
        cycle = execute(_RANK_CYCLE_STATES, rank)
        receipts.extend(cycle)
        classification = json.loads(cycle[-1].read_text(encoding="utf-8"))["payload"][
            "outcome"
        ]
        if classification == "accepted":
            receipts.extend(
                execute(
                    (
                        "SELECT_TERMINAL",
                        "EXPORT_ACCEPTED_TERMINAL",
                        "STOP_ACCEPTED",
                    ),
                    rank,
                )
            )
            return tuple(receipts)
        if classification != "pending":
            receipts.extend(execute(("HARD_FAIL",), rank))
            raise ValueError("Task 7B finalization classification hard-failed")
        if index + 1 < len(ranks):
            receipts.extend(execute(("DECIDE_EXTENSION",), rank))
            continue
        receipts.extend(execute(("STOP_PENDING",), rank))
        return tuple(receipts)
    raise AssertionError("unreachable Task 7B rank branch")


def _exclusive_bytes(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _reject_symlink_ancestors(path: Path, label: str) -> Path:
    absolute = path.absolute()
    for candidate in (absolute, *absolute.parents):
        if candidate.exists() and candidate.is_symlink():
            raise ValueError(f"{label} has a symlink ancestor")
    return absolute


def validate_state_root_base(path: Path | str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ValueError("durable state root must be absolute")
    absolute = _reject_symlink_ancestors(candidate, "durable state root")
    if absolute == Path("/tmp") or Path("/tmp") in absolute.parents:
        raise ValueError("durable state root cannot use temporary storage")
    if absolute == Path("/var/tmp") or Path("/var/tmp") in absolute.parents:
        raise ValueError("durable state root cannot use temporary storage")
    return absolute


def validate_backup_uri(
    uri: str,
    local_host: str | None = None,
    approved_root: Path | str | None = None,
) -> str:
    parsed = urlparse(uri)
    local = local_host or socket.gethostname()
    if parsed.scheme != "ssh" or not parsed.hostname or not parsed.path.startswith("/"):
        raise ValueError("backup requires an absolute ssh URI")
    if parsed.hostname in {local, "localhost", "127.0.0.1", "::1"}:
        raise ValueError("backup requires a distinct durable failure domain")
    if approved_root is not None:
        root = Path(approved_root)
        target = Path(parsed.path)
        if target != root and root not in target.parents:
            raise ValueError("backup path is outside profile-approved results root")
    return f"ssh://{parsed.hostname}{Path(parsed.path).as_posix()}"


def rank_trace(new_rank: int) -> tuple[int, ...]:
    if new_rank not in RANK_LADDER:
        raise ValueError("new rank is outside the immutable rank ladder")
    return RANK_LADDER[: RANK_LADDER.index(new_rank)]


def build_state_key(inputs: OrchestrationInputs) -> PublishedStateKey:
    _validate_inputs(inputs)
    payload = {
        "particles": inputs.particles,
        "base_configuration_sha256": inputs.base_configuration_sha256,
        "policy_sha256": inputs.policy_sha256,
        "source_manifest_sha256": inputs.source_manifest_sha256,
        "rank_ladder": list(inputs.rank_ladder),
        "rank_extension_policy_sha256": hashlib.sha256(
            canonical_json({"ladder": list(inputs.rank_ladder), "growth": "doubling"})
        ).hexdigest(),
        "seed_set": list(inputs.seeds),
        "runtime_set_local_sha256": inputs.runtime_set_local_sha256,
        "runtime_set_local_path_identity": f"local:{Path(inputs.runtime_set_local_path).absolute()}",
        "cpu_runtime_set_remote_sha256": inputs.cpu_runtime_set_remote_sha256,
        "cpu_runtime_set_remote_path_identity": (
            f"{inputs.cpu_controller}:{inputs.cpu_runtime_set_remote_path}"
        ),
        "cpu_runtime_set_receipt_sha256": inputs.cpu_runtime_set_receipt_sha256,
        "gpu_runtime_set_remote_sha256": inputs.gpu_runtime_set_remote_sha256,
        "gpu_runtime_set_remote_path_identity": (
            f"{inputs.gpu_controller}:{inputs.gpu_runtime_set_remote_path}"
        ),
        "gpu_runtime_set_receipt_sha256": inputs.gpu_runtime_set_receipt_sha256,
        "prerequisite_terminal_selection_sha256": (
            inputs.prerequisite_terminal_selection_sha256
        ),
        "cpu_controller": inputs.cpu_controller,
        "gpu_controller": inputs.gpu_controller,
        "cpu_profile_sha256": inputs.cpu_profile_sha256,
        "gpu_profile_sha256": inputs.gpu_profile_sha256,
        "cpu_deployment_receipt_sha256": inputs.cpu_deployment_receipt_sha256,
        "gpu_deployment_receipt_sha256": inputs.gpu_deployment_receipt_sha256,
        "cpu_results_root_identity": (
            f"{inputs.cpu_controller}:{inputs.cpu_results_root}"
        ),
        "gpu_results_root_identity": (
            f"{inputs.gpu_controller}:{inputs.gpu_results_root}"
        ),
        "durable_state_root_base_identity": (
            f"local:{validate_state_root_base(inputs.state_root_base)}"
        ),
        "state_backup_uri_identity": validate_backup_uri(inputs.state_backup_uri),
        "state_mirror_root_identity": (
            None
            if inputs.state_mirror_root is None
            else f"mirror:{validate_state_root_base(inputs.state_mirror_root)}"
        ),
        "transition_action_manifest_sha256": (
            inputs.transition_action_manifest_sha256
        ),
        "canonical_path_identities": {
            "base_config": inputs.base_configuration_sha256,
            "policy": inputs.policy_sha256,
            "source_manifest": inputs.source_manifest_sha256,
        },
    }
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    run_root = (
        validate_state_root_base(inputs.state_root_base)
        / f"source={inputs.source_revision}"
        / f"state={digest}"
    )
    return PublishedStateKey(payload=payload, sha256=digest, run_root=run_root)


def _validate_inputs(inputs: OrchestrationInputs) -> None:
    if inputs.particles not in {6, 7, 8}:
        raise ValueError("production particles must be N=6,7,8")
    if inputs.rank_ladder != RANK_LADDER or inputs.seeds != SEEDS:
        raise ValueError("rank ladder and five-seed set are immutable")
    if inputs.gpu_controller != "qdeshell":
        raise ValueError("GPU controller must be qdeshell")
    if inputs.cpu_controller not in {"lasg02", "wuzh02"}:
        raise ValueError("CPU controller is not approved")
    if inputs.particles == 6 and inputs.prerequisite_terminal_selection_sha256:
        raise ValueError("N=6 must omit prerequisite terminal selection")
    if inputs.particles > 6 and not inputs.prerequisite_terminal_selection_sha256:
        raise ValueError("N=7/N=8 require prerequisite terminal selection")
    hashes = (
        inputs.runtime_set_local_sha256,
        inputs.cpu_runtime_set_remote_sha256,
        inputs.gpu_runtime_set_remote_sha256,
    )
    if len(set(hashes)) != 1:
        raise ValueError("runtime-set copies have unequal canonical hashes")


def run_rank_cycle(
    previous_cycle: CycleOutcome | None,
    new_rank: int,
) -> CycleOutcome:
    previous = rank_trace(new_rank)
    if previous_cycle is None:
        if new_rank != 1:
            raise ValueError("non-root cycle requires verified prior CycleOutcome")
        parent = None
    else:
        if (
            previous_cycle.expected_ranks != previous
            or previous_cycle.new_rank != previous[-1]
            or previous_cycle.outcome_sha256
            != hashlib.sha256(
                canonical_json(
                    {
                        "new_rank": previous_cycle.new_rank,
                        "expected_ranks": list(previous_cycle.expected_ranks),
                        "parent_sha256": previous_cycle.parent_sha256,
                        "status": previous_cycle.status,
                    }
                )
            ).hexdigest()
        ):
            raise ValueError("prior CycleOutcome rank trace or digest is invalid")
        parent = previous_cycle.outcome_sha256
    expected = (*previous, new_rank)
    body = {
        "new_rank": new_rank,
        "expected_ranks": list(expected),
        "parent_sha256": parent,
        "status": "pending",
    }
    return CycleOutcome(
        new_rank=new_rank,
        expected_ranks=expected,
        previous_expected_ranks=previous,
        parent_sha256=parent,
        outcome_sha256=hashlib.sha256(canonical_json(body)).hexdigest(),
    )


def recover_before_act(
    namespace: Path | str,
    *,
    expected_schema: str,
    expected_identity: Mapping[str, Any],
) -> RecoveryDecision:
    """Select zero or one independently hashed intent-permitted candidate."""
    root = Path(namespace)
    if not root.exists():
        return RecoveryDecision(False, None, None)
    candidates = sorted(root.glob("*.json"))
    valid: list[tuple[Path, str]] = []
    for path in candidates:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            payload = document["payload"]
            computed = hashlib.sha256(canonical_json(payload)).hexdigest()
            if (
                document.get("schema") != expected_schema
                or document.get("payload_sha256") != computed
                or path.stem != computed
                or any(payload.get(key) != value for key, value in expected_identity.items())
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("tampered intent-permitted candidate") from exc
        valid.append((path, computed))
    if len(valid) > 1:
        raise ValueError("multiple intent-permitted candidates")
    if not valid:
        return RecoveryDecision(False, None, None)
    return RecoveryDecision(True, valid[0][0], valid[0][1])


def persist_state_key(key: PublishedStateKey) -> Path:
    destination = key.run_root / "state-key.json"
    data = canonical_json(
        {
            "schema": "challenge15.orchestration-state-key.v1",
            "payload": key.payload,
            "payload_sha256": key.sha256,
        }
    ) + b"\n"
    if key.run_root.exists():
        if (
            key.run_root.is_symlink()
            or not destination.is_file()
            or destination.read_bytes() != data
        ):
            raise ValueError("existing orchestration state key conflicts")
        return destination
    key.run_root.mkdir(parents=True, exist_ok=False)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(key.run_root)
    _fsync_directory(key.run_root.parent)
    return destination


def resolve_array_identity(
    identity_map_path: Path | str,
    task_id: int,
    *,
    expected_stage: str,
    expected_concurrency: int | None = None,
) -> dict[str, Any]:
    """Resolve one Slurm cell to one immutable rank/seed/input hash."""
    raw = Path(identity_map_path).read_bytes()
    document = json.loads(raw)
    payload = document.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("identity map payload is missing")
    computed = hashlib.sha256(canonical_json(payload)).hexdigest()
    if document.get("payload_sha256") != computed:
        raise ValueError("identity map payload SHA256 mismatch")
    if payload.get("stage") != expected_stage:
        raise ValueError("identity map stage mismatch")
    tasks = payload.get("tasks")
    count = payload.get("task_count")
    concurrency = payload.get("array_concurrency")
    if (
        not isinstance(tasks, list)
        or count != len(tasks)
        or not isinstance(concurrency, int)
        or isinstance(concurrency, bool)
        or concurrency < 1
        or (expected_concurrency is not None and concurrency != expected_concurrency)
    ):
        raise ValueError("identity map shape/concurrency mismatch")
    expected_seeds = list(range(5))
    if payload.get("expected_seeds") != expected_seeds:
        raise ValueError("identity map must contain exactly seeds 0..4")
    ranks = payload.get("expected_ranks")
    if not isinstance(ranks, list) or count != len(ranks) * 5:
        raise ValueError("identity map must contain exactly five identities per rank")
    if not isinstance(task_id, int) or isinstance(task_id, bool) or not 0 <= task_id < count:
        raise ValueError("Slurm array task ID is outside identity map")
    for index, task in enumerate(tasks):
        if (
            not isinstance(task, Mapping)
            or task.get("array_index") != index
            or set(task) != {
                "array_index", "rank", "seed", "input_sha256",
                    "input_path_identity", "output_relative_path",
            }
                or not Path(task["input_path_identity"]).is_absolute()
        ):
            raise ValueError("identity map tasks are not immutable canonical entries")
    selected = dict(tasks[task_id])
    if selected["rank"] not in ranks or selected["seed"] not in expected_seeds:
        raise ValueError("identity map selected task has unexpected identity")
    return selected
