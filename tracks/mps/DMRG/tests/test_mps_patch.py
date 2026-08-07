from __future__ import annotations

import numpy as np

from vmcrg_ref.mps_patch import PatchMPS


def test_mps_output_scalar() -> None:
    patch = np.array([-1, 1, -1, 1, 1, -1, -1, 1, 1], dtype=np.int8)
    for chi in (2, 4, 8):
        model = PatchMPS.random(chi=chi, seed=100 + chi)
        assert model.cores[0].shape == (1, 2, chi)
        assert all(core.shape == (chi, 2, chi) for core in model.cores[1:-1])
        assert model.cores[-1].shape == (chi, 2, 1)
        assert np.ndim(model.raw_value(patch)) == 0
        assert np.isfinite(model.raw_value(patch))


def test_mps_gradient_finite_difference() -> None:
    rng = np.random.default_rng(20260830)
    model = PatchMPS.random(chi=2, seed=20260831)
    patches = rng.choice(np.array([-1, 1], dtype=np.int8), size=(7, 9))
    weights = rng.normal(size=7)
    gradient = model.gradient(patches, weights=weights, symmetrize=True)
    epsilon = 1e-6
    core_index = 4
    index = (1, 0, 1)
    original = float(model.cores[core_index][index])
    model.cores[core_index][index] = original + epsilon
    plus = float(weights @ model.symmetric_values(patches))
    model.cores[core_index][index] = original - epsilon
    minus = float(weights @ model.symmetric_values(patches))
    model.cores[core_index][index] = original
    numeric = (plus - minus) / (2.0 * epsilon)
    assert abs(float(gradient.cores[core_index][index]) - numeric) < 2e-6


def test_mps_canonicalization_preserves_function() -> None:
    rng = np.random.default_rng(20260832)
    model = PatchMPS.random(chi=8, seed=20260833)
    patches = rng.choice(np.array([-1, 1], dtype=np.int8), size=(20, 9))
    before = model.raw_values(patches)
    model.left_canonicalize()
    np.testing.assert_allclose(model.raw_values(patches), before, atol=1e-12, rtol=1e-12)
