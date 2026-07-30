import math

import numpy as np

from oracle.oddcycle_transfer_portfolio import rank_transfer_portfolio
from oracle.oddcycle_word_operator import build_word_dictionary


def test_transfer_portfolio_is_spd_interacting_and_deterministic():
    columns = build_word_dictionary(max_length=1)
    first = rank_transfer_portfolio(columns, seed=20260730, sample_count=4)
    second = rank_transfer_portfolio(columns, seed=20260730, sample_count=4)
    assert first == second
    assert len(first) == 4
    for record in first:
        assert record.exact_minimum_row_margin > 0
        assert record.minimum_eigenvalue > 0
        assert record.interaction_norm > 0
        assert record.source_words


def test_nonfinite_transfer_spectrum_has_deterministic_empty_diagnostics(
    monkeypatch,
):
    def nonfinite_eigh(matrix):
        dimension = matrix.shape[0]
        return np.full(dimension, np.nan), np.eye(dimension)

    monkeypatch.setattr(
        "oracle.oddcycle_transfer_portfolio.np.linalg.eigh",
        nonfinite_eigh,
    )
    columns = build_word_dictionary(max_length=1)

    first = rank_transfer_portfolio(columns, seed=20260730, sample_count=1)
    second = rank_transfer_portfolio(columns, seed=20260730, sample_count=1)

    assert first == second
    record = first[0]
    assert record.status == "numerical-log-inconclusive"
    assert record.minimum_eigenvalue is None
    assert record.log_reconstruction_residual is None
    assert record.coordinate_reconstruction_residual is None
    assert record.interaction_norm is None
    assert record.gaussian_grade_distance is None
    assert record.body_order_norms == {}
    assert record.forbidden_support_norms == {}


def test_nonfinite_log_residual_is_not_retained(
    monkeypatch,
):
    real_eigh = np.linalg.eigh
    call_count = 0

    def nonfinite_second_eigh(matrix):
        nonlocal call_count
        call_count += 1
        if call_count % 2:
            return real_eigh(matrix)
        dimension = matrix.shape[0]
        return np.full(dimension, np.nan), np.eye(dimension)

    monkeypatch.setattr(
        "oracle.oddcycle_transfer_portfolio.np.linalg.eigh",
        nonfinite_second_eigh,
    )
    columns = build_word_dictionary(max_length=1)

    first = rank_transfer_portfolio(columns, seed=20260730, sample_count=1)
    second = rank_transfer_portfolio(columns, seed=20260730, sample_count=1)

    assert first == second
    record = first[0]
    assert record.status == "numerical-log-inconclusive"
    assert record.minimum_eigenvalue is not None
    assert math.isfinite(record.minimum_eigenvalue)
    assert record.log_reconstruction_residual is None
    assert record.coordinate_reconstruction_residual is None
    assert record.interaction_norm is None
    assert record.gaussian_grade_distance is None
