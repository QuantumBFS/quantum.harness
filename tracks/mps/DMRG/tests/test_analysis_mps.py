from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def evaluation_payload() -> dict:
    metric = {
        "acceptance_rate": 0.3,
        "autocorrelation": {"tau_int": 2.0, "ess_per_second": 4.0},
        "patch_distances": {"total_variation": 0.1, "jensen_shannon": 0.02},
        "two_point_correlations": {"10": {"mean": 0.03}},
        "held_out_multispin": {"four": {"mean": 0.04}, "six": {"mean": 0.05}},
        "sweep_seconds": 0.001,
    }
    return {arm: metric for arm in ("unbiased", "traditional", "traditional_mps")}


def test_analysis_keeps_different_lattice_sizes_separate(tmp_path) -> None:
    for length in (9, 27):
        directory = tmp_path / f"L{length}"
        directory.mkdir()
        payload = {
            "length": length,
            "coarse_length": length // 3,
            "rg_levels": 1,
            "chi": 2,
            "seed": length,
            "training": {"final_record": {"objective": -0.1}},
            "evaluation": evaluation_payload(),
        }
        (directory / "summary.json").write_text(json.dumps(payload), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/analyze_results.py"), "--root", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    with (tmp_path / "summary_aggregate.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert {row["length"] for row in rows} == {"9", "27"}
