import pytest

from long_range_percolation.model import (
    ModelSpec,
    canonical_edge,
    distance_classes,
    iter_unordered_edges,
)


def test_model_spec_rejects_non_even_or_nonphysical_parameters():
    for values in [
        {"length": 3, "sigma": 1.0, "kappa": 1.0},
        {"length": 2, "sigma": 0.0, "kappa": 1.0},
        {"length": 2, "sigma": 1.0, "kappa": -1.0},
        {"length": 2, "sigma": float("nan"), "kappa": 1.0},
        {"length": 2, "sigma": 1.0, "kappa": float("inf")},
    ]:
        with pytest.raises(ValueError):
            ModelSpec(**values)


def test_distance_classes_count_every_unordered_edge_once():
    for length in (2, 4, 6, 32):
        classes = distance_classes(length)
        assert sum(item.multiplicity for item in classes) == length * (length - 1) // 2
        assert classes[-1].distance == length // 2
        assert classes[-1].multiplicity == length // 2


def test_canonical_edges_match_direct_unordered_enumeration():
    length = 8
    from_classes = {
        canonical_edge(length, item.distance, offset)
        for item in distance_classes(length)
        for offset in range(item.multiplicity)
    }
    assert from_classes == set(iter_unordered_edges(length))
    assert len(from_classes) == length * (length - 1) // 2
