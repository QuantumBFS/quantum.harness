"""Rooted graph patches for the three geometries in issue #92."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True)
class Geometry:
    key: str
    label: str
    p: int
    q: int
    coordination: int
    line_graph: bool = False


GEOMETRIES = {
    "83": Geometry("83", "{8,3}", 8, 3, 3),
    "124": Geometry("124", "{12,4}", 12, 4, 4),
    "line83": Geometry("line83", "L({8,3})", 8, 3, 4, line_graph=True),
}


def _canonical_key(name: str) -> str:
    compact = name.lower().replace(" ", "").replace("{", "").replace("}", "")
    compact = compact.replace(",", "").replace("(", "").replace(")", "")
    aliases = {
        "83": "83",
        "8,3": "83",
        "124": "124",
        "12,4": "124",
        "line83": "line83",
        "l83": "line83",
        "l8,3": "line83",
    }
    try:
        return aliases[compact]
    except KeyError as error:
        raise ValueError(f"unknown geometry {name!r}; choose from {tuple(GEOMETRIES)}") from error


def rooted_radius_one(name: str) -> nx.Graph:
    """Return the exact induced radius-one ball, rooted at node zero.

    The two regular tilings have no edges among the root's neighbors because
    their girths are 8 and 12. In the line graph, the four neighboring edges
    form two pairs, one pair at each endpoint of the root edge.
    """
    key = _canonical_key(name)
    geometry = GEOMETRIES[key]
    graph = nx.Graph(
        geometry=key,
        label=geometry.label,
        root=0,
        radius=1,
        source="exact_local_combinatorics",
        infinite_coordination=geometry.coordination,
    )
    graph.add_nodes_from(range(geometry.coordination + 1))
    graph.add_edges_from((0, neighbor) for neighbor in range(1, geometry.coordination + 1))
    if geometry.line_graph:
        graph.add_edges_from(((1, 2), (3, 4)))
    return graph


def _hypertiling_parent(p: int, q: int, radius: int) -> nx.Graph:
    """Generate a site graph for {p,q} using the dual cell-adjacency graph.

    `hypertiling.HyperbolicGraph(a,b,...)` represents adjacency of the cells of
    {a,b}, whose degree is a.  The cell-adjacency graph of the dual {q,p} is
    combinatorially the vertex graph of {p,q}.
    """
    try:
        from hypertiling import HyperbolicGraph
    except ImportError as error:
        raise RuntimeError("install requirements.txt to use genuine hyperbolic patches") from error

    reflective_layers = radius + 3
    raw = HyperbolicGraph(q, p, reflective_layers, kernel="GRC")
    neighbors = raw.get_nbrs_list()
    graph = nx.Graph(source="hypertiling-1.x-dual-GRC", p=p, q=q, raw_nodes=len(neighbors))
    graph.add_nodes_from(range(len(neighbors)))
    for site, site_neighbors in enumerate(neighbors):
        graph.add_edges_from((site, int(neighbor)) for neighbor in site_neighbors)
    return graph


def _relabel_root_first(graph: nx.Graph, root: object, **attributes: object) -> nx.Graph:
    distances = nx.single_source_shortest_path_length(graph, root)
    ordered = sorted(graph.nodes, key=lambda node: (distances.get(node, 10**9), repr(node)))
    mapping = {node: index for index, node in enumerate(ordered)}
    result = nx.relabel_nodes(graph, mapping, copy=True)
    result.graph.update(root=0, **attributes)
    return result


def hyperbolic_rooted_ball(name: str, radius: int) -> nx.Graph:
    """Generate a genuine rooted ball with `hypertiling`, optionally line-graph it."""
    if radius < 1:
        raise ValueError("radius must be at least one")
    key = _canonical_key(name)
    geometry = GEOMETRIES[key]
    # The line-graph radius-r ball needs parent edges just beyond its boundary.
    parent_radius = radius + 1 if geometry.line_graph else radius
    parent_raw = _hypertiling_parent(geometry.p, geometry.q, parent_radius)

    if geometry.line_graph:
        root_neighbor = min(parent_raw.neighbors(0))
        root_edge = tuple(sorted((0, root_neighbor)))
        raw_graph = nx.line_graph(parent_raw)
        distances = nx.single_source_shortest_path_length(raw_graph, root_edge, cutoff=radius)
        selected = list(distances)
        induced = raw_graph.subgraph(selected).copy()
        result = _relabel_root_first(induced, root_edge)
    else:
        selected = nx.single_source_shortest_path_length(parent_raw, 0, cutoff=radius)
        induced = parent_raw.subgraph(selected).copy()
        result = _relabel_root_first(induced, 0)

    result.graph.update(
        geometry=key,
        label=geometry.label,
        radius=radius,
        source="hypertiling-1.x-dual-GRC",
        infinite_coordination=geometry.coordination,
    )
    if result.degree[0] != geometry.coordination:
        raise RuntimeError(
            f"generated root degree {result.degree[0]} does not equal {geometry.coordination}"
        )
    return result


def graph_summary(graph: nx.Graph) -> dict[str, object]:
    """Return JSON-friendly combinatorial diagnostics."""
    root = int(graph.graph.get("root", 0))
    degrees = [degree for _, degree in graph.degree]
    return {
        "geometry": graph.graph.get("geometry", "unknown"),
        "label": graph.graph.get("label", "unknown"),
        "source": graph.graph.get("source", "unknown"),
        "radius": int(graph.graph.get("radius", -1)),
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "root_degree": graph.degree[root],
        "degree_min": min(degrees),
        "degree_max": max(degrees),
        "triangles_at_root": nx.triangles(graph, root),
    }
