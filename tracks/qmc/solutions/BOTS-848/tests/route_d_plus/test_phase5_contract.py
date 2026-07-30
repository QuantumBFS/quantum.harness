from __future__ import annotations

import json
from pathlib import Path

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase5_schema_enforces_scalar_generator_gate() -> None:
    schema = json.loads(
        (ROUTE_D_PLUS_ROOT / "phase5.schema.json").read_text(encoding="utf-8")
    )
    properties = schema["properties"]
    assert properties["target_n_electrons"]["const"] == 6
    assert properties["target_two_q"]["const"] == 15
    assert properties["certification_n_electrons"]["const"] == 4
    assert properties["certification_two_q"]["const"] == 9
    assert properties["fock_dimension"]["const"] == 210
    assert properties["covariance"]["properties"]["retained_directions"][
        "const"
    ] == 3
    assert (
        properties["covariance"]["properties"]["covariance_scale"][
            "exclusiveMinimum"
        ]
        == 1.0e-8
    )
    errors = properties["max_errors"]["properties"]
    assert errors["proof_production"]["exclusiveMaximum"] == 1.0e-10
    assert errors["scalarity"]["exclusiveMaximum"] == 1.0e-11
    assert properties["passed"]["const"] is True


def test_phase5_batch_requires_phase4_certificate() -> None:
    batch = (ROUTE_D_PLUS_ROOT / "phase5.sbatch").read_text(encoding="utf-8")
    certificate = (ROUTE_D_PLUS_ROOT / "certify_phase5.py").read_text(
        encoding="utf-8"
    )
    assert "ROUTE_D_PLUS_PHASE4_CERTIFICATE:?" in batch
    assert "tests/route_d_plus -q" in batch
    assert "-m route_d_plus.certify_phase5" in batch
    assert "require_phase4_certificate" in certificate
    assert "validate_certificate(payload)" in certificate
