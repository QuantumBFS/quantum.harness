from __future__ import annotations

from oracle.exterior_seed61_counterexample import (
    audit_seed61_exact_counterexample,
)
from oracle.exterior_seed61_spectral_tail import (
    audit_seed61_stable_band_tail,
)


def test_seed61_length150_word_has_exact_negative_determinant() -> None:
    result = audit_seed61_exact_counterexample()

    assert result["word"]["length"] == 150
    assert result["word"]["sha256"] == (
        "e36ea7ebf0c2038acc3f2a2e0cc97c5fed4a497c8fc9aafa12b61fb24ff4d072"
    )
    assert result["determinant"]["sign"] == -1
    assert result["determinant"]["numerator_digits"] == 2223
    assert result["determinant"]["numerator_sha256"] == (
        "3ac8e5c102e147edfda33c646a43b1bef3118977f234f7c6a61996e056d69bfe"
    )
    assert result["determinant"]["denominator"] == 768 ** (5 * 150)


def test_seed61_counterexample_is_inside_the_exact_stable_band_tail() -> None:
    result = audit_seed61_exact_counterexample()
    stable_tail = audit_seed61_stable_band_tail()

    assert stable_tail["tail_length"] == 24
    assert result["word"]["length"] >= stable_tail["tail_length"]
    assert stable_tail["block_ratio"] < 1
    assert result["interpretation"]["stable_pair_factor_positive"] is True
    assert result["interpretation"]["top_pair_factor_negative"] is True
