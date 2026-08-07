from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.plot_stage6_ladder_calibration import build_ladder_diagnostic


def _write_manifest(path: Path) -> Path:
    payload = {
        "schema_version": 1,
        "classification": "CALIBRATION_COMPLETE",
        "scope": "stage6-ladder-calibration-only",
        "tc_evidence": False,
        "cell_id": "L03-J0000",
        "spec": {
            "temperatures": [2.0, 1.2, 0.8],
            "swap_target_minimum": 0.2,
            "swap_target_maximum": 0.5,
        },
        "parallel_tempering": {
            "edge_attempts": [100, 100],
            "edge_accepts": [35, 70],
            "edge_acceptance": [0.35, 0.70],
            "ladder_decision": "RECALIBRATE",
        },
    }
    path.write_text(json.dumps(payload) + "\n", encoding="ascii")
    return path


def test_ladder_diagnostic_writes_source_data_figures_and_hashes(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(tmp_path / "manifest.json")
    output = tmp_path / "diagnostic"
    record = build_ladder_diagnostic(manifest, output)
    assert record["classification"] == "DIAGNOSTIC_ONLY"
    assert record["tc_evidence"] is False
    assert record["ladder_decision"] == "RECALIBRATE"
    assert set(record["artifacts"]) == {
        "ladder_acceptance.csv",
        "ladder_acceptance.pdf",
        "ladder_acceptance.png",
    }
    assert (output / "ladder_acceptance.png").stat().st_size > 0
    assert (output / "ladder_acceptance.pdf").stat().st_size > 0
    with (output / "ladder_acceptance.csv").open(
        newline="", encoding="ascii"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert set(rows[0]) == {
        "edge",
        "temperature_upper",
        "temperature_lower",
        "beta_upper",
        "beta_lower",
        "attempts",
        "accepts",
        "acceptance",
        "ci95_low",
        "ci95_high",
        "inside_target_band",
    }
    assert rows[0]["inside_target_band"] == "true"
    assert rows[1]["inside_target_band"] == "false"
    with pytest.raises(FileExistsError, match="overwrite"):
        build_ladder_diagnostic(manifest, output)


def test_ladder_diagnostic_rejects_tc_or_noncalibration_inputs(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(tmp_path / "manifest.json")
    payload = json.loads(manifest.read_text(encoding="ascii"))
    payload["tc_evidence"] = True
    manifest.write_text(json.dumps(payload) + "\n", encoding="ascii")
    with pytest.raises(ValueError, match="calibration-only"):
        build_ladder_diagnostic(manifest, tmp_path / "diagnostic")


def test_ladder_diagnostic_cli_bootstraps_the_track_source_path(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(tmp_path / "manifest.json")
    output = tmp_path / "diagnostic"
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("MPLCONFIGDIR", None)
    environment["HOME"] = "/proc/hg3d-no-home"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/plot_stage6_ladder_calibration.py",
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert (output / "diagnostic_manifest.json").is_file()
