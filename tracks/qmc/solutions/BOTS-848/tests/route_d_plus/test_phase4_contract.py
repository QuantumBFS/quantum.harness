from __future__ import annotations

import json
from pathlib import Path

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase4_schema_enforces_analytic_mother_gate() -> None:
    schema = json.loads(
        (ROUTE_D_PLUS_ROOT / "phase4.schema.json").read_text(encoding="utf-8")
    )
    assert schema["properties"]["n_electrons"]["const"] == 6
    assert schema["properties"]["two_q"]["const"] == 15
    assert schema["properties"]["tower_components"]["const"] == 5
    assert (
        schema["properties"]["minimum_component_magnitude"][
            "exclusiveMinimum"
        ]
        == 1.0e-14
    )
    errors = schema["properties"]["max_errors"]["properties"]
    assert errors["mother_exchange"]["exclusiveMaximum"] == 1.0e-12
    assert errors["tower_exchange"]["exclusiveMaximum"] == 1.0e-10
    assert errors["ladder"]["exclusiveMaximum"] == 1.0e-8
    assert errors["finite_rotation"]["exclusiveMaximum"] == 1.0e-6
    assert schema["properties"]["passed"]["const"] is True


def test_phase4_batch_requires_phase3_certificate() -> None:
    batch = (ROUTE_D_PLUS_ROOT / "phase4.sbatch").read_text(encoding="utf-8")
    certificate = (ROUTE_D_PLUS_ROOT / "certify_phase4.py").read_text(
        encoding="utf-8"
    )
    assert "ROUTE_D_PLUS_PHASE3_CERTIFICATE:?" in batch
    assert "tests/route_d_plus -q" in batch
    assert "-m route_d_plus.certify_phase4" in batch
    assert "--n-electrons 6" in batch
    assert "--two-q 15" in batch
    assert "require_phase3_certificate" in certificate
    assert "validate_certificate(payload)" in certificate
