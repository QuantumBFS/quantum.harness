from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from oracle.gauge_cocycle import (
    affine_phase_exponent,
    apply_gauge_hop,
    audit_all_legal_transitions,
    audit_constrained_gauge_hamiltonian,
    central_rung_locality,
    closed_legal_word_counts,
    compensation_radius,
    compensation_support_edges,
    constrained_gauge_hamiltonian,
    fermion_hop_sign_exponent,
    gauss_occupation_mask,
    hop_is_legal,
    ladder_gauge_instance,
    minimum_legal_compensation,
)


SOLUTION_ROOT = Path(__file__).resolve().parents[1]


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


def test_checked_in_gauge_cocycle_certificate_matches_oracle() -> None:
    certificate = json.loads(
        (
            SOLUTION_ROOT / "fixtures" / "gauge_cocycle_certificates.json"
        ).read_text(encoding="utf-8")
    )
    square_audit = audit_all_legal_transitions(ladder_gauge_instance(2))
    overlap_audit = audit_all_legal_transitions(ladder_gauge_instance(3))

    assert certificate["protocol"] == "gauge-cocycle-ladder-v1"
    assert certificate["source_commit"] == (
        "b4d50afd47040bffbb06c934e85886052f3b4fe5"
    )
    assert certificate["square"] == square_audit.__dict__
    assert certificate["overlapping_plaquettes"][
        "closed_legal_words_depth_1_to_8"
    ] == list(
        closed_legal_word_counts(
            ladder_gauge_instance(3),
            maximum_depth=8,
        )
    )
    for key, value in overlap_audit.__dict__.items():
        assert certificate["overlapping_plaquettes"][key] == value
    assert certificate["central_rung_scaling"] == [
        central_rung_locality(columns)
        for columns in range(2, 11)
    ]


def test_square_constrained_hamiltonian_has_exact_link_basis_anchors() -> None:
    instance = ladder_gauge_instance(2)
    model = constrained_gauge_hamiltonian(
        instance,
        hopping_couplings=(2.0, 3.0, 5.0, 7.0),
        plaquette_couplings=(11.0,),
    )

    assert instance.edges == ((0, 1), (0, 2), (1, 3), (2, 3))
    assert model.matrix.shape == (16, 16)
    assert model.gauge_basis == tuple(range(16))
    assert model.occupation_basis[0] == 0
    assert model.occupation_basis[1] == 0b0011

    # The empty Gauss state has no legal matter hop, only the square flip.
    assert model.matrix[15, 0] == -11.0
    assert np.flatnonzero(model.matrix[:, 0]).tolist() == [15]

    # With link (0,1) set, exactly the two rungs can hop.
    assert model.matrix[3, 1] == -3.0
    assert model.matrix[5, 1] == -5.0
    assert model.matrix[14, 1] == -11.0
    assert np.flatnonzero(model.matrix[:, 1]).tolist() == [3, 5, 14]


def test_square_constrained_hamiltonian_is_exactly_stoquastic_and_reversible() -> None:
    model = constrained_gauge_hamiltonian(
        ladder_gauge_instance(2),
        hopping_couplings=(0.5, 1.0, 1.5, 2.0),
        plaquette_couplings=(0.75,),
        diagonal_energies=tuple(float(index) for index in range(16)),
    )
    audit = audit_constrained_gauge_hamiltonian(model)

    assert audit.basis_dimension == audit.expected_dimension == 16
    assert audit.directed_hopping_transitions == 32
    assert audit.directed_plaquette_transitions == 16
    assert audit.gauss_law_failures == 0
    assert audit.reverse_transition_failures == 0
    assert audit.hermiticity_error == 0.0
    assert audit.positive_offdiagonal_entries == 0
    assert np.array_equal(model.matrix, model.matrix.T)
    assert np.array_equal(np.diag(model.matrix), np.arange(16, dtype=float))


def test_constrained_hamiltonian_requires_positive_complete_couplings() -> None:
    instance = ladder_gauge_instance(2)

    with pytest.raises(ValueError, match="exactly 4"):
        constrained_gauge_hamiltonian(
            instance,
            hopping_couplings=(1.0,),
            plaquette_couplings=(1.0,),
        )
    with pytest.raises(ValueError, match="strictly positive"):
        constrained_gauge_hamiltonian(
            instance,
            hopping_couplings=(1.0, 1.0, 1.0, 0.0),
            plaquette_couplings=(1.0,),
        )
    with pytest.raises(ValueError, match="strictly positive"):
        constrained_gauge_hamiltonian(
            instance,
            hopping_couplings=(1.0, 1.0, 1.0, 1.0),
            plaquette_couplings=(-1.0,),
        )
