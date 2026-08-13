from __future__ import annotations

from itertools import combinations
import math

import pytest

from oracle.compound_gauge import (
    all_fermion_sectors_are_gauge_nonnegative,
    enumerate_connected_graph_audit,
    fermion_sector_is_gauge_nonnegative,
)


@pytest.mark.parametrize("sites", range(2, 8))
def test_open_paths_are_balanced_in_every_fermion_sector(sites: int) -> None:
    path_edges = [(site, site + 1) for site in range(sites - 1)]
    assert all_fermion_sectors_are_gauge_nonnegative(
        sites=sites,
        edges=path_edges,
    )


@pytest.mark.parametrize(
    ("sites", "edges"),
    [
        (3, [(0, 1), (1, 2), (2, 0)]),
        (4, [(0, 1), (1, 2), (2, 3), (3, 0)]),
        (4, [(0, 1), (0, 2), (0, 3)]),
    ],
)
def test_cycle_and_branch_motifs_are_frustrated_in_two_particle_sector(
    sites: int,
    edges: list[tuple[int, int]],
) -> None:
    assert not fermion_sector_is_gauge_nonnegative(
        sites=sites,
        edges=edges,
        particles=2,
    )


@pytest.mark.parametrize("sites", range(2, 6))
def test_exhaustive_connected_survivors_are_exactly_labelled_paths(
    sites: int,
) -> None:
    result = enumerate_connected_graph_audit(sites)
    expected_paths = math.factorial(sites) // 2

    assert result["all_sector_gauge_nonnegative"] == expected_paths
    assert result["labelled_paths"] == expected_paths


def test_complete_graph_fails_once_exchange_is_possible() -> None:
    sites = 5
    assert not all_fermion_sectors_are_gauge_nonnegative(
        sites=sites,
        edges=list(combinations(range(sites), 2)),
    )
