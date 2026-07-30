from __future__ import annotations

from types import MappingProxyType

import numpy as np
import pytest

from scalable_v1.routes.cf_operator_nqs.jets import PairJet, jet_determinant


def test_pair_jet_matches_known_polynomial_derivatives() -> None:
    u_i = PairJet.variable(1.2 - 0.3j, axis=0)
    v_i = PairJet.variable(-0.4 + 0.2j, axis=1)
    u_j = PairJet.variable(0.7 + 0.1j, axis=2)
    v_j = PairJet.variable(-0.2 - 0.5j, axis=3)
    value = (u_i * v_j - v_i * u_j) ** 3

    expected = (1.2 - 0.3j) * (-0.2 - 0.5j) - (
        -0.4 + 0.2j
    ) * (0.7 + 0.1j)
    np.testing.assert_allclose(value.constant_term, expected**3)
    np.testing.assert_allclose(
        value.derivative(0).constant_term,
        3.0 * expected**2 * (-0.2 - 0.5j),
    )


def test_pair_jet_determinant_is_division_free_and_exact() -> None:
    x = PairJet.variable(0.3 + 0.1j, axis=0)
    matrix = [
        [x, PairJet.constant(2.0)],
        [PairJet.constant(3.0), PairJet.constant(5.0)],
    ]

    determinant = jet_determinant(matrix)

    np.testing.assert_allclose(
        determinant.constant_term,
        5.0 * x.constant_term - 6.0,
    )
    np.testing.assert_allclose(determinant.derivative(0).constant_term, 5.0)


def test_pair_jet_coefficients_are_immutable() -> None:
    value = PairJet.variable(1.0, axis=0)

    assert isinstance(value.coefficients, MappingProxyType)
    with pytest.raises(TypeError):
        value.coefficients[(0, 0, 0, 0)] = 2.0  # type: ignore[index]


@pytest.mark.parametrize("axis", (True, -1, 4, 1.5))
def test_pair_jet_rejects_invalid_axes(axis: object) -> None:
    with pytest.raises(ValueError, match="axis"):
        PairJet.variable(1.0, axis=axis)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="axis"):
        PairJet.constant(1.0).derivative(axis)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", (np.nan, np.inf, -np.inf, 1.0j * np.inf))
def test_pair_jet_rejects_nonfinite_coefficients(value: complex) -> None:
    with pytest.raises(ValueError, match="finite"):
        PairJet.constant(value)


@pytest.mark.parametrize(
    "index",
    (
        (0, 0, 0),
        (0, 0, 0, 0, 0),
        (-1, 0, 0, 0),
        (True, 0, 0, 0),
    ),
)
def test_pair_jet_rejects_invalid_multi_indices(index: tuple[object, ...]) -> None:
    with pytest.raises(ValueError, match="multi-index"):
        PairJet({index: 1.0})  # type: ignore[arg-type]


def test_pair_jet_truncates_only_outside_per_particle_envelope() -> None:
    u_i = PairJet.variable(0.0, axis=0)
    v_i = PairJet.variable(0.0, axis=1)
    u_j = PairJet.variable(0.0, axis=2)

    assert not (u_i**5).coefficients
    assert not (u_i**4 * v_i).coefficients
    assert (u_i**4 * u_j**4).coefficients == {(4, 0, 4, 0): 1.0}


@pytest.mark.parametrize("exponent", (True, -1, 1.5))
def test_pair_jet_rejects_invalid_exponents(exponent: object) -> None:
    with pytest.raises(ValueError, match="exponent"):
        PairJet.constant(2.0) ** exponent  # type: ignore[operator]
