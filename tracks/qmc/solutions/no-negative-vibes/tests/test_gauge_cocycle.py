from __future__ import annotations

from oracle.gauge_cocycle import (
    affine_phase_exponent,
    apply_gauge_hop,
    audit_all_legal_transitions,
    central_rung_locality,
    closed_legal_word_counts,
    compensation_radius,
    compensation_support_edges,
    fermion_hop_sign_exponent,
    gauss_occupation_mask,
    hop_is_legal,
    ladder_gauge_instance,
    minimum_legal_compensation,
)


def test_square_and_shared_edge_ladder_geometry() -> None:
    square = ladder_gauge_instance(2)
    overlap = ladder_gauge_instance(3)

    assert square.sites == 4
    assert len(square.edges) == 4
    assert len(square.plaquettes) == 1
    assert overlap.sites == 6
    assert len(overlap.edges) == 7
    assert len(overlap.plaquettes) == 2
    assert overlap.edges[overlap.rung_edge_indices[1]] == (1, 4)


def test_gauss_law_is_preserved_by_matter_link_hop() -> None:
    instance = ladder_gauge_instance(3)
    for gauge_mask in range(1 << len(instance.edges)):
        occupation = gauss_occupation_mask(instance, gauge_mask)
        for edge_index in range(len(instance.edges)):
            if not hop_is_legal(instance, occupation, edge_index):
                continue
            new_occupation, new_gauge = apply_gauge_hop(
                instance,
                occupation,
                gauge_mask,
                edge_index,
            )
            assert new_occupation == gauss_occupation_mask(
                instance,
                new_gauge,
            )


def test_affine_gauge_phase_cancels_every_legal_fermion_hop_sign() -> None:
    instance = ladder_gauge_instance(3)
    for edge_index, edge in enumerate(instance.edges):
        compensation = minimum_legal_compensation(instance, edge_index)
        for gauge_mask in range(1 << len(instance.edges)):
            occupation = gauss_occupation_mask(instance, gauge_mask)
            if not hop_is_legal(instance, occupation, edge_index):
                continue
            assert affine_phase_exponent(
                compensation,
                gauge_mask,
            ) == fermion_hop_sign_exponent(occupation, edge)


def test_exhaustive_transition_audits_have_no_algebraic_failures() -> None:
    for columns, expected_states in ((2, 16), (3, 128)):
        audit = audit_all_legal_transitions(
            ladder_gauge_instance(columns)
        )
        assert audit.gauge_states == expected_states
        assert audit.legal_transitions > 0
        assert audit.sign_failures == 0
        assert audit.gauss_law_failures == 0
        assert audit.reverse_phase_failures == 0


def test_square_compensator_is_plaquette_local_but_not_link_local() -> None:
    instance = ladder_gauge_instance(2)
    edge_index = instance.rung_edge_indices[0]
    compensation = minimum_legal_compensation(instance, edge_index)

    assert compensation.coefficient_mask.bit_count() == 2
    assert compensation_radius(
        instance,
        edge_index,
        compensation.coefficient_mask,
    ) == 1
    assert set(compensation_support_edges(instance, compensation)) == {
        (0, 1),
        (1, 3),
    }


def test_two_overlapping_squares_require_the_whole_two_plaquette_patch() -> None:
    instance = ladder_gauge_instance(3)
    edge_index = instance.rung_edge_indices[1]
    compensation = minimum_legal_compensation(instance, edge_index)

    assert compensation.coefficient_mask.bit_count() == 4
    assert compensation_radius(
        instance,
        edge_index,
        compensation.coefficient_mask,
    ) == 1
    assert {
        instance.edges[index]
        for index in instance.rung_edge_indices
        if compensation.coefficient_mask & (1 << index)
    } == {(0, 3), (2, 5)}


def test_central_rung_compensation_grows_as_a_wilson_string() -> None:
    scaling = [central_rung_locality(columns) for columns in range(2, 11)]

    assert [row["phase_support"] for row in scaling] == [
        2,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
    ]
    assert [row["rung_variables_in_phase"] for row in scaling] == list(
        range(1, 10)
    )
    assert [row["locality_radius"] for row in scaling] == [
        1,
        1,
        2,
        2,
        3,
        3,
        4,
        4,
        5,
    ]


def test_closed_words_exist_and_all_step_signs_are_cancelled() -> None:
    instance = ladder_gauge_instance(3)
    counts = closed_legal_word_counts(instance, maximum_depth=8)

    assert counts[0] == 0
    assert counts[1] > 0
    assert all(count >= 0 for count in counts)
    assert all(counts[depth] == 0 for depth in range(0, 8, 2))
    assert all(counts[depth] > 0 for depth in range(1, 8, 2))
