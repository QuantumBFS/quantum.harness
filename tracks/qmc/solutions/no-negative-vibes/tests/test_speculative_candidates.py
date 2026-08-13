from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from oracle.speculative_candidates import (
    available_cases,
    random_generator,
    structure_residual,
)
from oracle.weights import classify_product, product_exponentials


EXPECTED_CASES = {
    "linf_contract4",
    "linf_moving_metric4",
    "reciprocal_parabolic4",
    "reciprocal_bicoupled4",
    "lusztig_d4_positive",
    "lusztig_d4_signed",
    "commuting_dense4",
    "near_commuting4",
}

EXPECTED_SHAPES = {
    case: ((8, 8) if case.startswith("lusztig_d4") else (4, 4))
    for case in EXPECTED_CASES
}


def _small_scan(
    case: str,
    *,
    depth: int,
    scale: float,
    seed: int,
    samples: int,
) -> Counter[str]:
    rng = np.random.default_rng(seed)
    counts: Counter[str] = Counter()
    for _ in range(samples):
        generators = [
            random_generator(case, rng, scale=scale)
            for _ in range(depth)
        ]
        product = product_exponentials(generators)
        counts[classify_product(product).classification] += 1
    return counts


def test_speculative_registry_has_all_declared_probes() -> None:
    assert set(available_cases()) == EXPECTED_CASES


@pytest.mark.parametrize("case", sorted(EXPECTED_CASES))
def test_random_speculative_generators_satisfy_declared_structure(
    case: str,
) -> None:
    generator = random_generator(
        case,
        np.random.default_rng(10100),
        scale=0.8,
    )

    assert generator.shape == EXPECTED_SHAPES[case]
    expected_norm = 0.8 * np.sqrt(generator.shape[0])
    assert np.isclose(np.linalg.norm(generator), expected_norm, rtol=1e-13)
    assert structure_residual(case, generator) < 1e-12


@pytest.mark.parametrize(
    "case",
    [
        "linf_contract4",
        "reciprocal_parabolic4",
        "lusztig_d4_positive",
        "commuting_dense4",
    ],
)
def test_theorem_positive_controls_survive_small_scan(case: str) -> None:
    counts = _small_scan(
        case,
        depth=8,
        scale=1.25,
        seed=10200,
        samples=60,
    )

    assert counts["negative"] == 0
    assert counts["complex"] == 0


@pytest.mark.parametrize(
    "case",
    [
        "linf_moving_metric4",
        "reciprocal_bicoupled4",
        "near_commuting4",
    ],
)
def test_relaxed_probes_are_not_mislabeled_as_known_positive(case: str) -> None:
    assert available_cases()[case].prior_status == "candidate"


@pytest.mark.parametrize(
    "case",
    ["lusztig_d4_positive", "lusztig_d4_signed"],
)
def test_d4_wedges_are_inside_the_known_split_orthogonal_algebra(
    case: str,
) -> None:
    generator = random_generator(
        case,
        np.random.default_rng(10300),
        scale=1.1,
    )
    identity = np.eye(4)
    split_metric = np.block(
        [[np.zeros((4, 4)), identity], [identity, np.zeros((4, 4))]]
    )

    assert np.linalg.norm(
        generator.T @ split_metric + split_metric @ generator
    ) < 1e-12
    assert available_cases()[case].prior_status == "known_nonnegative"


@pytest.mark.parametrize(
    ("case", "depth", "scale"),
    [
        ("linf_moving_metric4", 2, 2.0),
        ("reciprocal_bicoupled4", 2, 2.0),
        ("near_commuting4", 8, 3.0),
    ],
)
def test_adversarial_relaxations_expose_negative_weights(
    case: str,
    depth: int,
    scale: float,
) -> None:
    counts = _small_scan(
        case,
        depth=depth,
        scale=scale,
        seed=10400,
        samples=200,
    )

    assert counts["negative"] > 0
