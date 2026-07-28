import numpy as np
import pytest

import long_range_percolation as lrp
from long_range_percolation.sample import GraphSample
from long_range_percolation.union_find import UnionFind


def test_union_find_returns_deterministic_labels_and_sizes():
    union_find = UnionFind(6)
    for left, right in [(4, 5), (1, 2), (0, 2), (3, 5)]:
        union_find.union(left, right)
    np.testing.assert_array_equal(union_find.labels(), [0, 0, 0, 3, 3, 3])
    np.testing.assert_array_equal(union_find.component_sizes(), [3, 3])


def test_union_find_equal_size_tie_breaking_uses_smaller_root():
    union_find = UnionFind(4)
    for left, right in [(0, 1), (2, 3), (0, 2)]:
        union_find.union(left, right)
    np.testing.assert_array_equal(union_find.labels(), [0, 0, 0, 0])


def test_graph_sample_rejects_duplicate_or_noncanonical_edges():
    labels = np.arange(4)
    with pytest.raises(ValueError, match="canonical"):
        GraphSample(4, np.array([[2, 1]]), labels)
    with pytest.raises(ValueError, match="duplicate"):
        GraphSample(4, np.array([[0, 1], [0, 1]]), labels)


def test_graph_sample_rejects_non_integer_array_dtypes():
    labels = np.arange(4, dtype=np.int64)
    with pytest.raises(ValueError, match="integer dtype"):
        GraphSample(4, np.array([[0.5, 1.0]]), labels)
    with pytest.raises(ValueError, match="integer dtype"):
        GraphSample(
            4,
            np.array([[0, 1]], dtype=np.int64),
            np.array([True, False, True, False], dtype=np.bool_),
        )
    with pytest.raises(ValueError, match="integer dtype"):
        GraphSample(
            4,
            np.array([[0, 1]], dtype=np.int64),
            np.array([0, 1, 2, 3], dtype=object),
        )
    with pytest.raises(ValueError, match="integer dtype"):
        GraphSample(4, np.array([[0, 1]], dtype=np.complex128), labels)
    unsafe = np.array([np.iinfo(np.int64).max + 1], dtype=np.uint64)
    with pytest.raises(ValueError, match="int64"):
        GraphSample(4, np.array([[0, 1]], dtype=np.int64), unsafe.repeat(4))


def test_graph_sample_defensive_copy_isolates_caller_mutation():
    edges_in = np.array([[0, 1], [2, 3]], dtype=np.int64)
    labels_in = np.array([0, 0, 2, 2], dtype=np.int64)
    sample = GraphSample(4, edges_in, labels_in)
    edges_in[0, 0] = 99
    labels_in[0] = 99
    np.testing.assert_array_equal(sample.edges, [[0, 1], [2, 3]])
    np.testing.assert_array_equal(sample.labels, [0, 0, 2, 2])


def test_graph_sample_stored_arrays_are_read_only():
    sample = GraphSample(
        4,
        np.array([[0, 1], [2, 3]], dtype=np.int64),
        np.array([0, 0, 2, 2], dtype=np.int64),
    )
    assert sample.edges.flags.writeable is False
    assert sample.labels.flags.writeable is False
    with pytest.raises(ValueError):
        sample.edges[0, 0] = 1
    with pytest.raises(ValueError):
        sample.labels[0] = 1


def test_graph_sample_accepts_empty_edge_array():
    sample = GraphSample(
        3,
        np.empty((0, 2), dtype=np.int64),
        np.array([0, 1, 2], dtype=np.int64),
    )
    assert sample.edges.shape == (0, 2)
    assert sample.edges.dtype == np.int64
    np.testing.assert_array_equal(sample.labels, [0, 1, 2])


def test_graph_sample_rejects_label_partition_mismatch():
    with pytest.raises(ValueError, match="edge-induced partition"):
        GraphSample(
            4,
            np.array([[0, 1], [2, 3]], dtype=np.int64),
            np.array([0, 0, 0, 0], dtype=np.int64),
        )


def test_graph_sample_rejects_out_of_range_endpoints():
    labels = np.arange(4, dtype=np.int64)
    with pytest.raises(ValueError, match="out of range"):
        GraphSample(4, np.array([[-1, 1]], dtype=np.int64), labels)
    with pytest.raises(ValueError, match="out of range"):
        GraphSample(4, np.array([[0, 4]], dtype=np.int64), labels)


def test_graph_sample_rejects_unsorted_canonical_edges():
    labels = np.arange(4, dtype=np.int64)
    with pytest.raises(ValueError, match="sorted"):
        GraphSample(4, np.array([[2, 3], [0, 1]], dtype=np.int64), labels)


def test_package_root_exports_union_find_and_graph_sample():
    assert lrp.UnionFind is UnionFind
    assert lrp.GraphSample is GraphSample
    assert "UnionFind" in lrp.__all__
    assert "GraphSample" in lrp.__all__
