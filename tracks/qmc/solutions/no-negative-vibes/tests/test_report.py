from __future__ import annotations

import json

import pandas as pd

from oracle.report import summarize_rows, write_report


def test_summarize_rows_keeps_failures_and_uses_declared_sample_count() -> None:
    """Catches averaging only successful-looking cells or dividing by cell count."""
    rows = pd.DataFrame(
        [
            {
                "cell_id": "cell-1",
                "case": "a",
                "status": "success",
                "negative": 1,
                "complex": 0,
                "uncertain": 0,
                "max_structure_residual": 1e-15,
            },
            {
                "cell_id": "cell-2",
                "case": "a",
                "status": "failed",
                "negative": 2,
                "complex": 1,
                "uncertain": 0,
                "max_structure_residual": 2e-15,
            },
        ]
    )

    summary = summarize_rows(rows, samples_per_cell=10).loc["a"]

    assert summary["cells"] == 2
    assert summary["failed_cells"] == 1
    assert summary["samples"] == 20
    assert summary["negative"] == 3
    assert summary["negative_rate"] == 0.15
    assert summary["complex"] == 1
    assert summary["max_structure_residual"] == 2e-15


def test_write_report_creates_machine_and_human_readable_artifacts(tmp_path) -> None:
    """Catches a scan that finishes without a summary, plot, or run manifest."""
    rows = pd.DataFrame(
        [
            {
                "cell_id": "cell-1",
                "case": "o11",
                "status": "success",
                "negative": 0,
                "complex": 0,
                "uncertain": 0,
                "max_structure_residual": 0.0,
            }
        ]
    )
    rows.to_csv(tmp_path / "parameter-scan.csv", index=False)

    write_report(tmp_path, samples_per_cell=12)

    run = json.loads((tmp_path / "run.json").read_text())
    assert (tmp_path / "family-summary.csv").is_file()
    assert (tmp_path / "family-summary.png").stat().st_size > 0
    assert run["cells"] == 1
    assert run["samples"] == 12
