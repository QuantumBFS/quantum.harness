import math

import pytest

from long_range_percolation.kernel import periodic_kernel

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


def test_model_spec_rejects_positive_sigma_when_one_plus_sigma_rounds_to_one():
    sigma = math.nextafter(0.0, 1.0)
    assert sigma > 0.0
    assert 1.0 + sigma == 1.0
    with pytest.raises(ValueError, match=r"1\.0 \+ sigma > 1\.0"):
        ModelSpec(length=4, sigma=sigma, kappa=0.0)


def test_model_spec_accepts_boundary_sigma_values_and_kernel_stays_finite():
    for sigma in (math.ulp(1.0), 0.8, 1.0, 1.1):
        spec = ModelSpec(length=12, sigma=sigma, kappa=0.5)
        assert spec.sigma == sigma
        assert math.isfinite(1.0 + sigma)
        kernel = periodic_kernel(spec.length, spec.sigma)
        assert kernel.shape == (spec.length // 2,)
        assert all(math.isfinite(float(value)) for value in kernel)


def test_distance_classes_count_every_unordered_edge_once():
    for length in (2, 4, 6, 32):
        classes = distance_classes(length)
        assert sum(item.multiplicity for item in classes) == length * (length - 1) // 2
        assert classes[-1].distance == length // 2
        assert classes[-1].multiplicity == length // 2


@pytest.mark.parametrize("length", [1, 3])
def test_distance_classes_rejects_small_or_odd_lengths(length: int):
    with pytest.raises(ValueError, match="length must be even and at least two"):
        distance_classes(length)


def test_canonical_edges_match_direct_unordered_enumeration():
    length = 8
    from_classes = {
        canonical_edge(length, item.distance, offset)
        for item in distance_classes(length)
        for offset in range(item.multiplicity)
    }
    assert from_classes == set(iter_unordered_edges(length))
    assert len(from_classes) == length * (length - 1) // 2


@pytest.mark.parametrize("length", [1, 3])
def test_canonical_edge_rejects_small_or_odd_lengths(length: int):
    with pytest.raises(ValueError, match="length must be even and at least two"):
        canonical_edge(length, 1, 0)


@pytest.mark.parametrize("distance", [0, 5])
def test_canonical_edge_rejects_out_of_range_distance(distance: int):
    with pytest.raises(ValueError, match="distance is outside the canonical range"):
        canonical_edge(8, distance, 0)


@pytest.mark.parametrize("offset", [-1, 8])
def test_canonical_edge_rejects_out_of_range_offset(offset: int):
    with pytest.raises(ValueError, match="offset is outside the distance class"):
        canonical_edge(8, 1, offset)


@pytest.mark.parametrize("offset", [False, 1.5])
def test_canonical_edge_rejects_bool_and_non_integer_offset(offset: object):
    with pytest.raises(ValueError, match="offset must be an integer"):
        canonical_edge(8, 1, offset)
