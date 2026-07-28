from trottercert.resources import fourth_order_four_matching_resources


def test_fourth_order_boundary_merging() -> None:
    estimate = fourth_order_four_matching_resources(144, 59)
    assert estimate.group_exponentials == 1771
    assert estimate.local_propagators == 127512
    assert estimate.cnot_upper == 382536
