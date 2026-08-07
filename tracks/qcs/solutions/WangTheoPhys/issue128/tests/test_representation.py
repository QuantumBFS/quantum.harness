import pytest

from trottercert.representation import degree_three_four_matching_rank


@pytest.mark.slow
def test_degree_three_representation_has_full_free_lie_rank() -> None:
    rank, columns, rows = degree_three_four_matching_rank(4)
    assert rank == 20
    assert columns == 64
    assert rows == 4128
