import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "research"
VALIDATOR = RESEARCH / "validator" / "validate.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load_module("issue229_generator", RESEARCH / "database" / "generate_corpus.py")
reducer = load_module("issue229_reducer", RESEARCH / "candidate" / "reducer.py")


def run_validator(tmp_path, candidate, *extra):
    report = tmp_path / f"{candidate.name}.json"
    process = subprocess.run(
        [sys.executable, str(VALIDATOR), str(candidate), *extra, "--out", str(report)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return process, json.loads(report.read_text())


def test_projectors_reduce_and_reconstruct_representative_families():
    for spec in (generator.build_specs(0, 1)[0], generator.build_specs(1, 1)[0]):
        data = generator.generate_instance(spec)
        result = reducer.reduce_invariant_hermitian(**data)
        bases = [sector["basis"] for sector in result["sectors"]]
        blocks = [sector["block"] for sector in result["sectors"]]
        joined = np.concatenate(bases, axis=1)
        reconstructed = sum((basis @ block @ basis.conj().T for basis, block in zip(bases, blocks)), np.zeros_like(data["matrix"]))
        dense = np.linalg.eigvalsh(data["matrix"])
        reduced = np.sort(np.concatenate([np.linalg.eigvalsh(block) for block in blocks]))
        ratio = data["matrix"].shape[0] ** 3 / sum(block.shape[0] ** 3 for block in blocks)
        assert np.linalg.norm(joined.conj().T @ joined - np.eye(len(joined))) <= 1e-10
        assert np.linalg.norm(data["matrix"] - reconstructed) <= 1e-10
        assert np.allclose(dense, reduced, rtol=1e-7, atol=1e-7)
        assert ratio >= (3 if spec["family"] == "z2" else 10)


def spin_half_heisenberg(sites):
    sx = np.array([[0, 1], [1, 0]], dtype=complex) / 2
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex) / 2
    sz = np.diag([1, -1]) / 2
    identity = np.eye(2)

    def embedded(operator, site):
        result = np.ones((1, 1), dtype=complex)
        for index in range(sites):
            result = np.kron(result, operator if index == site else identity)
        return result

    total = np.zeros((2**sites, 2**sites), dtype=complex)
    for site in range(sites - 1):
        for operator in (sx, sy, sz):
            total += embedded(operator, site) @ embedded(operator, site + 1)
    return total


def test_su2_template_is_inferred_and_reconstructs_multiplets():
    result = reducer.decompose_by_template(spin_half_heisenberg(4), "su2")
    assert result["local_dim"] == 2
    assert result["sites"] == 4
    assert [sector["label"]["spin"] for sector in result["sectors"]] == [0, 1, 2]
    assert [sector["multiplicity"] for sector in result["sectors"]] == [2, 3, 1]
    assert result["commutator_residual"] < 1e-12
    assert result["spectrum_reconstruction_error"] < 1e-12


def test_u1_z2_and_translation_templates_match_common_spin_half_patterns():
    _, _, total_z = reducer.spin_generators(2, 3)
    u1 = reducer.decompose_by_template(total_z @ total_z + 0.3 * total_z, "u1")
    assert [sector["multiplicity"] for sector in u1["sectors"]] == [1, 3, 3, 1]

    sz = np.diag([1, -1])
    z2_hamiltonian = np.kron(sz, sz) + np.kron(np.eye(2), np.eye(2))
    z2 = reducer.decompose_by_template(z2_hamiltonian, "z2", local_dim=2, sites=2)
    assert len(z2["sectors"]) == 2

    translation = reducer._translation_operator(2, 3)
    periodic = translation + translation.conj().T
    translated = reducer.decompose_by_template(periodic, "translation", local_dim=2, sites=3)
    assert len(translated["sectors"]) == 3
    assert translated["spectrum_reconstruction_error"] < 1e-12


def test_template_matcher_rejects_noninvariant_and_reports_ambiguity():
    noninvariant = np.diag(np.arange(16, dtype=float))
    with np.testing.assert_raises_regex(ValueError, "no symmetry template matched"):
        reducer.decompose_by_template(noninvariant, "su2", local_dim=2, sites=4)
    with np.testing.assert_raises_regex(ValueError, "ambiguous symmetry representation"):
        reducer.match_symmetry_template(np.eye(16), "su2")


def test_hamiltonian_cli_writes_machine_readable_su2_decomposition(tmp_path):
    hamiltonian = tmp_path / "H.npy"
    output = tmp_path / "result.json"
    np.save(hamiltonian, spin_half_heisenberg(4))
    process = subprocess.run(
        [sys.executable, str(RESEARCH / "candidate" / "run.py"), str(hamiltonian),
         "--symmetry", "su2", "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    result = json.loads(output.read_text())
    assert result["symmetry"] == "su2"
    assert result["sites"] == 4
    assert [sector["multiplicity"] for sector in result["sectors"]] == [2, 3, 1]
    assert "matched su2" in process.stdout


def test_hamiltonian_cli_writes_machine_readable_npz_decomposition(tmp_path):
    hamiltonian = tmp_path / "H.npy"
    output = tmp_path / "result.npz"
    np.save(hamiltonian, spin_half_heisenberg(4))
    process = subprocess.run(
        [sys.executable, str(RESEARCH / "candidate" / "run.py"), str(hamiltonian),
         "--symmetry", "su2", "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    with np.load(output) as result:
        metadata = json.loads(result["metadata"].item())
        assert metadata["symmetry"] == "su2"
        assert metadata["sites"] == 4
        assert result["sector_0_basis"].shape == (16, 2)
        assert result["sector_1_block"].shape == (3, 3)


def test_automatic_decomposition_readme_documents_cli_contract():
    document = (RESEARCH / "candidate" / "README.md").read_text()
    assert "--symmetry su2" in document
    assert "--local-dim 2" in document
    assert "--sites 8" in document
    assert "sector_N_basis" in document
    assert "template matching, not unrestricted symmetry discovery" in document


def test_corpus_declares_30_dev_and_20_sealed_private_instances():
    dev = json.loads((RESEARCH / "benchmark" / "dev" / "specs.json").read_text())["instances"]
    manifest = json.loads((RESEARCH / "validator" / "manifest.json").read_text())
    ignore = (ROOT / ".gitignore").read_text()
    assert len(dev) == 30
    assert manifest["corpus"]["private_instances"] == 20
    assert "research/benchmark/private/" in ignore


def test_candidate_passes_development_validator(tmp_path):
    process, report = run_validator(tmp_path, RESEARCH / "candidate", "--instances", "dev")
    assert process.returncode == 0, process.stdout + process.stderr
    assert report["status"] == "scored"
    assert report["score"] >= 3
    assert len(report["per_instance"]) == 31
    assert not report["errors"]


def test_precheck_is_free_and_structural(tmp_path):
    process, report = run_validator(tmp_path, RESEARCH / "candidate", "--precheck")
    assert process.returncode == 0
    assert report["status"] == "scored"
    assert report["score"] is None


def test_negative_controls_are_rejected(tmp_path):
    controls = {
        "cheater": "instance ids differ",
        "wrong-answer": "populated characters differ",
        "env-escape": "sandbox blocks out-of-scope read",
        "dense-passthrough": "dense passthrough is rejected",
    }
    for name, diagnostic in controls.items():
        process, report = run_validator(tmp_path, RESEARCH / "validator" / "controls" / name)
        assert process.returncode == 1
        assert report["status"] == "rejected"
        assert report["errors"]
        assert diagnostic in json.dumps(report)


def test_timeout_control_is_rejected_with_small_overshoot(tmp_path):
    process, report = run_validator(tmp_path, RESEARCH / "validator" / "controls" / "timeout")
    assert process.returncode == 1
    assert report["status"] == "rejected"
    assert "timeout" in json.dumps(report).lower()
