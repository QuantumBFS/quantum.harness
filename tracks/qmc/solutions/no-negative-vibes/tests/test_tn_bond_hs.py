from __future__ import annotations

from itertools import product
import math

import numpy as np
import pytest
from scipy.linalg import expm, logm

from oracle.tn_bond_hs import (
    asymmetric_tn_bond_decomposition,
    embed_adjacent_bond,
    gaussian_fock_matrix,
    number_conserving_gaussian_fock_matrix,
    tn_bond_configuration_weight,
)


def test_asymmetric_gaussian_sum_is_exact_physical_bond_gate() -> None:
    time_step = 0.2
    hopping = 1.0
    interaction = 3.0
    chemical_potential = 0.4
    decomposition = asymmetric_tn_bond_decomposition(
        time_step=time_step,
        hopping=hopping,
        interaction=interaction,
        chemical_potential=chemical_potential,
        asymmetry=0.6,
    )

    local_hamiltonian = np.asarray(
        [
            [0.0, 0.0, 0.0, 0.0],
            [0.0, -chemical_potential, -hopping, 0.0],
            [0.0, -hopping, -chemical_potential, 0.0],
            [0.0, 0.0, 0.0, interaction - 2.0 * chemical_potential],
        ]
    )
    exact_gate = expm(-time_step * local_hamiltonian)
    auxiliary_sum = 0.5 * (
        gaussian_fock_matrix(decomposition.propagator_plus)
        + gaussian_fock_matrix(decomposition.propagator_minus)
    )

    assert np.allclose(auxiliary_sum, exact_gate, rtol=1e-13, atol=1e-13)


@pytest.mark.parametrize("asymmetry", [0.0, 0.2, 0.6, 0.99])
def test_each_auxiliary_propagator_is_invertible_tn(
    asymmetry: float,
) -> None:
    decomposition = asymmetric_tn_bond_decomposition(
        time_step=0.2,
        hopping=1.0,
        interaction=3.0,
        chemical_potential=-0.7,
        asymmetry=asymmetry,
    )

    average = 0.5 * (
        decomposition.propagator_plus + decomposition.propagator_minus
    )
    assert np.allclose(average, decomposition.target_one_particle)
    for matrix in (
        decomposition.propagator_plus,
        decomposition.propagator_minus,
    ):
        assert np.min(matrix) >= 0.0
        assert math.isclose(
            float(np.linalg.det(matrix)),
            decomposition.target_double_occupation,
            rel_tol=1e-13,
            abs_tol=1e-13,
        )
        generator = np.real_if_close(logm(matrix), tol=1000)
        assert not np.iscomplexobj(generator)
        assert generator[0, 1] >= -1e-13
        assert generator[1, 0] >= -1e-13


def test_positive_asymmetry_has_no_common_diagonal_symmetrizer() -> None:
    decomposition = asymmetric_tn_bond_decomposition(
        time_step=0.2,
        hopping=1.0,
        interaction=3.0,
        asymmetry=0.6,
    )
    plus = decomposition.propagator_plus
    minus = decomposition.propagator_minus

    plus_required_gauge_ratio_squared = plus[1, 0] / plus[0, 1]
    minus_required_gauge_ratio_squared = minus[1, 0] / minus[0, 1]
    assert plus_required_gauge_ratio_squared > 0.0
    assert minus_required_gauge_ratio_squared > 0.0
    assert not math.isclose(
        plus_required_gauge_ratio_squared,
        minus_required_gauge_ratio_squared,
    )
    assert math.isclose(
        plus_required_gauge_ratio_squared
        * minus_required_gauge_ratio_squared,
        1.0,
        rel_tol=1e-14,
    )


def test_single_bond_fields_do_share_a_nondiagonal_positive_metric() -> None:
    decomposition = asymmetric_tn_bond_decomposition(
        time_step=0.2,
        hopping=1.0,
        interaction=3.0,
        chemical_potential=0.4,
        asymmetry=0.6,
    )
    plus = decomposition.propagator_plus
    skew = 0.5 * (plus[0, 1] - plus[1, 0])
    splitting = 0.5 * (plus[0, 0] - plus[1, 1])
    metric = np.asarray([[1.0, skew / splitting], [skew / splitting, 1.0]])

    assert np.min(np.linalg.eigvalsh(metric)) > 0.0
    for matrix in (
        decomposition.propagator_plus,
        decomposition.propagator_minus,
    ):
        assert np.allclose(metric @ matrix, matrix.T @ metric, atol=1e-13)


