from __future__ import annotations

import json
from pathlib import Path

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase6_schema_enforces_blind_three_seed_dplus0_gate() -> None:
    schema = json.loads(
        (ROUTE_D_PLUS_ROOT / "phase6.schema.json").read_text(encoding="utf-8")
    )
    properties = schema["properties"]
    assert properties["n_electrons"]["const"] == 6
    assert properties["two_q"]["const"] == 15
    assert properties["ansatz"]["const"] == "D+0-linear-scalar"
    assert properties["seed_results"]["minItems"] == 3
    assert properties["seed_results"]["maxItems"] == 3
    assert properties["ed_accessed"]["const"] is False
    assert properties["forbidden_modules_loaded"]["maxItems"] == 0
    assert properties["forbidden_source_references"]["maxItems"] == 0
    assert properties["gates"]["properties"]["blind_training"]["const"] is True
    assert properties["passed"]["const"] is True


def test_phase6_batch_requires_phase5_and_gpu_certificate() -> None:
    batch = (ROUTE_D_PLUS_ROOT / "phase6.sbatch").read_text(encoding="utf-8")
    certificate = (ROUTE_D_PLUS_ROOT / "certify_phase6.py").read_text(
        encoding="utf-8"
    )
    assert "ROUTE_D_PLUS_PHASE5_CERTIFICATE:?" in batch
    assert "ROUTE_D_PLUS_PHASE6A_CERTIFICATE:?" in batch
    assert "tests/route_d_plus/test_train_dplus0.py" in batch
    assert "tests/route_d_plus/test_future_contracts.py" not in batch
    assert "-m route_d_plus.certify_phase6" in batch
    assert "require_phase5_certificate" in certificate
    assert "require_phase6a_certificate" in certificate
    assert 'devices[0].platform != "gpu"' in certificate
    assert 'jax.config.update("jax_enable_x64", True)' in certificate
    assert "FORBIDDEN_MODULE_PREFIXES" in certificate
    assert "blind_training_audit" in certificate
    assert "calibrate_architecture" in certificate
    assert "combined_state_averaged_sr" in certificate
    assert "ProcessPoolExecutor" in certificate
    assert 'multiprocessing.get_context("spawn")' in certificate
    training = (ROUTE_D_PLUS_ROOT / "train_dplus0.py").read_text(
        encoding="utf-8"
    )
    assert "mother_evaluator=ground_mother_channels" in training
    assert "ground_mother_channels,\n            tower_mother_channels" in training
    assert "executor.map(tower_raw_channels, tower_samples)" in training
    assert "executor.map(" in training
    assert "_pilot_tower_chain" in training
    assert 'multiprocessing.get_context("spawn")' in training
    assert "burn-in-only-target-0.35-0.60-frozen-before-training" in training
    assert "delta_max=ground_delta_maxima[chain]" in training
    assert "delta_max=tower_delta_maxima[chain]" in training
    assert "0.25 <= acceptance <= 0.70" in certificate
    assert "validate_certificate(collected)" in certificate
    assert "phase6-attempt.json" in certificate
    assert "validate_attempt(attempt)" in certificate
    assert "runtime_library_sha256=" in batch
    assert "LD_LIBRARY_PATH=" in batch


def test_phase6_smoke_uses_an_importable_spawn_entrypoint() -> None:
    smoke = (ROUTE_D_PLUS_ROOT / "smoke_phase6.py").read_text(
        encoding="utf-8"
    )
    assert 'if __name__ == "__main__"' in smoke
    assert "calibrate_architecture(" in smoke
    assert "source_revision=args.source_revision" in smoke
    assert "blind_training_audit" in smoke
    assert 'devices[0].platform != "gpu"' in smoke
