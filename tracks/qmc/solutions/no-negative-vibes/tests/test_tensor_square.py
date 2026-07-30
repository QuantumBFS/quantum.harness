from __future__ import annotations

from itertools import product
import json
import math
from pathlib import Path

import numpy as np
import sympy as sp

from oracle.tensor_square import (
    conformal_split_residual,
    independent_field_counterexample_exact,
    lifted_base_edge_generator,
    lifted_diagonal_field,
    plaquette_trotter_decomposition,
    square_kinetic_generator,
    tensor_square_density_fields,
    tensor_square_density_interaction_gate,
    tensor_square_history,
    tensor_square_weight,
    two_by_two_split_metric,
    two_by_two_weight_formula,
)
from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


SOLUTION_ROOT = Path(__file__).resolve().parents[1]


def test_tensor_square_history_is_closed_under_arbitrary_products() -> None:
    factors = (
        np.asarray([[1.2, 0.3], [-0.4, 0.9]]),
        np.asarray([[0.8, -0.7], [0.2, 1.4]]),
        np.asarray([[1.1, 0.5], [0.6, 0.7]]),
    )
    history = tensor_square_history(factors)
    base_product = np.eye(2)
    lifted_product = np.eye(4)
    for factor in factors:
        base_product = base_product @ factor
        lifted_product = lifted_product @ np.kron(factor, factor)

    assert np.allclose(history.base_product, base_product, atol=1e-14)
    assert np.allclose(history.lifted_product, lifted_product, atol=1e-14)
    assert np.allclose(
        history.lifted_product,
        np.kron(base_product, base_product),
        atol=1e-14,
    )
    assert history.weight >= -1e-12


def test_two_by_two_sum_of_squares_matches_direct_determinant() -> None:
    matrices = (
        np.asarray([[2.0, -3.0], [-3.0, 7.0]]),
        np.asarray([[0.0, -1.0], [1.0, 0.0]]),
        np.asarray([[1.2, 0.7], [-0.3, 0.8]]),
    )
    for matrix in matrices:
        direct = tensor_square_weight(matrix)
        formula = two_by_two_weight_formula(matrix)
        assert math.isclose(direct, formula, rel_tol=1e-11, abs_tol=1e-11)
        assert formula >= 0.0


def test_two_by_two_tensor_square_is_conformal_split_orthogonal() -> None:
    metric = two_by_two_split_metric()
    eigenvalues = np.linalg.eigvalsh(metric)
    matrices = (
        np.asarray([[2.0, -3.0], [-3.0, 7.0]]),
        np.asarray([[1.2, 0.7], [-0.3, 0.8]]),
    )

    assert np.count_nonzero(eigenvalues > 0.0) == 2
    assert np.count_nonzero(eigenvalues < 0.0) == 2
    for matrix in matrices:
        assert conformal_split_residual(matrix) < 1e-12


def test_tensor_square_is_not_contained_in_the_p0_principal_minor_class() -> None:
    rotation = np.asarray([[0.0, -1.0], [1.0, 0.0]])
    lifted = np.kron(rotation, rotation)

    assert np.linalg.det(lifted[np.ix_((0, 3), (0, 3))]) == -1.0
    assert tensor_square_weight(rotation) == 0.0


def test_independent_onsite_field_has_an_exact_negative_counterexample() -> None:
    counterexample = independent_field_counterexample_exact()

    assert counterexample.weight == -sp.Rational(155085, 32)
    assert counterexample.weight < 0
    assert all(matrix.is_positive_definite for matrix in counterexample.base_factors)


def test_diagonal_tensor_square_hs_is_an_exact_repulsive_density_gate() -> None:
    coupling = 0.7
    fields = tensor_square_density_fields(coupling)
    auxiliary_average = 0.5 * sum(
        (
            number_conserving_gaussian_fock_matrix(field)
            for field in fields.lifted_propagators
        ),
        start=np.zeros((16, 16)),
    )
    target = tensor_square_density_interaction_gate(coupling)

    assert np.allclose(auxiliary_average, target, atol=1e-13)
    assert fields.kappa == math.log(math.cosh(2.0 * coupling))
    assert fields.repulsive_coupling == 2.0 * fields.kappa
    assert fields.chemical_potential == fields.kappa


def test_square_kinetic_generator_has_four_cycle_support() -> None:
    generator = square_kinetic_generator(hopping=1.3)
    nonzero_edges = {
        (row, column)
        for row in range(4)
        for column in range(row + 1, 4)
        if abs(generator[row, column]) > 1e-14
    }

    assert nonzero_edges == {(0, 1), (0, 2), (1, 3), (2, 3)}
    assert np.allclose(generator, generator.T)


def test_positive_gaussian_average_is_exact_symmetric_trotter_gate() -> None:
    decomposition = plaquette_trotter_decomposition(
        time_step=0.2,
        hopping=1.1,
        field_coupling=0.6,
    )
    auxiliary_average = 0.5 * sum(
        decomposition.fock_field_gates,
        start=np.zeros((16, 16)),
    )
    sandwich = (
        decomposition.fock_half_kinetic
        @ decomposition.interaction_gate
        @ decomposition.fock_half_kinetic
    )

    assert np.allclose(auxiliary_average, sandwich, atol=1e-12)
    assert np.allclose(auxiliary_average, auxiliary_average.T, atol=1e-12)
    assert np.min(np.linalg.eigvalsh(auxiliary_average)) > 0.0


