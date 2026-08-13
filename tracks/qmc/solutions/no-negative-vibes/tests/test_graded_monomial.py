from __future__ import annotations

from itertools import permutations, product
import math

import numpy as np
import pytest
from scipy.linalg import expm

from oracle.graded_monomial import (
    ancilla_extended_real_generator,
    ancilla_extended_transposition_propagator,
    ancilla_graded_history_weight,
    dilated_transposition_propagator,
    fermion_annihilation_operator,
    graded_monomial_certificate,
    graded_transposition_history_weight,
    majorana_reflection_certificate,
    parameters_from_hopping_and_attraction,
    permutation_grade,
    positive_monomial_decomposition,
    site_sign_stoquastic_gauges,
    transposition_vertex_from_gaussian,
    transposition_vertex_operator,
)
from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


@pytest.mark.parametrize(
    ("sites", "first_mode", "second_mode", "dilation"),
    [
        (2, 0, 1, 1.2),
        (3, 0, 2, 1.7),
        (4, 1, 3, 2.1),
    ],
)
def test_gaussian_transposition_is_the_local_physical_vertex(
    sites: int,
    first_mode: int,
    second_mode: int,
    dilation: float,
) -> None:
    gaussian = transposition_vertex_from_gaussian(
        sites=sites,
        first_mode=first_mode,
        second_mode=second_mode,
        dilation=dilation,
    )
    analytic = transposition_vertex_operator(
        sites=sites,
        first_mode=first_mode,
        second_mode=second_mode,
        dilation=dilation,
    )

    assert np.allclose(gaussian, analytic, atol=1e-13)
    assert np.allclose(analytic, analytic.T, atol=1e-14)


def test_one_crossing_has_negative_determinant_but_positive_graded_weight() -> None:
    propagator = dilated_transposition_propagator(
        sites=3,
        first_mode=0,
        second_mode=2,
        dilation=1.7,
    )
    certificate = graded_monomial_certificate(propagator)
    direct = float(np.linalg.det(np.eye(3) + propagator))

    assert direct < 0.0
    assert certificate.permutation_grade == -1
    assert math.isclose(certificate.determinant, direct, abs_tol=1e-13)
    assert certificate.graded_determinant > 0.0


def test_one_ancilla_turns_each_crossing_into_a_real_exponential() -> None:
    parameters = {
        "sites": 4,
        "first_mode": 0,
        "second_mode": 2,
        "ancilla_mode": 3,
        "dilation": 1.7,
    }
    propagator = ancilla_extended_transposition_propagator(**parameters)
    generator = ancilla_extended_real_generator(**parameters)

    assert np.linalg.det(propagator) > 0.0
    assert np.allclose(expm(generator), propagator, atol=1e-13)


def test_occupied_ancilla_sector_stores_the_negative_scalar_grade() -> None:
    dilation = 1.7
    physical = dilated_transposition_propagator(
        sites=3,
        first_mode=0,
        second_mode=2,
        dilation=dilation,
    )
    extended = ancilla_extended_transposition_propagator(
        sites=4,
        first_mode=0,
        second_mode=2,
        ancilla_mode=3,
        dilation=dilation,
    )
    physical_fock = number_conserving_gaussian_fock_matrix(physical)
    extended_fock = number_conserving_gaussian_fock_matrix(extended)
    occupied_states = tuple(mask | (1 << 3) for mask in range(1 << 3))
    occupied_block = extended_fock[np.ix_(occupied_states, occupied_states)]

    assert np.allclose(
        occupied_block,
        -dilation * physical_fock,
        atol=1e-13,
    )


def test_cycle_factor_certificate_matches_direct_determinants() -> None:
    edge_types = (
        (0, 1, 1.2),
        (1, 2, 1.5),
        (0, 2, 2.0),
    )
    fields = [
        dilated_transposition_propagator(
            sites=3,
            first_mode=left,
            second_mode=right,
            dilation=dilation,
        )
        for left, right, dilation in edge_types
    ]

    for depth in range(7):
        for history in product(range(len(fields)), repeat=depth):
            propagator = np.eye(3)
            for field in history:
                propagator = fields[field] @ propagator
            certificate = graded_monomial_certificate(propagator)
            direct = float(np.linalg.det(np.eye(3) + propagator))

            assert math.isclose(
                certificate.determinant,
                direct,
                rel_tol=1e-11,
                abs_tol=1e-11,
            )
            assert certificate.graded_determinant >= 0.0


