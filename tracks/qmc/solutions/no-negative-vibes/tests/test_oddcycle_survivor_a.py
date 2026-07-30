from dataclasses import replace
from pathlib import Path

import mpmath as mp
import pytest
import sympy as sp

import oracle.oddcycle_survivor_a as survivor_module
from oracle.oddcycle_survivor_a import (
    FrozenSourceSpec,
    analyze_hamiltonian,
    load_survivor_a,
    reconstruct_survivor_transfer,
)
from oracle.oddcycle_word_operator import transpose_word


SOURCE_RESULT = (
    Path(__file__).resolve().parents[1]
    / "protocols"
    / "oddcycle-local-hs-v1"
    / "result.json"
)


def frozen_source_spec() -> FrozenSourceSpec:
    return FrozenSourceSpec(
        result_sha256=(
            "12e8ac1e0dcb8b06130556b9ea91392e558521ca20d3b7aeb71413fa77b5d01c"
        ),
        source_cell_payload_sha256=(
            "b93465d16f4c9d796bac26104b035ae74f85c1e1e297cc94ff2cb8e4373e2c42"
        ),
        source_raw_file_sha256=(
            "c16d32355448d9bd89e282323fbaa64852a408edc8439404feb82ff5bc21cae7"
        ),
        source_cell_id="portfolio-l2",
        sample_index=122,
        sample_seed=20260730,
        exact_shift=sp.Rational(42),
        exact_vacuum_value=sp.Rational(44),
        exact_minimum_row_margin=sp.Rational(12213, 15625),
    )


def test_loader_binds_survivor_a_to_its_frozen_source(tmp_path: Path):
    """Catches accepting a wrong result or any mismatched frozen identity field."""

    expected = frozen_source_spec()
    seed = load_survivor_a(SOURCE_RESULT, expected=expected)

    assert seed.source_cell_id == "portfolio-l2"
    assert seed.sample_index == 122
    assert seed.shift == 42
    assert seed.vacuum_value == 44
    assert seed.minimum_row_margin == sp.Rational(12213, 15625)
    assert all(weight > 0 for weight in seed.weights)
    assert sum(seed.weights) == 1

    modified = tmp_path / "result.json"
    modified.write_bytes(
        SOURCE_RESULT.read_bytes().replace(
            b'"numerator": 11', b'"numerator": 12', 1
        )
    )
    with pytest.raises(ValueError, match="source result SHA-256 mismatch"):
        load_survivor_a(modified, expected=expected)

    mismatches = (
        {"result_sha256": "0" * 64},
        {"source_cell_payload_sha256": "0" * 64},
        {"source_raw_file_sha256": "0" * 64},
        {"source_cell_id": "portfolio-l1"},
        {"sample_index": 121},
        {"sample_seed": 20260731},
        {"exact_shift": sp.Rational(41)},
        {"exact_vacuum_value": sp.Rational(43)},
        {"exact_minimum_row_margin": sp.Rational(1)},
    )
    for changes in mismatches:
        with pytest.raises(ValueError):
            load_survivor_a(SOURCE_RESULT, expected=replace(expected, **changes))


def test_reconstruction_replays_the_exact_spd_transfer():
    """Catches a missing source ray, nontranspose pair, or inexact SPD replay."""

    seed = load_survivor_a(SOURCE_RESULT, expected=frozen_source_spec())
    transfer, columns, certificate = reconstruct_survivor_transfer(seed)

    assert len(columns) == 12
    assert transfer == transfer.T
    assert transfer[0, 0] == 44
    margin = min(
        transfer[row, row]
        - sum(
            abs(transfer[row, column])
            for column in range(transfer.cols)
            if column != row
        )
        for row in range(transfer.rows)
    )
    assert margin == sp.Rational(12213, 15625)
    assert certificate["strict_symmetric_diagonal_dominance"] is True
    assert certificate["positive_diagonal"] is True
    assert certificate["canonical_matrix_sha256"] == (
        "9e11beac34618b287ffcac062be6f756875c797fccd8e687ea223c8f194f6f96"
    )
    assert all(
        transpose == transpose_word(word)
        for word, transpose in zip(seed.words, seed.transpose_words, strict=True)
    )


def test_precision_ladder_reconstructs_normalized_transfer_as_decimal_strings():
    """Catches a low-precision logarithm or scientific analysis on Windows."""

    analysis = analyze_hamiltonian(
        sp.diag(1, 2, 3, 4),
        sp.Rational(1),
        decimal_places=(40, 60),
        machine_role="wsl",
    )

    assert analysis.decimal_places == (40, 60)
    assert len(analysis.coordinates) == 6
    assert len(analysis.exponential_residuals) == 2
    assert len(analysis.coordinate_deltas) == 1
    assert len(analysis.body_order_norms) == 3
    assert all(isinstance(value, str) for value in analysis.coordinates)
    assert all(isinstance(value, str) for value in analysis.exponential_residuals)
    assert all(isinstance(value, str) for value in analysis.coordinate_deltas)
    assert all(isinstance(value, str) for value in analysis.body_order_norms)
    assert abs(mp.mpf(analysis.coordinates[1]) + mp.log(2)) < mp.mpf("1e-35")
    assert abs(mp.mpf(analysis.coordinates[4]) + mp.log(3)) < mp.mpf("1e-35")
    assert abs(mp.mpf(analysis.coordinates[5]) - mp.log(mp.mpf(3) / 2)) < mp.mpf(
        "1e-35"
    )
    assert mp.mpf(analysis.exponential_residuals[-1]) < mp.mpf("1e-45")
    with pytest.raises(
        ValueError,
        match="scientific analysis requires machine_role wsl or cpu",
    ):
        analyze_hamiltonian(
            sp.diag(1, 2, 3, 4),
            sp.Rational(1),
            decimal_places=(40, 60),
            machine_role="windows",
        )


def test_precision_analysis_is_invariant_under_eigenvector_signs(monkeypatch):
    """Catches comparing eigensolver vectors instead of reconstructed matrices."""

    transfer = sp.diag(1, 2, 3, 4)
    baseline = analyze_hamiltonian(
        transfer,
        sp.Rational(1),
        decimal_places=(40, 60),
        machine_role="cpu",
    )
    real_eigsy = survivor_module.mp.eigsy

    def eigsy_with_flipped_columns(matrix):
        eigenvalues, eigenvectors = real_eigsy(matrix)
        flipped = mp.matrix(eigenvectors)
        for column in range(flipped.cols):
            if column % 2:
                for row in range(flipped.rows):
                    flipped[row, column] = -flipped[row, column]
        return eigenvalues, flipped

    monkeypatch.setattr(survivor_module.mp, "eigsy", eigsy_with_flipped_columns)
    sign_flipped = analyze_hamiltonian(
        transfer,
        sp.Rational(1),
        decimal_places=(40, 60),
        machine_role="cpu",
    )

    assert sign_flipped == baseline