def test_overlapping_bonds_have_no_common_symmetric_metric() -> None:
    decomposition = asymmetric_tn_bond_decomposition(
        time_step=0.2,
        hopping=1.0,
        interaction=3.0,
        chemical_potential=0.4,
        asymmetry=0.6,
    )
    propagators = [
        embed_adjacent_bond(matrix, sites=3, left_site=left_site)
        for left_site in (0, 1)
        for matrix in (
            decomposition.propagator_plus,
            decomposition.propagator_minus,
        )
    ]
    symmetric_basis = []
    for row in range(3):
        for column in range(row, 3):
            basis = np.zeros((3, 3))
            basis[row, column] = 1.0
            basis[column, row] = 1.0
            symmetric_basis.append(basis)

    constraint_columns = []
    for basis in symmetric_basis:
        constraint_columns.append(
            np.concatenate(
                [
                    (basis @ matrix - matrix.T @ basis).ravel()
                    for matrix in propagators
                ]
            )
        )
    constraint_matrix = np.column_stack(constraint_columns)

    assert np.linalg.matrix_rank(constraint_matrix, tol=1e-11) == len(
        symmetric_basis
    )


def test_all_small_checkerboard_histories_have_positive_determinant() -> None:
    sites = 4
    bond_sequence = np.asarray([0, 2, 1] * 3)
    minimum_determinant = math.inf

    for fields in product((-1, 1), repeat=bond_sequence.size):
        weight = tn_bond_configuration_weight(
            np.asarray(fields),
            bond_sequence,
            sites=sites,
            time_step=0.2,
            hopping=1.0,
            interaction=3.0,
            chemical_potential=0.4,
            asymmetry=0.6,
        )
        minimum_determinant = min(minimum_determinant, weight.determinant)
        assert weight.total > 0.0

    assert minimum_determinant >= 1.0 - 1e-12


def test_enumerated_partition_sum_is_independent_of_asymmetry() -> None:
    sites = 3
    bond_sequence = np.asarray([0, 1] * 2)
    partition_sums = []

    for asymmetry in (0.0, 0.3, 0.6, 0.9):
        partition_sum = 0.0
        for fields in product((-1, 1), repeat=bond_sequence.size):
            weight = tn_bond_configuration_weight(
                np.asarray(fields),
                bond_sequence,
                sites=sites,
                time_step=0.2,
                hopping=1.0,
                interaction=3.0,
                chemical_potential=0.4,
                asymmetry=asymmetry,
            )
            partition_sum += weight.total
        partition_sums.append(partition_sum)

    assert np.allclose(partition_sums, partition_sums[0], rtol=1e-13, atol=1e-13)


def test_tn_gaussian_fock_matrix_is_entrywise_nonnegative() -> None:
    decomposition = asymmetric_tn_bond_decomposition(
        time_step=0.2,
        hopping=1.0,
        interaction=3.0,
        asymmetry=0.6,
    )
    one_particle = (
        embed_adjacent_bond(
            decomposition.propagator_plus,
            sites=3,
            left_site=0,
        )
        @ embed_adjacent_bond(
            decomposition.propagator_minus,
            sites=3,
            left_site=1,
        )
    )
    fock_matrix = number_conserving_gaussian_fock_matrix(one_particle)

    assert np.min(fock_matrix) >= -1e-13


def test_nonadjacent_hopping_obstructs_any_positive_tn_gaussian_sum() -> None:
    sites = 3
    dimension = 1 << sites

    def annihilation(mode: int) -> np.ndarray:
        operator = np.zeros((dimension, dimension))
        lower_bits = (1 << mode) - 1
        for state in range(dimension):
            if state & (1 << mode):
                parity = (state & lower_bits).bit_count()
                output = state ^ (1 << mode)
                operator[output, state] = -1.0 if parity % 2 else 1.0
        return operator

    annihilators = [annihilation(mode) for mode in range(sites)]
    creators = [operator.T for operator in annihilators]
    hopping_hamiltonian = -(
        creators[0] @ annihilators[2] + creators[2] @ annihilators[0]
    )
    physical_gate = expm(-0.1 * hopping_hamiltonian)

    one_particle_input = 1 << 2
    one_particle_output = 1 << 0
    two_particle_input = (1 << 1) | (1 << 2)
    two_particle_output = (1 << 0) | (1 << 1)
    assert physical_gate[one_particle_output, one_particle_input] > 0.0
    assert physical_gate[two_particle_output, two_particle_input] < 0.0


@pytest.mark.parametrize(
    ("keyword", "value", "message"),
    [
        ("time_step", 0.0, "time_step"),
        ("hopping", -1.0, "hopping"),
        ("interaction", -1.0, "interaction"),
        ("asymmetry", -0.1, "asymmetry"),
        ("asymmetry", 1.0, "asymmetry"),
    ],
)
def test_invalid_decomposition_parameters_are_rejected(
    keyword: str,
    value: float,
    message: str,
) -> None:
    parameters = {
        "time_step": 0.2,
        "hopping": 1.0,
        "interaction": 3.0,
        "chemical_potential": 0.0,
        "asymmetry": 0.5,
    }
    parameters[keyword] = value
    with pytest.raises(ValueError, match=message):
        asymmetric_tn_bond_decomposition(**parameters)
