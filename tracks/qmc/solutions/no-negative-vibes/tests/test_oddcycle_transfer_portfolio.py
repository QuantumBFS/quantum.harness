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
