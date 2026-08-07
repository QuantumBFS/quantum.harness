import json

import pytest

from oracle.symmetric_oddcycle_discovery import screen_oddcycle_parameters


def test_fixed_point_passes_all_fast_exterior_gates():
    result = screen_oddcycle_parameters(1.0, 1.0, 1.0)

    assert result["status"] == "passed-all-gates"
    assert result["failure_stage"] is None
    assert result["parameters"] == {"p": 1.0, "q": 1.0, "r": 1.0}

    short = result["short_words"]
    assert short["max_depth"] == 10
    assert short["word_count"] == 2046
    assert short["minimum_determinant"] > 0.0
    assert len(short["witness"]) == short["witness_depth"]

    assert result["grade4_atom_gate"]["passed"] is True
    block = result["grade34_block"]
    assert block["length"] == 13
    assert block["word_count"] == 8192
    assert block["maximum_ratio"] < block["required_strict_upper_bound"]

    remainder = result["grade34_short_remainder"]
    assert remainder["max_depth"] == 12
    assert remainder["word_count"] == 8191
    assert remainder["maximum_ratio"] == pytest.approx(10.0)
    assert remainder["witness"] == ""

    tail = result["low_sector_norm_tail"]
    assert tail["passed"] is True
    assert tail["tail_start"] == 6
    assert tail["grade1_growth_ratio"] < 1.0
    assert tail["grade2_growth_ratio"] < 1.0
    assert tail["strict_margin_at_tail_start"] > 0.0
    assert json.loads(json.dumps(result))["status"] == "passed-all-gates"


def test_negative_winding_orientation_stops_at_grade4_atom_gate():
    result = screen_oddcycle_parameters(
        1.0,
        1.0,
        -1.0,
        short_depth=1,
    )

    assert result["short_words"]["passed"] is True
    assert result["status"] == "failed"
    assert result["failure_stage"] == "grade4-atom-nonnegative"
    assert result["grade4_atom_gate"]["minimum_entry"] < 0.0
    assert "grade34_block" not in result
    assert "low_sector_norm_tail" not in result
