from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np


runner = importlib.import_module("run_physical_ensemble_v1")


def test_reduced_physical_run_is_deterministic(tmp_path: Path) -> None:
    first_json = tmp_path / "first.json"
    first_npz = tmp_path / "first.npz"
    second_json = tmp_path / "second.json"
    second_npz = tmp_path / "second.npz"
    first = runner.run(first_json, first_npz, samples=96, seed_blocks=8)
    second = runner.run(second_json, second_npz, samples=96, seed_blocks=8)
    assert first["split"] == {
        "train": 60,
        "validation": 18,
        "test": 18,
        "split_seed": runner.REGISTERED_SEED + 1,
    }
    assert first["all_checks_pass"] and second["all_checks_pass"]
    with np.load(first_npz) as left, np.load(second_npz) as right:
        np.testing.assert_array_equal(
            left["normalized_spectra"], right["normalized_spectra"]
        )
        assert left["normalized_spectra"].shape == (96, 50)
        assert np.all(left["active_ranks"] == 50)
        assert np.unique(left["seed_block"]).size == 8
        train = left["train_indices"]
        validation = left["validation_indices"]
        test = left["test_indices"]
        assert np.intersect1d(train, validation).size == 0
        assert np.intersect1d(train, test).size == 0
        assert np.intersect1d(validation, test).size == 0