def test_every_four_mode_permutation_obeys_the_grade_certificate() -> None:
    dilations = (1.0, 1.1, 1.7, 2.3)

    for permutation in permutations(range(4)):
        matrix = np.zeros((4, 4), dtype=float)
        for column, row in enumerate(permutation):
            matrix[row, column] = dilations[column]
        certificate = graded_monomial_certificate(matrix)
        direct = float(np.linalg.det(np.eye(4) + matrix))

        assert certificate.permutation_grade == permutation_grade(permutation)
        assert math.isclose(
            certificate.determinant,
            direct,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        assert certificate.graded_determinant >= 0.0


def test_all_odd_cycle_histories_have_strictly_positive_total_weight() -> None:
    edge_types = (
        ((0, 1), 1.2, 0.7),
        ((1, 2), 1.5, 1.1),
        ((0, 2), 2.0, 0.4),
    )

    for depth in range(1, 8):
        for history in product(range(len(edge_types)), repeat=depth):
            edges = tuple(edge_types[index][0] for index in history)
            dilations = tuple(edge_types[index][1] for index in history)
            couplings = tuple(edge_types[index][2] for index in history)
            weight = graded_transposition_history_weight(
                edges,
                sites=3,
                dilations=dilations,
                couplings=couplings,
            )

            assert int(math.copysign(1.0, weight.scalar_prefactor)) == (
                weight.permutation_grade
            )
            assert weight.total > 0.0


def test_all_ancilla_extended_histories_have_positive_determinants() -> None:
    edge_types = (
        ((0, 1), 1.2, 0.7),
        ((1, 2), 1.5, 1.1),
        ((0, 2), 2.0, 0.4),
    )

    for depth in range(7):
        for history in product(range(len(edge_types)), repeat=depth):
            weight = ancilla_graded_history_weight(
                tuple(edge_types[index][0] for index in history),
                sites=4,
                ancilla_mode=3,
                dilations=tuple(
                    edge_types[index][1] for index in history
                ),
                couplings=tuple(
                    edge_types[index][2] for index in history
                ),
            )

            assert math.isclose(
                weight.determinant,
                weight.physical_determinant * weight.ancilla_factor,
                rel_tol=1e-10,
                abs_tol=1e-10,
            )
            assert int(math.copysign(1.0, weight.ancilla_factor)) == (
                weight.physical_permutation_grade
            )
            assert weight.total > 0.0


def test_positive_hopping_triangle_has_no_site_sign_stoquastic_gauge() -> None:
    triangle = ((0, 1), (1, 2), (0, 2))
    path = ((0, 1), (1, 2))

    assert site_sign_stoquastic_gauges(sites=3, edges=triangle) == ()
    assert site_sign_stoquastic_gauges(sites=3, edges=path) == (
        (1, -1, 1),
    )


@pytest.mark.parametrize(
    ("hopping", "attraction"),
    [(1.0, 0.2), (1.3, 2.7), (0.4, 8.0)],
)
def test_any_positive_hopping_and_attraction_can_be_realized(
    hopping: float,
    attraction: float,
) -> None:
    parameters = parameters_from_hopping_and_attraction(
        hopping=hopping,
        attraction=attraction,
    )

    assert parameters.coupling > 0.0
    assert parameters.dilation > 1.0
    assert math.isclose(parameters.hopping, hopping, rel_tol=1e-13)
    assert math.isclose(parameters.attraction, attraction, rel_tol=1e-13)


def test_physical_model_has_a_majorana_reflection_positivity_certificate() -> None:
    sites = 3
    edge_types = (
        ((0, 1), 1.2, 0.7),
        ((1, 2), 1.5, 1.1),
        ((0, 2), 2.0, 0.4),
    )
    certificate = majorana_reflection_certificate(
        tuple(edge[0] for edge in edge_types),
        sites=sites,
        dilations=tuple(edge[1] for edge in edge_types),
        couplings=tuple(edge[2] for edge in edge_types),
    )

    assert np.allclose(
        certificate.majorana_positive_block,
        -certificate.one_body_kernel,
    )
    assert np.linalg.eigvalsh(certificate.majorana_positive_block).min() >= -1e-12
    assert all(value < 0.0 for value in certificate.interaction_couplings)

    annihilators = [
        fermion_annihilation_operator(sites=sites, mode=mode)
        for mode in range(sites)
    ]
    creators = [operator.T for operator in annihilators]
    identity = np.eye(1 << sites)
    centered = certificate.constant_shift * identity
    for left in range(sites):
        for right in range(sites):
            centered += (
                certificate.one_body_kernel[left, right]
                * creators[left]
                @ annihilators[right]
            )
    for edge_index, (edge, _, _) in enumerate(edge_types):
        first_number = creators[edge[0]] @ annihilators[edge[0]]
        second_number = creators[edge[1]] @ annihilators[edge[1]]
        centered += certificate.interaction_couplings[edge_index] * (
            (first_number - 0.5 * identity)
            @ (second_number - 0.5 * identity)
        )

    direct = sum(
        (
            coupling
            * transposition_vertex_operator(
                sites=sites,
                first_mode=edge[0],
                second_mode=edge[1],
                dilation=dilation,
            )
            for edge, dilation, coupling in edge_types
        ),
        start=np.zeros((1 << sites, 1 << sites), dtype=float),
    )
    assert np.allclose(centered, direct, atol=1e-12)


def test_auxiliary_histories_equal_physical_taylor_coefficients() -> None:
    sites = 3
    edge_types = (
        ((0, 1), 1.2, 0.7),
        ((1, 2), 1.5, 1.1),
        ((0, 2), 2.0, 0.4),
    )
    hamiltonian = sum(
        (
            coupling
            * transposition_vertex_operator(
                sites=sites,
                first_mode=edge[0],
                second_mode=edge[1],
                dilation=dilation,
            )
            for edge, dilation, coupling in edge_types
        ),
        start=np.zeros((1 << sites, 1 << sites), dtype=float),
    )

    for order in range(5):
        direct = float(np.trace(np.linalg.matrix_power(-hamiltonian, order)))
        auxiliary = 0.0
        for history in product(range(len(edge_types)), repeat=order):
            weight = graded_transposition_history_weight(
                tuple(edge_types[index][0] for index in history),
                sites=sites,
                dilations=tuple(
                    edge_types[index][1] for index in history
                ),
                couplings=tuple(
                    edge_types[index][2] for index in history
                ),
            )
            auxiliary += weight.total

        assert math.isclose(
            auxiliary,
            direct,
            rel_tol=1e-11,
            abs_tol=1e-11,
        )


@pytest.mark.parametrize(
    ("function", "args", "message"),
    [
        (
            positive_monomial_decomposition,
            (np.ones((2, 2)),),
            "one nonzero",
        ),
        (
            graded_monomial_certificate,
            (np.diag([0.9, 1.2]),),
            "at least one",
        ),
        (
            permutation_grade,
            ((0, 0),),
            "exactly once",
        ),
    ],
)
def test_invalid_monomial_inputs_are_rejected(
    function: object,
    args: tuple[object, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        function(*args)  # type: ignore[operator]


def test_invalid_physical_parameters_are_rejected() -> None:
    with pytest.raises(ValueError, match="greater than one"):
        dilated_transposition_propagator(
            sites=3,
            first_mode=0,
            second_mode=1,
            dilation=1.0,
        )
    with pytest.raises(ValueError, match="hopping"):
        parameters_from_hopping_and_attraction(
            hopping=0.0,
            attraction=1.0,
        )
