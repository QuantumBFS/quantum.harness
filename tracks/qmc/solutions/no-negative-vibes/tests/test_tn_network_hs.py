from __future__ import annotations

from itertools import combinations, product
import math

import numpy as np
import pytest

from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix
from oracle.tn_network_hs import (
    adjacent_jacobi_shear,
    embed_contiguous_propagator,
    hard_core_xy_vertex_operator,
    parity_string_vertex_from_gaussians,
    parity_string_vertex_operator,
    physical_parity_string_interaction,
    tn_parity_string_configuration_weight,
    tn_parity_string_decomposition,
)


def _all_square_minors(matrix: np.ndarray) -> list[float]:
    rows = matrix.shape[0]
    columns = matrix.shape[1]
    minors: list[float] = []
    for size in range(1, min(rows, columns) + 1):
        for row_subset in combinations(range(rows), size):
            for column_subset in combinations(range(columns), size):
                minors.append(
                    float(
                        np.linalg.det(
                            matrix[np.ix_(row_subset, column_subset)]
                        )
                    )
                )
    return minors


@pytest.mark.parametrize(
    ("first_weight", "second_weight"),
    [(0.2, 0.7), (1.0, 1.0), (2.0, 3.0)],
)
def test_four_gaussians_equal_the_parity_string_operator(
    first_weight: float,
    second_weight: float,
) -> None:
    gaussian_sum = parity_string_vertex_from_gaussians(
        first_weight=first_weight,
        second_weight=second_weight,
    )
    analytic_operator = parity_string_vertex_operator(
        first_weight=first_weight,
        second_weight=second_weight,
    )

    assert np.allclose(gaussian_sum, analytic_operator, atol=1e-13)
    assert np.allclose(analytic_operator, analytic_operator.T, atol=1e-14)


def test_every_auxiliary_field_and_contiguous_embedding_is_tn() -> None:
    decomposition = tn_parity_string_decomposition(
        first_weight=0.7,
        second_weight=1.3,
    )

    for local in decomposition.propagators:
        assert min(_all_square_minors(local)) >= -1e-13
        embedded = embed_contiguous_propagator(
            local,
            sites=6,
            left_site=2,
        )
        assert min(_all_square_minors(embedded)) >= -1e-13


def test_gaussian_fields_are_entrywise_nonnegative_in_full_fock_space() -> None:
    decomposition = tn_parity_string_decomposition(
        first_weight=0.7,
        second_weight=1.3,
    )

    for propagator in decomposition.propagators:
        gaussian = number_conserving_gaussian_fock_matrix(propagator)
        assert np.min(gaussian) >= -1e-13


def test_physical_vertex_contains_a_genuine_density_assisted_hopping() -> None:
    first_weight = 0.8
    second_weight = 1.1
    operator = parity_string_vertex_operator(
        first_weight=first_weight,
        second_weight=second_weight,
    )

    one_particle_input = 1 << 2
    one_particle_output = 1 << 0
    two_particle_input = (1 << 1) | (1 << 2)
    two_particle_output = (1 << 0) | (1 << 1)

    expected = first_weight * second_weight
    assert math.isclose(
        operator[one_particle_output, one_particle_input],
        expected,
    )
    assert math.isclose(
        operator[two_particle_output, two_particle_input],
        expected,
    )


def test_physical_interaction_is_hermitian_and_offdiagonal_nonpositive() -> None:
    interaction = physical_parity_string_interaction(
        coupling=1.7,
        first_weight=0.8,
        second_weight=1.1,
    )

    assert np.allclose(interaction, interaction.T, atol=1e-14)
    off_diagonal = interaction - np.diag(np.diag(interaction))
    assert np.max(off_diagonal) <= 1e-14


def test_jordan_wigner_maps_the_vertex_to_ferromagnetic_xy_hopping() -> None:
    parameters = {
        "first_weight": 0.8,
        "second_weight": 1.1,
    }

    assert np.array_equal(
        parity_string_vertex_operator(**parameters),
        hard_core_xy_vertex_operator(**parameters),
    )


def test_all_short_overlapping_histories_have_positive_weight() -> None:
    sites = 5
    left_sites = (0, 1, 2, 1)
    minimum_determinant = math.inf

    for fields in product(range(4), repeat=len(left_sites)):
        weight = tn_parity_string_configuration_weight(
            fields,
            left_sites,
            sites=sites,
            coupling=1.2,
            first_weight=0.7,
            second_weight=1.3,
        )
        minimum_determinant = min(minimum_determinant, weight.determinant)
        assert weight.total > 0.0

    assert minimum_determinant >= 1.0 - 1e-12


@pytest.mark.parametrize(
    ("function", "kwargs", "message"),
    [
        (
            adjacent_jacobi_shear,
            {"sites": 3, "row": 0, "column": 2, "weight": 1.0},
            "adjacent",
        ),
        (
            tn_parity_string_decomposition,
            {"first_weight": 0.0, "second_weight": 1.0},
            "positive",
        ),
        (
            physical_parity_string_interaction,
            {
                "coupling": 0.0,
                "first_weight": 1.0,
                "second_weight": 1.0,
            },
            "coupling",
        ),
    ],
)
def test_invalid_parameters_are_rejected(
    function: object,
    kwargs: dict[str, float | int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        function(**kwargs)  # type: ignore[operator]
