from scripts.audit_gap_3_4_5_7_completion import derive


def test_gap_3_4_5_7_scoped_statements_are_closed() -> None:
    result = derive()
    assert result["uses_target_trajectory"] is False
    assert result["uses_target_a_or_D"] is False
    assert result["gates"]["all_four_scoped_statements_closed"] is True
    assert result["statements"]["gap4"]["exact_recurrent_count"] == 13
    assert result["statements"]["gap5"][
        "physical_zero_field_quadratic_kubo_vertex"
    ] == 0.0
    assert result["statements"]["gap7"]["linear_mori_initial_slip"] == 0.0
