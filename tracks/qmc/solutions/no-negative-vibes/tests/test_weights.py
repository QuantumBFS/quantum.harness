from __future__ import annotations

import numpy as np

from oracle.weights import classify_product, product_exponentials


def test_classify_product_matches_hand_checked_o11_controls() -> None:
    """Catches a reversed sign convention or a zero classified as positive."""
    cases = [
        (
            np.array([[5.0 / 3.0, 4.0 / 3.0], [4.0 / 3.0, 5.0 / 3.0]]),
            "positive",
            16.0 / 3.0,
        ),
        (
            np.array([[-5.0 / 3.0, -4.0 / 3.0], [-4.0 / 3.0, -5.0 / 3.0]]),
            "negative",
            -4.0 / 3.0,
        ),
        (np.diag([1.0, -1.0]), "zero", 0.0),
    ]

    for product, expected_classification, expected_weight in cases:
        result = classify_product(product)
        assert result.classification == expected_classification
        assert np.isclose(result.value, expected_weight, atol=1e-12)


def test_product_exponentials_preserves_declared_factor_order() -> None:
    """Catches reversing the imaginary-time product order."""
    generators = [
        np.array([[0.0, -3.0], [0.0, 0.0]]),
        np.array([[0.0, 0.0], [1.0, 0.0]]),
        np.array([[0.0, -1.5], [0.0, 0.0]]),
        np.array([[0.0, 0.0], [2.0, 0.0]]),
    ]

    product = product_exponentials(generators)

    assert np.allclose(product, np.diag([-2.0, -0.5]), atol=1e-12)
    assert classify_product(product).classification == "negative"


def test_roundoff_compatible_phase_is_not_reported_as_complex() -> None:
    """Catches a fixed phase cutoff that ignores condition-number amplification."""
    shifted = np.diag([1.0e-4 + 1.0e-13j, 1.0e4])
    product = shifted - np.eye(2)

    result = classify_product(product)

    assert 1.0e7 < result.condition_number < 1.0e9
    assert result.classification == "positive"


def test_large_log_determinant_classifies_without_scalar_overflow() -> None:
    """Catches reconstructing a huge determinant even though slogdet stayed finite."""
    product = np.diag([1.0e200, 1.0e200])

    result = classify_product(product)

    assert result.classification == "positive"
    assert result.log_abs > 700.0
    assert np.isinf(result.value.real)
