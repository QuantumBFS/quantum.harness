import mpmath as mp

from trottercert.higher_order import (
    fourth_order_suzuki_stages,
    _second_order_scalar_stages,
)
from trottercert.lie_series import abstract_formula_log_series


def _degree_l1(series, degree: int) -> mp.mpf:
    return sum(abs(value) for value in series[degree].values())


def test_abstract_strang_has_zero_degree_two() -> None:
    stages = _second_order_scalar_stages(4, mp.mpf(1))
    logarithm = abstract_formula_log_series(stages, 3)
    assert _degree_l1(logarithm, 2) < mp.mpf("1e-60")
    assert _degree_l1(logarithm, 3) > 0


def test_abstract_suzuki_is_fourth_order() -> None:
    logarithm = abstract_formula_log_series(fourth_order_suzuki_stages(4), 5)
    for degree in (2, 3, 4):
        assert _degree_l1(logarithm, degree) < mp.mpf("1e-60")
    assert _degree_l1(logarithm, 5) > 0
