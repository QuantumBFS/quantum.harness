from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np


physical_runner = importlib.import_module("run_physical_ensemble_v1")
covariance_runner = importlib.import_module("run_covariance_model_v1")


def test_reduced_covariance_model_uses_strict_splits(tmp_path: Path) -> None:
    physical_npz = tmp_path / "physical.npz"
    physical_runner.run(
        tmp_path / "physical.json",
        physical_npz,
        samples=96,
        seed_blocks=8,
    )
    result = covariance_runner.run(
        physical_npz,
        tmp_path / "covariance.json",
        tmp_path / "covariance.npz",
        diagnostic_rows=32,
        model_samples=32,
    )
    assert result["all_checks_pass"]
    assert result["diagnostic_training_rows"] == 32
    assert result["haar_samples"] == 32
    assert result["deformed_samples"] == 32
    assert len(result["validation_scores"]) == 5
    with np.load(tmp_path / "covariance.npz") as arrays:
        assert arrays["haar_spectra"].shape == (32, 50)
        assert arrays["deformed_spectra"].shape == (32, 50)
        train = arrays["diagnostic_indices"]
        validation = arrays["validation_indices"]
        test = arrays["test_indices"]
        assert np.intersect1d(train, validation).size == 0
        assert np.intersect1d(train, test).size == 0
        assert np.intersect1d(validation, test).size == 0
