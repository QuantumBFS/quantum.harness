from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def _runner():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_autocorrelation_mitigation.py"
    )
    spec = importlib.util.spec_from_file_location(
        "run_autocorrelation_mitigation", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage4_ab_release_requires_passing_same_revision_m3_result(
    tmp_path: Path,
) -> None:
    runner = _runner()
    path = tmp_path / "m3.json"
    payload = {
        "experiment_id": runner.EXPERIMENT_ID,
        "phase": "m3_ed",
        "source_revision": "abc123",
        "decision": {"status": "PASS"},
    }
    encoded = (json.dumps(payload) + "\n").encode()
    path.write_bytes(encoded)

    assert runner._validate_m3_release(path, "abc123") == hashlib.sha256(
        encoded
    ).hexdigest()

    payload["decision"] = {"status": "STOP"}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="passing same-revision"):
        runner._validate_m3_release(path, "abc123")

    payload["decision"] = {"status": "PASS"}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="passing same-revision"):
        runner._validate_m3_release(path, "different")


def test_stability_gate_rejects_density_and_tau_audit_failures() -> None:
    runner = _runner()
    arm = {
        "acceptance_min": 0.5,
        "acceptance_max": 0.6,
        "temporal_block_acceptance_min": 0.4,
        "temporal_block_acceptance_max": 0.7,
        "tau_audit_pass": True,
        "direct_sign_min": 1.0,
        "weight_log_error_max": 1.0e-12,
        "density_min": 0.4,
        "density_max": 0.6,
    }
    assert runner._stability_pass(arm, block=True)

    arm["density_max"] = 1.0 + 2.0e-7
    assert not runner._stability_pass(arm, block=True)

    arm["density_max"] = 0.6
    arm["tau_audit_pass"] = False
    assert not runner._stability_pass(arm, block=True)


def test_shared_worker_preserves_candidate_experiment_id(
    tmp_path: Path,
) -> None:
    runner = _runner()
    payload = runner._run_task(
        {
            "output_dir": str(tmp_path),
            "experiment_id": "candidate-reflection-test",
            "phase": "m3_ed",
            "arm": "control",
            "replica": 0,
            "seed": 8123,
            "config": {
                "m": 3,
                "beta": 0.2,
                "dt": 0.1,
                "t": 0.2,
                "g_b_over_g_a": 0.5,
            },
            "warmup_sweeps": 1,
            "measurement_sweeps": 2,
            "measure_every": 1,
            "source_revision": "test",
            "m3_release_digest": None,
        }
    )

    assert payload["experiment_id"] == "candidate-reflection-test"
