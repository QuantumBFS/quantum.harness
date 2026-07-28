from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from oracle.fock_basis import quadratic_term
from oracle.overlap_klein import (
    bridge_labels,
    overlap_geometry,
    quadratic_basis,
    support_edges,
)


def test_overlap_geometry_has_two_fixed_plaquettes_and_two_bridges() -> None:
    geometry = overlap_geometry()
    assert geometry.modes == 6
    assert geometry.blocks == ((0, 1, 2, 3), (2, 3, 4, 5))
    assert geometry.bridge_edges == ((0, 4), (1, 5))
    assert geometry.ring_edges == (
        (0, 1),
        (0, 3),
        (1, 2),
        (2, 3),
        (2, 5),
        (3, 4),
        (4, 5),
    )
    assert geometry.diagonal_edges == ((0, 2), (1, 3), (2, 4), (3, 5))


def test_overlap_geometry_is_immutable() -> None:
    geometry = overlap_geometry()
    with pytest.raises(FrozenInstanceError):
        geometry.modes = 7  # type: ignore[misc]


def test_support_masks_are_nested_and_do_not_become_complete_graph() -> None:
    rings = set(support_edges("rings"))
    bridges = set(support_edges("rings-bridges"))
    full = set(support_edges("rings-diagonals-bridges"))
    assert rings < bridges < full
    assert len(full) == 13
    assert (0, 5) not in full
    assert (1, 4) not in full


def test_support_edges_have_a_stable_lexicographic_order() -> None:
    assert support_edges("rings-diagonals-bridges") == (
        (0, 1),
        (0, 2),
        (0, 3),
        (0, 4),
        (1, 2),
        (1, 3),
        (1, 5),
        (2, 3),
        (2, 4),
        (2, 5),
        (3, 4),
        (3, 5),
        (4, 5),
    )


def test_number_conserving_basis_has_directed_hops_and_onsite_terms() -> None:
    basis = quadratic_basis("number-conserving", "rings-bridges")
    labels = {item.label for item in basis}
    assert len(basis) == 6 + 2 * 9
    assert {"n0", "h0<-1", "h1<-0", "h0<-4", "h4<-0"} <= labels
    assert all(item.kind == "hop" for item in basis)
    assert tuple(item.label for item in basis) == tuple(sorted(labels))


def test_basis_labels_map_to_the_intended_exact_quadratic_terms() -> None:
    basis = {
        item.label: item
        for item in quadratic_basis("bdg", "rings-bridges")
    }
    expected = {
        "n0": ("hop", 0, 0),
        "h0<-4": ("hop", 0, 4),
        "h4<-0": ("hop", 4, 0),
        "pc0,4": ("pair_create", 0, 4),
        "pa0,4": ("pair_annihilate", 0, 4),
    }
    for label, (kind, i, j) in expected.items():
        item = basis[label]
        assert (item.kind, item.i, item.j) == (kind, i, j)
        assert item.fock == quadratic_term(6, kind, i, j)


def test_bdg_basis_adds_independent_creation_and_annihilation_terms() -> None:
    number = quadratic_basis("number-conserving", "rings-bridges")
    bdg = quadratic_basis("bdg", "rings-bridges")
    labels = {item.label for item in bdg}
    assert len(bdg) == len(number) + 2 * len(support_edges("rings-bridges"))
    assert {"pc0,4", "pa0,4"} <= labels
    assert set(bridge_labels("bdg")) == {
        "h0<-4",
        "h4<-0",
        "pc0,4",
        "pa0,4",
        "h1<-5",
        "h5<-1",
        "pc1,5",
        "pa1,5",
    }


def test_number_conserving_bridge_labels_exclude_pairing_terms() -> None:
    assert bridge_labels("number-conserving") == (
        "h0<-4",
        "h1<-5",
        "h4<-0",
        "h5<-1",
    )


@pytest.mark.parametrize(
    "mask",
    ("", "rings-diagonals", "complete"),
)
def test_unknown_support_masks_are_rejected(mask: str) -> None:
    with pytest.raises(ValueError, match="unknown support mask"):
        support_edges(mask)


@pytest.mark.parametrize("family", ("", "hopping", "pairing"))
def test_unknown_quadratic_families_are_rejected(family: str) -> None:
    with pytest.raises(ValueError, match="unknown quadratic family"):
        quadratic_basis(family, "rings")
    with pytest.raises(ValueError, match="unknown quadratic family"):
        bridge_labels(family)
