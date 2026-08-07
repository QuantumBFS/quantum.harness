from __future__ import annotations

from pathlib import Path
import sys

import pytest

TRIQS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRIQS_DIR))

from artifacts import canonical_json, sha256_bytes
from compare_mps import compare, validate_comparison


def test_comparison_keeps_all_error_axes_separate():
    model = {"beta": 16.0, "U": 0.8}
    mps = {
        "model": model,
        "reported_tau": [0.0, 4.0],
        "values": {"n_d": 1.001, "G_up": [-0.1, -0.2], "G_down": [-0.1, -0.2]},
        "common_real_frequency_sha256": "1" * 64,
    }
    budget = {
        "bath": 1e-4,
        "chain": 2e-4,
        "bond": 3e-4,
        "time_residual": 4e-4,
    }
    cthyb = {
        "model": model,
        "reported_tau": [0.0, 4.0],
        "values": {"n_d": 1.0, "G_up": [-0.1, -0.2], "G_down": [-0.1, -0.2]},
        "standard_errors": {"n_d": 1e-5, "G_up": [1e-5, 1e-5], "G_down": [1e-5, 1e-5]},
        "common_real_frequency_sha256": "1" * 64,
    }
    acceptance = {"passed": True, "global_max_error": 1e-7, "effective_threshold": 1e-6}
    artifact = compare(mps, budget, cthyb, acceptance)
    validate_comparison(artifact)
    gate = artifact["payload"]["comparisons"]["n_d"]
    assert gate["mps_error_components"] == budget
    assert gate["cthyb_student_component"] == pytest.approx(3.182446305284263e-5)
    assert gate["envelope"] == pytest.approx(0.0010318244630528427)
    assert gate["passed"] is True
    for key in tuple(budget):
        changed = dict(budget)
        del changed[key]
        with pytest.raises(ValueError, match=key):
            compare(mps, changed, cthyb, acceptance)


def test_comparison_hash_and_identity_fail_closed():
    payload = {
        "artifact_type": "mps_cthyb_comparison",
        "schema_version": 2,
        "status": "blocked",
        "comparisons": {},
    }
    artifact = {"payload": payload, "sha256": sha256_bytes(canonical_json(payload))}
    validate_comparison(artifact)
    artifact["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        validate_comparison(artifact)
