from __future__ import annotations

import itertools

import numpy as np
import pytest

from spinglass3d.rg import MajorityRG3D, block_majority_3d


def _random_q(length: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).choice(
        np.array([-1, 1], dtype=np.int8),
        size=(length, length, length),
    )


def _manual_block(q: np.ndarray, origin: tuple[int, int, int]) -> np.ndarray:
    length = q.shape[0]
    coarse = np.empty((length // 3,) * 3, dtype=np.int8)
    for site in np.ndindex(coarse.shape):
        total = 0
        for offset in itertools.product(range(3), repeat=3):
            microscopic = tuple(
                (origin[axis] + 3 * site[axis] + offset[axis]) % length
                for axis in range(3)
            )
            total += int(q[microscopic])
        coarse[site] = 1 if total > 0 else -1
    return coarse


@pytest.mark.parametrize("origin", tuple(itertools.product(range(3), repeat=3)))
def test_all_27_origins_match_manual_blocks(
    origin: tuple[int, int, int],
) -> None:
    q = _random_q(9, 2026072907)
    actual = block_majority_3d(q, origin=origin)
    expected = _manual_block(q, origin)
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("length,levels", [(9, 1), (18, 2), (45, 2)])
def test_incremental_rg_matches_full_recompute(length: int, levels: int) -> None:
    rng = np.random.default_rng(length + levels)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(length,) * 3)
    state = MajorityRG3D(q.copy(), levels=levels)
    for _ in range(200):
        site = tuple(int(rng.integers(length)) for _ in range(3))
        proposal = state.proposal(site)
        state.commit(proposal)
        state.assert_consistent()
    expected = state.q.copy()
    for _ in range(levels):
        expected = block_majority_3d(expected)
    np.testing.assert_array_equal(state.coarse, expected)


def test_proposal_is_side_effect_free_and_records_local_path() -> None:
    state = MajorityRG3D(_random_q(18, 91), levels=2, origin=(2, 1, 0))
    before_q = state.q.copy()
    before_levels = tuple(level.copy() for level in state.level_fields)
    proposal = state.proposal((17, 0, 4))
    np.testing.assert_array_equal(state.q, before_q)
    for before, after in zip(before_levels, state.level_fields, strict=True):
        np.testing.assert_array_equal(after, before)
    assert 1 <= len(proposal.level_changes) <= 2
    assert proposal.final_site == proposal.level_changes[-1].coarse_site
    assert proposal.final_changed == proposal.level_changes[-1].changed


@pytest.mark.parametrize("origin", tuple(itertools.product(range(3), repeat=3)))
def test_incremental_updates_respect_each_origin(
    origin: tuple[int, int, int],
) -> None:
    origin_code = sum(
        9**axis * value for axis, value in enumerate(origin)
    )
    rng = np.random.default_rng(1000 + origin_code)
    state = MajorityRG3D(_random_q(9, 96), levels=1, origin=origin)
    for _ in range(20):
        site = tuple(int(rng.integers(9)) for _ in range(3))
        state.commit(state.proposal(site))
        state.assert_consistent()
    np.testing.assert_array_equal(
        state.coarse,
        block_majority_3d(state.q, origin=origin),
    )


def test_stale_proposal_is_rejected() -> None:
    state = MajorityRG3D(_random_q(9, 92), levels=1)
    first = state.proposal((0, 0, 0))
    stale = state.proposal((0, 0, 0))
    state.commit(first)
    with pytest.raises(RuntimeError, match="stale"):
        state.commit(stale)


def test_origins_are_sensitivity_views_not_sample_records() -> None:
    q = _random_q(9, 93)
    states = [
        MajorityRG3D(q, levels=1, origin=origin)
        for origin in itertools.product(range(3), repeat=3)
    ]
    assert {state.source_fingerprint for state in states} == {
        states[0].source_fingerprint
    }
    assert len({state.origin for state in states}) == 27


def test_rg_rejects_invalid_shape_values_levels_and_origin() -> None:
    with pytest.raises(ValueError, match="cubic"):
        block_majority_3d(np.ones((9, 9, 8), dtype=np.int8))
    invalid = np.ones((9, 9, 9), dtype=np.int8)
    invalid[0, 0, 0] = 0
    with pytest.raises(ValueError, match=r"-1 and \+1"):
        block_majority_3d(invalid)
    with pytest.raises(ValueError, match="divisible"):
        MajorityRG3D(_random_q(6, 94), levels=2)
    with pytest.raises(ValueError, match="origin"):
        block_majority_3d(_random_q(9, 95), origin=(3, 0, 0))
