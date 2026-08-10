"""Create the durable state namespace for the sole production size command."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from challenge15.cli import _parser, _integer_list, _verify_remote_runtime_copy
from challenge15.orchestrator import (
    OrchestrationInputs,
    DurableStateStore,
    TransitionEvidence,
    build_state_key,
    persist_state_key,
    run_task7b_driver,
)
from challenge15.production_schema import canonical_json, payload_sha256, validate_envelope


def _sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _payload_hash(path: str, schema: str) -> str:
    return payload_sha256(validate_envelope(Path(path), schema))


class Task7BActionExecutor:
    """Recover and execute immutable external actions from a state-key-bound plan."""

    def __init__(self, path: Path, *, common: dict[str, Any], ranks: tuple[int, ...]):
        if not path.is_absolute() or path.resolve(strict=True) != path:
            raise ValueError(
                "transition action manifest must be a canonical no-symlink path"
            )
        raw = path.read_bytes()
        document = json.loads(raw)
        if raw != canonical_json(document) + b"\n":
            raise ValueError("transition action manifest is not canonical JSON")
        if set(document) != {"common", "actions", "backup_argv"}:
            raise ValueError("transition action manifest fields mismatch")
        if document["common"] != common:
            raise ValueError("transition action manifest immutable bindings mismatch")
        self.actions = document["actions"]
        self.backup_argv = document["backup_argv"]
        required = {
            "VERIFY_INPUTS", "VERIFY_RUNTIME_SET_COPIES", "ENSURE_ORACLE",
            "CLAIM_SEEDS",
        }
        cycle = (
            "PREPARE_RANK", "TRAIN_RANK", "COORDINATE_EVALUATE",
            "EXPORT_GPU_IDENTITY_MAP", "TRANSFER_GPU_TO_CPU",
            "IMPORT_GPU_RESULTS", "EXACT_EVALUATE", "REDUCE_EXACT_INPUTS",
            "PROVISIONAL_FINALIZE", "CLASSIFY_FINALIZATION",
        )
        for rank in ranks:
            required.update(f"{state}/rank={rank}" for state in cycle)
            required.update(
                f"{state}/rank={rank}"
                for state in (
                    "SELECT_TERMINAL", "EXPORT_ACCEPTED_TERMINAL",
                    "STOP_ACCEPTED", "HARD_FAIL",
                )
            )
        required.update(f"DECIDE_EXTENSION/rank={rank}" for rank in ranks[:-1])
        required.add(f"STOP_PENDING/rank={ranks[-1]}")
        if not isinstance(self.actions, dict) or set(self.actions) != required:
            raise ValueError("transition action manifest does not cover Task 7B graph")
        self._validate_argv(self.backup_argv, backup=True)
        for spec in self.actions.values():
            if set(spec) != {"argv", "input_paths", "outputs"}:
                raise ValueError("transition action specification fields mismatch")
            self._validate_argv(spec["argv"])
            if not spec["input_paths"] or not spec["outputs"]:
                raise ValueError("every transition action must publish evidence")
            for value in spec["input_paths"]:
                candidate = Path(value)
                if (
                    not candidate.is_absolute()
                    or candidate.resolve(strict=True) != candidate
                ):
                    raise ValueError(
                        "transition input path is not canonical/no-symlink"
                    )
            for output in spec["outputs"]:
                if (
                    not isinstance(output, dict)
                    or set(output) != {"path", "schema"}
                    or not Path(output["path"]).is_absolute()
                ):
                    raise ValueError("transition output specification is invalid")

    @staticmethod
    def _validate_argv(argv: Any, *, backup: bool = False) -> None:
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(item, str) and item for item in argv)
            or not Path(argv[0]).is_absolute()
        ):
            raise ValueError("transition action argv must use an absolute executable")
        if backup and Path(argv[0]).name != "backup_once.sh":
            raise ValueError("state backup action must invoke backup_once.sh")
        if not backup and not (
            Path(argv[0]).name in {
                "submit_once.sh", "transfer_once.sh", "backup_once.sh",
            }
            or (
                len(argv) >= 4
                and argv[1:3] == ["-m", "challenge15.cli"]
            )
        ):
            raise ValueError(
                "transition actions must invoke an approved wrapper or scientific CLI"
            )

    @staticmethod
    def _key(state: str, rank: int | None) -> str:
        return state if rank is None else f"{state}/rank={rank}"

    @staticmethod
    def _digest(path: Path) -> str:
        try:
            payload = validate_envelope(path)
        except ValueError:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        return payload_sha256(payload)

    def recover(self, state: str, rank: int | None) -> TransitionEvidence | None:
        spec = self.actions[self._key(state, rank)]
        output_specs = spec["outputs"]
        output_paths = [Path(item["path"]) for item in output_specs]
        present = [path.is_file() and not path.is_symlink() for path in output_paths]
        if not any(present):
            return None
        if not all(present):
            raise ValueError("transition recovery found partial output evidence")
        outputs: list[str] = []
        promotions: list[str] = []
        imports: list[str] = []
        transfers: list[str] = []
        schedulers: list[str] = []
        finalization: dict[str, Any] | None = None
        for item, path in zip(output_specs, output_paths, strict=True):
            if not path.is_absolute() or path.resolve(strict=True) != path:
                raise ValueError("transition output path is not canonical/no-symlink")
            payload = validate_envelope(path, item["schema"])
            digest = payload_sha256(payload)
            outputs.append(digest)
            if item["schema"] == "challenge15.output-promotion.v1":
                promotions.append(digest)
            elif item["schema"] == "challenge15.import-bundle.v1":
                imports.append(digest)
            elif item["schema"] == "challenge15.transfer-receipt.v1":
                transfers.append(digest)
            elif item["schema"] == "challenge15.submission-receipt.v1":
                schedulers.append(digest)
            elif item["schema"] == "challenge15.reduction-finalization.v1":
                finalization = payload
        inputs = tuple(self._digest(Path(value)) for value in spec["input_paths"])
        outcome = "completed"
        if state == "CLASSIFY_FINALIZATION":
            if finalization is None:
                raise ValueError("classification must bind a finalization artifact")
            outcome = "accepted" if finalization["production_accepted"] else "pending"
        return TransitionEvidence(
            inputs,
            tuple(outputs),
            outcome,
            tuple(promotions),
            tuple(imports),
            tuple(transfers),
            tuple(schedulers),
        )

    def act(self, state: str, rank: int | None) -> TransitionEvidence:
        spec = self.actions[self._key(state, rank)]
        subprocess.run(spec["argv"], check=True)
        evidence = self.recover(state, rank)
        if evidence is None:
            raise ValueError("transition action returned without publishing evidence")
        return evidence

    def backup(self, manifest: Path) -> Path:
        argv = [
            str(manifest) if item == "{state_manifest}" else item
            for item in self.backup_argv
        ]
        if "{state_manifest}" not in self.backup_argv:
            raise ValueError("backup argv does not bind the state manifest")
        completed = subprocess.run(
            argv, check=True, capture_output=True, text=True
        )
        receipt = Path(completed.stdout.strip())
        validate_envelope(
            receipt, "challenge15.state-manifest-backup-receipt.v1"
        )
        return receipt


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(["production-orchestrate-size", *(argv or sys.argv[1:])])
    prerequisite = args.prerequisite_terminal_selection
    if args.particles == 6 and prerequisite:
        raise ValueError("N=6 must omit prerequisite terminal selection")
    if args.particles > 6 and not prerequisite:
        raise ValueError("N=7/N=8 require prerequisite terminal selection")
    source = validate_envelope(
        Path(args.source_manifest), "challenge15.source-manifest.v1"
    )
    local_runtime = validate_envelope(
        Path(args.runtime_set_local), "challenge15.runtime-attestation-set.v1"
    )
    if _sha(args.runtime_set_local) != args.runtime_set_local_sha256:
        raise ValueError("local runtime-set SHA256 mismatch")
    cpu_receipt = validate_envelope(
        Path(args.cpu_runtime_set_receipt),
        "challenge15.runtime-set-publication-receipt.v1",
    )
    gpu_receipt = validate_envelope(
        Path(args.gpu_runtime_set_receipt),
        "challenge15.runtime-set-publication-receipt.v1",
    )
    local_payload_hash = payload_sha256(local_runtime)
    policy_sha = _payload_hash(args.policy, "challenge15.production-policy.v1")
    source_sha = payload_sha256(source)
    if (
        local_runtime["source_manifest_sha256"] != source_sha
        or local_runtime["policy_sha256"] != policy_sha
    ):
        raise ValueError("local runtime-set source/policy mismatch")
    cpu_deployment_payload = validate_envelope(
        Path(args.cpu_deployment_receipt), "challenge15.deployment-receipt.v1"
    )
    gpu_deployment_payload = validate_envelope(
        Path(args.gpu_deployment_receipt), "challenge15.deployment-receipt.v1"
    )
    for label, receipt, deployment, controller, remote in (
        (
            "CPU", cpu_receipt, cpu_deployment_payload,
            args.cpu_controller, args.cpu_runtime_set_remote,
        ),
        (
            "GPU", gpu_receipt, gpu_deployment_payload,
            args.gpu_controller, args.gpu_runtime_set_remote,
        ),
    ):
        if (
            receipt["controller"] != controller
            or receipt["payload_sha256"] != local_payload_hash
            or receipt["controller_local_path_identity"] != f"{controller}:{remote}"
            or receipt["source_manifest_sha256"] != source_sha
            or receipt["policy_sha256"] != policy_sha
            or receipt["deployment_receipt_sha256"] != payload_sha256(deployment)
        ):
            raise ValueError(f"{label} runtime-set publication receipt mismatch")
        _verify_remote_runtime_copy(
            controller=controller,
            remote_path=remote,
            deployment=deployment,
            expected_byte_sha256=args.runtime_set_local_sha256,
            expected_payload_sha256=local_payload_hash,
            expected_role_map_sha256=payload_sha256(local_runtime["roles"]),
            expected_source_sha256=source_sha,
            expected_policy_sha256=policy_sha,
        )
    cpu_deployment = payload_sha256(cpu_deployment_payload)
    gpu_deployment = payload_sha256(gpu_deployment_payload)
    cpu_profile = validate_envelope(
        Path(args.cpu_profile), "challenge15.cluster-profile.v1"
    )
    gpu_profile = validate_envelope(
        Path(args.gpu_profile), "challenge15.cluster-profile.v1"
    )
    action_manifest_sha = _sha(args.transition_action_manifest)
    for label, profile, controller, root in (
        ("CPU", cpu_profile, args.cpu_controller, args.cpu_results_root),
        ("GPU", gpu_profile, args.gpu_controller, args.gpu_results_root),
    ):
        if (
            profile["controller"] != controller
            or profile["approved_results_root"] != root
        ):
            raise ValueError(f"{label} profile/controller/results-root mismatch")
    inputs = OrchestrationInputs(
        particles=args.particles,
        rank_ladder=tuple(_integer_list(args.rank_ladder, "rank-ladder")),
        seeds=tuple(_integer_list(args.seeds, "seeds")),
        base_configuration_sha256=_sha(args.base_config),
        policy_sha256=policy_sha,
        source_manifest_sha256=source_sha,
        source_revision=str(source["git_revision"]),
        runtime_set_local_sha256=args.runtime_set_local_sha256,
        runtime_set_local_path=str(Path(args.runtime_set_local).absolute()),
        cpu_runtime_set_remote_sha256=args.runtime_set_local_sha256,
        cpu_runtime_set_remote_path=args.cpu_runtime_set_remote,
        cpu_runtime_set_receipt_sha256=_payload_hash(
            args.cpu_runtime_set_receipt,
            "challenge15.runtime-set-publication-receipt.v1",
        ),
        gpu_runtime_set_remote_sha256=args.runtime_set_local_sha256,
        gpu_runtime_set_remote_path=args.gpu_runtime_set_remote,
        gpu_runtime_set_receipt_sha256=_payload_hash(
            args.gpu_runtime_set_receipt,
            "challenge15.runtime-set-publication-receipt.v1",
        ),
        prerequisite_terminal_selection_sha256=(
            None if prerequisite is None else _sha(prerequisite)
        ),
        cpu_controller=args.cpu_controller,
        gpu_controller=args.gpu_controller,
        cpu_profile_sha256=payload_sha256(cpu_profile),
        gpu_profile_sha256=payload_sha256(gpu_profile),
        cpu_deployment_receipt_sha256=cpu_deployment,
        gpu_deployment_receipt_sha256=gpu_deployment,
        cpu_results_root=args.cpu_results_root,
        gpu_results_root=args.gpu_results_root,
        state_root_base=args.state_root_base,
        state_backup_uri=args.state_backup_uri,
        state_mirror_root=args.state_mirror_root,
        transition_action_manifest_sha256=action_manifest_sha,
    )
    key = build_state_key(inputs)
    persist_state_key(key)
    executor = Task7BActionExecutor(
        Path(args.transition_action_manifest),
        common={
            "particles": args.particles,
            "rank_ladder": list(inputs.rank_ladder),
            "seed_set": list(inputs.seeds),
            "base_configuration_sha256": inputs.base_configuration_sha256,
            "policy_sha256": policy_sha,
            "source_manifest_sha256": source_sha,
            "runtime_set_sha256": args.runtime_set_local_sha256,
            "cpu_profile_sha256": inputs.cpu_profile_sha256,
            "gpu_profile_sha256": inputs.gpu_profile_sha256,
            "cpu_deployment_receipt_sha256": cpu_deployment,
            "gpu_deployment_receipt_sha256": gpu_deployment,
        },
        ranks=inputs.rank_ladder,
    )
    receipts = run_task7b_driver(
        DurableStateStore(key.run_root, state_key=key.sha256),
        executor,
        rank_ladder=inputs.rank_ladder,
        source_revision=inputs.source_revision,
        backup_uri=inputs.state_backup_uri,
        mirror_root=inputs.state_mirror_root,
        backup=executor.backup,
    )
    print(
        json.dumps(
            {
                "state_key": key.sha256,
                "state_root": str(key.run_root),
                "transition_receipts": [str(path) for path in receipts],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
