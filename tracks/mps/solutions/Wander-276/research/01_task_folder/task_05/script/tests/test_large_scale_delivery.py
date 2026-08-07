from __future__ import annotations

import importlib
from pathlib import Path

import pytest


verifier = importlib.import_module("verify_large_scale_article_v1")
EXTERNAL_PHYSICAL = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "physical_ensemble_v1.npz"
)


@pytest.mark.skipif(
    not EXTERNAL_PHYSICAL.exists(),
    reason=(
        "activates with production arrays listed in release_manifest_v1.json"
    ),
)
def test_registered_delivery_gates_pass(tmp_path: Path) -> None:
    audit = verifier.run(tmp_path / "audit.json")
    assert audit["all_checks_pass"]
    assert audit["registered_scale"] == {
        "physical_matrices": 20_000,
        "haar_matrices": 10_000,
        "deformed_matrices": 10_000,
        "root_matrices": 8_750,
        "maximum_rank": 800,
    }
    assert audit["pdf"]["pages"] == 10
    assert len(audit["rendered_pages"]) == 10
