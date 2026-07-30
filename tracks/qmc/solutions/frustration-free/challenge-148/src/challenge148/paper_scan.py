from __future__ import annotations

import hashlib
import json
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, Mapping

import jsonschema

from .lattice import graph_sha256, honeycomb_graph, triangular_graph
from .planning import _json_file_bytes, _write_immutable
from .provenance import canonical_json


_SEED_DERIVATION = "sha256:challenge148-paper-scan-seed-v1||u64be"
_STAGE = "paper-aligned QMC_SSE finite-size reproduction"
_ALLOCATION = {
    "adapter_timeout_seconds": 3600,
    "cores_per_cell": 2,
    "memory_mb_per_cell": 6000,
    "max_concurrency": 16,
}
_FROZEN_PREREGISTRATION: dict[str, object] = {
    "schema_version": "challenge148-paper-scan-preregistration-v1",
    "stage": _STAGE,
    "model": {
        "hamiltonian": "H=-sum_<ij> sigma_i^z sigma_j^z-t sum_i sigma_i^x",
        "boundary": "periodic",
        "pauli_eigenvalues": [-1, 1],
        "coupling": 1.0,
    },
    "lattices": [
        {
            "name": "triangular",
            "field_center_decimal": "4.76811",
            "lengths": [6, 8, 10, 12, 14, 16, 18, 20],
        },
        {
            "name": "honeycomb",
            "field_center_decimal": "2.13250",
            "lengths": [10, 12, 14, 16, 18, 20],
        },
    ],
    "field_factors_decimal": ["0.995", "0.9975", "1.0", "1.0025", "1.005"],
    "chain_count": 2,
    "sampling": {
        "thermalization_sweeps": 500,
        "retained_samples": 1600,
        "thinning": 2,
        "serial_measurement_stride_samples": 1,
        "analysis_bin_length_samples": 100,
        "checkpoint_analysis_bins": 8,
    },
    "seed_derivation": _SEED_DERIVATION,
    "allocation": _ALLOCATION,
}


def _schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / name


def _schema(name: str) -> dict[str, Any]:
    return json.loads(_schema_path(name).read_text(encoding="utf-8"))


def _frozen_copy(value: object) -> Any:
    return json.loads(canonical_json(value))


