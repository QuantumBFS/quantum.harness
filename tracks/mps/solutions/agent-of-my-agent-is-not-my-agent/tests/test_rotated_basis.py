from __future__ import annotations

from functools import reduce

import numpy as np
import pytest

from lrtfim.dmrg_workflow import build_mpo_model, default_dmrg_options
from lrtfim.mpo import (
    build_nearest_neighbor_tfim_mpo,
    build_periodized_mpo,
    build_rotated_nearest_neighbor_tfim_mpo,
    build_rotated_periodized_mpo,
)
from lrtfim.exponential_fit import fit_power_law
from lrtfim.parity_dmrg import (
    physical_correlations_rotated,
    run_parity_spectrum,
)
from lrtfim.validation import dense_mpo_hamiltonian, lowest_eigenpairs


def _hadamard_rotation(length: int) -> np.ndarray:
    local = np.array([[1.0, 1.0], [1.0, -1.0]]) / np.sqrt(2.0)
    return reduce(np.kron, [local] * length)


def _physical_correlations_dense(vector: np.ndarray, length: int) -> np.ndarray:
    identity = np.eye(2)
    z = np.diag([1.0, -1.0])
    values = [1.0]
    for distance in range(1, length):
        by_origin = []
        for origin in range(length):
            operators = [identity] * length
            operators[origin] = z
            operators[(origin + distance) % length] = z
            operator = reduce(np.kron, operators)
            by_origin.append(np.vdot(vector, operator @ vector).real)
        values.append(float(np.mean(by_origin)))
    return np.asarray(values)


def test_rotated_nn_mpo_is_hadamard_rotation() -> None:
    length = 4
    gamma = 0.73
    physical = dense_mpo_hamiltonian(
        build_mpo_model(build_nearest_neighbor_tfim_mpo(length, gamma))
    )
    rotated_mpo = build_rotated_nearest_neighbor_tfim_mpo(length, gamma)
    rotated = dense_mpo_hamiltonian(build_mpo_model(rotated_mpo))
    hadamard = _hadamard_rotation(length)
    np.testing.assert_allclose(
        rotated,
        hadamard @ physical @ hadamard.T,
        atol=2.0e-13,
    )
    assert rotated_mpo.sites[0].conserve == "parity"


@pytest.fixture(scope="module")
def sigma_175_fit():
    return fit_power_law(
        sigma=1.75,
        num_exponentials=8,
        r_fit=128,
        min_rate_scale=0.5,
    )


@pytest.mark.parametrize("length", [8, 10, 12])
def test_rotated_nn_even_odd_spectrum_and_correlations_match_ed(length: int) -> None:
    gamma = 1.0
    physical_model = build_mpo_model(
        build_nearest_neighbor_tfim_mpo(length, gamma)
    )
    dense = dense_mpo_hamiltonian(physical_model)
    energies, vectors = lowest_eigenpairs(dense)
    exact_correlations = _physical_correlations_dense(vectors[:, 0], length)

    rotated_model = build_mpo_model(
        build_rotated_nearest_neighbor_tfim_mpo(length, gamma)
    )
    options = default_dmrg_options(chi_max=64)
    result = run_parity_spectrum(rotated_model, options)

    np.testing.assert_allclose(
        [result.ground.energy, result.excited.energy],
        energies,
        atol=1.0e-9,
    )
    assert result.ground.sector == "even"
    assert result.excited.sector == "odd"
    np.testing.assert_allclose(
        physical_correlations_rotated(result.ground.psi),
        exact_correlations,
        atol=1.0e-8,
    )


@pytest.mark.parametrize("length", [8, 10, 12])
def test_rotated_long_range_even_odd_spectrum_matches_dense_mpo_ed(
    length: int,
    sigma_175_fit,
) -> None:
    gamma = 1.56
    lambdas = np.append(sigma_175_fit.lambdas, 0.123)
    coefficients = np.append(sigma_175_fit.coefficients, 0.0)
    physical_mpo = build_periodized_mpo(
        length,
        lambdas,
        coefficients,
        gamma,
    )
    dense = dense_mpo_hamiltonian(build_mpo_model(physical_mpo))
    energies, vectors = lowest_eigenpairs(dense)
    exact_correlations = _physical_correlations_dense(vectors[:, 0], length)

    rotated_mpo = build_rotated_periodized_mpo(
        length,
        lambdas,
        coefficients,
        gamma,
        prune_zero_channels=True,
    )
    assert max(rotated_mpo.chi) == 2 * np.count_nonzero(coefficients) + 2
    result = run_parity_spectrum(
        build_mpo_model(rotated_mpo),
        default_dmrg_options(chi_max=64),
    )

    np.testing.assert_allclose(
        [result.ground.energy, result.excited.energy],
        energies,
        atol=1.0e-9,
    )
    np.testing.assert_allclose(
        physical_correlations_rotated(result.ground.psi),
        exact_correlations,
        atol=1.0e-8,
    )
