from pathlib import Path

from oracle.symmetric_oddcycle_cones import (
    exact_chi23_obstruction,
    exact_grade4_formula_replay,
    load_certificate,
    verify_compact_certificate,
)
from oracle.exterior_seed61_short_words import scan_shard


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_symbolic_grade4_positive_cone_and_chi23_obstruction():
    assert exact_grade4_formula_replay()
    assert exact_chi23_obstruction() == {
        "chi2": 13875,
        "chi3": -171633,
        "sum": -157758,
    }


def test_fixed_candidate_compact_cones_replay_exactly():
    expected = {
        "symmetric_oddcycle_grade14_certificate.json": ((1, 4), 10),
        "symmetric_oddcycle_grade24_certificate.json": ((2, 4), 15),
    }
    for name, (grades, dimension) in expected.items():
        result = verify_compact_certificate(load_certificate(FIXTURES / name))
        assert result["status"] == "exact-certificate"
        assert result["grades"] == grades
        assert result["dimension"] == dimension
        assert result["minimum_entry"] >= 0
        assert result["trace_compatible"] is True


def test_fixed_candidate_uses_existing_exact_short_word_oracle():
    result = scan_shard(
        max_depth=4,
        target="symmetric-oddcycle-fixed:0",
    )

    assert result["target"] == "symmetric-oddcycle-fixed:0"
    assert result["dimension"] == 5
    assert result["integer_atom_scale"] == 1
    assert result["status"] == "strictly-positive"
    assert sum(entry["global_word_count"] for entry in result["per_length"]) == 30
