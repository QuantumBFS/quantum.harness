import importlib.util
import json
import pathlib
import subprocess
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-002"
VALIDATE = ROOT / "tracks/qcs/solutions/YueYuan/research/validator/validate.py"


def load_module(name):
    sys.path.insert(0, str(ATTEMPT))
    spec = importlib.util.spec_from_file_location(name, ATTEMPT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_attempt_002_gate_infidelity_ignores_global_phase():
    quantum_device = load_module("quantum_device")

    cz = quantum_device.target_gate("CZ")

    assert quantum_device.gate_infidelity(np.exp(0.41j) * cz, cz) < 1e-12


def test_attempt_002_propagation_is_unitary():
    quantum_device = load_module("quantum_device")
    cz = quantum_device.target_gate("CZ")
    basis = quantum_device.su4_basis()
    mixing = np.zeros((12, 4, len(basis)))
    mixing[0, 0, 0] = 0.02

    unitary = quantum_device.propagate_error_pulse(
        np.ones(48) * 0.1, mixing, np.zeros(len(basis)), cz
    )

    ident = unitary.conj().T @ unitary
    assert np.max(np.abs(ident - np.eye(4))) < 1e-10


def test_attempt_002_model_has_rank_15_curvature():
    hessian_subspace = load_module("hessian_subspace")

    model = hessian_subspace.build_model(seed=2113)
    spectrum = np.linalg.eigvalsh(model.model_hessian)

    assert model.raw_dim == 48
    assert model.visible_rank == 15
    assert int(np.sum(spectrum > 1e-8)) == 15


def test_attempt_002_top_subspace_is_orthonormal():
    hessian_subspace = load_module("hessian_subspace")

    model = hessian_subspace.build_model(seed=2113)
    subspace = hessian_subspace.top_subspace(model.model_hessian, 15)

    assert subspace.shape == (48, 15)
    assert np.max(np.abs(subspace.T @ subspace - np.eye(15))) < 1e-10


def test_attempt_002_submission_has_required_methods_and_small_k_failure():
    closed_loop = load_module("closed_loop")

    payload = closed_loop.build_submission()
    summary = closed_loop.summarize_submission(payload)

    assert summary["minimum_hessian_speedup"] >= 2.0
    assert summary["has_small_k_failure"] is True
    assert summary["nonzero_gaps"] == [0.03, 0.08]
    assert summary["methods"] == [
        "full_raw_nelder_mead",
        "hessian_subspace_nelder_mead",
        "random_subspace_nelder_mead",
    ]


def test_attempt_002_submission_passes_validator(tmp_path):
    closed_loop = load_module("closed_loop")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "submission.json").write_text(
        json.dumps(closed_loop.build_submission(), indent=2, sort_keys=True) + "\n"
    )
    report_path = candidate / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATE),
            str(candidate),
            "--instances",
            "dev",
            "--out",
            str(report_path),
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(report_path.read_text())
    assert report["status"] == "accepted"
    assert report["score"] >= 2.0
