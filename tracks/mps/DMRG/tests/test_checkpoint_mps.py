from __future__ import annotations

import numpy as np

from vmcrg_ref.checkpoint import load_mps_checkpoint, save_mps_checkpoint
from vmcrg_ref.mps_patch import PatchMPS


def test_checkpoint_roundtrip(tmp_path) -> None:
    model = PatchMPS.random(chi=4, seed=20260880)
    linear_bias = np.linspace(-0.2, 0.02, 13)
    metadata = {"step": 17, "seed": 20260880, "objective": -0.125}
    save_mps_checkpoint(
        tmp_path / "checkpoint",
        model=model,
        alpha=0.37,
        linear_bias=linear_bias,
        metadata=metadata,
    )
    restored = load_mps_checkpoint(tmp_path / "checkpoint")
    assert restored.alpha == 0.37
    np.testing.assert_array_equal(restored.linear_bias, linear_bias)
    assert restored.metadata == metadata
    assert restored.model.chi == model.chi
    for actual, expected in zip(restored.model.cores, model.cores):
        np.testing.assert_array_equal(actual, expected)
