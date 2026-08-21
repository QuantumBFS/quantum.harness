"""Deterministic opened-pilot tests for lattice SUSY v10."""

from __future__ import annotations

import json

import numpy as np

from run_lattice_susy_geometric_eth_v10 import (
    OPENED_CYCLES,
    panel_size_for_cycles,
    run_pilot,
    scientific_projection,
)


def test_opened_registration_and_panel_sizes_are_fixed() -> None:
    assert OPENED_CYCLES == (1, 2, 3)
    assert [panel_size_for_cycles(value) for value in OPENED_CYCLES] == [4, 8, 8]


def test_reduced_pilot_passes_all_physics_gates(tmp_path) -> None:
    result = run_pilot(tmp_path, cycles=(1, 2), panel_kinds=("local", "isotropic"))
    assert result["all_checks_pass"] is True
    assert (tmp_path / "lattice_susy_pilot_v10.json").is_file()
    for case in result["cases"]:
        assert case["observed_rank"] == 2 ** case["cycles"]
        assert case["external_gap"] > 1e-8
        assert case["projector_motion_norm"] > 1e-8
        assert set(case["panels"]) == {"local", "isotropic"}
        for panel in case["panels"].values():
            assert panel["R4"] >= 0.0
            assert 0.0 < panel["hodge_balance"] <= 1.0
            assert all(panel["checks"].values())
            arrays = np.load(tmp_path / panel["arrays_file"], allow_pickle=False)
            assert arrays["total"].shape[0] == panel["panel_size"]
            assert np.linalg.norm(arrays["minus"]) > 0.0
            assert np.linalg.norm(arrays["plus"]) > 0.0


def test_scientific_projection_is_reproducible(tmp_path) -> None:
    first = run_pilot(tmp_path / "first", cycles=(1,), panel_kinds=("local",))
    second = run_pilot(tmp_path / "second", cycles=(1,), panel_kinds=("local",))
    assert scientific_projection(first) == scientific_projection(second)
    on_disk = json.loads(
        (tmp_path / "first" / "lattice_susy_pilot_v10.json").read_text(
            encoding="utf-8"
        )
    )
    assert scientific_projection(on_disk) == scientific_projection(first)
