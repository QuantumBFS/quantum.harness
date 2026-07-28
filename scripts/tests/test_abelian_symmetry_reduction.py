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
