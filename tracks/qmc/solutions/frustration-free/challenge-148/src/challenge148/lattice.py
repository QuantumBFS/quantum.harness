from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Literal

import jsonschema

from .provenance import canonical_json


@dataclass(frozen=True)
class PeriodicGraph:
    lattice: Literal["triangular", "honeycomb"]
    length: int
    site_count: int
    bonds: tuple[tuple[int, int], ...]


def _require_int(value: object, *, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int")
    return value


def _canonical_bond(left: int, right: int) -> tuple[int, int]:
    if left <= right:
        return (left, right)
    return (right, left)


def triangular_graph(length: int) -> PeriodicGraph:
    length = _require_int(length, name="length")
    if length < 3:
        raise ValueError("length must be at least 3")

    site_count = length * length
    bonds: set[tuple[int, int]] = set()

    directions = ((1, 0), (0, 1), (1, -1))
    for y in range(length):
        for x in range(length):
            left = x + length * y
            for dx, dy in directions:
                nx = (x + dx) % length
                ny = (y + dy) % length
                right = nx + length * ny
                if left == right:
                    continue
                bonds.add(_canonical_bond(left, right))

    graph = PeriodicGraph(
        lattice="triangular",
        length=length,
        site_count=site_count,
        bonds=tuple(sorted(bonds)),
    )
    validate_graph(graph)
    return graph


def honeycomb_graph(length: int) -> PeriodicGraph:
    length = _require_int(length, name="length")
    if length < 2:
        raise ValueError("length must be at least 2")

    site_count = 2 * length * length
    bonds: set[tuple[int, int]] = set()

    for y in range(length):
        for x in range(length):
            cell = x + length * y
            a = 2 * cell

            # Connect A(x,y) to B(x,y), B(x-1,y), B(x,y-1).
            neighbors = (
                (x, y),
                ((x - 1) % length, y),
                (x, (y - 1) % length),
            )
            for nx, ny in neighbors:
                ncell = nx + length * ny
                b = 2 * ncell + 1
                if a == b:
                    continue
                bonds.add(_canonical_bond(a, b))

    graph = PeriodicGraph(
        lattice="honeycomb",
        length=length,
        site_count=site_count,
        bonds=tuple(sorted(bonds)),
    )
    validate_graph(graph)
    return graph


def _expected_site_count(graph: PeriodicGraph) -> int:
    if graph.lattice == "triangular":
        return graph.length * graph.length
    if graph.lattice == "honeycomb":
        return 2 * graph.length * graph.length
    raise ValueError("unknown lattice kind")


def _expected_bond_count(graph: PeriodicGraph) -> int:
    if graph.lattice == "triangular":
        return 3 * graph.site_count
    if graph.lattice == "honeycomb":
        return 3 * graph.site_count // 2
    raise ValueError("unknown lattice kind")


def _expected_degree(graph: PeriodicGraph) -> int:
    if graph.lattice == "triangular":
        return 6
    if graph.lattice == "honeycomb":
        return 3
    raise ValueError("unknown lattice kind")


def validate_graph(graph: PeriodicGraph) -> None:
    if graph.lattice not in ("triangular", "honeycomb"):
        raise ValueError("unknown lattice")
    _require_int(graph.length, name="length")
    _require_int(graph.site_count, name="site_count")

    if graph.length < 1:
        raise ValueError("length must be positive")
    if graph.lattice == "triangular" and graph.length < 3:
        raise ValueError("length must be at least 3")
    if graph.lattice == "honeycomb" and graph.length < 2:
        raise ValueError("length must be at least 2")
    if graph.site_count <= 0:
        raise ValueError("site_count must be positive")

    expected_sites = _expected_site_count(graph)
    if graph.site_count != expected_sites:
        raise ValueError("site_count mismatch")

    if not isinstance(graph.bonds, tuple):
        raise TypeError("bonds must be a tuple")

    seen: set[tuple[int, int]] = set()
    degree = [0] * graph.site_count
    adjacency: list[list[int]] = [[] for _ in range(graph.site_count)]

    for bond in graph.bonds:
        if (
            not isinstance(bond, tuple)
            or len(bond) != 2
            or not isinstance(bond[0], int)
            or not isinstance(bond[1], int)
            or isinstance(bond[0], bool)
            or isinstance(bond[1], bool)
        ):
            raise TypeError("bond must be a pair of ints")
        left, right = bond
        if left == right:
            raise ValueError("self-loop bond detected")
        if left < 0 or right < 0 or left >= graph.site_count or right >= graph.site_count:
            raise ValueError("bond index out of range")
        if left > right:
            raise ValueError("bond endpoints must be canonical (min, max)")
        if bond in seen:
            raise ValueError("duplicate bond detected")
        seen.add(bond)
        degree[left] += 1
        degree[right] += 1
        adjacency[left].append(right)
        adjacency[right].append(left)

    if graph.bonds != tuple(sorted(graph.bonds)):
        raise ValueError("bonds must be sorted")

    expected_bonds = _expected_bond_count(graph)
    if len(graph.bonds) != expected_bonds:
        raise ValueError("bond count mismatch")

    expected_degree = _expected_degree(graph)
    if any(d != expected_degree for d in degree):
        raise ValueError("degree sequence mismatch")

    # Connectivity check.
    visited = [False] * graph.site_count
    queue: deque[int] = deque([0])
    visited[0] = True
    while queue:
        node = queue.popleft()
        for neigh in adjacency[node]:
            if not visited[neigh]:
                visited[neigh] = True
                queue.append(neigh)
    if not all(visited):
        raise ValueError("graph is disconnected")


def _graph_payload(graph: PeriodicGraph) -> dict[str, object]:
    validate_graph(graph)
    return {
        "lattice": graph.lattice,
        "length": graph.length,
        "site_count": graph.site_count,
        "bonds": [[left, right] for left, right in graph.bonds],
    }


def graph_sha256(graph: PeriodicGraph) -> str:
    payload = _graph_payload(graph)
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    return digest


def write_graph_json(graph: PeriodicGraph, path: Path) -> None:
    payload = _graph_payload(graph)
    payload_with_hash = dict(payload)
    payload_with_hash["sha256"] = graph_sha256(graph)

    encoded = json.dumps(payload_with_hash, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8")


def _reject_non_finite_json(token: str) -> None:
    raise ValueError(f"non-finite JSON token {token}")


def _graph_schema_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "schemas" / "graph.schema.json"


def _load_graph_schema() -> dict[str, object]:
    path = _graph_schema_path()
    return json.loads(path.read_text(encoding="utf-8"))


def read_graph_json(path: Path) -> PeriodicGraph:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_non_finite_json,
        )
    except ValueError as exc:
        if str(exc).startswith("non-finite JSON token"):
            raise ValueError(str(exc)) from exc
        raise ValueError("invalid graph JSON") from exc
    except (OSError, JSONDecodeError) as exc:
        raise ValueError("invalid graph JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("graph payload must be a JSON object")

    expected_keys = {"lattice", "length", "site_count", "bonds", "sha256"}
    if set(payload.keys()) != expected_keys:
        raise ValueError("graph payload contains unknown keys")

    schema = _load_graph_schema()
    try:
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError("graph payload violates schema") from exc

    embedded_hash = payload.get("sha256")
    if not isinstance(embedded_hash, str) or len(embedded_hash) != 64:
        raise ValueError("graph payload missing sha256")

    payload_without_hash = dict(payload)
    payload_without_hash.pop("sha256", None)
    expected_hash = hashlib.sha256(canonical_json(payload_without_hash)).hexdigest()
    if embedded_hash != expected_hash:
        raise ValueError("graph payload sha256 mismatch")

    bonds_raw = payload["bonds"]
    bonds: list[tuple[int, int]] = []
    for bond in bonds_raw:
        if not isinstance(bond, list) or len(bond) != 2:
            raise ValueError("graph payload has malformed bond entry")
        left, right = bond
        if (
            not isinstance(left, int)
            or not isinstance(right, int)
            or isinstance(left, bool)
            or isinstance(right, bool)
        ):
            raise ValueError("graph payload has malformed bond endpoint")
        bonds.append((left, right))

    graph = PeriodicGraph(
        lattice=payload["lattice"],
        length=payload["length"],
        site_count=payload["site_count"],
        bonds=tuple(bonds),
    )
    try:
        validate_graph(graph)
    except (TypeError, ValueError) as exc:
        raise ValueError("graph payload is not a valid periodic graph") from exc
    return graph
