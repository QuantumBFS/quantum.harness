import importlib


def test_exact_nambu_reduction_excludes_full_wei_contraction():
    audit = importlib.import_module("oracle.oddcycle_majorana_wei_audit")

    result = audit.majorana_wei_no_go_summary()

    assert result["status"] == "exact-no-wei-contraction-certificate"
    assert result["alphabet"] == {
        "dimension": 5,
        "points": ("1/1000", "4/5"),
        "letter_count": 4,
        "determinant": 8,
    }
    assert result["dual"] == {
        "exact_cancellation": True,
        "normalization_trace": {"numerator": 1, "denominator": 1},
        "positive_definite_multipliers": 4,
        "nonstrict_gaps_forced_to_zero": True,
    }
    assert result["commutant"] == {
        "ambient_dimension": 25,
        "constraint_rank": 24,
        "nullity": 1,
        "scalar_only": True,
    }
    assert result["boundary"] == {
        "diagonal_blocks_zero": True,
        "off_diagonal_block": "k*I_5",
    }
    assert result["compatibility"] == {
        "wei_sign": -1,
        "boundary_sign": 1,
        "compatible": False,
    }
    assert len(result["exact_certificate_sha256"]) == 64
