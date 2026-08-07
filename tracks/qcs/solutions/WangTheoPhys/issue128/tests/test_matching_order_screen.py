from __future__ import annotations

import pytest

from trottercert.matching_screen import permutation_from_index


def test_permutation_index_covers_exactly_24_orders() -> None:
    values = [permutation_from_index(index) for index in range(24)]
    assert len(set(values)) == 24
    assert values[0] == (0, 1, 2, 3)
    assert values[-1] == (3, 2, 1, 0)


def test_permutation_index_rejects_out_of_range() -> None:
    with pytest.raises(IndexError, match="permutation index"):
        permutation_from_index(24)
