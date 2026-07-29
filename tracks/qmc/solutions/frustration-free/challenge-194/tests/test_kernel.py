from decimal import Decimal, localcontext
import math

import numpy as np
import pytest
from scipy.special import zeta

from long_range_percolation.kernel import (
    edge_probabilities,
    kernel_weight_sum,
    periodic_kernel,
    periodic_kernel_reference,
)
from long_range_percolation.model import ModelSpec, distance_classes


def test_sigma_one_kernel_matches_cosecant_identity():
    for length in (4, 6, 32, 256):
        distances = np.arange(1, length // 2 + 1, dtype=np.float64)
        expected = (np.pi / length) ** 2 / np.sin(np.pi * distances / length) ** 2
        np.testing.assert_allclose(
            periodic_kernel(length, 1.0),
            expected,
            rtol=2e-14,
            atol=2e-14,
        )


def test_hurwitz_kernel_is_enclosed_by_direct_image_sum():
    values = periodic_kernel(12, 0.8)
    partial, bound = periodic_kernel_reference(12, 0.8, images=100_000)
    assert np.all(np.abs(values - partial) <= bound)


def test_reference_error_and_bound_shrink_with_more_images():
    values = periodic_kernel(12, 0.8)
    coarse, coarse_bound = periodic_kernel_reference(12, 0.8, images=100)
    fine, fine_bound = periodic_kernel_reference(12, 0.8, images=200)
    assert np.all(np.abs(values - fine) < np.abs(values - coarse))
    assert np.all(fine_bound < coarse_bound)


def test_global_kernel_sum_identity():
    for length, sigma in [(4, 0.8), (12, 1.0), (32, 1.1)]:
        values = periodic_kernel(length, sigma)
        measured = sum(
            item.multiplicity * values[item.distance - 1]
            for item in distance_classes(length)
        )
        expected = length * zeta(1.0 + sigma, 1.0) * (
            1.0 - length ** (-(1.0 + sigma))
        )
        assert measured == pytest.approx(expected, rel=2e-13)


def test_kernel_weight_sum_matches_periodic_kernel_table():
    for length, sigma in [(4, 0.8), (12, 1.0), (32, 1.1)]:
        values = periodic_kernel(length, sigma)
        measured = sum(
            item.multiplicity * values[item.distance - 1]
            for item in distance_classes(length)
        )
        assert kernel_weight_sum(length, sigma) == pytest.approx(measured, rel=2e-13)


def test_periodic_kernel_uses_full_periodic_image_convention():
    length = 12
    sigma = 0.8
    distance = 3
    exponent = 1.0 + sigma
    value = periodic_kernel(length, sigma)[distance - 1]
    bare_minimum_image = distance ** (-exponent)
    hurwitz_value = length ** (-exponent) * (
        zeta(exponent, distance / length) + zeta(exponent, 1.0 - distance / length)
    )
    assert value == pytest.approx(hurwitz_value, rel=2e-13)
    assert value > bare_minimum_image


def test_rearranged_kernel_matches_old_hurwitz_form_in_stable_regime():
    length = 64
    sigma = 0.9
    exponent = 1.0 + sigma
    distances = np.arange(1, length // 2 + 1, dtype=np.float64)
    fractions = distances / length
    old_form = length ** (-exponent) * (
        zeta(exponent, fractions) + zeta(exponent, 1.0 - fractions)
    )
    np.testing.assert_allclose(
        periodic_kernel(length, sigma),
        old_form,
        rtol=3e-15,
        atol=0.0,
    )


def test_high_sigma_kernel_matches_high_precision_direct_images():
    length = 256
    sigma = 128.0
    exponent = 129
    values = periodic_kernel(length, sigma)
    assert np.all(np.isfinite(values))
    assert np.all(values > 0.0)

    with localcontext() as context:
        context.prec = 120
        for distance in (1, 2, 64, 128):
            expected = sum(
                Decimal(abs(distance + image * length)) ** (-exponent)
                for image in range(-16, 17)
            )
            observed = float(values[distance - 1])
            assert math.isclose(
                observed,
                float(expected),
                rel_tol=4e-15,
                abs_tol=0.0,
            )


def test_kernel_rejects_positive_entries_below_float64_representability():
    with pytest.raises(ValueError, match="representability"):
        periodic_kernel(256, 1024.0)


def test_edge_probabilities_use_stable_exponential_form():
    spec = ModelSpec(length=4, sigma=1.0, kappa=1e-16)
    probability = edge_probabilities(spec, periodic_kernel(4, 1.0))[0]
    assert probability > 0.0
    assert probability == pytest.approx(
        spec.kappa * periodic_kernel(4, 1.0)[0],
        rel=1e-15,
    )
