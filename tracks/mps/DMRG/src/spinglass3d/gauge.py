"""Gauge transformations and canonical graph-loop encodings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from .model import EABonds


Edge = tuple[int, int]


def _edge_key(edge: Sequence[int]) -> Edge:
    if len(edge) != 2:
        raise ValueError("an edge must contain two vertices")
    left, right = (int(edge[0]), int(edge[1]))
    if left == right:
        raise ValueError("self edges are not allowed")
    return (left, right) if left < right else (right, left)


def _validated_edges(edge_signs: Mapping[Sequence[int], int]) -> dict[Edge, int]:
    result: dict[Edge, int] = {}
    for edge, sign in edge_signs.items():
        key = _edge_key(edge)
        value = int(sign)
        if value not in (-1, 1):
            raise ValueError("edge signs must be -1 or +1")
        if key in result:
            raise ValueError("duplicate graph edge")
        result[key] = value
    if not result:
        raise ValueError("edge graph must not be empty")
    return result


def gauge_transform(bonds: EABonds, epsilon: np.ndarray) -> EABonds:
    """Apply J_xy -> epsilon_x epsilon_y J_xy on a periodic cubic lattice."""
    if not isinstance(bonds, EABonds):
        raise TypeError("bonds must be EABonds")
    field = np.asarray(epsilon)
    expected = (bonds.length,) * 3
    if field.shape != expected:
        raise ValueError(f"epsilon must have shape {expected}")
    if not np.all((field == -1) | (field == 1)):
        raise ValueError("epsilon must contain only -1 and +1")
    field = field.astype(np.int8, copy=False)
    values = np.empty_like(bonds.values)
    for axis in range(3):
        values[..., axis] = (
            bonds.values[..., axis]
            * field
            * np.roll(field, -1, axis=axis)
        )
    return EABonds(values)


def gauge_fixed_edges(
    edge_signs: Mapping[Sequence[int], int],
    tree_edges: Sequence[Sequence[int]],
) -> dict[Edge, int]:
    """Return the unique root-fixed gauge with every selected tree edge +1."""
    edges = _validated_edges(edge_signs)
    tree = tuple(_edge_key(edge) for edge in tree_edges)
    if len(set(tree)) != len(tree):
        raise ValueError("tree edges must be unique")
    if any(edge not in edges for edge in tree):
        raise ValueError("every tree edge must belong to the graph")
    vertices = sorted({vertex for edge in edges for vertex in edge})
    if len(tree) != len(vertices) - 1:
        raise ValueError("tree must contain V-1 edges")

    adjacency: dict[int, list[int]] = {vertex: [] for vertex in vertices}
    for left, right in tree:
        adjacency[left].append(right)
        adjacency[right].append(left)
    epsilon = {vertices[0]: 1}
    stack = [vertices[0]]
    while stack:
        left = stack.pop()
        for right in adjacency[left]:
            if right in epsilon:
                continue
            epsilon[right] = epsilon[left] * edges[_edge_key((left, right))]
            stack.append(right)
    if len(epsilon) != len(vertices):
        raise ValueError("tree must connect the graph")

    fixed = {
        edge: sign * epsilon[edge[0]] * epsilon[edge[1]]
        for edge, sign in edges.items()
    }
    if any(fixed[edge] != 1 for edge in tree):
        raise AssertionError("tree gauge fixing failed")
    return fixed


def canonical_chords(
    edge_signs: Mapping[Sequence[int], int],
    tree_edges: Sequence[Sequence[int]],
) -> np.ndarray:
    """Emit sorted gauge-fixed non-tree signs for a connected graph."""
    fixed = gauge_fixed_edges(edge_signs, tree_edges)
    tree = {_edge_key(edge) for edge in tree_edges}
    chords = sorted(edge for edge in fixed if edge not in tree)
    values = np.asarray([fixed[edge] for edge in chords], dtype=np.int8)
    values.setflags(write=False)
    return values
