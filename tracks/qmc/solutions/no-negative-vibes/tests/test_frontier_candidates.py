from __future__ import annotations

from itertools import combinations

import numpy as np
import pytest
from scipy.linalg import expm

from oracle.frontier_candidates import (
    available_cases,
    mixed_split_boundary_counterexample,
    random_generator,
    structure_residual,
)
from oracle.weights import classify_product, product_exponentials


@pytest.mark.parametrize("case", sorted(available_cases()))
def test_frontier_generator_satisfies_declared_structure(case: str) -> None:
    generator = random_generator(
        case,
        np.random.default_rng(20260728),
        scale=1.3,
    )

    assert generator.shape == available_cases()[case].shape
    assert structure_residual(case, generator) < 1e-12


@pytest.mark.parametrize("case", ["tn_path4_sym", "tn_path4_asym"])
def test_path_exponential_is_totally_nonnegative(case: str) -> None:
    generator = random_generator(
        case,
        np.random.default_rng(17),
        scale=1.0,
    )
    evolution = expm(generator)
    size = evolution.shape[0]

    for order in range(1, size + 1):
        for rows in combinations(range(size), order):
            for columns in combinations(range(size), order):
                minor = np.linalg.det(evolution[np.ix_(rows, columns)])
                assert minor > -1e-11


@pytest.mark.parametrize(
    "case",
    ["tn_path4_sym", "tn_path4_asym", "tn_path6_sym", "tn_path6_asym"],
)
def test_path_product_has_nonnegative_principal_minors_and_weight(
    case: str,
) -> None:
    rng = np.random.default_rng(23)
    product = product_exponentials(
        [random_generator(case, rng, scale=0.7) for _ in range(5)]
    )
    size = product.shape[0]
    principal_minor_sum = 1.0

    for order in range(1, size + 1):
        for indices in combinations(range(size), order):
            minor = np.linalg.det(product[np.ix_(indices, indices)])
            assert minor > -2e-9
            principal_minor_sum += minor

    weight = np.linalg.det(np.eye(size) + product)
    assert np.isclose(weight, principal_minor_sum, rtol=2e-10, atol=2e-10)
    assert weight >= 1.0 - 2e-9


def test_block_upper_weight_factors_into_known_diagonal_weights() -> None:
    rng = np.random.default_rng(29)
    generators = [
        random_generator("block_upper_split11", rng, scale=0.8)
        for _ in range(6)
    ]
    full_product = product_exponentials(generators)
    first_product = product_exponentials(
        [generator[:2, :2] for generator in generators]
    )
    second_product = product_exponentials(
        [generator[2:, 2:] for generator in generators]
    )
    full_weight = np.linalg.det(np.eye(4) + full_product)
    factored_weight = (
        np.linalg.det(np.eye(2) + first_product)
        * np.linalg.det(np.eye(2) + second_product)
    )

    assert np.allclose(full_weight, factored_weight, rtol=1e-11, atol=1e-11)
    assert classify_product(full_product).classification == "positive"


@pytest.mark.parametrize("angle", [0.5, 0.05, 0.005])
def test_any_nonzero_mixed_split_angle_has_two_slice_counterexample(
    angle: float,
) -> None:
    amplitude = 1.1 / abs(np.sin(angle))
    first, second = mixed_split_boundary_counterexample(
        angle=angle,
        amplitude=amplitude,
    )
    eta = np.diag([1.0, 1.0, -1.0, -1.0])
    cosine = np.cos(angle)
    sine = np.sin(angle)
    rotation = np.eye(4)
    rotation[np.ix_([0, 2], [0, 2])] = [
        [cosine, -sine],
        [sine, cosine],
    ]
    rotated_eta = rotation @ eta @ rotation.T

    assert np.linalg.norm(first @ first) < 1e-10
    assert np.linalg.norm(second @ second) < 1e-9
    assert np.linalg.eigvalsh(first.T @ eta + eta @ first)[0] > -1e-12
    assert (
        np.linalg.eigvalsh(
            second.T @ rotated_eta + rotated_eta @ second
        )[0]
        > -1e-10
    )

    weight = np.linalg.det(
        np.eye(4) + product_exponentials([first, second])
    )
    exact_formula = 16.0 * (
        1.0 - amplitude**2 * np.sin(angle) ** 2
    )
    assert np.isclose(weight, exact_formula, rtol=2e-9, atol=2e-9)
    assert weight < 0.0


@pytest.mark.parametrize("angle", [0.0, np.pi])
def test_counterexample_rejects_rotations_that_leave_the_cone_unchanged(
    angle: float,
) -> None:
    with pytest.raises(ValueError, match="different cone"):
        mixed_split_boundary_counterexample(angle=angle, amplitude=2.0)


@pytest.mark.parametrize(
    "case",
    ["tn_path4_sym", "tn_path4_asym", "split_cone22", "block_upper_split11"],
)
def test_known_semigroup_controls_have_positive_sample_weights(case: str) -> None:
    rng = np.random.default_rng(41)
    for _ in range(20):
        generators = [
            random_generator(case, rng, scale=1.5)
            for _ in range(8)
        ]
        assert (
            classify_product(product_exponentials(generators)).classification
            == "positive"
        )
