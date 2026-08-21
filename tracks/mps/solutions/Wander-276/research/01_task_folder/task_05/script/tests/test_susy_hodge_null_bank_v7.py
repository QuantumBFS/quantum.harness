"""Safe per-realization null banks for parallel SUSY/Hodge production."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from run_susy_hodge_geometric_eth_v7 import prepare_realization, run_panel
from run_susy_hodge_null_bank_v7 import null_bank_paths, write_null_bank


def test_null_bank_uses_only_safe_panel_files(tmp_path: Path) -> None:
    case = (6, "central", 0, "sparse")
    prepare_realization(6, "central", 0, root=tmp_path, reduced=True, force=True)
    run_panel(*case, root=tmp_path, reduced=True, force=True)
    outcome_path = (
        tmp_path / "panels" / "N6_central_seed000_sparse_v7.outcome.json"
    )
    outcome_path.unlink()
    result = write_null_bank(
        *case,
        checkpoint_root=tmp_path,
        output_root=tmp_path / "banks",
        draws=8,
        force=True,
    )
    assert result["passed"]
    metadata_path, arrays_path = null_bank_paths(
        tmp_path / "banks",
        *case,
    )
    text = metadata_path.read_text(encoding="utf-8").lower()
    assert "r4" not in text
    assert "four_point" not in text
    assert "connected" not in text
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["draws"] == 8
    with np.load(arrays_path) as arrays:
        assert arrays["collapsed_null"].shape == (8,)
        assert arrays["hodge_null"].shape == (8,)
        assert np.all(np.isfinite(arrays["collapsed_null"]))
        assert np.all(np.isfinite(arrays["hodge_null"]))


def test_null_bank_is_deterministic_and_hash_checked(tmp_path: Path) -> None:
    case = (6, "adjacent", 1, "isotropic")
    prepare_realization(6, "adjacent", 1, root=tmp_path, reduced=True, force=True)
    run_panel(*case, root=tmp_path, reduced=True, force=True)
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = write_null_bank(
        *case,
        checkpoint_root=tmp_path,
        output_root=first_root,
        draws=8,
        force=True,
    )
    second = write_null_bank(
        *case,
        checkpoint_root=tmp_path,
        output_root=second_root,
        draws=8,
        force=True,
    )
    assert first["collapsed_sha256"] == second["collapsed_sha256"]
    assert first["hodge_sha256"] == second["hodge_sha256"]


def test_pilot_slurm_array_maps_complete_n10_n12_grid() -> None:
    slurm_root = Path(__file__).resolve().parents[1] / "slurm"
    array = (slurm_root / "run_susy_hodge_pilot_v7_array.sbatch").read_text(
        encoding="utf-8"
    )
    submit = (slurm_root / "submit_susy_hodge_pilot_v7.sh").read_text(
        encoding="utf-8"
    )
    assert 'if [[ "$TASK_ID" -lt 96 ]]' in array
    assert "COUNT=48" in array and "COUNT=32" in array
    assert "LOCAL_ID=$((TASK_ID - 96))" in array
    assert array.count("run_susy_hodge_null_bank_v7.py") == 1
    assert "for PANEL_KIND in sparse isotropic" in array
    assert "TASK_ID=ARRAY_ID; TASK_ID<160; TASK_ID+=8" in array
    assert "--array=0-7%8" in submit
    logical_ids = {
        task_id for array_id in range(8) for task_id in range(array_id, 160, 8)
    }
    assert logical_ids == set(range(160))
    assert "sbatch" in submit
