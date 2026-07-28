from fractions import Fraction

import pytest

from trottercert.refined_error import defect_tail_site_bound
from trottercert.rigorous_fourth import fourth_order_suzuki_interval_stages


def test_defect_tail_decreases_with_steps() -> None:
    stages, _ = fourth_order_suzuki_interval_stages(4, decimal_digits=8)
    assert defect_tail_site_bound(stages, 200) < defect_tail_site_bound(stages, 100)


@pytest.mark.slow
def test_refined_bound_crosses_global_twofold_target() -> None:
    from trottercert.refined_error import (
        build_refined_fourth_order_constants,
        evaluate_refined_fourth_order_bound,
    )

    constants = build_refined_fourth_order_constants()
    bound = evaluate_refined_fourth_order_bound(constants, 144, 136)
    previous = evaluate_refined_fourth_order_bound(constants, 144, 135)
    assert bound.global_error_bound <= Fraction(1, 10**6)
    assert previous.global_error_bound > Fraction(1, 10**6)
