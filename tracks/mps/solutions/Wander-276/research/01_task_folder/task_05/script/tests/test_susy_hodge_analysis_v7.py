"""Sealed prediction and complete-realization inference tests for v7."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from analyze_susy_hodge_geometric_eth_v7 import (
    aggregate_pilot_from_banks,
    score_unsealed_n14,
    select_frozen_branch,
    write_n14_prediction,
)
from run_susy_hodge_geometric_eth_v7 import (
    panel_paths,
    prepare_realization,
    run_panel,
)
from run_susy_hodge_null_bank_v7 import write_null_bank


def _reduced_prediction_fixture(
    tmp_path: Path,
    *,
    delete_outcomes: bool = True,
) -> list[tuple[int, str, int, str]]:
    checkpoint_root = tmp_path / "checkpoints"
    bank_root = tmp_path / "banks"
    cases: list[tuple[int, str, int, str]] = []
    for sector in ("central", "adjacent"):
        for realization in range(2):
            prepare_realization(
                6,
                sector,
                realization,
                root=checkpoint_root,
                reduced=True,
                force=True,
            )
            case = (6, sector, realization, "sparse")
            run_panel(*case, root=checkpoint_root, reduced=True, force=True)
            write_null_bank(
                *case,
                checkpoint_root=checkpoint_root,
                output_root=bank_root,
                draws=8,
                force=True,
            )
            if delete_outcomes:
                # Prediction generation must succeed with no outcome sidecars.
                _, _, outcome_path = panel_paths(checkpoint_root, *case)
                outcome_path.unlink()
            cases.append(case)
    return cases


def test_prediction_is_sealed_before_any_outcome_is_read(tmp_path: Path) -> None:
    cases = _reduced_prediction_fixture(tmp_path)
    prediction_json = tmp_path / "prediction.json"
    prediction_npz = tmp_path / "prediction.npz"
    prediction_seal = tmp_path / "prediction.sha256"
    payload = write_n14_prediction(
        cases,
        checkpoint_root=tmp_path / "checkpoints",
        null_bank_root=tmp_path / "banks",
        safe_covariates_json=tmp_path / "safe.json",
        output_json=prediction_json,
        output_npz=prediction_npz,
        seal_path=prediction_seal,
        null_replicates=24,
        seed=71,
    )
    assert payload["passed"]
    assert prediction_seal.is_file()
    serialized = prediction_json.read_text(encoding="utf-8").lower()
    assert "r4" not in serialized
    assert "four_point" not in serialized
    assert "connected" not in serialized
    assert {
        (item["sector"], item["panel_kind"])
        for item in payload["primary_pair"]
    } == {("central", "sparse"), ("adjacent", "sparse")}
    with np.load(prediction_npz) as arrays:
        assert arrays["N6_central_sparse_collapsed"].shape == (24,)
        assert arrays["N6_adjacent_sparse_hodge"].shape == (24,)


def test_scoring_fails_closed_when_prediction_seal_is_corrupted(
    tmp_path: Path,
) -> None:
    cases = _reduced_prediction_fixture(tmp_path)
    prediction_json = tmp_path / "prediction.json"
    prediction_npz = tmp_path / "prediction.npz"
    prediction_seal = tmp_path / "prediction.sha256"
    write_n14_prediction(
        cases,
        checkpoint_root=tmp_path / "checkpoints",
        null_bank_root=tmp_path / "banks",
        safe_covariates_json=tmp_path / "safe.json",
        output_json=prediction_json,
        output_npz=prediction_npz,
        seal_path=prediction_seal,
        null_replicates=12,
        seed=73,
    )
    unsealed = {
        "records": [
            {
                "N": N,
                "sector": sector,
                "realization": realization,
                "panel_kind": panel,
                "R4": float(0.1 + 0.01 * realization),
            }
            for N, sector, realization, panel in cases
        ],
        "passed": True,
    }
    unsealed_json = tmp_path / "unsealed.json"
    unsealed_json.write_text(json.dumps(unsealed), encoding="utf-8")
    prediction_seal.write_text("0" * 64 + "  prediction.json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="seal mismatch"):
        score_unsealed_n14(
            prediction_json,
            prediction_seal,
            unsealed_json,
            output_json=tmp_path / "inference.json",
            bootstrap_replicates=32,
            seed=79,
        )


def test_frozen_branch_selection_is_exhaustive_and_fail_closed() -> None:
    assert select_frozen_branch(True, True, False, True) == (
        "strong_covariance_universality"
    )
    assert select_frozen_branch(False, True, False, True) == (
        "hodge_resolved_geometric_eth"
    )
    assert select_frozen_branch(False, False, False, True) == (
        "cohomological_non_gaussian_class"
    )
    assert select_frozen_branch(False, False, True, True) == (
        "structured_cohomology"
    )
    assert select_frozen_branch(True, False, False, True) == (
        "feasibility_failure"
    )
    assert select_frozen_branch(True, True, False, False) == (
        "feasibility_failure"
    )


def test_scheduler_stops_after_the_prediction_seal() -> None:
    script_root = Path(__file__).resolve().parents[1]
    submit = (
        script_root / "slurm" / "submit_susy_hodge_N14_v7.sh"
    ).read_text(encoding="utf-8")
    assert "seal_susy_hodge_N14_v7.sbatch" in submit
    assert "run_susy_hodge_N14_null_v7_array.sbatch" in submit
    assert 'dependency="afterok:${ARRAY_JOB}"' in submit
    assert 'dependency="afterok:${NULL_JOB}"' in submit
    assert "analyze_susy_hodge_geometric_eth_v7.py unseal" not in submit
    seal_job = (
        script_root / "slurm" / "seal_susy_hodge_N14_v7.sbatch"
    ).read_text(encoding="utf-8")
    assert " predict " in seal_job
    assert " unseal" not in seal_job
    response_job = (
        script_root / "slurm" / "run_susy_hodge_N14_v7_array.sbatch"
    ).read_text(encoding="utf-8")
    assert 'WORKER_COUNT="${N14_RESPONSE_WORKERS:-16}"' in response_job
    logical_ids = {
        logical_id
        for array_id in range(8)
        for logical_id in range(array_id, 48, 8)
    }
    assert logical_ids == set(range(48))
    null_job = (
        script_root / "slurm" / "run_susy_hodge_N14_null_v7_array.sbatch"
    ).read_text(encoding="utf-8")
    assert 'WORKER_COUNT="${N14_NULL_WORKERS:-48}"' in null_job
    null_logical_ids = {
        logical_id
        for array_id in range(8)
        for logical_id in range(array_id, 48, 8)
    }
    assert null_logical_ids == set(range(48))


def test_pilot_aggregate_resamples_complete_realizations(tmp_path: Path) -> None:
    cases = _reduced_prediction_fixture(tmp_path, delete_outcomes=False)
    payload = aggregate_pilot_from_banks(
        cases,
        checkpoint_root=tmp_path / "checkpoints",
        null_bank_root=tmp_path / "banks",
        safe_covariates_json=tmp_path / "pilot_safe.json",
        output_json=tmp_path / "pilot.json",
        output_npz=tmp_path / "pilot.npz",
        null_replicates=12,
        bootstrap_replicates=16,
        seed=83,
    )
    assert payload["passed"]
    assert payload["uncertainty_unit"] == "complete_disorder_realization"
    assert len(payload["groups"]) == 2
    with np.load(tmp_path / "pilot.npz") as arrays:
        assert arrays["N6_central_sparse_physical"].shape == (2,)
        assert arrays["N6_central_sparse_physical_bootstrap"].shape == (16,)
        assert arrays["N6_central_sparse_collapsed_null"].shape == (12,)
        assert arrays["N6_central_sparse_hodge_null"].shape == (12,)
