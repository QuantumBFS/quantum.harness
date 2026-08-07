from __future__ import annotations

import json
from pathlib import Path

import jsonschema

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase6_final_v2_schemas_are_strict() -> None:
    for name in (
        "phase6-final-v2.schema.json",
        "phase6-final-v2-readback.schema.json",
    ):
        schema = json.loads(
            (ROUTE_D_PLUS_ROOT / name).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False
        assert schema["properties"]["passed"]["const"] is True


def test_v2_finalizer_binds_all_three_source_revisions() -> None:
    source = (
        ROUTE_D_PLUS_ROOT / "finalize_phase6_v2.py"
    ).read_text(encoding="utf-8")
    assert 'exact_failed_gates(attempt) != ["gap_precision"]' in source
    assert "checkpoint_producer" in source
    assert "measurement_source_revision" in source
    assert "finalizer_revision" in source
    assert "architecture-freeze-protocol.json" in source
    assert "phase7-capacity-protocol.json" in source
    assert "measurement task hash mismatch" in source
    assert "measurement task set is not exact" in source
    assert "PHASE6_ATTEMPT_READBACK=passed" in source
    assert "gres/gpu=1" in source
    assert "all_artifact_hashes" in source
    assert "all_artifact_schemas" in source


def test_v2_finalize_batch_captures_three_jobs() -> None:
    batch = (
        ROUTE_D_PLUS_ROOT / "phase6_finalize_v2.sbatch"
    ).read_text(encoding="utf-8")
    assert "#SBATCH --gres=gpu:1" in batch
    assert "ROUTE_D_PLUS_TRAINING_JOB_ID:?" in batch
    assert "ROUTE_D_PLUS_ATTEMPT_READBACK_JOB_ID:?" in batch
    assert "ROUTE_D_PLUS_MEASUREMENT_JOB_ID:?" in batch
    assert batch.count("sacct -j") == 3
    assert "-m route_d_plus.finalize_phase6_v2 finalize" in batch
    assert "-m route_d_plus.finalize_phase6_v2 verify" in batch
    assert "PHASE6_FROZEN_GATE_V2=passed" in batch
