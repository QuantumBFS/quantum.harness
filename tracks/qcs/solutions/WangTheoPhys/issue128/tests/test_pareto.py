from fractions import Fraction

from trottercert.pareto import (
    minimum_published_suzuki_point,
    recursive_suzuki_interval_stages,
)


def test_recursive_suzuki_stage_counts() -> None:
    assert len(recursive_suzuki_interval_stages(2, decimal_digits=8)) == 7
    assert len(recursive_suzuki_interval_stages(4, decimal_digits=8)) == 31
    assert len(recursive_suzuki_interval_stages(6, decimal_digits=8)) == 151
    assert len(recursive_suzuki_interval_stages(8, decimal_digits=8)) == 751


def test_small_published_pareto_search_is_minimal() -> None:
    point = minimum_published_suzuki_point(
        4,
        n_sites=4,
        tolerance=Fraction(1, 100),
        decimal_digits=8,
    )
    assert point.global_error_bound <= Fraction(1, 100)
