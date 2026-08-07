from __future__ import annotations

import numpy as np

from vmcrg_ref.mps_patch import PatchMPS
from vmcrg_ref.patch_table import (
    PatchEnergyCache,
    PatchLookupTable,
    decode_patch,
    encode_patch,
    enumerate_patches,
)


def test_patch_bit_encoding_roundtrip() -> None:
    patches = enumerate_patches()
    assert patches.shape == (512, 9)
    for pattern_id, patch in enumerate(patches):
        assert encode_patch(patch) == pattern_id
        np.testing.assert_array_equal(decode_patch(pattern_id), patch)


def test_lookup_table_matches_direct_mps() -> None:
    model = PatchMPS.random(chi=4, seed=20260840)
    lookup = PatchLookupTable.from_model(model)
    direct = model.symmetric_values(enumerate_patches())
    direct -= direct.mean()
    np.testing.assert_allclose(lookup.values, direct, atol=1e-12, rtol=0.0)


def test_uniform_target_patch_histogram() -> None:
    patches = enumerate_patches()
    counts = np.bincount([encode_patch(patch) for patch in patches], minlength=512)
    np.testing.assert_array_equal(counts, np.ones(512, dtype=np.int64))


def test_bias_constant_gauge() -> None:
    model = PatchMPS.random(chi=2, seed=20260841)
    lookup = PatchLookupTable.from_model(model)
    assert abs(float(lookup.values.mean())) < 1e-14


def test_cache_consistency_after_random_flips() -> None:
    rng = np.random.default_rng(20260842)
    spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(7, 7))
    lookup = PatchLookupTable.from_model(PatchMPS.random(chi=2, seed=20260843))
    cache = PatchEnergyCache(spins, lookup)
    for _ in range(100):
        x = int(rng.integers(7))
        y = int(rng.integers(7))
        before = cache.energy
        proposal = cache.proposal(x, y)
        trial = spins.copy()
        trial[x, y] *= -1
        assert abs((cache.full_energy(trial) - before) - proposal.delta_energy) < 1e-12
        cache.commit(proposal)
        spins[x, y] *= -1
        cache.assert_consistent()
