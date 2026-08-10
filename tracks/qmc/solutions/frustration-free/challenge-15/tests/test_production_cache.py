from __future__ import annotations

from dataclasses import replace
import re

import numpy as np
import pytest

from challenge15.fermions import DeterminantBasis
from challenge15.production_cache import (
    ProductionCacheKey,
    build_production_cache,
    clear_production_cache,
)
from challenge15.spec import SphereSpec


def _key(**changes) -> ProductionCacheKey:
    spec = SphereSpec(4)
    defaults = {
        "particles": spec.particles,
        "sectors": (0, 2),
        "orders": ((37, 10), (37, 11)),
        "dtype": "complex128",
        "source_sha256": "a" * 64,
        "policy_sha256": "b" * 64,
        "runtime_profile": "cpu-cp312-jax-0.4.38",
        "rank": 2,
        "determinant_block": 7,
        "carrier_block": 2,
        "quadrature_block": 13,
    }
    defaults.update(changes)
    return ProductionCacheKey(**defaults)


def _arrays(value):
    if isinstance(value, np.ndarray):
        yield value
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _arrays(item)
    elif hasattr(value, "__dataclass_fields__"):
        for name in value.__dataclass_fields__:
            yield from _arrays(getattr(value, name))


def test_cache_key_is_canonical_and_binds_every_required_identity():
    baseline = _key()
    assert re.fullmatch(r"[0-9a-f]{64}", baseline.sha256)
    changed = [
        replace(baseline, particles=5, orders=((61, 16), (61, 17))),
        replace(baseline, sectors=(2, 0), orders=((37, 11), (37, 10))),
        replace(baseline, orders=((39, 10), (39, 11))),
        replace(baseline, dtype="float64"),
        replace(baseline, source_sha256="c" * 64),
        replace(baseline, policy_sha256="d" * 64),
        replace(baseline, runtime_profile="cuda-cp312-jax-0.4.38"),
        replace(baseline, rank=4),
        replace(baseline, determinant_block=1),
        replace(baseline, carrier_block=1),
        replace(baseline, quadrature_block=64),
    ]
    assert len({baseline.sha256, *(key.sha256 for key in changed)}) == 12
    assert _key().canonical_bytes == baseline.canonical_bytes


def test_cache_contains_immutable_static_padded_scientific_data():
    clear_production_cache()
    key = _key()
    cache = build_production_cache(key)
    spec = SphereSpec(key.particles)
    basis = DeterminantBasis.with_two_m(spec, 0)

    assert cache.key is key
    assert re.fullmatch(r"[0-9a-f]{64}", cache.content_sha256)
    assert tuple(grid.target_l for grid in cache.projection_grids) == key.sectors
    assert tuple((grid.n_alpha, grid.n_beta) for grid in cache.projection_grids) == key.orders
    assert cache.determinant_blocks.shape[1:] == (key.determinant_block,)
    assert cache.determinant_masks.shape == cache.determinant_blocks.shape
    assert cache.occupation_indices.shape == (
        cache.determinant_blocks.shape[0],
        key.determinant_block,
        key.particles,
    )
    assert int(cache.determinant_masks.sum()) == basis.dimension
    np.testing.assert_array_equal(
        cache.determinant_blocks[cache.determinant_masks],
        np.asarray(basis.states, dtype=np.int64),
    )
    assert cache.carrier_masks.shape == (1, key.carrier_block)
    np.testing.assert_array_equal(cache.carrier_masks, [[True, True]])
    assert cache.sector_tokens.shape == (2, 2)
    np.testing.assert_array_equal(cache.sector_tokens, np.eye(2))

    for sector_index, grid in enumerate(cache.projection_grids):
        assert cache.beta_rotations[sector_index].shape == (grid.n_beta, 2, 2)
        assert cache.alpha_phases[sector_index].shape == (grid.n_alpha, 2)
        masks = cache.quadrature_masks[sector_index]
        assert masks.shape[1] == key.quadrature_block
        assert int(masks.sum()) == grid.n_alpha * grid.n_beta

    assert not hasattr(cache, "quadrature_rotations")
    for array in _arrays(cache):
        assert not array.flags.writeable
        with pytest.raises(ValueError):
            array.setflags(write=True)


def test_cache_is_reused_by_content_identity_and_has_no_mutable_aliases():
    clear_production_cache()
    first = build_production_cache(_key())
    second = build_production_cache(_key())
    distinct = build_production_cache(_key(quadrature_block=64))
    assert first is second
    assert first is not distinct
    assert first.content_sha256 != distinct.content_sha256
    assert first.projection_grids[0] is second.projection_grids[0]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"particles": 1}, "particles"),
        ({"sectors": (0,)}, "sectors"),
        ({"sectors": (0, 3)}, "sector"),
        ({"orders": ((37, 10),)}, "orders"),
        ({"dtype": "complex64"}, "dtype"),
        ({"source_sha256": "no"}, "source_sha256"),
        ({"policy_sha256": "A" * 64}, "policy_sha256"),
        ({"runtime_profile": ""}, "runtime_profile"),
        ({"rank": 0}, "rank"),
        ({"determinant_block": True}, "determinant_block"),
        ({"carrier_block": -1}, "carrier_block"),
        ({"quadrature_block": 0}, "quadrature_block"),
    ],
)
def test_cache_key_rejects_malformed_or_unsafe_identity(changes, message):
    with pytest.raises(ValueError, match=message):
        _key(**changes)
