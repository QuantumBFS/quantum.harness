from __future__ import annotations

import json
from pathlib import Path

import pytest

from challenge15.cli import _parser
from challenge15.orchestrator import DurableStateStore, validate_state_root_base
from challenge15.production_schema import canonical_json


TASK7_COMMANDS = (
    "resource-override",
    "exact-shard",
    "cumulative-reducer-identity-map",
    "cycle-ranks",
    "accepted-terminal-identity-map",
    "runtime-set-identity-map",
    "reduce-size",
    "export-bundle",
    "import-bundle",
    "output-promotion",
    "select-published",
    "verify-transfer",
    "transfer-receipt",
    "bootstrap-export",
    "bootstrap-import",
    "reduce-cross-size",
)


def test_every_advertised_task7_command_has_an_execution_handler():
    parser = _parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(getattr(action, "choices", None), dict)
        and "resource-override" in action.choices
    )
    placeholder = parser.parse_args(
        [
            "resource-override",
            "--extension", "/e", "--attempt", "1", "--reason", "oom",
            "--walker-microbatch", "1", "--carrier-block", "1",
            "--quadrature-block", "1", "--output-dir", "/o", "--create-only",
        ]
    ).handler
    assert placeholder.__name__ != "_contract_not_executed"
    for command in TASK7_COMMANDS:
        assert subparsers.choices[command].get_default("handler").__name__ != (
            "_contract_not_executed"
        )


