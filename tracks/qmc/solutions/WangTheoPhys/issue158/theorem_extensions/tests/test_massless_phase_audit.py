import json
import os
import subprocess
import sys
from pathlib import Path

from issue158.kernel import C_INFINITY_SIGMA2


ROOT = Path(__file__).resolve().parents[1]


def test_committed_massless_artifact_has_closed_quantifiers():
    payload = json.loads(
        (ROOT / "artifacts/massless_phase_audit.json").read_text()
    )
    assert payload["schema"] == "issue158-massless-phase-audit-v1"
    assert all(
        row["status"] == "verified" for row in payload["obligations"]
    )
    theorem = payload["theorem"]
    assert theorem["quantifier_order"] == [
        "fix nonzero lattice displacement x",
        "embed a fixed free box Lambda_n containing 0 and x",
        "take torus L to infinity at fixed n",
        "take n to infinity",
    ]
    assert theorem["effective_inverse_temperature"] == "beta*c_infinity"
    assert theorem["threshold"] == "beta >= beta_c_NN/c_infinity"
    assert theorem["lower_bound"] == "1/(8*|x|)"
    assert theorem["c_infinity"] == C_INFINITY_SIGMA2
    assert payload["decision_record"]["updates"][
        "ordinary_gapped_phase"
    ] == "excluded"
    assert payload["decision_record"]["updates"][
        "eventual_bkt"
    ] == "unresolved"
    assert "uniform finite-L correlation bound" in payload[
        "decision_record"
    ]["does_not_imply"]


def test_massless_artifact_is_reproducible(tmp_path):
    output = tmp_path / "massless.json"
    command = [
        sys.executable,
        "scripts/massless_phase_audit.py",
        "--output",
        str(output),
    ]
    subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        env={**os.environ, "PYTHONPATH": "."},
    )
    expected = (
        ROOT / "artifacts/massless_phase_audit.json"
    ).read_bytes()
    assert output.read_bytes() == expected
