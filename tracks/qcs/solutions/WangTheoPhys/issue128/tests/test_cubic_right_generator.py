from __future__ import annotations

import pytest

from trottercert.cubic_field import fourth_order_suzuki_cubic_stages
from trottercert.cubic_local import exact_right_generator_stage_contribution
from trottercert.hpc_artifacts import coordinate_encode_series, merge_coordinate_series


@pytest.mark.slow
def test_stage_contributions_reconstruct_fourth_order_conditions() -> None:
    stages = fourth_order_suzuki_cubic_stages()
    shards = [
        coordinate_encode_series(
            *exact_right_generator_stage_contribution(stages, index, 4)
        )
        for index in range(len(stages))
    ]
    series = merge_coordinate_series(shards)
    assert not series[1]
    assert not series[2]
    assert not series[3]
    assert series[4]


def test_stage_contribution_rejects_invalid_index_and_order() -> None:
    stages = fourth_order_suzuki_cubic_stages()
    with pytest.raises(IndexError, match="stage index"):
        exact_right_generator_stage_contribution(stages, len(stages), 4)
    with pytest.raises(ValueError, match="nonnegative"):
        exact_right_generator_stage_contribution(stages, 0, -1)
