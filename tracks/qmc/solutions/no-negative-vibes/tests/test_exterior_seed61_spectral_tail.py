from __future__ import annotations

from fractions import Fraction

from oracle.exterior_seed61_spectral_tail import (
    BLOCK_LENGTH,
    audit_seed61_stable_band_tail,
)


def test_exact_ten_block_weighted_ratio_is_strictly_contracting() -> None:
    result = audit_seed61_stable_band_tail()

    assert result["block_length"] == BLOCK_LENGTH == 10
    assert result["upper_word"] == (1, 0, 1, 0, 1, 1, 0, 1, 1, 1)
    assert result["lower_word"] == (0,) * 10
    assert result["block_ratio"] == Fraction(
        140069234893420513349411826255996828139180583377937872380734577296116865537995,
        200200542368656762406096089328573547753146738147263530057688153284699104477184,
    )
    assert result["block_ratio"] < 1
    assert result["one_particle_strict_depth"] == 4
    assert result["grade3_strict_depth"] == 3


def test_exact_residue_bounds_cover_every_length_from_twenty_four() -> None:
    result = audit_seed61_stable_band_tail()
    residues = result["residue_bounds"]

    assert [entry["blocks_required"] for entry in residues] == [
        1,
        2,
        2,
        2,
        2,
        1,
        1,
        1,
        1,
        1,
    ]
    assert [entry["first_certified_length"] for entry in residues] == [
        10,
        21,
        22,
        23,
        24,
        15,
        16,
        17,
        18,
        19,
    ]
    assert all(entry["strict"] for entry in residues)
    assert result["tail_length"] == 24
