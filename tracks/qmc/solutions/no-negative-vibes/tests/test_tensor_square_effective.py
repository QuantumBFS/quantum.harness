from __future__ import annotations

from itertools import product
import math

import numpy as np
import pytest
from scipy.linalg import expm
from scipy.special import roots_hermitenorm

from oracle.tensor_square_effective import (
    continuous_gaussian_hs_history,
    continuous_gaussian_hs_model,
    continuous_model_fock_hamiltonian,
    coordinate_sum_charges,
    discrete_collective_density_gate,
    discrete_effective_transfer_mwe,
    lifted_one_body_generator,
    number_conserving_fock_generator,
    occupation_polynomial_values,
    tensor_square_determinant_certificate,
)
from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


def test_fock_lift_identity_for_density_and_bond_generators() -> None:
    generators = (
        np.diag([0.4, -0.7]),
        np.asarray([[0.0, 0.8], [0.8, 0.0]]),
    )

    for base_generator, amplitude in product(generators, (-0.6, 0.35)):
        lifted_generator = lifted_one_body_generator(base_generator)
        collective_operator = number_conserving_fock_generator(
            lifted_generator
        )
        base_propagator = expm(amplitude * base_generator)
        lifted_propagator = np.kron(base_propagator, base_propagator)
        direct_fock_lift = number_conserving_gaussian_fock_matrix(
            lifted_propagator
        )

        assert np.allclose(
            direct_fock_lift,
            expm(amplitude * collective_operator),
            rtol=1e-11,
            atol=1e-11,
        )


def test_continuous_model_is_hermitian_and_contains_pair_hopping() -> None:
    diagonal = np.diag([0.5, -0.3])
    bond = np.asarray([[0.0, 1.0], [1.0, 0.0]])
    model = continuous_gaussian_hs_model(
        base_kinetic=np.asarray([[0.0, -0.7], [-0.7, 0.0]]),
        base_generators=(diagonal, bond),
        couplings=(0.6, 0.4),
    )
    fock = continuous_model_fock_hamiltonian(model)
    bond_collective = fock.collective_operators[1]

    assert np.allclose(fock.hamiltonian, fock.hamiltonian.T, atol=1e-13)
    assert np.allclose(bond_collective, bond_collective.T, atol=1e-13)
    assert bond_collective[0b1100, 0b0011] == 0.0
    assert (bond_collective @ bond_collective)[0b1100, 0b0011] == 2.0
    assert math.isclose(
        fock.hamiltonian[0b1100, 0b0011],
        -model.effective_couplings[1],
        rel_tol=0.0,
        abs_tol=1e-13,
    )


def test_continuous_gaussian_hs_integral_reproduces_the_square_gate() -> None:
    base_generator = np.asarray([[0.0, 0.8], [0.8, 0.0]])
    collective = number_conserving_fock_generator(
        lifted_one_body_generator(base_generator)
    )
    time_step = 0.07
    coupling = 0.6
    nodes, weights = roots_hermitenorm(24)
    quadrature = sum(
        (
            weight
            * expm(
                node
                * math.sqrt(time_step * coupling)
                * collective
            )
            for node, weight in zip(nodes, weights, strict=True)
        ),
        start=np.zeros_like(collective),
    ) / math.sqrt(2.0 * math.pi)
    exact = expm(
        0.5 * time_step * coupling * (collective @ collective)
    )

    assert np.allclose(quadrature, exact, rtol=1e-12, atol=1e-12)


def test_kac_scaling_makes_collective_square_coupling_inverse_volume() -> None:
    for base_dimension in (2, 3):
        identity = np.eye(base_dimension)
        model = continuous_gaussian_hs_model(
            base_kinetic=np.zeros_like(identity),
            base_generators=(identity,),
            couplings=(2.5,),
            kac_normalize=True,
        )

        assert model.physical_modes == base_dimension**2
        assert model.kac_scale == 1.0 / model.physical_modes
        assert model.effective_couplings == (
            2.5 / model.physical_modes,
        )


