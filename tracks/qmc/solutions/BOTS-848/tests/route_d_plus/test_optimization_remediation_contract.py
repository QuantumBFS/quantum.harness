from __future__ import annotations

import json
from pathlib import Path

import jsonschema

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_remediation_protocol_is_frozen_and_schema_valid() -> None:
    schema = json.loads(
        (
            ROUTE_ROOT
            / "optimization-remediation-protocol.schema.json"
        ).read_text(encoding="utf-8")
    )
    protocol = json.loads(
        (
            ROUTE_ROOT / "optimization-remediation-protocol.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(protocol)
    assert protocol["capacity"] == "D+0"
    assert protocol["architecture_modified"] is False
    assert protocol["ed_used_for_gradient"] is False
    assert protocol["ed_used_for_checkpoint_selection"] is False
    assert protocol["run_seeds_concurrently"] is True


def test_remediation_certificate_schemas_are_strict() -> None:
    for name in (
        "remediated-checkpoint.schema.json",
        "optimization-remediation-seed.schema.json",
        "optimization-remediation.schema.json",
    ):
        schema = json.loads(
            (ROUTE_ROOT / name).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False


def test_remediation_does_not_import_ed_and_uses_fixed_final_update() -> None:
    source = (ROUTE_ROOT / "remediate_dplus0.py").read_text(
        encoding="utf-8"
    )
    batch = (ROUTE_ROOT / "optimization_remediation.sbatch").read_text(
        encoding="utf-8"
    )
    assert "from benchmark_v0" not in source
    assert "import benchmark_v0" not in source
    assert "ProcessPoolExecutor" in source
    assert "max_workers=3" in source
    assert "initial_checkpoint=request" in source
    assert "nvidia-smi" in batch


def test_original_training_defaults_remain_unchanged() -> None:
    source = (ROUTE_ROOT / "train_dplus0.py").read_text(
        encoding="utf-8"
    )
    assert "learning_rate: float = 0.1" in source
    assert "diagonal_shift: float = 1.0e-2" in source
    assert "trust_radius: float = 0.05" in source
    assert 'checkpoint_selection: str = "final_update"' in source
