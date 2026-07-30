from __future__ import annotations

import json
from pathlib import Path

import jsonschema

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase6_final_and_readback_schemas_are_strict() -> None:
    for name in ("phase6-final.schema.json", "phase6-readback.schema.json"):
        schema = json.loads(
            (ROUTE_D_PLUS_ROOT / name).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False
        assert schema["properties"]["passed"]["const"] is True


def test_phase6_finalizer_rehashes_every_exit_artifact() -> None:
    source = (ROUTE_D_PLUS_ROOT / "finalize_phase6.py").read_text(
        encoding="utf-8"
    )
    assert "phase6.schema.json" in source
    assert "phase6a.schema.json" in source
    assert "architecture hash mismatch" in source
    assert "checkpoint hash mismatch" in source
    assert "symmetry hash mismatch" in source
    assert "blind access audit hash mismatch" in source
    assert "gres/gpu=1" in source
    assert "all_artifact_schemas" in source
