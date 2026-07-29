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
