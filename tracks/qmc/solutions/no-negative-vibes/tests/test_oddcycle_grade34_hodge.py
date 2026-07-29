from oracle.oddcycle_grade34_hodge import (
    exact_symbolic_hodge_identity,
    exact_word_grade34_reduction,
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
