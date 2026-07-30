"""Immutable definition of the seven-observable atlas-669 target.

This graph (atlas index 669 among 7-vertex graphs) has:
- 7 vertices, 11 edges
- independence number alpha = 2
- Lovasz theta = sqrt(5) ~ 2.2361
- Level-2 hierarchy value = 2.0000000027 (numerically closed)
- Level-3 hierarchy value = 2.0000000018 (numerically closed)

Corresponds to one of graphs 25-32 in Table 4 of arXiv:2310.00612.
"""

from __future__ import annotations

from itertools import combinations

PROBLEM_ID = "uncertainty-table4-atlas669-v1"
VERTICES = tuple(range(7))

# Edge list from networkx graph_atlas_g() index 669 (7-vertex graphs).
EDGES = frozenset(
    {
        (0, 1),
        (0, 2),
        (0, 3),
        (0, 4),
        (1, 2),
        (1, 6),
        (2, 6),
        (3, 4),
        (3, 5),
        (4, 5),
        (5, 6),
    }
)
EDGES = frozenset(tuple(sorted(edge)) for edge in EDGES)

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
