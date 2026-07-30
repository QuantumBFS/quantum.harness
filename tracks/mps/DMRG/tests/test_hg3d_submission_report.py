from __future__ import annotations

import json
from pathlib import Path
import zipfile

from scripts.hard_goal_submission_report import build_report
from vmcrg_ref.artifacts import sha256_file


def test_builds_self_contained_resource_no_go_submission(tmp_path: Path) -> None:
    output = tmp_path / "submission"
    archive = tmp_path / "submission.zip"

    result = build_report(output, archive)

    assert result["classification"] == "RESOURCE_NO_GO"
    manifest = json.loads((output / "manifest.json").read_text(encoding="ascii"))
    assert manifest["stage"] == "stage9"
    assert manifest["stage4_classification"] == "PASS"
    assert manifest["stage5_classification"] == "PASS"
    assert manifest["stage6_decision"] == "RECALIBRATE"
    assert manifest["stage7_executed"] is False
    assert manifest["stage8_executed"] is False
    assert len(manifest["cancelled_jobs"]) == 4
    for relative, digest in manifest["artifacts"].items():
        assert sha256_file(output / relative) == digest

    html = (output / "report.html").read_text(encoding="utf-8")
    assert "RESOURCE_NO_GO" in html
    assert "data:image/png;base64," in html
    assert "No numerical Tc estimate" in html
    assert archive.is_file()
    assert archive.with_suffix(".zip.sha256").is_file()
    with zipfile.ZipFile(archive) as handle:
        names = set(handle.namelist())
    assert f"{output.name}/report.html" in names
    assert f"{output.name}/manifest.json" in names
