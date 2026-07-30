from __future__ import annotations

import json
from pathlib import Path

import jsonschema

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase7_registration_schema_is_strict() -> None:
    schema = json.loads(
        (ROUTE_D_PLUS_ROOT / "phase7-registration.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["exact_task_count"]["const"] == 7
    assert schema["properties"]["ed_accessed"]["const"] is False


def test_phase7_registration_has_exact_parallel_dag() -> None:
    source = (ROUTE_D_PLUS_ROOT / "prepare_phase7.py").read_text(
        encoding="utf-8"
    )
    assert "phase6-final-v2.schema.json" in source
    assert "phase6-frozen-checkpoint-gate" in source
    assert 'for m in range(-2, 3)' in source
    assert '"kind": "overlap"' in source
    assert '"kind": "span-ceiling"' in source
    assert "validate_dispatch(dispatch)" in source
    assert '"ed_accessed": False' in source


def test_finalizer_registers_but_does_not_run_phase7() -> None:
    batch = (ROUTE_D_PLUS_ROOT / "phase6_finalize_v2.sbatch").read_text(
        encoding="utf-8"
    )
    assert "ROUTE_D_PLUS_PHASE7_RUN_ID:?" in batch
    assert "-m route_d_plus.prepare_phase7" in batch
    assert "phase7-registration.json" in batch
    assert "phase7_parallel.sbatch" not in batch
