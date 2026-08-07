from __future__ import annotations

import numpy as np

from vmcrg_ref.blockspin import block_majority
from vmcrg_ref.rg import MajorityRGState


def test_block_spin_majority_rule() -> None:
    block = np.ones((3, 3), dtype=np.int8)
    block.flat[:4] = -1
    tiled = np.tile(block, (3, 3))
    np.testing.assert_array_equal(block_majority(tiled), np.ones((3, 3), dtype=np.int8))


def test_block_spin_incremental_update() -> None:
    rng = np.random.default_rng(20260803)
    spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(45, 45))
    state = MajorityRGState(spins.copy(), block_size=3, levels=2)
    for _ in range(100):
        x = int(rng.integers(45))
        y = int(rng.integers(45))
        proposal = state.proposal(x, y)
        state.commit(proposal)
        expected_level1 = block_majority(state.micro_spins, 3)
        expected_level2 = block_majority(expected_level1, 3)
        np.testing.assert_array_equal(state.level_spins[0], expected_level1)
        np.testing.assert_array_equal(state.level_spins[1], expected_level2)
        state.assert_consistent()
