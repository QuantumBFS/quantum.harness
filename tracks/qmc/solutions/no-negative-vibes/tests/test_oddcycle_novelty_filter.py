from oracle.oddcycle_novelty_filter import exact_oddcycle_novelty_filter


def test_oddcycle_minimal_novelty_filter_replays_exactly():
    result = exact_oddcycle_novelty_filter()

    assert result["dimension"] == 5
    assert result["determinant"] == 8
    assert result["characteristic_coefficients"] == (1, -2, 1, -7, 16, -8)
    assert result["positive_real_root_count"] == 1
    assert result["negative_real_root_count"] == 0
    assert result["square_free_characteristic"] is True
    assert result["one_letter_weight"] == 35
    assert result["one_letter_weight_is_integer_square"] is False

    split = result["split_orthogonal"]
    assert split["status"] == "excluded-exactly"
    assert split["orthogonal_determinant_square"] == 64
    assert split["common_bilinear_invariant_nullity"] == 0

    kramers = result["standard_kramers"]
    assert kramers["status"].startswith("excluded-exactly")
    assert kramers["odd_dimension"] is True
    assert kramers["common_commutant_nullity"] == 1

    reductions = result["obvious_similarity_reductions"]
    assert reductions["generated_algebra_rank"] == 25
    assert reductions["full_matrix_algebra_dimension"] == 25
    assert reductions["witness_word_count"] == 25
    assert reductions["maximum_witness_length"] == 5
    assert reductions["negative_directed_cycle_product"] == -1

    assert (
        result["broader_semigroup_majorana"]["status"]
        == "not-excluded-by-this-minimal-filter"
    )