def test_durable_state_rejects_symlinked_ancestor(tmp_path: Path):
    durable = tmp_path / "durable"
    durable.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(durable, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink ancestor"):
        validate_state_root_base(linked / "state")


def test_transition_receipt_binds_external_evidence(tmp_path: Path):
    store = DurableStateStore(tmp_path / "state")
    receipt = store.complete_transition(
        state="TRANSFER_GPU_TO_CPU",
        attempt=1,
        input_sha256s=("a" * 64,),
        output_sha256s=("b" * 64,),
        outcome="imported",
        output_promotion_sha256s=("c" * 64,),
        import_receipt_sha256s=("d" * 64,),
        transfer_receipt_sha256s=("e" * 64,),
        scheduler_receipt_sha256s=("f" * 64,),
    )
    payload = json.loads(receipt.read_text())["payload"]
    assert payload["output_promotion_sha256s"] == ["c" * 64]
    assert payload["import_receipt_sha256s"] == ["d" * 64]
    assert payload["transfer_receipt_sha256s"] == ["e" * 64]
    assert payload["scheduler_receipt_sha256s"] == ["f" * 64]


def test_transition_driver_recovers_then_backs_up_every_new_marker(tmp_path: Path):
    from challenge15.orchestrator import (
        TransitionEvidence,
        TransitionStep,
        run_transition_driver,
    )

    calls: list[str] = []
    evidence = TransitionEvidence(("a" * 64,), ("b" * 64,), "done")

    def backup(manifest: Path) -> Path:
        calls.append(f"backup:{manifest.name}")
        receipt = tmp_path / f"backup-{len(calls)}.json"
        receipt.write_text("{}")
        return receipt

    steps = (
        TransitionStep("VERIFY_INPUTS", lambda: evidence, lambda: (_ for _ in ()).throw(
            AssertionError("recovered transition acted")
        )),
        TransitionStep(
            "VERIFY_RUNTIME_SET_COPIES",
            lambda: None,
            lambda: calls.append("act") or evidence,
        ),
    )
    receipts = run_transition_driver(
        DurableStateStore(tmp_path / "state", state_key="1" * 64),
        steps,
        source_revision="2" * 40,
        backup_uri="ssh://cpu/approved",
        mirror_root=None,
        backup=backup,
    )
    assert len(receipts) == 2
    assert calls[0].startswith("backup:")
    assert calls[1] == "act"
    assert calls[2].startswith("backup:")


def test_identity_map_task_resolves_exact_immutable_identity(tmp_path: Path):
    tasks = [
        {
            "array_index": index,
            "rank": 2,
            "seed": index,
            "input_sha256": f"{index + 1:x}" * 64,
            "input_path_identity": f"/inputs/rank=2/seed={index}.json",
            "output_relative_path": f"rank=2/seed={index}.json",
        }
        for index in range(5)
    ]
    path = tmp_path / "map.json"
    payload = {
        "stage": "training",
        "expected_ranks": [2],
        "expected_seeds": [0, 1, 2, 3, 4],
        "task_count": 5,
        "array_concurrency": 5,
        "tasks": tasks,
    }
    import hashlib

    path.write_bytes(
        canonical_json(
            {
                "schema": "challenge15.identity-map.v1",
                "payload": payload,
                "payload_sha256": hashlib.sha256(canonical_json(payload)).hexdigest(),
            }
        )
        + b"\n"
    )
    from challenge15.orchestrator import resolve_array_identity

    assert resolve_array_identity(path, 3, expected_stage="training") == tasks[3]


def test_restart_repairs_manifest_and_backup_after_marker(tmp_path: Path):
    from challenge15.orchestrator import (
        TransitionEvidence,
        TransitionStep,
        run_transition_driver,
    )

    store = DurableStateStore(tmp_path / "state", state_key="1" * 64)
    store.complete_transition(
        state="VERIFY_INPUTS",
        attempt=1,
        input_sha256s=("a" * 64,),
        output_sha256s=("b" * 64,),
        outcome="verified",
    )
    backed_up: list[Path] = []

    def backup(manifest: Path) -> Path:
        backed_up.append(manifest)
        receipt = tmp_path / "backup.json"
        receipt.write_text("{}")
        return receipt

    arguments = (
        store,
        (
            TransitionStep(
                "VERIFY_INPUTS",
                lambda: TransitionEvidence(
                    ("a" * 64,), ("b" * 64,), "verified"
                ),
                lambda: (_ for _ in ()).throw(AssertionError("must not act")),
            ),
        ),
    )
    keyword_arguments = {
        "source_revision": "2" * 40,
        "backup_uri": "ssh://cpu/approved",
        "mirror_root": None,
        "backup": backup,
    }
    run_transition_driver(*arguments, **keyword_arguments)
    run_transition_driver(*arguments, **keyword_arguments)
    assert len(backed_up) == 1
    assert backed_up[0].parent.name == "state-manifests"


def test_identity_map_rejects_more_than_five_scientific_cells():
    from challenge15.reducer import build_identity_map

    hashes = {
        (rank, seed): f"{rank + seed + 1:x}"[-1] * 64
        for rank in (1, 2)
        for seed in range(5)
    }
    with pytest.raises(ValueError, match="exactly five new-rank"):
        build_identity_map(
            stage="training",
            expected_ranks=(1, 2),
            input_sha256_by_identity=hashes,
            array_concurrency=5,
            policy_sha256="a" * 64,
            source_manifest_sha256="b" * 64,
            runtime_attestations={},
            base_configuration_sha256="c" * 64,
            particles=6,
        )


def test_array_resolution_rejects_wrong_envelope_hash(tmp_path: Path):
    source = tmp_path / "map.json"
    source.write_bytes(
        canonical_json(
            {
                "schema": "challenge15.identity-map.v1",
                "payload": {
                    "stage": "training",
                    "expected_ranks": [2],
                    "expected_seeds": list(range(5)),
                    "task_count": 5,
                    "array_concurrency": 5,
                    "tasks": [
                        {
                            "array_index": seed,
                            "rank": 2,
                            "seed": seed,
                            "input_sha256": f"{seed + 1:x}" * 64,
                            "input_path_identity": f"/inputs/rank=2/seed={seed}.json",
                            "output_relative_path": f"rank=2/seed={seed}.json",
                        }
                        for seed in range(5)
                    ],
                },
                "payload_sha256": "0" * 64,
            }
        )
        + b"\n"
    )
    from challenge15.orchestrator import resolve_array_identity

    with pytest.raises(ValueError, match="payload SHA256"):
        resolve_array_identity(source, 0, expected_stage="training")


@pytest.mark.parametrize(
    ("cores", "memory", "passes"),
    [(128, "500000M", True), (127, "500000M", False), (128, "499999M", False)],
)
def test_wuzh_activation_requires_documented_capacity(cores, memory, passes):
    from challenge15.cluster_profile import validate_wuzh_capacity

    if passes:
        validate_wuzh_capacity(cpus_per_task=cores, memory=memory)
    else:
        with pytest.raises(ValueError, match="WUZH02 capacity"):
            validate_wuzh_capacity(cpus_per_task=cores, memory=memory)


def test_backup_receipt_schema_is_registered():
    from challenge15.production_policy import ARTIFACT_SCHEMAS

    assert "challenge15.state-manifest-backup-receipt.v1" in ARTIFACT_SCHEMAS


def test_remote_runtime_copy_uses_deployment_interpreter(monkeypatch):
    import subprocess
    from challenge15.cli import _verify_remote_runtime_copy

    expected = {
        "byte_sha256": "a" * 64,
        "payload_sha256": "b" * 64,
        "role_map_sha256": "c" * 64,
        "source_manifest_sha256": "d" * 64,
        "policy_sha256": "e" * 64,
    }
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, json.dumps(expected), "")

    monkeypatch.setattr("challenge15.cli.subprocess.run", fake_run)
    _verify_remote_runtime_copy(
        controller="lasg02",
        remote_path="/remote/runtime.json",
        deployment={
            "deployment_root": "/approved/deploy",
            "interpreter": "/approved/deploy/venv/bin/python",
        },
        expected_byte_sha256=expected["byte_sha256"],
        expected_payload_sha256=expected["payload_sha256"],
        expected_role_map_sha256=expected["role_map_sha256"],
        expected_source_sha256=expected["source_manifest_sha256"],
        expected_policy_sha256=expected["policy_sha256"],
    )
    assert calls == [
        [
            "ssh", "lasg02", "/approved/deploy/venv/bin/python", "-m",
            "challenge15.cli", "runtime-set-remote-digest", "--runtime-set",
            "/remote/runtime.json", "--source-manifest-sha256", "d" * 64,
            "--policy-sha256", "e" * 64,
        ]
    ]


