from __future__ import annotations

from itertools import product
import math

import numpy as np
import pytest
from scipy.linalg import expm

from oracle.grade_charge_model import (
    extended_edge_fock_vertex,
    extended_edge_propagator,
    extended_edge_real_generator,
    fugacities_are_uniformly_safe,
    fugacity_safety_bounds,
    grade_charge_model,
    grade_charge_fock_hamiltonian,
    grade_charge_history_weight,
    physical_edge_propagator,
    triangle_grade_charge_model,
    unsafe_fugacity_witness_edge,
    vertex_mode_support,
)
from oracle.graded_monomial import fermion_annihilation_operator
from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


TRIANGLE_LAYOUTS = ("global", "per_edge", "partitioned")


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_model_validation_rejects_nonfinite_parameters(
    bad_value: float,
) -> None:
    with pytest.raises(ValueError, match="dilations"):
        grade_charge_model(
            physical_modes=3,
            edges=((0, 1),),
            dilations=(bad_value,),
            couplings=(0.7,),
            grade_groups=(0,),
        )
    with pytest.raises(ValueError, match="couplings"):
        grade_charge_model(
            physical_modes=3,
            edges=((0, 1),),
            dilations=(1.2,),
            couplings=(bad_value,),
            grade_groups=(0,),
        )


@pytest.mark.parametrize(
    ("layout", "expected_groups", "expected_total_modes"),
    [
        ("global", (0, 0, 0), 4),
        ("per_edge", (0, 1, 2), 6),
        ("partitioned", (0, 0, 1), 5),
    ],
)
def test_triangle_layouts_have_expected_grade_modes(
    layout: str,
    expected_groups: tuple[int, int, int],
    expected_total_modes: int,
) -> None:
    model = triangle_grade_charge_model(layout)

    assert model.edges == ((0, 1), (1, 2), (0, 2))
    assert model.grade_groups == expected_groups
    assert model.total_modes == expected_total_modes


@pytest.mark.parametrize("layout", TRIANGLE_LAYOUTS)
def test_triangle_vertices_are_hermitian_real_exponentials_with_three_mode_support(
    layout: str,
) -> None:
    model = triangle_grade_charge_model(layout)
    hamiltonian = grade_charge_fock_hamiltonian(model)

    assert np.allclose(hamiltonian, hamiltonian.T, atol=1e-12)
    for edge_index, (left, right) in enumerate(model.edges):
        propagator = extended_edge_propagator(model, edge_index)
        generator = extended_edge_real_generator(model, edge_index)
        vertex = extended_edge_fock_vertex(model, edge_index)
        expected_support = tuple(
            sorted((left, right, model.ancilla_mode(edge_index)))
        )

        assert np.allclose(propagator, propagator.T, atol=1e-13)
        assert np.allclose(expm(generator), propagator, atol=1e-11)
        assert np.allclose(vertex, vertex.T, atol=1e-12)
        assert vertex_mode_support(model, edge_index) == expected_support

        for outside_mode in (
            mode
            for mode in range(model.total_modes)
            if mode not in expected_support
        ):
            annihilator = fermion_annihilation_operator(
                sites=model.total_modes,
                mode=outside_mode,
            )
            number = annihilator.T @ annihilator
            assert np.linalg.norm(vertex @ number - number @ vertex) < 1e-11


def test_global_occupied_ancilla_block_matches_the_projected_model() -> None:
    model = triangle_grade_charge_model("global")
    full_hamiltonian = grade_charge_fock_hamiltonian(model)
    occupied_indices = tuple(
        physical_state | (1 << model.physical_modes)
        for physical_state in range(1 << model.physical_modes)
    )
    occupied_block = full_hamiltonian[
        np.ix_(occupied_indices, occupied_indices)
    ]
    expected = np.zeros_like(occupied_block)
    for edge_index, (coupling, dilation) in enumerate(
        zip(model.couplings, model.dilations, strict=True)
    ):
        expected += (
            coupling
            * dilation
            * number_conserving_gaussian_fock_matrix(
                physical_edge_propagator(model, edge_index)
            )
        )

    assert np.allclose(occupied_block, expected, atol=1e-12)


