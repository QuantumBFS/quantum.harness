from oracle.oddcycle_metric_dual import exact_no_common_metric_certificate


def test_exact_dual_excludes_a_common_strict_metric_for_the_leading_pair():
    result = exact_no_common_metric_certificate()

    assert (
        result["status"]
        == "exact-no-common-quadratic-metric-certificate"
    )
    assert result["points"] == [
        {"p": "1/1000", "q": "1", "r": "1"},
        {"p": "4/5", "q": "1", "r": "1"},
    ]
    assert result["cancellation_exact_zero"] is True
    assert result["all_multipliers_positive_definite"] is True
    assert result["normalization_trace"] == {
        "numerator": 1,
        "denominator": 1,
    }
    assert all(
        minor > 0
        for record in result["leading_principal_minor_numerators"]
        for minor in record
    )
