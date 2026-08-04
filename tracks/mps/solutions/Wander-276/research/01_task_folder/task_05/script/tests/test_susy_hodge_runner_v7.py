"""Reduced end-to-end tests for the sealed SUSY/Hodge runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from run_susy_hodge_geometric_eth_v7 import (
    panel_paths,
    prepare_realization,
    run_panel,
    seal_file_hash,
    unseal_outcomes,
    write_safe_covariates,
)


def test_reduced_runner_splits_safe_hodge_data_from_r4(tmp_path: Path) -> None:
    case = (6, "central", 0, "sparse")
    kernel = prepare_realization(
        6,
        "central",
        0,
        root=tmp_path,
        reduced=True,
        force=True,
    )
    assert all(kernel["checks"].values())
    summary = run_panel(
        *case,
        root=tmp_path,
        reduced=True,
        force=True,
    )
    assert all(summary["safe"]["checks"].values())
    safe_json, safe_npz, outcome_json = panel_paths(tmp_path, *case)
    safe_text = safe_json.read_text(encoding="utf-8")
    safe_lower = safe_text.lower()
    assert "r4" not in safe_lower
    assert "four_point" not in safe_lower
    assert "connected" not in safe_lower
    assert '"R4"' in outcome_json.read_text(encoding="utf-8")
    with pytest.raises(KeyError):
        with __import__("numpy").load(safe_npz) as arrays:
            _ = arrays["minus"]

    covariate_path = tmp_path / "covariates.json"
    covariates = write_safe_covariates(
        [case],
        root=tmp_path,
        output_json=covariate_path,
    )
    assert covariates["checks"]["no_outcome_leakage"]
    assert "r4" not in covariate_path.read_text(encoding="utf-8").lower()


def test_unseal_requires_intact_prediction_and_outcome_identity(tmp_path: Path) -> None:
    case = (6, "central", 0, "isotropic")
    prepare_realization(6, "central", 0, root=tmp_path, reduced=True, force=True)
    run_panel(*case, root=tmp_path, reduced=True, force=True)
    prediction = tmp_path / "prediction.json"
    prediction.write_text(json.dumps({"prediction": "frozen"}), encoding="utf-8")
    seal = tmp_path / "prediction.sha256"
    with pytest.raises(FileNotFoundError, match="prediction hash seal"):
        unseal_outcomes(
            [case],
            root=tmp_path,
            prediction_json=prediction,
            prediction_seal=seal,
            output_json=tmp_path / "outcomes.json",
            output_npz=tmp_path / "outcomes.npz",
        )
    seal_file_hash(prediction, seal)
    prediction.write_text(json.dumps({"prediction": "changed"}), encoding="utf-8")
    with pytest.raises(ValueError, match="prediction hash seal mismatch"):
        unseal_outcomes(
            [case],
            root=tmp_path,
            prediction_json=prediction,
            prediction_seal=seal,
            output_json=tmp_path / "outcomes.json",
            output_npz=tmp_path / "outcomes.npz",
        )
    prediction.write_text(json.dumps({"prediction": "frozen"}), encoding="utf-8")
    seal_file_hash(prediction, seal)
    result = unseal_outcomes(
        [case],
        root=tmp_path,
        prediction_json=prediction,
        prediction_seal=seal,
        output_json=tmp_path / "outcomes.json",
        output_npz=tmp_path / "outcomes.npz",
    )
    assert result["passed"]

    _, _, outcome_path = panel_paths(tmp_path, *case)
    outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
    outcome["safe_identity_hash"] = "0" * 64
    outcome_path.write_text(json.dumps(outcome), encoding="utf-8")
    with pytest.raises(ValueError, match="outcome identity mismatch"):
        unseal_outcomes(
            [case],
            root=tmp_path,
            prediction_json=prediction,
            prediction_seal=seal,
            output_json=tmp_path / "corrupt.json",
            output_npz=tmp_path / "corrupt.npz",
        )
