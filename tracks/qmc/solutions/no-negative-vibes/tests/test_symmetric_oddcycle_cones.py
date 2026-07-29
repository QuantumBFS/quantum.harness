from pathlib import Path

from oracle.symmetric_oddcycle_cones import (
    exact_chi23_obstruction,
    exact_complementary_sector_audit,
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


def test_complementary_sector_identity_and_local_obstructions_replay_exactly():
    result = exact_complementary_sector_audit()

    assert result["determinant_per_letter"] == 8
    assert all(result["jacobi_checks"].values())
    assert [
        item["sum"] for item in result["negative_complementary_minor_pairs"]
    ] == [-1, -8, -8]
    assert result["mixed_word"] == {
        "word": "0001010101",
        "chi2": -1307360,
        "chi3": 5656076689,
        "determinant": 1073741824,
        "F": 6728511154,
    }
    assert result["pure_power_values"] == {
        7: {
            "chi2": 13875,
            "chi3": -171633,
            "determinant": 2097152,
            "F": 1939395,
        },
        10: {
            "chi2": 988330,
            "chi3": -192388191,
            "determinant": 1073741824,
            "F": 882341964,
        },
    }
