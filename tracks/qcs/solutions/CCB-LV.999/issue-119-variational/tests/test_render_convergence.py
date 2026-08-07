from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

from src.render_convergence import render_run


def test_render_run_writes_plot_and_short_report(tmp_path: Path) -> None:
    result = {
        "schema_version": 1,
        "status": "completed",
        "instance": "tiny",
        "method": "block2-dmrg",
        "sector": {"norb": 2, "nelec": 2, "ms2": 0, "spin": 0},
        "input": {"sha256": "a" * 64},
        "ordering": {"method": "fiedler", "permutation": [0, 1]},
        "stages": [
            {
                "bond_dimension": 8,
                "energy_hartree": -0.7,
                "discarded_weight": 1.0e-3,
                "wall_time_s": 1.0,
                "rss_mb": 100.0,
            },
            {
                "bond_dimension": 16,
                "energy_hartree": -0.8,
                "discarded_weight": 1.0e-4,
                "wall_time_s": 2.0,
                "rss_mb": 110.0,
            },
        ],
        "headline": {
            "kind": "finite_m_mps_expectation",
            "bond_dimension": 16,
            "energy_hartree": -0.8,
        },
        "references": {"external": -0.75, "skqd": -0.75},
    }
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")

    plot, report = render_run(tmp_path)

    assert plot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    text = report.read_text(encoding="utf-8")
    assert "−0.800000000000" in text
    assert "finite-M MPS expectation" in text
    comparison = tmp_path / "skqd-comparison.png"
    assert comparison.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "![SKQD comparison](skqd-comparison.png)" in text
