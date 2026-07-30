from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from oracle.fock_cp_screen import (
    all_tensorizations,
    analyze_tensorization,
    candidate_transform,
    klein_circuit_catalog,
    quadratic_directions,
    support_edges,
)

SOLUTION_ROOT = Path(__file__).resolve().parents[1]


def test_overlap_geometry_contains_two_declared_bridge_edges() -> None:
    edges = support_edges("rings-bridges")
    assert (0, 4) in edges
    assert (1, 5) in edges
    with pytest.raises(ValueError, match="unknown support mask"):
        support_edges("missing")


def test_number_conserving_and_bdg_bases_have_expected_bridge_directions() -> None:
    number_conserving = quadratic_directions(
        family="number-conserving",
        mask="rings-bridges",
    )
    bdg = quadratic_directions(
        family="bdg",
        mask="rings-bridges",
    )

    assert len(number_conserving) == 24
    assert len(bdg) == 42
    assert sum(direction.bridge for direction in number_conserving) == 4
    assert sum(direction.bridge for direction in bdg) == 8


def test_candidate_transforms_are_exactly_orthogonal_numerically() -> None:
    for name in (
        "identity",
        "overlap-klein",
        "klein:0",
        "klein:1",
        "klein:2",
        "klein:0,2",
    ):
        transform = candidate_transform(name)
        assert transform.shape == (64, 64)
        assert np.allclose(transform @ transform.T, np.eye(64), atol=1e-14)


def test_depth_two_klein_catalog_contains_thirteen_fixed_circuits() -> None:
    catalog = klein_circuit_catalog(maximum_depth=2)

    assert len(catalog) == 13
    assert catalog[0] == "identity"
    assert "klein:0,2" in catalog
    assert "klein:2,0" in catalog
    assert np.allclose(
        candidate_transform("klein:0,2"),
        candidate_transform("overlap-klein"),
        atol=1e-14,
    )


def test_six_mode_tensorization_catalog_has_twenty_bijections() -> None:
    tensorizations = all_tensorizations()

    assert len(tensorizations) == 20
    assert len(set(tensorizations)) == 20
    assert all(len(tensorization) == 3 for tensorization in tensorizations)


def test_identity_screen_returns_a_deterministic_hp_subspace_report() -> None:
    first = analyze_tensorization(
        transform_name="identity",
        family="number-conserving",
        mask="rings-bridges",
        ket_modes=(0, 1, 2),
        samples=8,
        seed=17,
    )
    second = analyze_tensorization(
        transform_name="identity",
        family="number-conserving",
        mask="rings-bridges",
        ket_modes=(0, 1, 2),
        samples=8,
        seed=17,
    )

    assert first == second
    assert first.basis_dimension == 24
    assert 0 <= first.hp_dimension <= first.basis_dimension
    assert 0 <= first.drift_dimension <= first.hp_dimension
    assert first.conditional_span_rank + first.drift_dimension == first.hp_dimension
    assert first.maximum_bridge_hp_projection >= 0.0


def test_committed_depth_two_screen_fixture_records_the_closed_finite_catalog() -> None:
    fixture = json.loads(
        (
            SOLUTION_ROOT
            / "fixtures"
            / "fock_cp_overlap_screen.json"
        ).read_text()
    )

    assert fixture["protocol"] == "fock-cp-overlap-v1"
    assert fixture["summary"] == {
        "cells": 520,
        "families": 2,
        "maximum_bridge_nullspace_projection": 6.980656370442376e-15,
        "sampled_bridge_ccp_cells": 0,
        "surviving_bridge_cells": 0,
        "tensorizations": 20,
        "transforms": 13,
    }
    assert fixture["interpretation"]["closed"].endswith("depth at most two")
    assert fixture["interpretation"]["open"].startswith("general non-Klein")
