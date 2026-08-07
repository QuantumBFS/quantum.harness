from __future__ import annotations

import numpy as np
import pytest

from oracle.az_semigroup_cones import (
    available_cases,
    bdi_two_sided_boundary_counterexample,
    random_generator,
    structure_residual,
)
from oracle.scan import scan_cell
from oracle.weights import product_exponentials


EXPECTED_CASES = {
    "azcone_bdi_split",
    "azcone_bdi_two_sided",
    "azcone_aii_kramers",
    "azcone_diii_phs",
    "azcone_diii_generic",
    "azcone_cii_kramers",
    "azcone_cii_generic",
}


def test_az_cone_registry_has_all_declared_probes() -> None:
    assert set(available_cases()) == EXPECTED_CASES


@pytest.mark.parametrize("case", sorted(EXPECTED_CASES))
def test_random_az_cone_generators_satisfy_declared_structure(
    case: str,
) -> None:
    generator = random_generator(
        case,
        np.random.default_rng(9100),
        scale=0.8,
    )

    assert generator.shape == (4, 4)
    assert np.isclose(np.linalg.norm(generator), 1.6, rtol=1e-13)
    assert structure_residual(case, generator) < 1e-12


@pytest.mark.parametrize(
    "case",
    [
        "azcone_bdi_split",
        "azcone_aii_kramers",
        "azcone_cii_kramers",
    ],
)
def test_known_positive_controls_survive_small_scan(case: str) -> None:
    manifest = scan_cell(
        case=case,
        depth=6,
        scale=1.0,
        seed=9200,
        samples=40,
    )

    assert manifest["counts"]["negative"] == 0
    assert manifest["counts"]["complex"] == 0
    assert manifest["max_structure_residual"] < 1e-12


def test_bdi_two_sided_boundary_counterexample_is_exactly_negative() -> None:
    q = 2.0
    generators = bdi_two_sided_boundary_counterexample(q)

    assert all(np.allclose(generator @ generator, 0.0) for generator in generators)
    assert all(
        structure_residual("azcone_bdi_two_sided", generator) < 1e-12
        for generator in generators
    )

    product = product_exponentials(generators)
    weight = np.linalg.det(np.eye(4) + product)
    assert np.isclose(weight, 16.0 * (1.0 - q**2), atol=1e-12)
    assert weight < 0.0
