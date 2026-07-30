from __future__ import annotations

import json
from pathlib import Path

import jsonschema

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_measurement_extension_schemas_pin_blind_parallel_protocol() -> None:
    task_schema = json.loads(
        (
            ROUTE_D_PLUS_ROOT
            / "phase6-measurement-task.schema.json"
        ).read_text(encoding="utf-8")
    )
    aggregate_schema = json.loads(
        (
            ROUTE_D_PLUS_ROOT / "phase6-measurement.schema.json"
        ).read_text(encoding="utf-8")
    )
    attempt_schema = json.loads(
        (
            ROUTE_D_PLUS_ROOT
            / "phase6-measurement-attempt.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(task_schema)
    jsonschema.Draft202012Validator.check_schema(aggregate_schema)
    jsonschema.Draft202012Validator.check_schema(attempt_schema)
    task_properties = task_schema["properties"]
    assert task_properties["samples"]["const"] == 2048
    assert task_properties["measurement_chunk"]["const"] == 128
    assert task_properties["blind_audit_events"]["maxItems"] == 0
    assert task_properties["ed_accessed"]["const"] is False
    properties = aggregate_schema["properties"]
    assert properties["tasks"]["minItems"] == 24
    assert properties["tasks"]["maxItems"] == 24
    assert (
        properties["protocol"]["properties"]["chains_per_sector"]["const"]
        == 4
    )
    assert (
        properties["gates"]["properties"]["gap_precision"]["const"]
        is True
    )
    assert properties["ed_accessed"]["const"] is False
    assert attempt_schema["properties"]["passed"]["type"] == "boolean"


def test_measurement_extension_keeps_checkpoints_immutable() -> None:
    source = (
        ROUTE_D_PLUS_ROOT / "extend_phase6_measurement.py"
    ).read_text(encoding="utf-8")
    assert 'failed != ["gap_precision"]' in source
    assert "sha256_file(checkpoint_path)" in source
    assert "checkpoint_coefficients_unchanged" in source
    assert (
        "extend-sole-gap-precision-failure-without-ed-or-retraining"
        in source
    )
    assert "ProcessPoolExecutor" in source
    assert 'multiprocessing.get_context("spawn")' in source
    assert "SAMPLES_PER_CHAIN = 2048" in source
    assert "MEASUREMENT_CHUNK = 128" in source
    assert "blind_measurement_audit" in source
    assert 'devices[0].platform != "gpu"' in source
    assert "phase6-measurement-attempt.json" in source


def test_measurement_batch_uses_one_gpu_allocation_for_all_tasks() -> None:
    batch = (
        ROUTE_D_PLUS_ROOT / "phase6_measurement.sbatch"
    ).read_text(encoding="utf-8")
    assert "#SBATCH --cpus-per-task=24" in batch
    assert "#SBATCH --gres=gpu:1" in batch
    assert "ROUTE_D_PLUS_PHASE6_ATTEMPT:?" in batch
    assert "ROUTE_D_PLUS_MEASUREMENT_RUN_ID:?" in batch
    assert "-m route_d_plus.extend_phase6_measurement" in batch
    assert '--workers "${SLURM_CPUS_PER_TASK}"' in batch
