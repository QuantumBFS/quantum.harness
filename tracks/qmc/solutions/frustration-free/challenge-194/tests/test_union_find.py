import numpy as np
import pytest

from long_range_percolation.sample import GraphSample
from long_range_percolation.union_find import UnionFind


def test_union_find_returns_deterministic_labels_and_sizes():
    union_find = UnionFind(6)
    for left, right in [(4, 5), (1, 2), (0, 2), (3, 5)]:
        union_find.union(left, right)
    np.testing.assert_array_equal(union_find.labels(), [0, 0, 0, 3, 3, 3])
    np.testing.assert_array_equal(union_find.component_sizes(), [3, 3])


def test_graph_sample_rejects_duplicate_or_noncanonical_edges():
    labels = np.arange(4)
    with pytest.raises(ValueError, match="canonical"):
        GraphSample(4, np.array([[2, 1]]), labels)
    with pytest.raises(ValueError, match="duplicate"):
        GraphSample(4, np.array([[0, 1], [0, 1]]), labels)
