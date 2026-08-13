from __future__ import annotations

import mpmath as mp
import pytest

from oracle.high_precision import replay_weight


def test_replay_weight_handles_real_generators() -> None:
    example = {
        "generators": [
            [[0.0, 0.4], [0.4, 0.0]],
            [[0.2, 0.0], [0.0, -0.1]],
        ]
    }

    weight = replay_weight(example, dps=50)

    assert mp.im(weight) == 0
    assert mp.re(weight) > 0


def test_replay_weight_handles_direct_factors() -> None:
    example = {
        "factors": [
            [[0.0, 2.0], [0.5, 0.0]],
            [[0.0, 0.25], [4.0, 0.0]],
        ]
    }

    weight = replay_weight(example, dps=50)

    expected = mp.det(
        mp.eye(2)
        + mp.matrix(example["factors"][0]) * mp.matrix(example["factors"][1])
    )
    assert mp.almosteq(weight, expected)


def test_replay_weight_rejects_too_little_precision() -> None:
    with pytest.raises(ValueError, match="at least 30"):
        replay_weight({"generators": [[[0.0]]]}, dps=20)
