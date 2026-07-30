from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from route_d_plus.phase7 import _phase7_tasks

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase7_domain_and_authorization_schemas_are_valid() -> None:
    for name in (
        "phase7-authorization.schema.json",
        "phase7-domain.schema.json",
    ):
        schema = json.loads(
            (ROUTE_ROOT / name).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False


def test_phase7_execution_uses_exact_isolated_task_set() -> None:
    tasks = _phase7_tasks()
    assert len(tasks) == 7
    assert sorted(
        task["m_sector"]
        for task in tasks
        if task["kind"] == "ed-sector"
    ) == [-2, -1, 0, 1, 2]
    assert sum(task["kind"] == "overlap" for task in tasks) == 1
    assert sum(task["kind"] == "span-ceiling" for task in tasks) == 1
    assert len({task["run_dir"] for task in tasks}) == 7


def test_phase7_batch_runs_tasks_concurrently_and_aggregates() -> None:
    source = (ROUTE_ROOT / "phase7_run.sbatch").read_text(
        encoding="utf-8"
    )
    assert "user-authorized" not in source
    assert "route_d_plus.phase7 authorize" in source
    assert "srun --exclusive" in source
    assert 'pids+=("$!")' in source
    assert "route_d_plus.phase7 finalize" in source
    assert "route_d_plus.future.verify aggregate" in source


def test_user_override_preserves_causal_boundaries() -> None:
    schema = json.loads(
        (ROUTE_ROOT / "phase7-authorization.schema.json").read_text(
            encoding="utf-8"
        )
    )
    properties = schema["properties"]
    assert properties["phase6_frozen"]["const"] is False
    assert properties["checkpoint_modified"]["const"] is False
    assert properties["capacity_protocol_modified"]["const"] is False
    assert properties["heldout_accessed"]["const"] is False
    assert properties["beyond_ed_accessed"]["const"] is False