def test_plaquette_fields_are_noncommuting_and_outside_ordinary_tn() -> None:
    decomposition = plaquette_trotter_decomposition(
        time_step=0.2,
        hopping=1.1,
        field_coupling=0.6,
    )
    first, second = decomposition.base_field_propagators
    commutator = first @ second - second @ first
    lifted = decomposition.lifted_field_propagators[0]
    second_order_minors = [
        np.linalg.det(lifted[np.ix_(rows, columns)])
        for rows in product(range(4), repeat=2)
        for columns in product(range(4), repeat=2)
        if rows[0] < rows[1] and columns[0] < columns[1]
    ]

    assert np.linalg.norm(commutator) > 0.9
    assert min(second_order_minors) < -0.4


def test_all_short_noncommuting_plaquette_histories_have_positive_weight() -> None:
    decomposition = plaquette_trotter_decomposition(
        time_step=0.2,
        hopping=1.1,
        field_coupling=0.6,
    )
    fields = decomposition.base_field_propagators

    for depth in range(1, 9):
        for history in product(range(2), repeat=depth):
            result = tensor_square_history(
                tuple(fields[index] for index in history)
            )
            assert result.weight > 0.0


def test_local_base_operations_lift_to_system_size_strips() -> None:
    for base_dimension in (2, 3, 5):
        edge_generator = lifted_base_edge_generator(
            base_dimension=base_dimension,
            edge=(0, 1),
            coupling=1.0,
        )
        undirected_edges = sum(
            abs(edge_generator[row, column]) > 1e-14
            for row in range(edge_generator.shape[0])
            for column in range(row + 1, edge_generator.shape[1])
        )
        diagonal = lifted_diagonal_field(
            np.asarray([1.0, -1.0] + [0.0] * (base_dimension - 2))
        )

        assert undirected_edges == 2 * base_dimension
        assert np.count_nonzero(diagonal) == 4 * base_dimension - 6


def test_checked_in_tensor_square_certificate_matches_oracle() -> None:
    certificate_path = (
        SOLUTION_ROOT / "fixtures" / "tensor_square_certificates.json"
    )
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    counterexample = independent_field_counterexample_exact()
    decomposition = plaquette_trotter_decomposition(
        time_step=certificate["plaquette"]["time_step"],
        hopping=certificate["plaquette"]["hopping"],
        field_coupling=certificate["plaquette"]["field_coupling"],
    )
    density_fields = tensor_square_density_fields(
        certificate["plaquette"]["field_coupling"]
    )
    first, second = decomposition.base_field_propagators
    commutator_norm = np.linalg.norm(first @ second - second @ first)
    lifted = decomposition.lifted_field_propagators[0]
    minimum_second_order_minor = min(
        np.linalg.det(lifted[np.ix_(rows, columns)])
        for rows in product(range(4), repeat=2)
        for columns in product(range(4), repeat=2)
        if rows[0] < rows[1] and columns[0] < columns[1]
    )
    short_history_weights = [
        tensor_square_history(
            tuple(
                decomposition.base_field_propagators[index]
                for index in history
            )
        ).weight
        for depth in range(1, 9)
        for history in product(range(2), repeat=depth)
    ]

    assert certificate["protocol"] == "tensor-square-plaquette-v1"
    assert certificate["source_commit"] == (
        "37f69a3992925b598b8c2a75428185012678af7c"
    )
    assert sp.Rational(
        certificate["exact_independent_field_counterexample"]["weight"]
    ) == counterexample.weight
    assert math.isclose(
        certificate["plaquette"]["kappa"],
        density_fields.kappa,
        rel_tol=0.0,
        abs_tol=1e-14,
    )
    assert math.isclose(
        certificate["plaquette"]["repulsive_gate_coupling"],
        density_fields.repulsive_coupling,
        rel_tol=0.0,
        abs_tol=1e-14,
    )
    assert math.isclose(
        certificate["plaquette"]["commutator_norm"],
        commutator_norm,
        rel_tol=0.0,
        abs_tol=1e-14,
    )
    assert math.isclose(
        certificate["plaquette"]["minimum_second_order_minor"],
        minimum_second_order_minor,
        rel_tol=0.0,
        abs_tol=1e-14,
    )
    assert certificate["plaquette"]["short_histories"] == len(
        short_history_weights
    )
    assert certificate["plaquette"]["short_history_negative_count"] == sum(
        weight < 0.0 for weight in short_history_weights
    )
    assert certificate["locality_counts"] == [
        {
            "base_dimension": dimension,
            "lifted_diagonal_support": 4 * dimension - 6,
            "lifted_hopping_edges": 2 * dimension,
        }
        for dimension in (2, 3, 5, 8)
    ]
