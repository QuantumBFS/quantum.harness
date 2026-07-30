from oracle.oddcycle_final_certificate import final_certificate_summary


def test_final_certificate_replays_every_exact_publication_gate():
    result = final_certificate_summary()

    assert result["status"] == "all-exact-gates-passed"
    assert result["candidate"]["dimension"] == 5
    assert result["candidate"]["points"] == [
        ["1/1000", "1", "1"],
        ["4/5", "1", "1"],
    ]
    assert result["gates"] == {
        "arbitrary_word_determinant_positive": True,
        "no_common_strict_quadratic_metric": True,
        "hermitian_interacting_positive_field_model": True,
        "outside_wei_majorana_sufficient_class": True,
    }
    assert result["majorana_wei"] == {
        "commutant_nullity": 1,
        "boundary_sign": 1,
        "wei_sign": -1,
    }
    assert len(result["exact_certificate_sha256"]) == 64
    assert result["discovery_evidence"][
        "exhaustive_words_through_depth_12"
    ] == 22_369_620
    assert result["physical"]["field_coefficients"] == (
        "37/41",
        "1/41",
        "1/41",
        "1/41",
        "1/41",
    )
