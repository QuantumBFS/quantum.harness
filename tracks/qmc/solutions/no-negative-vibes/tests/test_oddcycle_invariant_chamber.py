from oracle.oddcycle_invariant_chamber import exact_chamber_counterexample


def test_two_invariant_open_chamber_has_an_exact_negative_word():
    result = exact_chamber_counterexample()

    assert result == {
        "D": 10,
        "T": -9,
        "inside_open_chamber": True,
        "word": "00100110011",
        "determinant": -86709610990738,
    }
