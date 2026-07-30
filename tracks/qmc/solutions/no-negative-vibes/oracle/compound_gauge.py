"""Gauge-balance audit for fermionic additive-compound hopping sectors."""

from __future__ import annotations

import argparse
from itertools import combinations
import math
from typing import Iterable


Edge = tuple[int, int]


def _canonical_edges(sites: int, edges: Iterable[Edge]) -> frozenset[Edge]:
    if sites < 1:
        raise ValueError("sites must be positive")
    canonical: set[Edge] = set()
    for raw_left, raw_right in edges:
        left = int(raw_left)
        right = int(raw_right)
        if not 0 <= left < sites or not 0 <= right < sites:
            raise ValueError("edge endpoint is outside the graph")
        if left == right:
            raise ValueError("self edges are not supported")
        canonical.add((min(left, right), max(left, right)))
    return frozenset(canonical)


def fermion_sector_is_gauge_nonnegative(
    *,
    sites: int,
    edges: Iterable[Edge],
    particles: int,
) -> bool:
    """Return whether one fixed sign gauge removes all hopping-edge signs.

    The vertices are ordered occupation subsets.  An edge moves one fermion
    along an allowed one-particle edge, and its sign is the exterior-power
    orientation sign.  A gauge exists exactly when this signed configuration
    graph is balanced.
    """

    graph_edges = _canonical_edges(sites, edges)
    if not 0 <= particles <= sites:
        raise ValueError("particles must satisfy 0 <= particles <= sites")

    states = list(combinations(range(sites), particles))
    state_index = {state: index for index, state in enumerate(states)}
    adjacency: list[list[tuple[int, int]]] = [[] for _ in states]
    for column_index, column_state in enumerate(states):
        occupied = set(column_state)
        for removed in column_state:
            for added in range(sites):
                edge = (min(added, removed), max(added, removed))
                if added in occupied or edge not in graph_edges:
                    continue
                row_state = tuple(sorted((occupied - {removed}) | {added}))
                row_index = state_index[row_state]
                orientation = (
                    -1
                    if (
                        column_state.index(removed) + row_state.index(added)
                    )
                    % 2
                    else 1
                )
                adjacency[column_index].append((row_index, orientation))

    gauge: dict[int, int] = {}
    for root in range(len(states)):
        if root in gauge:
            continue
        gauge[root] = 1
        stack = [root]
        while stack:
            source = stack.pop()
            for target, orientation in adjacency[source]:
                required = orientation * gauge[source]
                if target in gauge:
                    if gauge[target] != required:
                        return False
                else:
                    gauge[target] = required
                    stack.append(target)
    return True


def all_fermion_sectors_are_gauge_nonnegative(
    *,
    sites: int,
    edges: Iterable[Edge],
) -> bool:
    """Check the fixed sign-gauge condition in every particle-number sector."""

    graph_edges = _canonical_edges(sites, edges)
    return all(
        fermion_sector_is_gauge_nonnegative(
            sites=sites,
            edges=graph_edges,
            particles=particles,
        )
        for particles in range(1, sites)
    )


def graph_is_connected(*, sites: int, edges: Iterable[Edge]) -> bool:
    """Return whether a simple graph reaches every vertex."""

    graph_edges = _canonical_edges(sites, edges)
    adjacency = [[] for _ in range(sites)]
    for left, right in graph_edges:
        adjacency[left].append(right)
        adjacency[right].append(left)
    seen = {0}
    stack = [0]
    while stack:
        for neighbor in adjacency[stack.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return len(seen) == sites


def graph_is_path(*, sites: int, edges: Iterable[Edge]) -> bool:
    """Return whether a connected labelled graph is one open path."""

    graph_edges = _canonical_edges(sites, edges)
    if not graph_is_connected(sites=sites, edges=graph_edges):
        return False
    degrees = [0] * sites
    for left, right in graph_edges:
        degrees[left] += 1
        degrees[right] += 1
    return len(graph_edges) == sites - 1 and max(degrees, default=0) <= 2


def enumerate_connected_graph_audit(sites: int) -> dict[str, int]:
    """Exhaust all labelled connected graphs at a small fixed size."""

    if sites < 2:
        raise ValueError("the connected-graph audit starts at two sites")
    possible_edges = list(combinations(range(sites), 2))
    connected_count = 0
    balanced_count = 0
    path_count = 0
    for edge_mask in range(1 << len(possible_edges)):
        edges = [
            edge
            for index, edge in enumerate(possible_edges)
            if edge_mask & (1 << index)
        ]
        if not graph_is_connected(sites=sites, edges=edges):
            continue
        connected_count += 1
        if graph_is_path(sites=sites, edges=edges):
            path_count += 1
        if all_fermion_sectors_are_gauge_nonnegative(
            sites=sites,
            edges=edges,
        ):
            balanced_count += 1
    return {
        "sites": sites,
        "connected_graphs": connected_count,
        "all_sector_gauge_nonnegative": balanced_count,
        "labelled_paths": path_count,
        "expected_labelled_paths": math.factorial(sites) // 2,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exhaust fermionic sector sign gauges on small graphs."
    )
    parser.add_argument("--max-sites", type=int, default=6)
    arguments = parser.parse_args()
    if arguments.max_sites < 2:
        parser.error("--max-sites must be at least two")

    print(
        "sites,connected_graphs,all_sector_gauge_nonnegative,"
        "labelled_paths,expected_labelled_paths"
    )
    for sites in range(2, arguments.max_sites + 1):
        result = enumerate_connected_graph_audit(sites)
        print(
            f"{result['sites']},{result['connected_graphs']},"
            f"{result['all_sector_gauge_nonnegative']},"
            f"{result['labelled_paths']},"
            f"{result['expected_labelled_paths']}"
        )


if __name__ == "__main__":
    main()
