"""Machine-readable analytic-control artifact tests for SUSY/Hodge v7."""

from __future__ import annotations

import json
from pathlib import Path

from generate_susy_hodge_controls_v7 import generate_controls


def test_decomposable_atoms_and_one_sided_regression_are_audited(
    tmp_path: Path,
) -> None:
    output = tmp_path / "controls.json"
    payload = generate_controls(output)
    assert payload["passed"]
    assert payload["decomposable_N6"]["diagonal_multiplicities"] == {
        "negative": 1,
        "zero": 16,
        "positive": 1,
    }
    assert payload["decomposable_N6"]["off_diagonal_multiplicities"] == {
        "negative": 2,
        "zero": 14,
        "positive": 2,
    }
    assert payload["decomposable_N8"]["bps_rank"] == 60
    assert payload["one_sided_regression"]["max_absolute_difference"] == 0.0
    reloaded = json.loads(output.read_text(encoding="utf-8"))
    assert reloaded["sources"] == payload["sources"]
