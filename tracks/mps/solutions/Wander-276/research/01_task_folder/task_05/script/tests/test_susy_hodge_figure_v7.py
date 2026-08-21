"""Publication-figure and source-backed report tests for SUSY/Hodge v7."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.image as mpimg

from make_susy_hodge_figure_v7 import make_figure


def _write_sources(tmp_path: Path) -> tuple[Path, Path]:
    groups = []
    for N in (8, 10, 12):
        for sector, balance in (("central", 1.0), ("adjacent", 0.1)):
            for panel_index, panel in enumerate(("sparse", "isotropic")):
                observed = 0.34 - 0.01 * (N - 8) - 0.03 * panel_index
                groups.append(
                    {
                        "N": N,
                        "sector": sector,
                        "panel_kind": panel,
                        "observed_median": observed,
                        "physical_bootstrap_interval": [
                            observed - 0.01,
                            observed + 0.01,
                        ],
                        "collapsed_prediction_interval": [0.12, 0.13, 0.14],
                        "hodge_prediction_interval": [0.14, 0.15, 0.16],
                        "collapsed_covered": False,
                        "hodge_covered": False,
                        "median_hodge_balance": balance,
                    }
                )
    pilot = {
        "version": "v7",
        "uncertainty_unit": "complete_disorder_realization",
        "groups": groups,
        "checks": {"synthetic_complete_grid": True},
        "passed": True,
    }
    primary = []
    for sector, observed in (("central", 0.29), ("adjacent", 0.31)):
        primary.append(
            {
                "N": 14,
                "sector": sector,
                "panel_kind": "sparse",
                "observed_median": observed,
                "physical_bootstrap_interval": [observed - 0.01, observed + 0.01],
                "collapsed_prediction_interval": [0.10, 0.11, 0.12],
                "hodge_prediction_interval": [0.13, 0.14, 0.15],
                "collapsed_covered": False,
                "hodge_covered": False,
                "robust_outside_both": True,
            }
        )
    inference = {
        "version": "v7",
        "prediction_sha256": "a" * 64,
        "selected_branch": "cohomological_non_gaussian_class",
        "primary_pair": primary,
        "checks": {"valid_prediction_seal": True},
        "passed": True,
    }
    pilot_path = tmp_path / "pilot.json"
    inference_path = tmp_path / "inference.json"
    pilot_path.write_text(json.dumps(pilot), encoding="utf-8")
    inference_path.write_text(json.dumps(inference), encoding="utf-8")
    return pilot_path, inference_path


def test_figure_and_report_are_provenance_complete(tmp_path: Path) -> None:
    pilot, inference = _write_sources(tmp_path)
    pdf = tmp_path / "figure.pdf"
    png = tmp_path / "figure.png"
    manifest_path = tmp_path / "figure.json"
    report_path = tmp_path / "report.md"
    manifest = make_figure(
        pilot_json=pilot,
        inference_json=inference,
        output_pdf=pdf,
        output_png=png,
        manifest_json=manifest_path,
        report_md=report_path,
    )
    assert all(manifest["checks"].values())
    assert manifest["selected_branch"] == "cohomological_non_gaussian_class"
    assert manifest["pilot_group_count"] == 12
    assert pdf.is_file() and png.is_file() and manifest_path.is_file()
    image = mpimg.imread(png)
    assert image.shape[1] >= 2000
    report = report_path.read_text(encoding="utf-8")
    assert "## Established" in report
    assert "## Not established" in report
    assert "cohomological_non_gaussian_class" in report
    assert "](https://" in report
