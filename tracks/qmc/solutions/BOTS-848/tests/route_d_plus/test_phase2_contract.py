from __future__ import annotations

import json
from pathlib import Path


SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase2_certificate_schema_enforces_the_fixed_gate() -> None:
    schema = json.loads(
        (ROUTE_D_PLUS_ROOT / "phase2.schema.json").read_text(encoding="utf-8")
    )

    assert schema["properties"]["two_q"]["const"] == 15
    assert schema["properties"]["orbital_count"]["const"] == 16
    assert schema["properties"]["tolerance"]["const"] == 1.0e-12
    assert schema["properties"]["passed"]["const"] is True
    errors = schema["properties"]["max_errors"]["properties"]
    assert errors["orbital_reconstruction"]["exclusiveMaximum"] == 1.0e-12
    assert errors["orbital_overlap"]["exclusiveMaximum"] == 1.0e-12


def test_phase2_batch_requires_remote_phase1_evidence() -> None:
    batch = (ROUTE_D_PLUS_ROOT / "phase2.sbatch").read_text(encoding="utf-8")
    certificate = (ROUTE_D_PLUS_ROOT / "certify_phase2.py").read_text(
        encoding="utf-8"
    )

    assert "ROUTE_D_PLUS_REPO_ROOT:?" in batch
    assert "ROUTE_D_PLUS_PHASE1_MANIFEST:?" in batch
    assert "ROUTE_D_PLUS_RUN_ID:?" in batch
    assert ".venv/bin/python" in batch
    assert "-m ruff check" in batch
    assert "-m pytest" in batch
    assert "tests/route_d_plus -q" in batch
    assert "-m route_d_plus.certify_phase2" in batch
    assert "--two-q 15" in batch
    assert "require_phase1_manifest" in certificate
    assert "git_dirty" in certificate
    assert "validate_certificate(payload)" in certificate