@pytest.mark.parametrize("depth", [1, 2, 5, 12])
def test_noncommuting_continuous_hs_histories_have_positive_weight(
    depth: int,
) -> None:
    diagonal = np.diag([0.6, -0.4])
    bond = np.asarray([[0.0, 0.9], [0.9, 0.0]])
    model = continuous_gaussian_hs_model(
        base_kinetic=np.asarray([[0.2, -0.5], [-0.5, -0.1]]),
        base_generators=(diagonal, bond),
        couplings=(0.7, 0.3),
    )
    fields = tuple(
        (
            (-1.0) ** index * (0.2 + 0.03 * index),
            0.4 - 0.05 * index,
        )
        for index in range(depth)
    )
    history = continuous_gaussian_hs_history(
        model,
        fields,
        time_step=0.08,
    )

    assert np.linalg.norm(diagonal @ bond - bond @ diagonal) > 1.0
    assert history.gaussian_prefactor > 0.0
    assert history.determinant_certificate.closure_residual < 1e-11
    assert history.determinant_certificate.direct_weight > 0.0
    assert history.total_weight > 0.0


def test_tensor_square_certificate_covers_three_by_three_base_products() -> None:
    factors = (
        expm(
            np.asarray(
                [
                    [0.2, 0.3, 0.0],
                    [0.3, -0.1, -0.4],
                    [0.0, -0.4, 0.5],
                ]
            )
        ),
        expm(
            np.asarray(
                [
                    [-0.3, 0.0, 0.2],
                    [0.0, 0.4, 0.1],
                    [0.2, 0.1, -0.2],
                ]
            )
        ),
        expm(
            np.asarray(
                [
                    [0.1, -0.5, 0.0],
                    [-0.5, 0.2, 0.25],
                    [0.0, 0.25, -0.1],
                ]
            )
        ),
    )
    certificate = tensor_square_determinant_certificate(factors)

    assert certificate.closure_residual < 1e-11
    assert certificate.diagonal_spectral_factor >= 0.0
    assert certificate.direct_weight > 0.0
    assert math.isclose(
        certificate.direct_weight,
        certificate.spectral_weight,
        rel_tol=1e-10,
        abs_tol=1e-10,
    )


def test_three_by_three_multichannel_hs_model_is_noncommuting_and_positive() -> None:
    kinetic = np.asarray(
        [
            [0.2, -0.4, 0.0],
            [-0.4, -0.1, -0.3],
            [0.0, -0.3, 0.5],
        ]
    )
    diagonal = np.diag([0.7, -0.2, 0.4])
    bond = np.asarray(
        [
            [0.0, 0.6, 0.0],
            [0.6, 0.0, -0.5],
            [0.0, -0.5, 0.0],
        ]
    )
    model = continuous_gaussian_hs_model(
        base_kinetic=kinetic,
        base_generators=(diagonal, bond),
        couplings=(0.8, 0.35),
        kac_normalize=True,
    )
    fields = (
        (0.3, -0.4),
        (-0.7, 0.2),
        (0.5, 0.6),
        (-0.1, -0.8),
        (0.9, 0.15),
        (-0.35, 0.45),
    )
    history = continuous_gaussian_hs_history(
        model,
        fields,
        time_step=0.06,
    )
    fock = continuous_model_fock_hamiltonian(model)

    assert model.physical_modes == 9
    assert np.linalg.norm(diagonal @ bond - bond @ diagonal) > 0.5
    assert np.linalg.norm(kinetic @ bond - bond @ kinetic) > 0.1
    assert np.allclose(fock.hamiltonian, fock.hamiltonian.T, atol=1e-12)
    assert history.gaussian_prefactor > 0.0
    assert history.determinant_certificate.closure_residual < 1e-10
    assert history.determinant_certificate.direct_weight > 0.0
    assert history.total_weight > 0.0


