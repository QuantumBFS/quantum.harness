"""Reduced sequential-pilot aggregation for the SUSY/Hodge program."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from run_susy_hodge_geometric_eth_v7 import (
    aggregate_pilot,
    prepare_realization,
    run_panel,
)


def test_reduced_pilot_uses_complete_realizations_and_is_reproducible(
    tmp_path: Path,
) -> None:
    cases: list[tuple[int, str, int, str]] = []
    for sector in ("central", "adjacent"):
        for realization in range(2):
            prepare_realization(
                6,
                sector,
                realization,
                root=tmp_path,
                reduced=True,
                force=True,
            )
            for panel_kind in ("sparse", "isotropic"):
                case = (6, sector, realization, panel_kind)
                run_panel(*case, root=tmp_path, reduced=True, force=True)
                cases.append(case)

    first = aggregate_pilot(
        cases,
        root=tmp_path,
        null_samples=12,
        null_draws_per_realization=6,
        seed=109,
        safe_output_json=tmp_path / "safe_first.json",
        output_json=tmp_path / "pilot_first.json",
        output_npz=tmp_path / "pilot_first.npz",
    )
    second = aggregate_pilot(
        cases,
        root=tmp_path,
        null_samples=12,
        null_draws_per_realization=6,
        seed=109,
        safe_output_json=tmp_path / "safe_second.json",
        output_json=tmp_path / "pilot_second.json",
        output_npz=tmp_path / "pilot_second.npz",
    )
    assert first["passed"] and second["passed"]
    assert len(first["cases"]) == 4
    assert all(record["realizations"] == 2 for record in first["cases"])
    with np.load(tmp_path / "pilot_first.npz") as first_arrays:
        with np.load(tmp_path / "pilot_second.npz") as second_arrays:
            assert set(first_arrays.files) == set(second_arrays.files)
            for key in first_arrays.files:
                assert np.array_equal(first_arrays[key], second_arrays[key])
            assert first_arrays["N6_central_sparse_physical"].shape == (2,)
            assert first_arrays["N6_central_sparse_collapsed_null"].shape == (12,)
            assert first_arrays["N6_central_sparse_hodge_null"].shape == (12,)
    safe_text = (tmp_path / "safe_first.json").read_text(encoding="utf-8").lower()
    assert "r4" not in safe_text
    payload = json.loads((tmp_path / "pilot_first.json").read_text(encoding="utf-8"))
    assert payload["uncertainty_unit"] == "complete_disorder_realization"
    assert payload["null_draws_per_realization"] == 6