def _validate_preregistration(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("preregistration must be a mapping")
    candidate = dict(value)
    plan_schema = _schema("paper-plan.schema.json")
    try:
        jsonschema.validate(
            candidate,
            {
                "$schema": plan_schema["$schema"],
                "$defs": plan_schema["$defs"],
                "$ref": "#/$defs/preregistration",
            },
        )
    except jsonschema.ValidationError as exc:
        raise ValueError("preregistration violates the closed schema") from exc
    if canonical_json(candidate) != canonical_json(_FROZEN_PREREGISTRATION):
        raise ValueError("preregistration does not match the frozen paper contract")
    return _frozen_copy(candidate)


def _validate_build_info(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("build info must be a mapping")
    candidate = dict(value)
    try:
        jsonschema.validate(
            candidate, _schema("paper-plan.schema.json")["$defs"]["build_info"]
        )
    except jsonschema.ValidationError as exc:
        raise ValueError("build info violates the closed QMC_SSE schema") from exc
    return _frozen_copy(candidate)


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text if "." in text else f"{text}.0"


def _graph_payload(graph: Any) -> dict[str, object]:
    return {
        "bonds": [[left, right] for left, right in graph.bonds],
        "lattice": graph.lattice,
        "length": graph.length,
        "sha256": graph_sha256(graph),
        "site_count": graph.site_count,
    }


def _seed(preregistration_sha256: str, coordinates: Mapping[str, object]) -> int:
    material = {
        "coordinates": dict(coordinates),
        "domain": _SEED_DERIVATION,
        "preregistration_sha256": preregistration_sha256,
    }
    return int.from_bytes(hashlib.sha256(canonical_json(material)).digest()[:8], "big")


def _generate(
    preregistration: dict[str, object], build_info: dict[str, object]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    preregistration_sha256 = hashlib.sha256(
        canonical_json(preregistration)
    ).hexdigest()
    sampling = preregistration["sampling"]
    model = preregistration["model"]
    assert isinstance(sampling, dict) and isinstance(model, dict)
    factors = preregistration["field_factors_decimal"]
    assert isinstance(factors, list)
    graphs: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []
    graph_hashes: set[str] = set()
    seeds: set[int] = set()

    for lattice_entry in preregistration["lattices"]:
        assert isinstance(lattice_entry, dict)
        lattice = lattice_entry["name"]
        center_text = lattice_entry["field_center_decimal"]
        assert isinstance(lattice, str) and isinstance(center_text, str)
        center = Decimal(center_text)
        for length in lattice_entry["lengths"]:
            assert isinstance(length, int)
            graph = (
                triangular_graph(length)
                if lattice == "triangular"
                else honeycomb_graph(length)
            )
            graph_hash = graph_sha256(graph)
            graph_path = f"graphs/{graph_hash}.json"
            if graph_hash not in graph_hashes:
                graph_hashes.add(graph_hash)
                graphs.append(
                    {
                        "content": _graph_payload(graph),
                        "lattice": lattice,
                        "length": length,
                        "path": graph_path,
                        "sha256": graph_hash,
                    }
                )
            for field_index, factor_text in enumerate(factors):
                assert isinstance(factor_text, str)
                with localcontext() as context:
                    context.prec = 60
                    field_decimal = center * Decimal(factor_text)
                    beta_decimal = Decimal(length) / field_decimal
                field_text = _decimal_text(field_decimal)
                beta_text = _decimal_text(beta_decimal)
                field = float(field_decimal)
                beta = float(beta_decimal)
                for chain_index in range(2):
                    coordinates = {
                        "adapter": "QMC_SSE",
                        "chain_index": chain_index,
                        "field_decimal": field_text,
                        "field_factor_decimal": factor_text,
                        "field_index": field_index,
                        "lattice": lattice,
                        "length": length,
                    }
                    seed = _seed(preregistration_sha256, coordinates)
                    if seed in seeds:
                        raise ValueError("SHA-256 seed derivation collision")
                    seeds.add(seed)
                    cell_id = (
                        f"paper-{lattice}-l{length:02d}-f{field_index}-c{chain_index}"
                    )
                    request = {
                        "adapter": "QMC_SSE",
                        "beta": beta,
                        "bin_length": sampling["analysis_bin_length_samples"],
                        "checkpoint_bins": sampling["checkpoint_analysis_bins"],
                        "coupling": model["coupling"],
                        "expected_build_hash": build_info["build_hash"],
                        "expected_source_hash": build_info["source_hash"],
                        "field": field,
                        "graph_path": graph_path,
                        "graph_sha256": graph_hash,
                        "retained_samples": sampling["retained_samples"],
                        "schema_version": "qmc-request-v1",
                        "seed": seed,
                        "serial_measurement_stride_samples": sampling[
                            "serial_measurement_stride_samples"
                        ],
                        "thermalization_sweeps": sampling["thermalization_sweeps"],
                        "thinning": sampling["thinning"],
                    }
                    try:
                        jsonschema.validate(request, _schema("qmc-request.schema.json"))
                    except jsonschema.ValidationError as exc:
                        raise ValueError("generated request violates schema") from exc
                    request_path = f"requests/{cell_id}.json"
                    cells.append(
                        {
                            "beta": beta,
                            "beta_decimal": beta_text,
                            "cell_id": cell_id,
                            "chain_index": chain_index,
                            "field": field,
                            "field_center_decimal": center_text,
                            "field_decimal": field_text,
                            "field_factor_decimal": factor_text,
                            "field_index": field_index,
                            "graph_path": graph_path,
                            "graph_sha256": graph_hash,
                            "lattice": lattice,
                            "length": length,
                            "request": request,
                            "request_path": request_path,
                            "request_sha256": hashlib.sha256(
                                canonical_json(request)
                            ).hexdigest(),
                            "seed": seed,
                        }
                    )
    return graphs, cells


def _plan_sha256(plan: Mapping[str, object]) -> str:
    unsigned = dict(plan)
    unsigned.pop("plan_sha256", None)
    return hashlib.sha256(canonical_json(unsigned)).hexdigest()


def build_paper_scan_plan(
    preregistration: Mapping[str, object],
    build_info: Mapping[str, object],
    root: Path,
) -> dict[str, object]:
    frozen = _validate_preregistration(preregistration)
    build = _validate_build_info(build_info)
    if not isinstance(root, Path):
        raise TypeError("root must be a Path")
    graphs, cells = _generate(frozen, build)
    for graph in graphs:
        _write_immutable(root / graph["path"], _json_file_bytes(graph["content"]))
    for cell in cells:
        _write_immutable(root / cell["request_path"], _json_file_bytes(cell["request"]))
    plan: dict[str, object] = {
        "schema_version": "challenge148-paper-scan-plan-v1",
        "stage": _STAGE,
        "preregistration": frozen,
        "preregistration_sha256": hashlib.sha256(canonical_json(frozen)).hexdigest(),
        "seed_derivation": _SEED_DERIVATION,
        "allocation": dict(_ALLOCATION),
        "build_info": build,
        "graphs": graphs,
        "cells": cells,
    }
    plan["plan_sha256"] = _plan_sha256(plan)
    validate_paper_scan_plan(plan)
    return plan


def validate_paper_scan_plan(plan: Mapping[str, object]) -> None:
    if not isinstance(plan, Mapping):
        raise ValueError("plan must be a mapping")
    value = dict(plan)
    try:
        jsonschema.validate(value, _schema("paper-plan.schema.json"))
    except jsonschema.ValidationError as exc:
        raise ValueError("plan violates schema") from exc
    if value["plan_sha256"] != _plan_sha256(value):
        raise ValueError("plan_sha256 mismatch")
    frozen = _validate_preregistration(value["preregistration"])
    if value["preregistration_sha256"] != hashlib.sha256(
        canonical_json(frozen)
    ).hexdigest():
        raise ValueError("preregistration sha256 mismatch")
    if value["allocation"] != frozen["allocation"]:
        raise ValueError("allocation does not match preregistration")
    build = _validate_build_info(value["build_info"])
    graphs, cells = _generate(frozen, build)
    if value["graphs"] != graphs or value["cells"] != cells:
        raise ValueError("frozen paper artifacts or cell order mismatch")
    if len({cell["cell_id"] for cell in cells}) != 140:
        raise ValueError("paper plan cell IDs must be unique")
    if len({cell["seed"] for cell in cells}) != 140:
        raise ValueError("paper plan seeds must be unique")
