from __future__ import annotations

import numpy as np

from oracle.az_families import (
    available_cases,
    random_generator,
    structure_residual,
    symmetry_operators,
)


EXPECTED = {
    "az_a": (None, None, False),
    "az_ai": (1, None, False),
    "az_bdi": (1, 1, True),
    "az_d": (None, 1, False),
    "az_diii": (-1, 1, True),
    "az_aii": (-1, None, False),
    "az_cii": (-1, -1, True),
    "az_c": (None, -1, False),
    "az_ci": (1, -1, True),
    "az_aiii": (None, None, True),
}


def test_az_registry_contains_the_tenfold_way_once() -> None:
    """Catches an omitted class or an accidental duplicate label."""
    assert set(available_cases()) == set(EXPECTED)


def test_canonical_antiunitary_operators_have_declared_squares() -> None:
    """Catches swapping the +1 and -1 implementations of T or C."""
    for case, (trs_square, phs_square, has_chiral) in EXPECTED.items():
        operators = symmetry_operators(case)
        assert operators["has_chiral"] is has_chiral

        for name, expected_square in (("T", trs_square), ("C", phs_square)):
            operator = operators[name]
            if expected_square is None:
                assert operator is None
                continue
            identity = np.eye(operator.shape[0])
            assert np.allclose(
                operator @ operator.conj(),
                expected_square * identity,
                atol=1e-14,
            )


def test_random_az_generators_are_hermitian_and_satisfy_all_constraints() -> None:
    """Catches a projector that labels generic matrices as an AZ class."""
    for index, case in enumerate(EXPECTED):
        rng = np.random.default_rng(800 + index)
        generator = random_generator(case, rng, scale=0.7)

        assert generator.shape == (4, 4)
        assert np.allclose(generator, generator.conj().T, atol=1e-13)
        assert np.isclose(np.linalg.norm(generator), 1.4, rtol=1e-13)
        assert structure_residual(case, generator) < 1e-13
