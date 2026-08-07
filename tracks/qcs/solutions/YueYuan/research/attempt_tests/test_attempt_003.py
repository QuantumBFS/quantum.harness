import importlib.util
import json
import pathlib
import subprocess
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-003"
VALIDATE = ROOT / "tracks/qcs/solutions/YueYuan/research/validator/validate.py"


def load_module(name):
    for module_name in ["quantum_device", "hessian_subspace", "optimizer", "closed_loop"]:
        sys.modules.pop(module_name, None)
    sys.path.insert(0, str(ATTEMPT))
    spec = importlib.util.spec_from_file_location(name, ATTEMPT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_attempt_003_optimizer_reduces_quadratic():
    optimizer = load_module("optimizer")
    target = np.array([0.12, -0.08])

    def objective(x):
        exact = float(np.sum((x - target) ** 2))
        return exact, exact

    result = optimizer.nelder_mead(
        objective, np.zeros(2), step=0.15, max_queries=80, target_exact=1e-5
    )

    assert result.queries < 80
    assert result.best_exact <= 1e-5
    assert result.queries_to_target is not None


def test_attempt_003_gate_infidelity_and_propagation_are_physical():
    quantum_device = load_module("quantum_device")

    cz = quantum_device.target_gate("CZ")
    basis = quantum_device.su4_basis()
    mixing = np.zeros((12, 4, len(basis)))
    mixing[0, 0, 0] = 0.02
    unitary = quantum_device.propagate_error_pulse(
        np.ones(48) * 0.1, mixing, np.zeros(len(basis)), cz
    )

    assert quantum_device.gate_infidelity(np.exp(0.23j) * cz, cz) < 1e-12
    assert np.max(np.abs(unitary.conj().T @ unitary - np.eye(4))) < 1e-10


def test_attempt_003_model_has_rank_15_curvature():
    hessian_subspace = load_module("hessian_subspace")

    model = hessian_subspace.build_model(seed=3113)
    spectrum = np.linalg.eigvalsh(model.model_hessian)
    subspace = hessian_subspace.top_subspace(model.model_hessian, 15)

    assert model.raw_dim == 48
    assert model.visible_rank == 15
    assert int(np.sum(spectrum > 1e-8)) == 15
    assert np.max(np.abs(subspace.T @ subspace - np.eye(15))) < 1e-10


def test_attempt_003_oracle_counts_queries():
    closed_loop = load_module("closed_loop")
    model = closed_loop.build_model()
    oracle = closed_loop.NoisyOracle(
        model,
        closed_loop.device_mixing(model.model_mixing, 0.03),
        closed_loop.device_bias(0.03),
        shots=1024,
        seed=0,
    )

    noisy, exact = oracle(np.zeros(48))

    assert oracle.queries == 1
    assert isinstance(noisy, float)
    assert isinstance(exact, float)
    assert noisy >= 0.0
    assert exact >= 0.0


def test_attempt_003_submission_passes_validator(tmp_path):
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