@pytest.mark.parametrize("layout", TRIANGLE_LAYOUTS)
@pytest.mark.parametrize(
    "history",
    [
        (),
        (0,),
        (2,),
        (0, 1),
        (2, 1, 0),
        (0, 1, 2, 0),
    ],
)
def test_direct_fock_trace_matches_closed_history_formula(
    layout: str,
    history: tuple[int, ...],
) -> None:
    model = triangle_grade_charge_model(layout)
    fugacities = tuple(
        1.0 + 0.2 * group for group in range(model.group_count)
    )
    weight = grade_charge_history_weight(
        model,
        history,
        fugacities=fugacities,
        beta=0.7,
    )

    assert weight.direct_fock_trace is not None
    assert math.isclose(
        weight.direct_fock_trace,
        weight.closed_form_trace,
        rel_tol=1e-10,
        abs_tol=1e-10,
    )
    assert math.isclose(
        weight.direct_extended_determinant,
        weight.closed_form_trace,
        rel_tol=1e-10,
        abs_tol=1e-10,
    )
    assert weight.taylor_prefactor > 0.0
    assert weight.total_weight >= -1e-10


@pytest.mark.parametrize("layout", TRIANGLE_LAYOUTS)
def test_all_triangle_histories_through_depth_six_are_nonnegative(
    layout: str,
) -> None:
    model = triangle_grade_charge_model(layout)
    checked = 0

    for depth in range(1, 7):
        for history in product(range(len(model.edges)), repeat=depth):
            weight = grade_charge_history_weight(
                model,
                history,
                compute_direct_fock_trace=False,
            )
            assert weight.direct_fock_trace is None
            assert weight.closed_form_trace >= -1e-9
            assert weight.direct_extended_determinant >= -1e-9
            assert weight.total_weight >= -1e-9
            checked += 1

    assert checked == 1092


@pytest.mark.parametrize("layout", TRIANGLE_LAYOUTS)
def test_fugacities_at_least_one_preserve_positive_depth_regression(
    layout: str,
) -> None:
    model = triangle_grade_charge_model(layout)
    fugacities = tuple(
        1.0 + 0.3 * group for group in range(model.group_count)
    )

    assert fugacities_are_uniformly_safe(model, fugacities)
    for depth in range(1, 6):
        for history in product(range(len(model.edges)), repeat=depth):
            weight = grade_charge_history_weight(
                model,
                history,
                fugacities=fugacities,
                compute_direct_fock_trace=False,
            )
            assert weight.total_weight >= -1e-9


def test_subunit_fugacity_has_a_sharp_safe_and_unsafe_boundary() -> None:
    model = triangle_grade_charge_model("global")
    (bound,) = fugacity_safety_bounds(model)
    safe_subunit = (0.9,)
    boundary = (bound,)
    unsafe = (0.5,)

    assert math.isclose(bound, 1.0 / min(model.dilations))
    assert bound < safe_subunit[0] < 1.0
    assert fugacities_are_uniformly_safe(model, safe_subunit)
    assert fugacities_are_uniformly_safe(model, boundary)
    assert not fugacities_are_uniformly_safe(model, unsafe)
    assert unsafe_fugacity_witness_edge(model, safe_subunit) is None
    assert unsafe_fugacity_witness_edge(model, unsafe) == 0

    for depth in range(1, 5):
        for history in product(range(len(model.edges)), repeat=depth):
            assert (
                grade_charge_history_weight(
                    model,
                    history,
                    fugacities=safe_subunit,
                    compute_direct_fock_trace=False,
                ).total_weight
                >= -1e-9
            )

    zero_weight = grade_charge_history_weight(
        model,
        (0,),
        fugacities=boundary,
    )
    negative_weight = grade_charge_history_weight(
        model,
        (0,),
        fugacities=unsafe,
    )

    assert abs(zero_weight.total_weight) < 1e-12
    assert negative_weight.physical_determinant < 0.0
    assert negative_weight.ancilla_factor > 0.0
    assert negative_weight.closed_form_trace < 0.0
    assert negative_weight.direct_fock_trace is not None
    assert negative_weight.direct_fock_trace < 0.0
    assert math.isclose(
        negative_weight.direct_fock_trace,
        negative_weight.closed_form_trace,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_partitioned_layout_detects_the_specific_unsafe_group() -> None:
    model = triangle_grade_charge_model("partitioned")
    bounds = fugacity_safety_bounds(model)
    fugacities = (1.0, 0.4)
    witness = unsafe_fugacity_witness_edge(model, fugacities)

    assert bounds == pytest.approx((1.0 / 1.2, 1.0 / 1.7))
    assert witness == 2
    weight = grade_charge_history_weight(
        model,
        (witness,),
        fugacities=fugacities,
    )
    assert weight.total_weight < 0.0
