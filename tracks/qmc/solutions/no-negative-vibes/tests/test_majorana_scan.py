from __future__ import annotations

import json

from oracle.majorana_scan import run_spec, scan_cell


def test_majorana_scan_common_cone_counts_every_sample() -> None:
    manifest = scan_cell(
        case="mrp_common",
        block_size=2,
        depth=5,
        scale=0.8,
        angle=0.0,
        seed=31,
        samples=30,
    )
    assert sum(manifest["counts"].values()) == 30
    assert manifest["counts"]["positive"] == 30
    assert manifest["max_structure_residual"] < 1e-12
    assert manifest["max_common_reality_residual"] < 1e-12
    assert manifest["max_reliable_square_identity_residual"] < 1e-11
    assert manifest["unreliable_determinant_checks"] == 0


def test_shared_j1_mixture_remains_real_and_is_deterministic() -> None:
    settings = {
        "case": "mrp_shared_j1_mixed",
        "block_size": 2,
        "depth": 6,
        "scale": 1.2,
        "angle": 1.1,
        "seed": 37,
        "samples": 25,
    }
    left = scan_cell(**settings)
    right = scan_cell(**settings)
    assert left == right
    assert left["counts"]["complex"] == 0
    assert left["max_common_reality_residual"] < 1e-12


def test_majorana_run_spec_is_resumable(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    spec_path = run_dir / "run_spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "run_id": "majorana-test",
                "run_dir": str(run_dir),
                "settings": {"samples": 8, "progress_every": 100},
                "provenance": {"protocol": "majorana-test-v1"},
                "cells": [
                    {
                        "cell_id": "cell-0001",
                        "params": {
                            "case": "mrp_rotated_common",
                            "block_size": 2,
                            "depth": 3,
                            "scale": 0.5,
                            "angle": 0.4,
                            "seed": 41,
                        },
                    }
                ],
            }
        )
    )

    assert run_spec(spec_path) == {"completed": 1, "skipped": 0}
    assert run_spec(spec_path) == {"completed": 0, "skipped": 1}
    manifest = json.loads(
        (run_dir / "cells" / "cell-0001" / "manifest.json").read_text()
    )
    assert manifest["provenance"] == {"protocol": "majorana-test-v1"}
    assert manifest["oracle_provenance"]["weight"].startswith("Tr(")
