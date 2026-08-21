"""Fail-closed manuscript-asset tests for the SUSY/Hodge result."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from make_susy_hodge_manuscript_assets_v7 import build_manuscript_assets
from run_susy_hodge_geometric_eth_v7 import sha256


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sources(root: Path, *, branch: str = "hodge_resolved_geometric_eth") -> dict:
    groups = [
        {
            "N": size,
            "sector": sector,
            "panel_kind": panel,
            "collapsed_covered": False,
            "hodge_covered": False,
        }
        for size in (8, 10, 12)
        for sector in ("central", "adjacent")
        for panel in ("sparse", "isotropic")
    ]
    primary = [
        {
            "N": 14,
            "sector": sector,
            "panel_kind": "sparse",
            "observed_median": 0.3,
            "physical_bootstrap_interval": [0.29, 0.31],
            "collapsed_prediction_interval": [0.1, 0.12, 0.14],
            "hodge_prediction_interval": [0.28, 0.30, 0.32],
        }
        for sector in ("central", "adjacent")
    ]
    pilot = root / "pilot.json"
    inference = root / "inference.json"
    figure = root / "figure.pdf"
    figure_manifest = root / "figure.json"
    common = {"version": "v7", "checks": {"passed": True}, "passed": True}
    _write_json(pilot, {**common, "groups": groups})
    _write_json(
        inference,
        {
            **common,
            "selected_branch": branch,
            "prediction_sha256": "a" * 64,
            "primary_pair": primary,
        },
    )
    figure.write_bytes(b"%PDF-1.4\nsynthetic\n")
    _write_json(
        figure_manifest,
        {
            **common,
            "selected_branch": branch,
            "inputs": {
                pilot.name: sha256(pilot),
                inference.name: sha256(inference),
            },
            "outputs": {figure.name: sha256(figure)},
        },
    )
    return {
        "pilot_json": pilot,
        "inference_json": inference,
        "figure_manifest_json": figure_manifest,
        "figure_pdf": figure,
        "results_tex": root / "results.tex",
        "figure_target": root / "copied.pdf",
        "manifest_json": root / "assets.json",
    }


def test_build_manuscript_assets_enables_results_after_hash_audit(
    tmp_path: Path,
) -> None:
    paths = _sources(tmp_path)
    manifest = build_manuscript_assets(**paths)

    assert manifest["passed"]
    text = paths["results_tex"].read_text(encoding="utf-8")
    assert r"\heldoutcompletetrue" in text
    assert r"\heldoutcompletefalse" not in text
    assert r"hodge\_resolved\_geometric\_eth" in text
    assert r"\newcommand{\HeldoutAdjacentPhysical}" in text
    assert r"\newcommand{\HeldoutCentralHodge}" in text
    assert sha256(paths["figure_pdf"]) == sha256(paths["figure_target"])


def test_build_manuscript_assets_rejects_feasibility_failure(
    tmp_path: Path,
) -> None:
    paths = _sources(tmp_path, branch="feasibility_failure")

    with pytest.raises(ValueError, match="not publishable"):
        build_manuscript_assets(**paths)
