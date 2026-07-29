from __future__ import annotations

from fractions import Fraction
from itertools import product

from oracle.exterior_candidates import candidate_card, exact_atoms_from_card
from oracle.exterior_seed61_positive_realization import exact_determinant_weight
from oracle.exterior_seed61_short_words import (
    canonical_word,
    canonical_words,
    collect_shards,
    scan_shard,
    symmetry_orbit,
)


def test_twisted_bracelets_partition_all_binary_words() -> None:
    for length in range(1, 8):
        representatives = tuple(canonical_words(length))
        assert representatives == tuple(sorted(representatives))
        assert len(set(representatives)) == len(representatives)
        assert sum(len(symmetry_orbit(word)) for word in representatives) == 2**length
        assert {
            member
            for representative in representatives
            for member in symmetry_orbit(representative)
        } == set(product((0, 1), repeat=length))
        assert all(canonical_word(word) == word for word in representatives)


def test_sharded_exact_scan_matches_naive_seed61_minimum() -> None:
    manifests = [
        scan_shard(max_depth=7, shard_id=shard, shard_count=3)
        for shard in range(3)
    ]
    result = collect_shards(manifests)

    atoms = exact_atoms_from_card(
        candidate_card(template="exact5-shear-loop-pair", seed=61)
    )
    complement_counterexample = (0, 0, 1, 0, 1, 1)
    assert exact_determinant_weight(atoms, complement_counterexample) != (
        exact_determinant_weight(
            atoms,
            tuple(1 - symbol for symbol in complement_counterexample),
        )
    )
    naive = min(
        (
            exact_determinant_weight(atoms, word),
            word,
        )
        for length in range(1, 8)
        for word in product((0, 1), repeat=length)
    )

    assert result["status"] == "strictly-positive"
    assert result["covered_word_count"] == sum(2**length for length in range(1, 8))
    assert result["canonical_class_count"] == sum(
        len(tuple(canonical_words(length))) for length in range(1, 8)
    )
    assert Fraction(
        int(result["minimum_weight"]["numerator"]),
        int(result["minimum_weight"]["denominator"]),
    ) == naive[0]
    assert tuple(result["minimum_weight"]["word"]) in symmetry_orbit(naive[1])
