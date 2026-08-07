from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/plot_results.py"
SPEC = importlib.util.spec_from_file_location("plot_results", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_plot_selection_defaults_to_largest_lattice() -> None:
    rows = [
        {"length": "9", "rg_levels": "1", "chi": "2", "arm": "traditional"},
        {"length": "27", "rg_levels": "1", "chi": "2", "arm": "traditional"},
        {"length": "27", "rg_levels": "1", "chi": "4", "arm": "traditional"},
    ]
    selected, metadata = MODULE.select_plot_rows(rows)
    assert {row["length"] for row in selected} == {"27"}
    assert metadata == {"length": 27, "rg_levels": 1}
