from dataclasses import replace
from pathlib import Path

import pytest

from challenge15.orchestrator import (
    DurableStateStore,
    OrchestrationInputs,
    orchestrate_rank_outcomes,
    build_state_key,
    persist_state_key,
    rank_trace,
    validate_backup_uri,
    validate_state_root_base,
)


def _inputs(tmp_path: Path) -> OrchestrationInputs:
    return OrchestrationInputs(
        particles=6,
        rank_ladder=(1, 2, 4, 8),
        seeds=(0, 1, 2, 3, 4),
        base_configuration_sha256="a" * 64,
        policy_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        source_revision="d" * 40,
        runtime_set_local_sha256="e" * 64,
        runtime_set_local_path="/persistent/runtime.json",
        cpu_runtime_set_remote_sha256="e" * 64,
        cpu_runtime_set_remote_path="/public/home/student090/results/challenge15/runtime.json",
        cpu_runtime_set_receipt_sha256="f" * 64,
        gpu_runtime_set_remote_sha256="e" * 64,
        gpu_runtime_set_remote_path="/work/share/giggleliu/jiangweiqi/results/challenge15/runtime.json",
        gpu_runtime_set_receipt_sha256="1" * 64,
        prerequisite_terminal_selection_sha256=None,
        cpu_controller="lasg02",
        gpu_controller="qdeshell",
        cpu_profile_sha256="2" * 64,
        gpu_profile_sha256="3" * 64,
        cpu_deployment_receipt_sha256="4" * 64,
        gpu_deployment_receipt_sha256="5" * 64,
        cpu_results_root="/public/home/student090/results/challenge15",
        gpu_results_root="/work/share/giggleliu/jiangweiqi/results/challenge15",
        state_root_base=f"/home/footman/.local/state/challenge15-test-{tmp_path.name}",
        state_backup_uri=(
            "ssh://lasg02-student090/public/home/student090/results/"
            "challenge15/orchestration-backups"
        ),
        state_mirror_root=None,
    )


def test_rank_trace_is_not_caller_derived():
    assert rank_trace(1) == ()
    assert rank_trace(2) == (1,)
    assert rank_trace(4) == (1, 2)
    assert rank_trace(8) == (1, 2, 4)
    with pytest.raises(ValueError, match="rank ladder"):
        rank_trace(3)


def test_every_input_change_changes_state_key(tmp_path):
    inputs = _inputs(tmp_path)
    changed = replace(inputs, cpu_results_root=inputs.cpu_results_root + "/other")
    assert build_state_key(inputs).sha256 != build_state_key(changed).sha256


@pytest.mark.parametrize("path", ["/tmp/c15", "/var/tmp/c15", "relative"])
def test_durable_state_rejects_temporary_or_relative(path):
    with pytest.raises(ValueError, match="durable state root"):
        validate_state_root_base(path)


def test_backup_rejects_local_or_unapproved_failure_domain(tmp_path):
    with pytest.raises(ValueError, match="distinct durable failure domain"):
        validate_backup_uri("ssh://localhost/backup", local_host="localhost")
    with pytest.raises(ValueError, match="approved results root"):
        validate_backup_uri(
            "ssh://lasg02-student090/tmp/backup",
            local_host="localhost",
            approved_root="/public/home/student090/results/challenge15",
        )


def test_transition_marker_is_create_only_and_restartable(tmp_path):
    root = tmp_path / "durable"
    store = DurableStateStore(root)
    receipt = store.complete_transition(
        state="VERIFY_INPUTS",
        attempt=1,
        input_sha256s=("a" * 64,),
        output_sha256s=("b" * 64,),
        outcome="verified",
    )
    restarted = DurableStateStore(root)
    assert restarted.completed_receipt("VERIFY_INPUTS") == receipt
    with pytest.raises(ValueError, match="conflicting completion marker"):
        restarted.complete_transition(
            state="VERIFY_INPUTS",
            attempt=2,
            input_sha256s=("a" * 64,),
            output_sha256s=("c" * 64,),
            outcome="different",
        )


def test_persist_state_key_reopens_identical_state(tmp_path):
    inputs = _inputs(tmp_path)
    key = build_state_key(inputs)
    first = persist_state_key(key)
    second = persist_state_key(key)
    assert second == first
    assert second.read_bytes() == first.read_bytes()


def test_rank_outcome_machine_runs_full_cycles_and_selects_only_accepted():
    outcome = orchestrate_rank_outcomes(
        {1: "pending", 2: "pending", 4: "pending", 8: "accepted"}
    )
    assert outcome.visited_ranks == (1, 2, 4, 8)
    assert outcome.cycle_inputs == (
        (1, ()),
        (2, (1,)),
        (4, (1, 2)),
        (8, (1, 2, 4)),
    )
    assert outcome.state == "STOP_ACCEPTED"
    assert "SELECT_TERMINAL" in outcome.transition_names


def test_pending_at_rank8_never_selects_terminal():
    outcome = orchestrate_rank_outcomes(
        {1: "pending", 2: "pending", 4: "pending", 8: "pending"}
    )
    assert outcome.state == "STOP_PENDING"
    assert "SELECT_TERMINAL" not in outcome.transition_names
