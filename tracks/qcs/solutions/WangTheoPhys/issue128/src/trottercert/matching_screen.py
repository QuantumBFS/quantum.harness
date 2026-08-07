from __future__ import annotations

from itertools import permutations

from .defect_series import right_generator_local_series
from .higher_order import ScalarStage, fourth_order_suzuki_stages


MATCHING_ORDERS = tuple(permutations(range(4)))


def permutation_from_index(index: int) -> tuple[int, int, int, int]:
    if index < 0 or index >= len(MATCHING_ORDERS):
        raise IndexError("permutation index must be in [0, 23]")
    return MATCHING_ORDERS[index]


def screen_matching_order(index: int, order: int = 6) -> dict[str, object]:
    if order < 4:
        raise ValueError("screening order must be at least four")
    permutation = permutation_from_index(index)
    stages = tuple(
        ScalarStage(permutation[stage.fragment_index], stage.coefficient)
        for stage in fourth_order_suzuki_stages(4)
    )
    series = right_generator_local_series(stages, order)
    metrics = {
        str(degree): {
            "term_count": len(series[degree]),
            "coefficient_l1": float(
                sum(abs(value) for value in series[degree].values())
            ),
        }
        for degree in range(4, order + 1)
    }
    return {
        "schema_version": 1,
        "kind": "issue128_matching_order_screen",
        "trusted": False,
        "purpose": "discovery-ranking",
        "permutation_index": index,
        "permutation": list(permutation),
        "order": order,
        "metrics": metrics,
    }