@pytest.mark.parametrize(
    "base_field",
    [
        np.asarray([0.4, -0.7]),
        np.asarray([0.25, -0.45, 0.8]),
    ],
)
def test_discrete_density_gate_is_the_average_of_two_fock_lifts(
    base_field: np.ndarray,
) -> None:
    gate = discrete_collective_density_gate(
        base_field,
        time_step=0.2,
    )
    fock_diagonals = []

    for sign in (1.0, -1.0):
        lifted = np.diag(np.exp(sign * gate.mode_charges))
        fock = number_conserving_gaussian_fock_matrix(lifted)
        expected = np.exp(sign * gate.occupation_charges)

        assert np.allclose(fock, np.diag(expected), atol=1e-12)
        fock_diagonals.append(np.diag(fock))

    average = 0.5 * (fock_diagonals[0] + fock_diagonals[1])
    assert np.allclose(average, gate.transfer_diagonal, atol=1e-12)
    assert np.min(gate.transfer_diagonal) >= 1.0


@pytest.mark.parametrize(
    ("base_field", "maximum_body_order"),
    [
        (np.asarray([0.4, -0.7]), 4),
        (np.asarray([0.25, -0.45, 0.8]), 9),
    ],
)
def test_mobius_decomposition_resolves_m2_and_m3_body_orders(
    base_field: np.ndarray,
    maximum_body_order: int,
) -> None:
    gate = discrete_collective_density_gate(
        base_field,
        time_step=0.2,
    )
    decomposition = gate.mobius

    assert decomposition.modes == maximum_body_order
    assert np.allclose(
        decomposition.reconstructed_values,
        gate.effective_energy_diagonal,
        rtol=0.0,
        atol=2e-12,
    )
    assert np.allclose(
        occupation_polynomial_values(decomposition.coefficients),
        gate.effective_energy_diagonal,
        rtol=0.0,
        atol=2e-12,
    )
    assert decomposition.coefficients[0] == 0.0
    assert decomposition.body_orders[-1].body_order == maximum_body_order
    assert decomposition.body_orders[-1].term_count == 1
    assert decomposition.body_orders[-1].nonzero_count == 1
    assert all(
        summary.term_count == math.comb(maximum_body_order, summary.body_order)
        for summary in decomposition.body_orders
    )


def test_positive_transfer_gate_defines_an_exact_hermitian_minus_log_model(
) -> None:
    time_step = 0.15
    mwe = discrete_effective_transfer_mwe(
        base_kinetic=np.asarray([[0.2, -0.9], [-0.9, -0.1]]),
        base_field=np.asarray([0.45, -0.65]),
        time_step=time_step,
    )
    field_average = 0.5 * (
        mwe.fock_slice_transfers[0] + mwe.fock_slice_transfers[1]
    )
    density_sandwich = (
        mwe.fock_half_kinetic
        @ np.diag(mwe.density_gate.transfer_diagonal)
        @ mwe.fock_half_kinetic
    )

    assert np.allclose(field_average, mwe.transfer_gate, atol=1e-12)
    assert np.allclose(density_sandwich, mwe.transfer_gate, atol=1e-12)
    assert np.allclose(mwe.transfer_gate, mwe.transfer_gate.T, atol=1e-12)
    assert mwe.minimum_transfer_eigenvalue > 0.0
    assert all(
        np.min(np.linalg.eigvalsh(field_gate)) > 0.0
        for field_gate in mwe.fock_slice_transfers
    )
    assert np.allclose(
        mwe.effective_hamiltonian,
        mwe.effective_hamiltonian.T,
        atol=1e-12,
    )
    assert np.allclose(
        expm(-time_step * mwe.effective_hamiltonian),
        mwe.transfer_gate,
        rtol=1e-10,
        atol=1e-10,
    )


def test_discrete_log_cosh_tends_to_the_continuous_attractive_square() -> None:
    time_step = 1e-5
    coupling = 0.7
    unscaled_field = np.asarray([0.4, -0.7])
    gate = discrete_collective_density_gate(
        math.sqrt(time_step * coupling) * unscaled_field,
        time_step=time_step,
    )
    unscaled_charges = coordinate_sum_charges(unscaled_field)
    occupation_values = np.zeros_like(gate.occupation_charges)
    for mask in range(occupation_values.size):
        occupation_values[mask] = sum(
            unscaled_charges[mode]
            for mode in range(unscaled_charges.size)
            if mask & (1 << mode)
        )
    continuous_limit = -0.5 * coupling * occupation_values**2

    assert np.allclose(
        gate.effective_energy_diagonal,
        continuous_limit,
        rtol=0.0,
        atol=2e-4,
    )
