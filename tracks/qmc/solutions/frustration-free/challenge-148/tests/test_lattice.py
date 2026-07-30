from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from challenge148.provenance import canonical_json

from challenge148.lattice import (
    PeriodicGraph,
    graph_sha256,
    honeycomb_graph,
    read_graph_json,
    triangular_graph,
    validate_graph,
    write_graph_json,
)


def degree_sequence(graph: PeriodicGraph) -> list[int]:
    degree = [0] * graph.site_count
    for left, right in graph.bonds:
        degree[left] += 1
        degree[right] += 1
    return sorted(degree)


def load_graph_schema() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    schema_path = root / "schemas" / "graph.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("length", [3, 4, 6])
def test_triangular_periodic_graph_contract(length):
    graph = triangular_graph(length)
    assert graph.site_count == length**2
    assert len(graph.bonds) == 3 * graph.site_count
    assert degree_sequence(graph) == [6] * graph.site_count
    assert graph.bonds == tuple(sorted(set(graph.bonds)))


@pytest.mark.parametrize("length", [2, 3, 4])
def test_honeycomb_periodic_graph_contract(length):
    graph = honeycomb_graph(length)
    assert graph.site_count == 2 * length**2
    assert len(graph.bonds) == 3 * graph.site_count // 2
    assert degree_sequence(graph) == [3] * graph.site_count
    assert graph.bonds == tuple(sorted(set(graph.bonds)))


def test_triangular_length_two_is_rejected_as_parallel_bond_cell():
    with pytest.raises(ValueError, match="length must be at least 3"):
        triangular_graph(2)


def test_validate_graph_rejects_duplicate_or_out_of_range_bonds():
    graph = triangular_graph(3)
    bonds = list(graph.bonds)
    bonds.append(bonds[0])
    with pytest.raises(ValueError, match="duplicate bond"):
        validate_graph(
            PeriodicGraph(
                lattice=graph.lattice,
                length=graph.length,
                site_count=graph.site_count,
                bonds=tuple(bonds),
            )
        )

    with pytest.raises(ValueError, match="bond index out of range"):
        validate_graph(
            PeriodicGraph(
                lattice=graph.lattice,
                length=graph.length,
                site_count=graph.site_count,
                bonds=((0, graph.site_count),),
            )
        )


def test_graph_sha256_is_payload_hash_excluding_embedded_hash(tmp_path: Path):
    graph = honeycomb_graph(2)
    path = tmp_path / "graph.json"
    write_graph_json(graph, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    embedded = payload["sha256"]
    assert embedded == graph_sha256(graph)

    without_hash = dict(payload)
    without_hash.pop("sha256")
    expected = hashlib.sha256(canonical_json(without_hash)).hexdigest()
    assert embedded == expected


def test_graph_json_is_deterministic_and_schema_valid(tmp_path: Path):
    graph = triangular_graph(3)
    first = tmp_path / "g1.json"
    second = tmp_path / "g2.json"
    write_graph_json(graph, first)
    write_graph_json(graph, second)
    assert first.read_bytes() == second.read_bytes()

    schema = load_graph_schema()
    payload = json.loads(first.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)

    payload["extra"] = 5
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


def test_schema_rejects_lattice_specific_minimum_lengths():
    schema = load_graph_schema()

    triangular_too_small = {
        "lattice": "triangular",
        "length": 2,
        "site_count": 4,
        "bonds": [],
        "sha256": "0" * 64,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(triangular_too_small, schema)

    honeycomb_too_small = {
        "lattice": "honeycomb",
        "length": 1,
        "site_count": 2,
        "bonds": [],
        "sha256": "0" * 64,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(honeycomb_too_small, schema)


def test_schema_rejects_duplicate_bond_entries():
    schema = load_graph_schema()
    payload = {
        "lattice": "honeycomb",
        "length": 2,
        "site_count": 8,
        "bonds": [[0, 1], [0, 1]],
        "sha256": "0" * 64,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


def test_read_graph_json_round_trips(tmp_path: Path):
    graph = triangular_graph(3)
    path = tmp_path / "graph.json"
    write_graph_json(graph, path)
    loaded = read_graph_json(path)
    assert loaded == graph


def test_read_graph_json_rejects_tampered_hash(tmp_path: Path):
    graph = honeycomb_graph(2)
    path = tmp_path / "graph.json"
    write_graph_json(graph, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["sha256"] = "0" * 64
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="sha256"):
        read_graph_json(path)


def test_read_graph_json_rejects_tampered_payload(tmp_path: Path):
    graph = honeycomb_graph(2)
    path = tmp_path / "graph.json"
    write_graph_json(graph, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["bonds"][0] = [payload["bonds"][0][0], payload["bonds"][0][1] + 2]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        read_graph_json(path)


def test_read_graph_json_rejects_non_finite_json(tmp_path: Path):
    path = tmp_path / "graph.json"
    path.write_text(
        '{"lattice":"triangular","length":NaN,"site_count":9,"bonds":[],"sha256":"'
        + ("0" * 64)
        + '"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-finite"):
        read_graph_json(path)


def test_read_graph_json_rejects_unknown_keys(tmp_path: Path):
    graph = triangular_graph(3)
    path = tmp_path / "graph.json"
    write_graph_json(graph, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["extra"] = 5
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        read_graph_json(path)


def test_read_graph_json_rejects_bool_as_int_bond_elements(tmp_path: Path):
    path = tmp_path / "graph.json"
    path.write_text(
        json.dumps(
            {
                "lattice": "triangular",
                "length": 3,
                "site_count": 9,
                "bonds": [[True, 1]],
                "sha256": "0" * 64,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        read_graph_json(path)

