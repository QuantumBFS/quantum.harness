import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def test_tiny_run_generates_one_hashed_bilingual_result(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    run_dir = tmp_path / "tiny-run"
    environment = {
        **os.environ,
        "LEARNING_MIT_PYTHON": sys.executable,
        "LEARNING_MIT_CARGO_PROFILE": "",
        "MPLCONFIGDIR": str(tmp_path / "matplotlib"),
    }
    subprocess.run(
        [str(root / "run.sh"), "test", str(run_dir)],
        cwd=root,
        env=environment,
        check=True,
        timeout=120,
    )

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] != "validation_failed"
    for relative in (
        "summary.json",
        "report.html",
        "report-zh.html",
        "report.pdf",
        "report-zh.pdf",
        "raw/oracles.json",
        "raw/benchmark.json",
        "raw/negative-control.json",
    ):
        path = run_dir / relative
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        assert manifest["artifact_sha256"][relative] == expected

    english = (run_dir / "report.html").read_text(encoding="utf-8")
    chinese = (run_dir / "report-zh.html").read_text(encoding="utf-8")
    summary_hash = hashlib.sha256((run_dir / "summary.json").read_bytes()).hexdigest()
    assert f'name="summary-sha256" content="{summary_hash}"' in english
    assert f'name="summary-sha256" content="{summary_hash}"' in chinese

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert set(
        (
            "candidate_selection",
            "entanglement_c_eff",
            "casimir_c_eff",
            "estimator_comparison",
            "claim",
        )
    ).issubset(summary)
    assert summary["claim"]["status"] == "unavailable"
    assert summary["claim"]["reasons"]
    assert summary["entanglement"]["coefficients"] == []
    assert "None" not in json.dumps(summary)
