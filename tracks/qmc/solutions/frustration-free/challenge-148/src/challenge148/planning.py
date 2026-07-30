from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from pathlib import Path
from typing import Mapping

import jsonschema

from .lattice import graph_sha256, honeycomb_graph, triangular_graph
from .provenance import canonical_json


_SEED_DERIVATION = "sha256:challenge148-coarse-qmc-sse-seed-v1||u64be"
_ALLOCATION = {
    "cores_per_cell": 2,
    "memory_mb_per_cell": 6000,
    "max_concurrency": 16,
}
_FROZEN_PREREGISTRATION: dict[str, object] = {
    "schema_version": "challenge148-coarse-crossing-preregistration-v1",
    "stage": "QMC_SSE coarse localization",
    "model": {
        "name": "transverse-field-ising",
        "boundary": "periodic",
        "pauli_eigenvalues": [-1, 1],
        "coupling": 1.0,
    },
    "lattices": [
        {"name": "triangular", "field_center": 4.76811},
        {"name": "honeycomb", "field_center": 2.1325},
    ],
    "scan": {
        "lengths": [4, 6, 8],
        "field_factors": [0.99, 1.0, 1.01],
        "beta_ratios": [1, 2],
    },
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


def _load_schema(name: str) -> dict[str, object]:
    return json.loads(_schema_path(name).read_text(encoding="utf-8"))


def _validate_preregistration(preregistration: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(preregistration, Mapping):
        raise ValueError("preregistration must be a mapping")
    value = dict(preregistration)
    plan_schema = _load_schema("plan.schema.json")
    preregistration_schema = {
        "$schema": plan_schema["$schema"],
        "$defs": plan_schema["$defs"],
        "$ref": "#/$defs/preregistration",
    }
    try:
        jsonschema.validate(value, preregistration_schema)
    except jsonschema.ValidationError as exc:
        raise ValueError("preregistration violates the closed schema") from exc
    if canonical_json(value) != canonical_json(_FROZEN_PREREGISTRATION):
        raise ValueError("preregistration does not match the frozen coarse crossing contract")
    return json.loads(canonical_json(value))


def _validate_build_info(build_info: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(build_info, Mapping):
        raise ValueError("build info must be a mapping")
    value = dict(build_info)
    build_schema = _load_schema("plan.schema.json")["$defs"]["build_info"]
    try:
        jsonschema.validate(value, build_schema)
    except jsonschema.ValidationError as exc:
        raise ValueError("build info violates the closed QMC_SSE schema") from exc
    return json.loads(canonical_json(value))


def _json_file_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _read_published_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"mismatched generated artifact: {path}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"mismatched generated artifact: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("short write while publishing generated artifact")
        view = view[written:]


def _write_immutable(path: Path, payload: bytes) -> None:
    """Atomically publish bytes once, accepting only identical existing bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (
        f".{path.name}.publish-{os.getpid()}-{secrets.token_hex(12)}"
    )
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(temporary, flags, 0o644)
    try:
        _write_all(descriptor, payload)
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise
    else:
        os.close(descriptor)

    published = False
    try:
        try:
            os.link(temporary, path, follow_symlinks=False)
            published = True
        except FileExistsError:
            if _read_published_bytes(path) != payload:
                raise ValueError(
                    f"refusing to overwrite mismatched generated artifact: {path}"
                )
    finally:
        temporary.unlink(missing_ok=True)

    if published:
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def _graph_payload(graph) -> dict[str, object]:
    return {
        "bonds": [[left, right] for left, right in graph.bonds],
        "lattice": graph.lattice,
        "length": graph.length,
        "sha256": graph_sha256(graph),
        "site_count": graph.site_count,
    }


def _derive_seed(
    preregistration_sha256: str,
    *,
    lattice: str,
    length: int,
    field_index: int,
    field_factor: float,
    beta_ratio: int,
    chain_index: int,
) -> int:
    coordinates = {
        "adapter": "QMC_SSE",
        "beta_ratio": beta_ratio,
        "chain_index": chain_index,
        "field_factor": field_factor,
        "field_index": field_index,
        "lattice": lattice,
        "length": length,
    }
    material = {
        "coordinates": coordinates,
        "domain": _SEED_DERIVATION,
        "preregistration_sha256": preregistration_sha256,
    }
    return int.from_bytes(hashlib.sha256(canonical_json(material)).digest()[:8], "big")


def _cell_id(
    lattice: str,
    length: int,
    field_index: int,
    beta_ratio: int,
    chain_index: int,
) -> str:
    return (
        f"{lattice}-l{length:02d}-f{field_index}-"
        f"b{beta_ratio}-c{chain_index}"
    )


def _generate_artifacts(
    frozen: dict[str, object],
    build_info: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    preregistration_sha256 = hashlib.sha256(canonical_json(frozen)).hexdigest()
    scan = frozen["scan"]
    sampling = frozen["sampling"]
    model = frozen["model"]
    assert isinstance(scan, dict)
    assert isinstance(sampling, dict)
    assert isinstance(model, dict)

    graphs: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []
    seeds: set[int] = set()

    for lattice_entry in frozen["lattices"]:
        assert isinstance(lattice_entry, dict)
        lattice = lattice_entry["name"]
        field_center = lattice_entry["field_center"]
        assert isinstance(lattice, str)
        assert isinstance(field_center, float)

        for length in scan["lengths"]:
            assert isinstance(length, int)
            graph = (
                triangular_graph(length)
                if lattice == "triangular"
                else honeycomb_graph(length)
            )
            graph_hash = graph_sha256(graph)
            graph_path = f"graphs/{graph_hash}.json"
            graph_content = _graph_payload(graph)
            graphs.append(
                {
                    "content": graph_content,
                    "lattice": lattice,
                    "length": length,
                    "path": graph_path,
                    "sha256": graph_hash,
                }
            )

            for field_index, field_factor in enumerate(scan["field_factors"]):
                assert isinstance(field_factor, float)
                field = field_center * field_factor
                for beta_ratio in scan["beta_ratios"]:
                    assert isinstance(beta_ratio, int)
                    # QMC_SSE deserializes beta as f64 and hashes its typed
                    # canonical representation (for example, 4.0). Preserve
                    # that numeric representation in the bound request.
                    beta = float(length * beta_ratio)
                    for chain_index in range(frozen["chain_count"]):
                        seed = _derive_seed(
                            preregistration_sha256,
                            lattice=lattice,
                            length=length,
                            field_index=field_index,
                            field_factor=field_factor,
                            beta_ratio=beta_ratio,
                            chain_index=chain_index,
                        )
                        if seed in seeds:
                            raise ValueError("SHA-256 seed derivation collision")
                        seeds.add(seed)

                        cell_id = _cell_id(
                            lattice,
                            length,
                            field_index,
                            beta_ratio,
                            chain_index,
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
                            "thermalization_sweeps": sampling[
                                "thermalization_sweeps"
                            ],
                            "thinning": sampling["thinning"],
                        }
                        try:
                            jsonschema.validate(
                                request, _load_schema("qmc-request.schema.json")
                            )
                        except jsonschema.ValidationError as exc:
                            raise ValueError("generated request violates schema") from exc

                        request_path = f"requests/{cell_id}.json"
                        cells.append(
                            {
                                "beta": beta,
                                "beta_ratio": beta_ratio,
                                "cell_id": cell_id,
                                "chain_index": chain_index,
                                "field": field,
                                "field_factor": field_factor,
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
    """Hash canonical complete-plan JSON after omitting only plan_sha256."""
    unsigned = dict(plan)
    unsigned.pop("plan_sha256", None)
    return hashlib.sha256(canonical_json(unsigned)).hexdigest()


def build_coarse_plan(
    preregistration: Mapping[str, object],
    build_info: Mapping[str, object],
    root: Path,
) -> dict[str, object]:
    frozen = _validate_preregistration(preregistration)
    validated_build = _validate_build_info(build_info)
    if not isinstance(root, Path):
        raise TypeError("root must be a Path")

    graphs, cells = _generate_artifacts(frozen, validated_build)
    for graph in graphs:
        _write_immutable(root / graph["path"], _json_file_bytes(graph["content"]))
    for cell in cells:
        _write_immutable(root / cell["request_path"], _json_file_bytes(cell["request"]))

    plan: dict[str, object] = {
        "schema_version": "challenge148-coarse-plan-v1",
        "stage": frozen["stage"],
        "preregistration": frozen,
        "preregistration_sha256": hashlib.sha256(canonical_json(frozen)).hexdigest(),
        "seed_derivation": _SEED_DERIVATION,
        "allocation": dict(_ALLOCATION),
        "build_info": validated_build,
        "graphs": graphs,
        "cells": cells,
    }
    plan["plan_sha256"] = _plan_sha256(plan)
    validate_plan(plan)
    return plan


def validate_plan(plan: Mapping[str, object]) -> None:
    if not isinstance(plan, Mapping):
        raise ValueError("plan must be a mapping")
    value = dict(plan)
    try:
        jsonschema.validate(value, _load_schema("plan.schema.json"))
    except jsonschema.ValidationError as exc:
        raise ValueError("plan violates schema") from exc

    if value["plan_sha256"] != _plan_sha256(value):
        raise ValueError("plan_sha256 mismatch")

    frozen = _validate_preregistration(value["preregistration"])
    expected_preregistration_sha256 = hashlib.sha256(canonical_json(frozen)).hexdigest()
    if value["preregistration_sha256"] != expected_preregistration_sha256:
        raise ValueError("preregistration sha256 mismatch")
    if value["allocation"] != frozen["allocation"]:
        raise ValueError("allocation does not match preregistration")

    validated_build = _validate_build_info(value["build_info"])
    cells = value["cells"]
    assert isinstance(cells, list)
    cell_ids = [cell["cell_id"] for cell in cells]
    if len(cell_ids) != len(set(cell_ids)):
        raise ValueError("duplicate cell_id")
    seeds = [cell["seed"] for cell in cells]
    if len(seeds) != len(set(seeds)):
        raise ValueError("duplicate seed")
    request_paths = [cell["request_path"] for cell in cells]
    if len(request_paths) != len(set(request_paths)):
        raise ValueError("duplicate request path")

    expected_graphs, expected_cells = _generate_artifacts(frozen, validated_build)
    if value["graphs"] != expected_graphs:
        raise ValueError("canonical graph bindings or contents mismatch")
    if cells != expected_cells:
        raise ValueError("frozen cell order, coordinates, seed, or request mismatch")
