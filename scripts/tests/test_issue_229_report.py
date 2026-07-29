import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "research" / "issue_229_report.py"
ARTIFACT = ROOT / "research" / "benchmark" / "issue-229-evidence.json"
REPORT = ROOT / "docs" / "discussion" / "issue-229-final.html"


def load_report_module():
    spec = importlib.util.spec_from_file_location("issue_229_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = load_report_module()


def test_su2_spectrum_multiplicities_and_residuals():
    expected_multiplicities = {
        4: [2, 3, 1],
        6: [5, 9, 5, 1],
        8: [14, 28, 20, 7, 1],
    }
    for length in (4, 6, 8):
        case = report.compute_su2_case(length)
        multiplicities = [sector["multiplicity"] for sector in case["sectors"]]
        assert multiplicities == expected_multiplicities[length]
        assert sum(
            (2 * sector["spin"] + 1) * sector["multiplicity"]
            for sector in case["sectors"]
        ) == 2**length
        assert case["multiplicity_completeness"] == case["dense_dimension"] == 2**length
        assert case["spectrum_max_error"] < 1e-12
        assert case["commutator_residual"] < 1e-12
        assert case["block_leakage_residual"] < 1e-12
        assert case["orthogonality_residual"] < 1e-12
        assert case["s2_projection_residual"] < 1e-12


def test_heisenberg_operator_is_open_antiferromagnetic_chain():
    hamiltonian, spin_squared = report.heisenberg_operators(4)
    assert hamiltonian.shape == spin_squared.shape == (16, 16)
    assert np.allclose(hamiltonian, hamiltonian.T)
    assert np.isclose(np.linalg.eigvalsh(hamiltonian)[0], -1.616025403784438)


def test_committed_artifact_and_report_have_all_cases():
    evidence = json.loads(ARTIFACT.read_text())
    baseline = evidence["finite_abelian_baseline"]["instances"]
    su2_cases = evidence["su2_evidence"]["cases"]
    document = REPORT.read_text()
    assert len(baseline) == 50
    assert sum(item["corpus"] == "development" for item in baseline) == 30
    assert sum(item["corpus"] == "private" for item in baseline) == 20
    assert len(su2_cases) == 3
    assert [case["length"] for case in su2_cases] == [4, 6, 8]
    assert document.count("data-baseline-instance") == 50
    assert document.count("data-su2-case") == 3
    assert document.count("<svg") == 1
    assert "SU(2) cubic work proxy and spectrum reconstruction error" in document
    assert "An NC moment SDP is not identified with non-Abelian symmetry" in document
