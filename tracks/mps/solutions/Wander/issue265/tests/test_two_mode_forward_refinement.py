from __future__ import annotations

import json
from pathlib import Path

from src.two_mode_forward_refinement import (
    audit_deterministic_forward_refinement,
)

ROOT = Path(__file__).resolve().parents[1]


def test_registered_final_grid_refines_and_passes_manufactured_truth() -> None:
    config = json.loads(
        (
            ROOT / "configs" / "two_mode_solver_budget_20260730.json"
        ).read_text()
    )
    result = audit_deterministic_forward_refinement(
        config["forward_refinement"]
    )
    assert result["status"] == "pass"
    assert result["quantum_fit_error_used"] is False
    assert result["checks"] == {
        "profile": True,
        "current": True,
        "profile_refines": True,
        "current_refines": True,
        "conservation": True,
    }
