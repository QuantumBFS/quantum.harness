from __future__ import annotations

from itertools import combinations

import numpy as np
import pytest
from scipy.linalg import expm, logm

from oracle.monomial_candidates import (
    available_cases,
    even_v4_boundary_factors,
    factor_structure_residual,
    local_c3_crossed_tn_boundary_factors,
    random_factor,
    real_exponential_witnesses,
    real_log_audit,
)


EXPECTED_CASES = {
    "odd_monomial_c3",
    "odd_monomial_c5",
    "even_monomial_v4",
    "odd_block_tn_c3",
}


def _product(factors: list[np.ndarray]) -> np.ndarray:
    result = np.eye(factors[0].shape[0])
    for factor in factors:
        result = result @ factor
    return result


def test_registry_contains_declared_monomial_probes() -> None:
    assert set(available_cases()) == EXPECTED_CASES


@pytest.mark.parametrize("case", sorted(EXPECTED_CASES))
def test_random_factors_satisfy_structure_and_have_real_exponential_witnesses(
    case: str,
) -> None:
    rng = np.random.default_rng(20260728)
    for _ in range(12):
        factor = random_factor(case, rng, scale=0.7)

        assert factor.shape == available_cases()[case].shape
        assert factor_structure_residual(case, factor) < 1e-12
        assert real_log_audit(case, factor).exists

        witnesses = real_exponential_witnesses(case, factor)
        reconstruction = np.eye(factor.shape[0])
        for generator in witnesses:
            assert np.linalg.norm(generator.imag) == 0.0
            reconstruction = reconstruction @ expm(generator)
        assert np.allclose(reconstruction, factor, rtol=2e-8, atol=2e-9)


@pytest.mark.parametrize("case", ["odd_monomial_c3", "odd_monomial_c5"])
def test_odd_scalar_products_are_p0_and_have_positive_weight(case: str) -> None:
    rng = np.random.default_rng(711)
    size = available_cases()[case].shape[0]
    for _ in range(30):
        product = _product(
            [random_factor(case, rng, scale=1.1) for _ in range(12)]
        )
        principal_minor_sum = 1.0
        for order in range(1, size + 1):
            for indices in combinations(range(size), order):
                minor = float(
                    np.linalg.det(product[np.ix_(indices, indices)])
                )
                assert minor > -1e-9
                principal_minor_sum += minor

        weight = float(np.linalg.det(np.eye(size) + product))
        assert weight > 0.0
        assert np.isclose(
            weight,
            principal_minor_sum,
            rtol=2e-10,
            atol=2e-9,
        )


def test_odd_block_tn_products_have_positive_weight() -> None:
    rng = np.random.default_rng(1703)
    for _ in range(100):
        product = _product(
            [
                random_factor("odd_block_tn_c3", rng, scale=0.55)
                for _ in range(10)
            ]
        )
        sign, _ = np.linalg.slogdet(np.eye(6) + product)
        assert sign > 0.0


def test_even_v4_two_real_exponential_atoms_have_exact_negative_product() -> None:
    q = 2.0
    factors = list(even_v4_boundary_factors(q))

    for factor in factors:
        assert factor_structure_residual("even_monomial_v4", factor) < 1e-12
        assert real_log_audit("even_monomial_v4", factor).exists
        witnesses = real_exponential_witnesses(
            "even_monomial_v4",
            factor,
        )
        assert np.allclose(
            expm(witnesses[0]) @ expm(witnesses[1]),
            factor,
            atol=2e-9,
        )

    product = _product(factors)
    weight = float(np.linalg.det(np.eye(4) + product))
    exact_weight = (1.0 - q**2) * (1.0 - q**-2)

    assert np.isclose(weight, exact_weight, atol=1e-12)
    assert weight < 0.0
    audit = real_log_audit("even_monomial_v4", product)
    assert not audit.exists
    assert "odd Jordan-block multiplicity" in audit.reason


def test_random_even_v4_products_find_the_expected_boundary_failure() -> None:
    rng = np.random.default_rng(404)
    classifications: list[float] = []
    for _ in range(80):
        product = _product(
            [
                random_factor("even_monomial_v4", rng, scale=1.0)
                for _ in range(8)
            ]
        )
        classifications.append(float(np.linalg.det(np.eye(4) + product)))

    assert any(weight < -1e-9 for weight in classifications)
    assert any(weight > 1e-9 for weight in classifications)


def test_local_c3_routes_and_crossed_tn_hopping_have_exact_negative_weight() -> None:
    hopping, route = local_c3_crossed_tn_boundary_factors()

    assert np.allclose(route @ route @ route, np.eye(6), atol=1e-13)
    route_logarithm = logm(route)
    assert np.linalg.norm(route_logarithm.imag) < 1e-12
    assert np.allclose(expm(route_logarithm.real), route, atol=1e-12)

    for flavor in range(3):
        modes = (flavor, 3 + flavor)
        block = hopping[np.ix_(modes, modes)]
        assert np.allclose(block, block.T, atol=1e-14)
        assert np.min(block) > 0.0
        assert np.linalg.det(block) > 0.0
        assert np.linalg.eigvalsh(block).min() > 0.0

    hopping_logarithm = logm(hopping)
    assert np.linalg.norm(hopping_logarithm.imag) < 1e-12
    assert np.allclose(expm(hopping_logarithm.real), hopping, atol=1e-12)

    assert np.linalg.det(np.eye(6) + hopping) > 0.0
    assert np.linalg.det(np.eye(6) + route) > 0.0
    weight = float(np.linalg.det(np.eye(6) + hopping @ route))
    assert np.isclose(weight, -2.0, atol=1e-12)


def test_structure_residual_rejects_dense_perturbation() -> None:
    factor = random_factor(
        "odd_monomial_c3",
        np.random.default_rng(5),
        scale=0.4,
    )
    factor = factor + 0.2 * np.ones((3, 3))

    assert factor_structure_residual("odd_monomial_c3", factor) > 1e-2


@pytest.mark.parametrize("q", [-1.0, 0.0, 1.0, np.inf])
def test_even_boundary_rejects_invalid_q(q: float) -> None:
    with pytest.raises(ValueError):
        even_v4_boundary_factors(q)
