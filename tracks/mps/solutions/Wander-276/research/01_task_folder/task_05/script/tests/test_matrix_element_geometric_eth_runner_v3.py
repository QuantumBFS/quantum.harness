"""Runner tests for the matrix-element Geometric-ETH production artifact."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from run_matrix_element_geometric_eth_v3 import (
    OUTPUT_JSON,
    run,
    select_result_branch,
)


def test_reduced_runner_emits_all_gate_families(tmp_path: Path) -> None:
    result = run(
        output_json=tmp_path / "result.json",
        output_npz=tmp_path / "result.npz",
        checkpoint_dir=tmp_path / "checkpoints",
        case_indices=(0,),
        panels=3,
        gaussian_samples=32,
        production=False,
    )
    assert set(result["checks"]) >= {
        "kernel_count",
        "external_gap",
        "resolvent_residual",
        "channel_support",
        "gauge_invariance",
        "reference_reproducibility",
    }
    assert result["configuration"]["panel_size"] == 8
    assert result["cases"][0]["N"] == 3
    assert result["cases"][0]["rank"] == 16
    assert result["result_branch"] in {
        "wick_compatible_trend",
        "deformed_geometric_eth",
        "no_matrix_element_eth_trend",
        "manybody_sequence_incomplete",
    }


def test_reduced_runner_reuses_hash_identical_checkpoint(
    tmp_path: Path,
) -> None:
    arguments = {
        "output_json": tmp_path / "first.json",
        "output_npz": tmp_path / "first.npz",
        "checkpoint_dir": tmp_path / "checkpoints",
        "case_indices": (0,),
        "panels": 2,
        "gaussian_samples": 8,
        "production": False,
    }
    first = run(**arguments)
    arguments["output_json"] = tmp_path / "second.json"
    arguments["output_npz"] = tmp_path / "second.npz"
    second = run(**arguments)
    assert first["cases"][0]["checkpoint_reused"] is False
    assert second["cases"][0]["checkpoint_reused"] is True
    np.testing.assert_allclose(
        first["cases"][0]["physical_R4"],
        second["cases"][0]["physical_R4"],
    )


@pytest.mark.skipif(
    not OUTPUT_JSON.exists(),
    reason="production artifact has not been generated",
)
def test_production_artifact_uses_true_particle_number_sequence() -> None:
    payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    assert [row["N"] for row in payload["cases"]] == [3, 4, 5]
    assert [row["rank"] for row in payload["cases"]] == [16, 25, 36]
    assert all(
        row["n_flux"] == 2 * row["N"] + 2
        for row in payload["cases"]
    )


@pytest.mark.skipif(
    not OUTPUT_JSON.exists(),
    reason="production artifact has not been generated",
)
def test_claim_branch_is_recomputed_from_raw_metrics() -> None:
    payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    assert payload["result_branch"] == select_result_branch(payload)
