from oracle.oddcycle_path_metric import (
    EXACT_DENOMINATOR,
    exact_last_letter_path_metric_certificate,
)


def test_frozen_last_letter_path_metric_certificate_is_exact():
    result = exact_last_letter_path_metric_certificate()

    assert result["status"] == (
        "exact-positive-last-letter-path-metric-certificate"
    )
    assert result["state_count"] == 4
    assert result["transition_count"] == 16
    certificate = result["certificate"]
    assert certificate["denominator"] == EXACT_DENOMINATOR
    assert certificate["correct_split_inertia"] is True
    assert certificate["all_transition_gaps_positive_definite"] is True
    assert certificate["exact_arbitrary_word_contraction"] is True
    assert all(
        record["split_inertia_1_4"] for record in certificate["inertias"]
    )
    assert all(
        record["positive_definite_by_sylvester"]
        for record in certificate["transitions"]
    )
    orientation = result["time_orientation"]
    assert orientation["all_time_vectors_positive"] is True
    assert orientation["all_inverse_transitions_future_preserving"] is True
    assert orientation["atom_determinants"] == [8, 8, 8, 8]
    assert orientation["all_atom_determinants_positive"] is True
    assert result["exact_arbitrary_word_determinant_positive"] is True
