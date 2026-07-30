from __future__ import annotations

import numpy as np

from vmcrg_ref.mps_patch import PatchMPS
from vmcrg_ref.symmetries import D4_INDEX_MAPS, transform_patch


def test_patch_d4_transformations() -> None:
    patch = np.arange(9, dtype=np.int8)
    transformed = {tuple(transform_patch(patch, index)) for index in range(8)}
    assert len(D4_INDEX_MAPS) == 8
    assert len(transformed) == 8
    np.testing.assert_array_equal(transform_patch(patch, 0), patch)
    rotated_four_times = patch.copy()
    for _ in range(4):
        rotated_four_times = transform_patch(rotated_four_times, 1)
    np.testing.assert_array_equal(rotated_four_times, patch)


def test_z2_symmetry_exact() -> None:
    rng = np.random.default_rng(20260820)
    model = PatchMPS.random(chi=4, seed=20260821)
    patches = rng.choice(np.array([-1, 1], dtype=np.int8), size=(100, 9))
    np.testing.assert_allclose(
        model.symmetric_values(patches),
        model.symmetric_values(-patches),
        atol=5e-14,
        rtol=0.0,
    )


def test_d4_symmetry_exact() -> None:
    rng = np.random.default_rng(20260822)
    model = PatchMPS.random(chi=4, seed=20260823)
    patches = rng.choice(np.array([-1, 1], dtype=np.int8), size=(100, 9))
    reference = model.symmetric_values(patches)
    for index in range(8):
        transformed = np.stack([transform_patch(patch, index) for patch in patches])
        np.testing.assert_allclose(
            model.symmetric_values(transformed), reference, atol=5e-14, rtol=0.0
        )
