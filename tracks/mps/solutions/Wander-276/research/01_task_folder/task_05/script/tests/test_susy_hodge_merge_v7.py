"""Tests for the compact sequential-pilot merge."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from merge_susy_hodge_pilot_v7 import merge_pilot_artifacts
from run_susy_hodge_geometric_eth_v7 import sha256


def _source(root: Path, size: int) -> tuple[Path, Path]:
    json_path = root / f"N{size}.json"
    npz_path = root / f"N{size}.npz"
    arrays = {}
    groups = []
    for sector in ("central", "adjacent"):
        for panel in ("sparse", "isotropic"):
            prefix = f"N{size}_{sector}_{panel}"
            arrays[f"{prefix}_physical"] = np.arange(3.0) + size
            arrays[f"{prefix}_physical_bootstrap"] = np.arange(5.0) + size
            arrays[f"{prefix}_collapsed_null"] = np.arange(4.0) + size
            arrays[f"{prefix}_hodge_null"] = np.arange(4.0) + size + 0.5
            groups.append(
                {
                    "N": size,
                    "sector": sector,
                    "panel_kind": panel,
                    "realizations": 3,
                }
            )
    np.savez_compressed(npz_path, **arrays)
    json_path.write_text(
        json.dumps(
            {
                "version": "v7",
                "uncertainty_unit": "complete_disorder_realization",
                "null_replicates": 4,
                "physical_bootstrap_replicates": 5,
                "prediction_coverage": 0.975,
                "groups": groups,
                "safe_covariates_sha256": f"safe-{size}",
                "arrays_sha256": sha256(npz_path),
                "checks": {"source_passed": True},
                "passed": True,
            }
        ),
        encoding="utf-8",
    )
    return json_path, npz_path


def test_merge_pilot_artifacts_preserves_complete_grid(tmp_path: Path) -> None:
    first_json, first_npz = _source(tmp_path, 8)
    second_json, second_npz = _source(tmp_path, 10)
    output_json = tmp_path / "combined.json"
    output_npz = tmp_path / "combined.npz"

    result = merge_pilot_artifacts(
        [first_json, second_json],
        [first_npz, second_npz],
        output_json=output_json,
        output_npz=output_npz,
        expected_sizes=(8, 10),
    )

    assert result["passed"]
    assert len(result["groups"]) == 8
    assert result["arrays_sha256"] == sha256(output_npz)
    with np.load(output_npz) as arrays:
        assert len(arrays.files) == 32


def test_merge_pilot_artifacts_rejects_tampered_npz(tmp_path: Path) -> None:
    json_path, npz_path = _source(tmp_path, 8)
    np.savez_compressed(npz_path, changed=np.arange(2.0))

    with pytest.raises(ValueError, match="hash mismatch"):
        merge_pilot_artifacts(
            [json_path],
            [npz_path],
            output_json=tmp_path / "combined.json",
            output_npz=tmp_path / "combined.npz",
            expected_sizes=(8,),
        )
