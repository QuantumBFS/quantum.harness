from __future__ import annotations

import json
from pathlib import Path

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase3_schema_enforces_tensor_algebra_gate() -> None:
    schema = json.loads(
        (ROUTE_D_PLUS_ROOT / "phase3.schema.json").read_text(encoding="utf-8")
    )
    assert schema["properties"]["two_q"]["const"] == 15
    assert schema["properties"]["tensor_count"]["const"] == 256
    errors = schema["properties"]["max_errors"]["properties"]
    assert errors["hermiticity"]["exclusiveMaximum"] == 1.0e-12
    assert errors["finite_rotation"]["exclusiveMaximum"] == 1.0e-6
    assert errors["one_body_action"]["exclusiveMaximum"] == 1.0e-12
    assert schema["properties"]["passed"]["const"] is True


def test_phase3_batch_requires_phase2_certificate() -> None:
    batch = (ROUTE_D_PLUS_ROOT / "phase3.sbatch").read_text(encoding="utf-8")
    certificate = (ROUTE_D_PLUS_ROOT / "certify_phase3.py").read_text(
        encoding="utf-8"
    )
    assert "ROUTE_D_PLUS_PHASE2_CERTIFICATE:?" in batch
    assert "tests/route_d_plus -q" in batch
    assert "-m route_d_plus.certify_phase3" in batch
    assert "--two-q 15" in batch
    assert "require_phase2_certificate" in certificate
    assert "validate_certificate(payload)" in certificate
