"""Runner tests for fixed-Chern Wilson holonomy production."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from run_topological_holonomy_v3 import (
    OUTPUT_JSON,
    run,
    select_topology_branch,
)


EXTERNAL_REDUCED_BUNDLE = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "topology_v3_checkpoints"
    / "N3_mesh6_twist_bundle_v3.json"
)


@pytest.mark.skipif(
    not EXTERNAL_REDUCED_BUNDLE.exists(),
    reason=(
        "activates with production arrays listed in release_manifest_v1.json"
    ),
)
def test_reduced_runner_contains_topology_and_holonomy_gates(
    tmp_path: Path,
) -> None:
    payload = run(
        output_json=tmp_path / "result.json",
        output_npz=tmp_path / "result.npz",
        sizes=((3, 8, 16),),
        primary_mesh=6,
        convergence_mesh=8,
        g_values=(0.0, 0.25),
        generator_seeds=(20260728400,),
        cue_samples=64,
        workers=1,
        production=False,
    )
    assert set(payload["checks"]) >= {
        "kernel_count",
        "gap_open",
        "mesh_chern_integer",
        "mesh_chern_agreement",
        "determinant_trace_agreement",
        "branch_margin",
        "random_gauge_invariance",
        "isospectral_orbit",
    }
    assert payload["sizes"][0]["base_chern_integer"] == 6
    assert payload["configuration"]["g_values"] == [0.0, 0.25]


@pytest.mark.skipif(
    not OUTPUT_JSON.exists(),
    reason="production topology artifact has not been generated",
)
def test_chern_and_energy_are_fixed_across_g() -> None:
    payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    for size in payload["sizes"]:
        assert (
            max(size["primary_chern_range"])
            - min(size["primary_chern_range"])
            < 1e-8
        )
        assert size["maximum_energy_spectrum_error"] < 1e-13
        assert size["maximum_gap_error"] < 1e-13


@pytest.mark.skipif(
    not OUTPUT_JSON.exists(),
    reason="production topology artifact has not been generated",
)
def test_result_branch_is_recomputed_from_raw_topology_metrics() -> None:
    payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    assert payload["result_branch"] == select_topology_branch(payload)
