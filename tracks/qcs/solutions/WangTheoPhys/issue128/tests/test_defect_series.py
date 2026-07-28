from trottercert.defect_series import right_generator_local_series
from trottercert.higher_order import fourth_order_suzuki_stages


def test_suzuki_right_generator_vanishes_through_degree_three() -> None:
    series = right_generator_local_series(fourth_order_suzuki_stages(4), 4)
    for degree in (1, 2, 3):
        assert sum(abs(value) for value in series[degree].values()) < 1e-9
    assert sum(abs(value) for value in series[4].values()) > 0
