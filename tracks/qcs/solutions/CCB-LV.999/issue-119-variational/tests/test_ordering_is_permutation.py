from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from src.orderings import (
    OrderingError,
    corrected_block2_ga_ordering,
    validate_ordering,
)


def test_validate_ordering_accepts_strict_permutation() -> None:
    assert validate_ordering([2, 0, 1], 3) == (2, 0, 1)


@pytest.mark.parametrize("ordering", ([0, 0, 1], [0, 1], [0, 1, 3]))
def test_validate_ordering_rejects_invalid_permutation(ordering: list[int]) -> None:
    with pytest.raises(OrderingError, match="permutation"):
        validate_ordering(ordering, 3)


class _FakeRandom:
    seed = 0

    @classmethod
    def rand_seed(cls, seed: int) -> None:
        cls.seed = seed


class _FakeVector(tuple):
    pass


class _FakeOrbitalOrdering:
    candidates = {
        1234: _FakeVector([0, 1, 2]),
        1235: _FakeVector([2, 1, 0]),
        1236: _FakeVector([1, 0, 2]),
    }
    costs = {
        (0, 1, 2): 8.0,
        (2, 1, 0): 5.0,
        (1, 0, 2): 3.0,
    }

    @classmethod
    def ga_opt(cls, n: int, kmat: object, **kwargs: object) -> _FakeVector:
        assert n == 3
        return cls.candidates[_FakeRandom.seed]

    @classmethod
    def evaluate(
        cls, n: int, kmat: object, ordering: _FakeVector
    ) -> float:
        assert n == 3
        assert isinstance(ordering, _FakeVector)
        return cls.costs[tuple(ordering)]


def _fake_driver() -> SimpleNamespace:
    backend = SimpleNamespace(
        VectorDouble=lambda values: tuple(values),
        Random=_FakeRandom,
        OrbitalOrdering=_FakeOrbitalOrdering,
    )
    return SimpleNamespace(bw=SimpleNamespace(b=backend))


def test_corrected_ga_selects_lowest_evaluated_cost_deterministically() -> None:
    h1e = np.eye(3)
    g2e = np.zeros((3, 3, 3, 3))

    first = corrected_block2_ga_ordering(
        _fake_driver(), h1e, g2e, n_tasks=3, base_seed=1234
    )
    second = corrected_block2_ga_ordering(
        _fake_driver(), h1e, g2e, n_tasks=3, base_seed=1234
    )

    assert first.ordering == (1, 0, 2)
    assert first.cost == 3.0
    assert first == second
    assert first.cost <= min(candidate.cost for candidate in first.candidates)
