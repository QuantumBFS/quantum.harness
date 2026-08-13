from __future__ import annotations

from fractions import Fraction

from oracle.exterior_seed61_top_product_tail import (
    BLOCK_LENGTH,
    audit_seed61_top_product_tail,
    top_factor_lower_bound,
)


def test_exact_five_block_top_product_ratio_is_strictly_contracting() -> None:
    result = audit_seed61_top_product_tail()

    assert result["block_length"] == BLOCK_LENGTH == 5
    assert result["upper_word"] == (1, 1, 0, 1, 0)
    assert result["lower_word"] == (0, 0, 0, 0, 1)
    assert result["block_ratio"] == Fraction(
        45809663718420017101544620032000,
        51474730402860830203560494083391,
    )
    assert result["block_ratio"] < 1


def test_exact_residues_prove_top_pair_product_exceeds_one_from_18() -> None:
    result = audit_seed61_top_product_tail()
    residues = result["residue_bounds"]

    assert [entry["blocks_required"] for entry in residues] == [1, 4, 4, 3, 1]
    assert [entry["first_certified_length"] for entry in residues] == [
        5,
        21,
        22,
        18,
        9,
    ]
    assert all(entry["strict"] for entry in residues)
    assert result["tail_length"] == 18
    assert result["stable_band_tail_length"] == 24
    assert result["nonnegative_trace_branch_tail_length"] == 24


def test_nonnegative_trace_branch_has_positive_top_factor() -> None:
    lower_bound = top_factor_lower_bound(
        trace_minus_perron=Fraction(0),
        top_pair_product=Fraction(1001, 1000),
        stable_radius=Fraction(999, 1000),
    )

    assert lower_bound == Fraction(3, 1000)
    assert lower_bound > 0
