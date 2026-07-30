"""Contract tests for the pre-registered Phase 7--11 interfaces."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from route_d_plus.future.verify import (
    SCHEMA_DIR,
    validate_dispatch,
    validate_stage_gate,
)

REVISION = "1" * 40
SHA256 = "2" * 64


def phase7_dispatch(run_root: Path) -> dict[str, object]:
    tasks = [
        {
            "task_id": f"m-{m + 2}",
            "kind": "ed-sector",
            "run_dir": f"phase7/m-{m + 2}",
            "required_gates": ["sector_energy", "symmetry_readback"],
            "n_electrons": 6,
            "m_sector": m,
        }
        for m in range(-2, 3)
    ]
    tasks.extend(
        [
            {
                "task_id": "overlap",
                "kind": "overlap",
                "run_dir": "phase7/overlap",
                "required_gates": ["overlap_complete"],
                "n_electrons": 6,
                "m_sector": None,
            },
            {
                "task_id": "span",
                "kind": "span-ceiling",
                "run_dir": "phase7/span",
                "required_gates": ["span_ceiling_complete"],
                "n_electrons": 6,
                "m_sector": None,
            },
        ]
    )
    return {
        "schema_version": (
            "challenge-15-route-d-plus-future-dispatch-v1"
        ),
        "stage": "phase7",
        "run_id": "phase7-contract-test",
        "run_root": str(run_root),
        "source_revision": REVISION,
        "created_at_utc": "2026-07-30T00:00:00+00:00",
        "prerequisites": [
            {
                "kind": "phase6-frozen-checkpoint-gate",
                "path": "/remote/phase6-freeze.json",
                "sha256": SHA256,
            }
        ],
        "tasks": tasks,
    }


def test_all_future_schemas_are_valid_draft_2020_12() -> None:
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)


def test_phase7_capacity_rules_are_preregistered_before_reveal() -> None:
    schema_path = SCHEMA_DIR / "phase7-capacity-protocol.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    protocol = json.loads(
        (SCHEMA_DIR / "phase7-capacity-protocol.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(protocol)
    assert protocol["frozen_before_phase7"] is True
    assert protocol["mandatory_benchmark"] == {
        "gap_absolute_error_max": 0.005,
        "fidelity0_min": 0.95,
        "fidelity2_min": 0.9,
    }
    assert [item["capacity"] for item in protocol["phase8_candidates"]] == [
        "D+1",
        "D+2",
    ]
    assert all(
        item["run_concurrently"]
        for item in protocol["phase8_candidates"]
    )
    assert protocol["heldout_used_for_structure_selection"] is False
    assert protocol["beyond_ed_used_for_structure_selection"] is False


def test_architecture_freeze_protocol_blocks_postfreeze_selection() -> None:
    schema_path = SCHEMA_DIR / "architecture-freeze-protocol.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    protocol = json.loads(
        (SCHEMA_DIR / "architecture-freeze-protocol.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(protocol)
    assert protocol["phase7_may_modify_capacity"] is False
    assert protocol["dplus0"]["checkpoint_selection"] == "final-update-no-ed"
    assert all(protocol["postfreeze_rules"].values())


def test_phase7_requires_exact_parallel_task_set(tmp_path: Path) -> None:
    dispatch = phase7_dispatch(tmp_path)
    validate_dispatch(dispatch, verify_prerequisites=False)

    dispatch["tasks"] = dispatch["tasks"][:-1]
    with pytest.raises(ValueError, match="five sectors, overlap, and span"):
        validate_dispatch(dispatch, verify_prerequisites=False)


def test_dispatch_rejects_shared_run_directory(tmp_path: Path) -> None:
    dispatch = phase7_dispatch(tmp_path)
    dispatch["tasks"][1]["run_dir"] = dispatch["tasks"][0]["run_dir"]
    with pytest.raises(ValueError, match="not isolated"):
        validate_dispatch(dispatch, verify_prerequisites=False)


def test_phase7_gate_cannot_change_capacity_protocol(
    tmp_path: Path,
) -> None:
    dispatch = phase7_dispatch(tmp_path)
    gate = {
        "schema_version": (
            "challenge-15-route-d-plus-future-stage-gate-v1"
        ),
        "stage": "phase7",
        "source_revision": REVISION,
        "task_ids": [task["task_id"] for task in dispatch["tasks"]],
        "created_at_utc": "2026-07-30T00:00:00+00:00",
        "decision": {
            "kind": "phase7-capacity-decision",
            "benchmark_classification": "expression-limited",
            "capacity_action": "trigger-preregistered-D+1-D+2",
            "capacity_protocol_modified": False,
            "checkpoint_modified": False,
        },
        "passed": True,
    }
    validate_stage_gate(gate, dispatch=dispatch)

    gate["decision"]["capacity_protocol_modified"] = True
    with pytest.raises(jsonschema.ValidationError):
        validate_stage_gate(gate, dispatch=dispatch)


def test_postfreeze_stages_require_architecture_freeze(
    tmp_path: Path,
) -> None:
    dispatch = {
        "schema_version": (
            "challenge-15-route-d-plus-future-dispatch-v1"
        ),
        "stage": "phase11",
        "run_id": "phase11-contract-test",
        "run_root": str(tmp_path),
        "source_revision": REVISION,
        "created_at_utc": "2026-07-30T00:00:00+00:00",
        "prerequisites": [
            {
                "kind": "protocol-registration",
                "path": "/remote/protocol.json",
                "sha256": SHA256,
            }
        ],
        "tasks": [
            {
                "task_id": "n-8-seed-848",
                "kind": "beyond-ed",
                "run_dir": "phase11/n-8-seed-848",
                "required_gates": ["sampling", "symmetry", "resource"],
                "n_electrons": 8,
                "seed": 848,
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        validate_dispatch(dispatch, verify_prerequisites=False)
