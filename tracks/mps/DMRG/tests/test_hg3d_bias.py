from __future__ import annotations

import numpy as np
import pytest

from spinglass3d.bias import BiasRoute, LocalBiasCache, OverlapBias
from spinglass3d.gauge import gauge_transform
from spinglass3d.linear_bias import LinearFeatureBasis
from spinglass3d.model import EABonds
from spinglass3d.templates import TemplateEncoder
from spinglass3d.tensor_train import LocalTensorTrain, SymmetricLocalTT


def _route_c_case(seed: int = 53) -> tuple[np.ndarray, EABonds, TemplateEncoder, OverlapBias]:
    rng = np.random.default_rng(seed)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(3, 3, 3))
    bonds = EABonds.sample(9, rng)
    encoder = TemplateEncoder("cube", True, 1)
    tt = SymmetricLocalTT(
        LocalTensorTrain.random(encoder.token_count, 2, seed=seed + 1),
        encoder,
    )
    bias = OverlapBias(
        route=BiasRoute.C_LINEAR_PLUS_TT,
        basis=LinearFeatureBasis.cube_v1(),
        coefficients=np.array([0.1, -0.07, 0.03, 0.04, -0.02]),
        tt=tt,
    )
    return q, bonds, encoder, bias


def test_cached_route_c_delta_matches_full_recompute_for_1000_proposals() -> None:
    q, bonds, encoder, bias = _route_c_case()
    cache = LocalBiasCache(q, bonds, encoder, bias)
    assert cache.lookup_size == 8192
    assert cache.lookup_complete is True
    rng = np.random.default_rng(2026072916)
    for _ in range(1000):
        site = tuple(int(rng.integers(3)) for _ in range(3))
        proposal = cache.proposal(site)
        assert proposal.delta == pytest.approx(
            cache.full_delta(site),
            abs=1e-10,
            rel=0.0,
        )
        if rng.random() < 0.55:
            cache.commit(proposal)
        cache.assert_consistent()


def test_route_c_bias_is_exactly_q_even_and_gauge_invariant() -> None:
    q, bonds, encoder, bias = _route_c_case(60)
    rng = np.random.default_rng(61)
    epsilon = rng.choice(np.array([-1, 1], dtype=np.int8), size=(9, 9, 9))
    reference = bias.value(q, bonds, encoder)
    assert bias.value(-q, bonds, encoder) == pytest.approx(
        reference,
        abs=5e-13,
        rel=0.0,
    )
    assert bias.value(q, gauge_transform(bonds, epsilon), encoder) == pytest.approx(
        reference,
        abs=5e-13,
        rel=0.0,
    )


def test_frozen_residual_projection_is_reported() -> None:
    _, _, encoder, bias = _route_c_case(65)
    rng = np.random.default_rng(66)
    tokens = rng.choice(
        np.array([-1, 1], dtype=np.int8),
        size=(64, encoder.token_count),
    )
    projection = bias.residual_projection(tokens)
    assert projection.coefficients.shape == (5,)
    assert np.all(np.isfinite(projection.coefficients))
    assert np.isfinite(projection.residual_norm)
    assert 0 <= projection.rank <= 5


def test_route_a_rejects_disorder_tokens() -> None:
    encoder = TemplateEncoder("cube", False, 1)
    tt = SymmetricLocalTT(LocalTensorTrain.random(8, 2, seed=70), encoder)
    bias = OverlapBias(
        route=BiasRoute.A_Q_ONLY,
        basis=None,
        coefficients=np.empty(0),
        tt=tt,
    )
    assert bias.tt.encoder.conditioned is False
    conditioned = TemplateEncoder("cube", True, 1)
    with pytest.raises(ValueError, match="Route A"):
        OverlapBias(
            route=BiasRoute.A_Q_ONLY,
            basis=None,
            coefficients=np.empty(0),
            tt=SymmetricLocalTT(
                LocalTensorTrain.random(13, 2, seed=71),
                conditioned,
            ),
        )


def test_cache_rejects_stale_proposal() -> None:
    q, bonds, encoder, bias = _route_c_case(80)
    cache = LocalBiasCache(q, bonds, encoder, bias)
    first = cache.proposal((0, 0, 0))
    stale = cache.proposal((0, 0, 0))
    cache.commit(first)
    with pytest.raises(RuntimeError, match="stale"):
        cache.commit(stale)


def test_lookup_rebuild_after_parameter_update_refreshes_all_cached_values() -> None:
    q, bonds, encoder, bias = _route_c_case(81)
    cache = LocalBiasCache(q, bonds, encoder, bias)
    stale = cache.proposal((0, 0, 0))
    before = cache.total_value
    bias.tt.model.cores[0] *= 1.25
    cache.rebuild_lookup()

    assert cache.total_value != pytest.approx(before, abs=1e-12, rel=0.0)
    cache.assert_consistent()
    with pytest.raises(RuntimeError, match="stale"):
        cache.commit(stale)


def test_conditioned_cross_lookup_matches_direct_symmetric_values() -> None:
    encoder = TemplateEncoder("cross", True, 1)
    tt = SymmetricLocalTT(
        LocalTensorTrain.random(encoder.token_count, 2, seed=2026073560),
        encoder,
    )
    bias = OverlapBias(
        BiasRoute.B_CONDITIONED_TT,
        None,
        np.empty(0),
        tt,
    )

    lookup = bias.build_lookup(encoder)

    assert lookup.shape == (1 << 19,)
    assert np.all(np.isfinite(lookup))
    rng = np.random.default_rng(2026073561)
    for code in rng.integers(0, 1 << 19, size=16):
        tokens = np.where(
            ((int(code) >> np.arange(19)) & 1) == 1,
            1,
            -1,
        ).astype(np.int8)
        assert lookup[int(code)] == pytest.approx(
            bias.local_value(tokens),
            abs=2e-11,
            rel=0.0,
        )
