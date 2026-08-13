from oracle.symmetric_oddcycle_interval_family import (
    exact_interval_family_theorem,
)


def test_continuum_alphabet_has_an_exact_independent_letter_certificate():
    result = exact_interval_family_theorem()

    assert result["status"] == "exact-continuum-alphabet-certificate"
    assert result["parameter_interval"] == {
        "lower": {"numerator": 99, "denominator": 100},
        "upper": {"numerator": 101, "denominator": 100},
        "closed": True,
    }
    assert result["parameter_choices"] == "independent-per-letter"
    assert result["conclusion"] == (
        "det(I+W)>0 for every finite word over the continuum alphabet"
    )

    finite = result["finite_depth"]
    assert finite["status"] == "exact-independent-letter-finite-certificate"
    assert finite["max_depth"] == 12
    assert finite["word_count"] == 8190
    assert finite["global_full_lower_bound"] == {
        "numerator": 3499,
        "denominator": 100,
    }
    assert finite["global_full_witness"] == "0"
    assert finite["global_complementary_lower_bound"] == {
        "numerator": 1699,
        "denominator": 100,
    }

    block = result["grade34_tail"]
    assert block["status"] == (
        "exact-independent-letter-block-tail-certificate"
    )
    assert block["grade4_atoms_interval_nonnegative"] is True
    assert block["common_loop_weight"] == 8
    assert block["block_length"] == 13
    assert block["block_word_count"] == 8192
    assert block["block_witness"] == "0000001111111"
    assert block["block_minimum_raw_margin"] == int(
        "17885432888260091992976094678617191678771759066816123079705733862324608427900"
    )
    assert block["block_scale_denominator"] == 100**26
    assert block["short_remainder_word_count"] == 8191
    assert block["short_remainder_minimum_margin"] == {
        "empty_remainder": {"numerator": 0, "denominator": 1},
        "minimum_nonempty": {"numerator": 3502563, "denominator": 10000},
        "minimum_nonempty_depth": 1,
        "minimum_nonempty_witness": "0",
    }

    low = result["low_sector_tail"]
    assert low["status"] == "exact-uniform-low-sector-certificate"
    assert low["tail_start"] == 6
    assert low["strict_integer_margin_at_six"] == 17174
    assert low["norm_gates"][0]["leading_minor_lower_bounds"] == (
        {"numerator": 2, "denominator": 1},
        {"numerator": 4, "denominator": 1},
        {"numerator": 9799, "denominator": 2500},
        {"numerator": 9799, "denominator": 1250},
        {"numerator": 48191, "denominator": 2500},
    )
    assert all(
        bound["numerator"] > 0
        for gate in low["norm_gates"]
        for bound in gate["leading_minor_lower_bounds"]
    )

    assert result["real_logarithm_gate"] == {
        "determinant": 8,
        "negative_axis_polynomial": (
            "-x^5-2*x^4-x^3+(z-8)*x^2-16*x-8"
        ),
        "all_coefficients_strictly_negative_for_x_positive": True,
        "conclusion": "B(z) has no negative real eigenvalue",
    }
