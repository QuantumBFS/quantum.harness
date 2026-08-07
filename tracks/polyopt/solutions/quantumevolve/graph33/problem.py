"""Immutable definition of the seven-observable graph-33 target."""

from __future__ import annotations

from itertools import combinations

PROBLEM_ID = "uncertainty-table4-graph33-v1"
VERTICES = tuple(range(7))

# Manually transcribed from Table 4 of arXiv:2310.00612.  Vertices are labelled
# left-to-right within the drawing; this edge list is part of the immutable
# evaluator, never candidate-controlled.
EDGES = frozenset(
    {
        (1, 3),
        (1, 2),
        (1, 5),
        (0, 2),
        (0, 4),
        (0, 6),
        (2, 3),
        (2, 6),
        (3, 4),
        (3, 5),
        (4, 5),
        (4, 6),
        (5, 6),
    }
)
EDGES = frozenset(tuple(sorted(edge)) for edge in EDGES)

PAPER_BOUNDS = {1: 2.2361, 2: 2.0363, 3: 2.0067, 7: 2.0013}
KNOWN_LOWER_BOUND = 2.0


def induced_edges(vertices: tuple[int, ...]) -> frozenset[tuple[int, int]]:
    selected = frozenset(vertices)
    return frozenset(edge for edge in EDGES if edge[0] in selected and edge[1] in selected)


def independence_number(
    vertices: tuple[int, ...] = VERTICES,
    edges: frozenset[tuple[int, int]] = EDGES,
) -> int:
    """Return alpha(G) by exhaustive search (only seven vertices here)."""
    edge_set = frozenset(tuple(sorted(edge)) for edge in edges)
    for size in range(len(vertices), -1, -1):
        for subset in combinations(vertices, size):
            if all(tuple(sorted(pair)) not in edge_set for pair in combinations(subset, 2)):
                return size
    raise AssertionError("unreachable")
