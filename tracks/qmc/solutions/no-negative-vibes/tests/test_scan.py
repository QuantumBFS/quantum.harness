from __future__ import annotations

import json

from oracle.scan import run_spec, scan_cell


def test_scan_cell_counts_every_sample_and_echoes_setup() -> None:
    """Catches dropped failures or a manifest that cannot reproduce its cell."""
    manifest = scan_cell(case="o11", depth=4, scale=0.4, seed=17, samples=40)

    assert manifest["params"] == {
        "case": "o11",
        "depth": 4,
        "scale": 0.4,
        "seed": 17,
    }
    assert manifest["settings"]["samples"] == 40
    assert sum(manifest["counts"].values()) == 40
    assert manifest["max_structure_residual"] < 1e-12
    assert manifest["provenance"]["oracle_version"]
    assert manifest["counts"]["negative"] == 0
    assert manifest["counts"]["complex"] == 0


def test_scan_cell_is_deterministic() -> None:
    """Catches hidden randomness that makes a reported cell irreproducible."""
    left = scan_cell(case="sp2", depth=5, scale=0.8, seed=123, samples=25)
    right = scan_cell(case="sp2", depth=5, scale=0.8, seed=123, samples=25)

    assert left == right


def test_scan_cell_accepts_az_candidates_through_the_common_manifest() -> None:
    """Catches an AZ generator that bypasses provenance or result accounting."""
    manifest = scan_cell(case="az_aii", depth=4, scale=0.5, seed=29, samples=30)

    assert manifest["provenance"]["family"] == "az_aii_hermitian"
    assert sum(manifest["counts"].values()) == 30
    assert manifest["max_structure_residual"] < 1e-12
    assert manifest["counts"]["negative"] == 0
    assert manifest["counts"]["complex"] == 0


def test_run_spec_writes_resumable_parameter_scan_manifest(tmp_path) -> None:
    """Catches writing results outside the declared cell or recomputing completed cells."""
    run_dir = tmp_path / "run"
    spec_path = run_dir / "run_spec.json"
    run_dir.mkdir()
    spec_path.write_text(
        json.dumps(
            {
                "run_id": "test-run",
                "run_dir": str(run_dir),
                "settings": {"samples": 12, "progress_every": 100},
                "provenance": {"protocol": "test-v1"},
                "cells": [
                    {
                        "cell_id": "cell-0001",
                        "params": {
                            "case": "su2",
                            "depth": 2,
                            "scale": 0.3,
                            "seed": 7,
                        },
                    }
                ],
            }
        )
    )

    first = run_spec(spec_path)
    second = run_spec(spec_path)
    manifest = json.loads(
        (run_dir / "cells" / "cell-0001" / "manifest.json").read_text()
    )

    assert first == {"completed": 1, "skipped": 0}
    assert second == {"completed": 0, "skipped": 1}
    assert manifest["cell_id"] == "cell-0001"
    assert manifest["settings"]["samples"] == 12
    assert manifest["provenance"] == {"protocol": "test-v1"}
