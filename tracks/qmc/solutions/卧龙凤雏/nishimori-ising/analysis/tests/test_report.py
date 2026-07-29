import json
import re
import subprocess
import sys

from analysis.data_io import write_json_atomic
from analysis.report_builder import build_report_document
from analysis.run_analysis import analyze_run
from analysis.tests.helpers import create_synthetic_run


def test_offline_report_contains_all_sections_and_embeds_six_figures(tmp_path):
    run_dir = create_synthetic_run(tmp_path / "run")
    summary = analyze_run(run_dir, bootstrap_samples=64, bootstrap_seed=17)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    document = build_report_document(summary, manifest)
    assert [section["title"] for section in document["sections"]] == [
        "Setup",
        "Quenched transfer product",
        "Central charge",
        "Scientific diagnostics",
        "Verification",
        "Reproduction",
    ]
    write_json_atomic(run_dir / "report.json", document)
    repository_root = __import__("pathlib").Path(__file__).resolve().parents[7]
    renderer = repository_root / "skills" / "report" / "render_report.py"
    subprocess.run(
        [sys.executable, str(renderer), str(run_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    html = (run_dir / "report.html").read_text()
    assert html.count("data:image/png;base64,") == 6
    assert not re.search(r'<(?:script|img)\b[^>]+\bsrc=["\']https?://', html)
    assert not re.search(r'<link\b[^>]+\bhref=["\']https?://', html)