def test_task7b_driver_executes_rank_branch_and_terminal_states(tmp_path: Path):
    from challenge15.orchestrator import (
        TransitionEvidence,
        run_task7b_driver,
    )

    calls: list[str] = []

    class FakeExecutor:
        def recover(self, state, rank):
            return None

        def act(self, state, rank):
            key = state if rank is None else f"{state}/rank={rank}"
            calls.append(key)
            outcome = (
                "accepted"
                if state == "CLASSIFY_FINALIZATION" and rank == 2
                else "pending"
                if state == "CLASSIFY_FINALIZATION"
                else "completed"
            )
            return TransitionEvidence(("a" * 64,), ("b" * 64,), outcome)

    run_task7b_driver(
        DurableStateStore(tmp_path / "state", state_key="1" * 64),
        FakeExecutor(),
        rank_ladder=(1, 2, 4, 8),
        source_revision="2" * 40,
        backup_uri="ssh://cpu/approved",
        mirror_root=None,
        backup=lambda manifest: manifest,
    )
    assert calls[:4] == [
        "VERIFY_INPUTS",
        "VERIFY_RUNTIME_SET_COPIES",
        "ENSURE_ORACLE",
        "CLAIM_SEEDS",
    ]
    assert "DECIDE_EXTENSION/rank=1" in calls
    assert "SELECT_TERMINAL/rank=2" in calls
    assert calls[-1] == "STOP_ACCEPTED/rank=2"
    assert not any("rank=4" in call for call in calls)
