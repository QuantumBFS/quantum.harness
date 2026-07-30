import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def _run_audit(output: Path) -> dict:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "."
    subprocess.run(
        [
            sys.executable,
            "scripts/on_theorem_audit.py",
            "--output",
            str(output),
        ],
        check=True,
        env=environment,
    )
    return json.loads(output.read_text())


def test_on_theorem_audit_closes_scope_and_algebra(tmp_path):
    output = tmp_path / "audit.json"
    payload = _run_audit(output)
    assert payload["schema"] == "issue158.on_theorem_audit.v1"
    assert payload["theorem_scope"]["spin_space"] == "unit sphere S^(n-1)"
    assert payload["theorem_scope"]["component_count"] == (
        "finite integer n>=2"
    )
    assert "arbitrary continuous field theories" in payload["excluded_scope"]
    assert payload["numerical_certificates_are_proof_premises"] is False
    assert all(
        item["status"] == "verified"
        for item in payload["obligations"]
    )
    rows = payload["algebra_certificates"]
    assert [row["n"] for row in rows] == [2, 3, 4, 8]
    assert rows[0]["xy_reduction"] == (
        "one transverse channel and factor n-1=1"
    )
    assert all(
        row["transverse_channels"] == row["n"] - 1 for row in rows
    )
    assert all(
        row["maximum_second_variation_residual"] <= 5e-14
        and row["maximum_sampled_plane_projection"] <= 1.0 + 1e-14
        and row["budget_bound_satisfied"]
        for row in rows
    )


def test_on_theorem_audit_is_byte_reproducible(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _run_audit(first)
    _run_audit(second)
    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text())
    digest = hashlib.sha256(Path("ON_PROOF_AUDIT.md").read_bytes()).hexdigest()
    assert payload["proof_document"]["sha256"] == digest


def test_on_proof_document_states_subtleties_without_overclaim():
    text = Path("ON_PROOF_AUDIT.md").read_text()
    required = [
        "hard-spin \\(O(n)\\) finite-volume infrared criterion",
        "divergence-free Killing field",
        "selected two-dimensional internal plane",
        "The factor \\(n-1\\)",
        "There is no odd--even obstruction in this proof",
        "not a theorem for all long-range models",
        "not a statement about every continuous field theory",
    ]
    for phrase in required:
        assert phrase in text
    assert "every two-dimensional continuous field theory has no order" not in text
