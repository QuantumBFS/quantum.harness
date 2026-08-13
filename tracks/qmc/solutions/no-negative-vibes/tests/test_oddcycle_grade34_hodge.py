from oracle.oddcycle_grade34_hodge import (
    exact_symbolic_hodge_identity,
    exact_word_grade34_reduction,
    joint_hodge_margin_profile,
    joint_low_sector_pair_profile,
    joint_positive_compound_trace_profile,
)


def test_symbolic_hodge_identity_reduces_grade_three_to_positive_grade_four():
    result = exact_symbolic_hodge_identity()

    assert result["status"] == "exact-symbolic-hodge-identity"
    assert result["forward_identity"] is True
    assert result["transpose_identity"] is True
    assert result["grade4_atom_entrywise_nonnegative_for_p_positive"] is True


def test_word_level_grade34_scalar_reduction_is_exact():
    result = exact_word_grade34_reduction()

    assert result["status"] == "exact-word-grade34-reduction"
    assert result["hodge_matrix_identity"] is True
    assert result["scalar_identity"] is True


def test_joint_hodge_profile_enumerates_every_short_word():
    result = joint_hodge_margin_profile(
        [(0.0, 1.0, 1.0), (0.8, 1.0, 1.0)],
        max_depth=3,
    )

    assert result["status"] == "complete"
    assert [record["word_count"] for record in result["per_depth"]] == [
        4,
        16,
        64,
    ]
    assert all(
        record["minimum_relative_margin"] > 0.0
        for record in result["per_depth"]
    )


def test_positive_compound_trace_profile_counts_short_words():
    result = joint_positive_compound_trace_profile(
        [(0.0, 1.0, 1.0)],
        compound_grade=3,
        max_depth=3,
    )

    assert result["status"] == "complete"
    assert [record["word_count"] for record in result["per_depth"]] == [
        2,
        4,
        8,
    ]


def test_low_sector_pair_profile_counts_short_words():
    result = joint_low_sector_pair_profile(
        [(0.0, 1.0, 1.0)],
        max_depth=3,
    )

    assert result["status"] == "complete"
    assert [record["word_count"] for record in result["per_depth"]] == [
        2,
        4,
        8,
    ]
