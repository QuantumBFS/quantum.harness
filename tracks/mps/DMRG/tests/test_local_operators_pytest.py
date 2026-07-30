from __future__ import annotations

import numpy as np
import pytest

from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis


@pytest.mark.parametrize("operator_index", range(len(EVEN_SHAPES)))
def test_local_operator_delta_matches_full_recompute(operator_index: int) -> None:
    rng = np.random.default_rng(20260810 + operator_index)
    spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(15, 15))
    basis = OperatorBasis(15, (EVEN_SHAPES[operator_index],))
    before = basis.values(spins)
    for x, y in ((0, 0), (7, 3), (14, 14)):
        delta = basis.delta_for_flip(spins, x, y)
        trial = spins.copy()
        trial[x, y] *= -1
        np.testing.assert_array_equal(basis.values(trial) - before, delta)
