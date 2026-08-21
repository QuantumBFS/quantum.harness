import sys
from pathlib import Path

import numpy as np
import pytest
from tenpy.algorithms.exact_diag import get_numpy_Hamiltonian
from tenpy.models.lattice import Chain
from tenpy.models.model import MPOModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lrtfim.mpo import (
    active_exponential_channels,
    build_periodized_mpo,
    build_periodized_mpo_graph,
    build_rotated_periodized_mpo,
)
from lrtfim.exponential_fit import ExponentialFit, periodized_exponential_couplings
from lrtfim.dmrg_workflow import build_mpo_model
from lrtfim.validation import dense_mpo_hamiltonian, lowest_eigenpairs


def _sample_parameters():
    return np.array([0.72, 0.31]), np.array([0.4, 0.08])


def _has_edge(graph, site, left, right, operator, strength):
    return any(
        op == operator and value == pytest.approx(strength)
        for op, value in graph.graph[site][left][right]
    )


def test_graph_uses_direct_wrapped_and_pauli_field_channels():
    length = 5
    lambdas, coefficients = _sample_parameters()
    gamma = 0.37
    graph = build_periodized_mpo_graph(length, lambdas, coefficients, gamma)
    amplitude = coefficients[0] / (1.0 - lambdas[0] ** length)
    direct = (0, 0, 0)
    wrapped = (0, 1, 0)

    assert _has_edge(graph, 0, "IdL", direct, "Sigmaz", lambdas[0])
    assert _has_edge(graph, 2, direct, direct, "Id", lambdas[0])
    assert _has_edge(graph, 3, direct, "IdR", "Sigmaz", -amplitude)
    assert _has_edge(graph, 2, "IdL", wrapped, "Sigmaz", lambdas[0] ** 2)
    assert _has_edge(graph, 3, wrapped, wrapped, "Id", 1.0)
    assert _has_edge(
        graph,
        4,
        wrapped,
        "IdR",
        "Sigmaz",
        -amplitude * lambdas[0],
    )
    assert _has_edge(graph, 2, "IdL", "IdR", "Sigmax", -gamma)


def test_mpo_has_expected_bulk_bond_dimension():
    lambdas, coefficients = _sample_parameters()
    mpo = build_periodized_mpo(6, lambdas, coefficients, gamma=0.2)

    assert max(mpo.chi) == 2 * len(lambdas) + 2


def test_exact_zero_channels_are_pruned_but_tiny_positive_channel_is_kept():
    lambdas = np.array([0.9, 0.7, 0.5, 0.3])
    coefficients = np.array([0.4, 0.0, 1.0e-300, 0.0])

    active_lambdas, active_coefficients, indices = active_exponential_channels(
        lambdas,
        coefficients,
    )

    np.testing.assert_array_equal(active_lambdas, lambdas[[0, 2]])
    np.testing.assert_array_equal(active_coefficients, coefficients[[0, 2]])
    np.testing.assert_array_equal(indices, [0, 2])


def test_zero_channel_pruning_preserves_dense_spectrum_and_observable():
    length = 6
    lambdas = np.array([0.91, 0.72, 0.5, 0.31])
    coefficients = np.array([0.4, 0.0, 1.0e-6, 0.08])
    common = (length, lambdas, coefficients, 1.2)
    full = build_rotated_periodized_mpo(*common, prune_zero_channels=False)
    pruned = build_rotated_periodized_mpo(*common, prune_zero_channels=True)

    assert max(full.chi) == 2 * len(lambdas) + 2
    assert max(pruned.chi) == 2 * np.count_nonzero(coefficients) + 2
    dense_full = dense_mpo_hamiltonian(build_mpo_model(full))
    dense_pruned = dense_mpo_hamiltonian(build_mpo_model(pruned))
    np.testing.assert_allclose(dense_pruned, dense_full, atol=2e-13)

    energies_full, states_full = lowest_eigenpairs(dense_full, count=2)
    energies_pruned, states_pruned = lowest_eigenpairs(dense_pruned, count=2)
    np.testing.assert_allclose(energies_pruned, energies_full, atol=2e-13)
    sigmax = np.array([[0.0, 1.0], [1.0, 0.0]])
    for distance in range(1, length // 2 + 1):
        operator = sum(
            _many_body_operator(
                {
                    origin: sigmax,
                    (origin + distance) % length: sigmax,
                },
                length,
            )
            for origin in range(length)
        ) / length
        full_correlation = np.vdot(
            states_full[:, 0],
            operator @ states_full[:, 0],
        ).real
        pruned_correlation = np.vdot(
            states_pruned[:, 0],
            operator @ states_pruned[:, 0],
        ).real
        assert pruned_correlation == pytest.approx(full_correlation, abs=2e-12)


def _many_body_operator(local_operator, sites):
    identity = np.eye(2)
    factors = [
        local_operator[index] if index in local_operator else identity
        for index in range(sites)
    ]
    result = factors[0]
    for factor in factors[1:]:
        result = np.kron(result, factor)
    return result


def test_dense_mpo_reconstructs_all_pairs_and_transverse_field():
    length = 5
    gamma = 0.37
    lambdas, coefficients = _sample_parameters()
    mpo = build_periodized_mpo(length, lambdas, coefficients, gamma)
    lattice = Chain(length, mpo.sites[0], bc="open", bc_MPS="finite")
    dense = get_numpy_Hamiltonian(MPOModel(lattice, mpo), from_mpo=True)
    sigmaz = np.diag([1.0, -1.0])
    sigmax = np.array([[0.0, 1.0], [1.0, 0.0]])
    dimension = 2**length
    relative_errors = []
    fit = ExponentialFit(
        sigma=1.75,
        r_fit=64,
        lambdas=lambdas,
        coefficients=coefficients,
        max_relative_error=np.nan,
        rms_relative_error=np.nan,
    )
    expected_by_distance = periodized_exponential_couplings(length, fit)

    for i in range(length):
        field_operator = _many_body_operator({i: sigmax}, length)
        field_coefficient = np.trace(dense @ field_operator).real / dimension
        assert field_coefficient == pytest.approx(-gamma, abs=2e-14)
        for j in range(i + 1, length):
            pair_operator = _many_body_operator({i: sigmaz, j: sigmaz}, length)
            reconstructed = -np.trace(dense @ pair_operator).real / dimension
            distance = j - i
            expected = expected_by_distance[distance - 1]
            relative_errors.append(abs(reconstructed - expected) / expected)

    assert max(relative_errors) < 2e-13


@pytest.mark.parametrize(
    ("length", "lambdas", "coefficients"),
    [(1, [0.5], [1.0]), (4, [1.0], [1.0]), (4, [0.5], [-1.0])],
)
def test_mpo_rejects_invalid_parameters(length, lambdas, coefficients):
    with pytest.raises(ValueError):
        build_periodized_mpo(
            length,
            np.asarray(lambdas),
            np.asarray(coefficients),
            gamma=0.2,
        )
