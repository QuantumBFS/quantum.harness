from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections.abc import Mapping, Sequence
from itertools import pairwise
from pathlib import Path
from types import MappingProxyType
from typing import Never

import numpy as np

from .counter_rng import STREAM_COUNT, StreamIdentity, derive_stream_material
from .kernel import periodic_kernel
from .pilot import PILOT_MASTER_SEED, PILOT_REPLICAS
from .pilot_analysis import (
    P1_MASTER_SEED,
    P1_REPLICAS,
    _selector_estimates,
    _transition_evidence,
)
from .trajectory import TrajectoryRequest, request_digest

EXTENSION_PROTOCOL_SCHEMA = "challenge-194-p0-extension-protocol-v1"
EXTENSION_RUN_SPEC_SCHEMA = "challenge-194-p0-extension-run-spec-v1"
EXTENSION_PROGRESS_SCHEMA = "challenge-194-p0-extension-progress-v1"
EXTENSION_ANALYSIS_SCHEMA = "challenge-194-p0-extension-analysis-v1"
COMBINED_ANALYSIS_SCHEMA = "challenge-194-p0-combined-analysis-v2"
COMBINED_BRACKET_SCHEMA = "challenge-194-p1-brackets-v2"
EXTENSION_SIGMAS = (0.9, 1.0)
EXTENSION_LENGTHS = (2**10, 2**14, 2**18)
EXTENSION_REPLICAS = tuple(range(24, 40))
EXTENSION_MASTER_SEED = 19_420_262_729
EXTENSION_PHASE = "pilot"
EXTENSION_GRID_NAMESPACE = "pilot-p0-extension-v1"
EXTENSION_GRID_HASHES = MappingProxyType(
    {
        (0.9).hex(): "76dc7e07639ed085873a8f291cc2aaee0e8942ddac8efce3982743dd67491071",
        (1.0).hex(): "d40b4a2afac533d74965513513fff1870918831000b2e040063ca2a0e29ad091",
    }
)

P0_RUN_SPEC_SHA256 = "d17d3df9528a09f0d834ebe9d5ce6f283e488d2326f6cb14873a90923c5d9840"
P0_PROGRESS_SHA256 = "ea29a8163a5d3e85768842d64fac4c719f5aeadf965b3318b305fb7a2cc2d15f"
P0_ANALYSIS_DOCUMENT_SHA256 = (
    "e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8"
)
P0_ANALYSIS_FILE_SHA256 = (
    "44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b"
)
P0_BRACKET_DOCUMENT_SHA256 = (
    "fb3df666044bf9531443fc00c5c2c2d489512b4162864b3a92ffc2e756832403"
)
P0_SOURCE_REVISION = "739880d9ccdcffbfc8a15310250349bd11d63bbb"
DESIGN_SHA256 = "5426e3007e9d83039f371ca6a9372f1868ef9d5447b66a12b1643ecf72907aba"

_PROTOCOL_FIELDS = {
    "schema_version",
    "source_p0_run_spec_sha256",
    "source_p0_progress_sha256",
    "source_p0_analysis_document_sha256",
    "source_p0_bracket_document_sha256",
    "design_sha256",
    "source_revision",
    "grid_namespace",
    "master_seed",
    "phase",
    "purpose",
    "lengths",
    "replicas",
    "loop_order",
    "sigma_entries",
    "cells",
    "cell_count",
    "rng_assignment_sha256",
    "protocol_sha256",
}
_SIGMA_ENTRY_FIELDS = {
    "sigma_hex",
    "lengths",
    "q_g_components",
    "four_sector_components",
    "selected_q_g_component",
    "selected_four_sector_component",
    "guard_interval_indices",
    "lower_kappa_hex",
    "upper_kappa_hex",
    "kappas",
    "grid_sha256",
    "sigma_grid_id",
}
_CELL_FIELDS = {
    "cell_index",
    "cell_id",
    "sigma",
    "length",
    "replica",
    "sigma_grid_id",
    "kappas",
    "kernel_sha256",
    "request_sha256",
    "cell_path",
    "run_path",
    "manifest_path",
    "rng_material_sha256",
}


def _canonical_bytes(document: object) -> bytes:
    try:
        return (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("document is not canonical finite JSON") from error


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _malformed(message: str) -> Never:
    raise RuntimeError(message)


def _solution_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_root() -> Path:
    return _solution_root().parents[4]


def _design_path() -> Path:
    return (
        _repo_root()
        / "docs/superpowers/specs/2026-07-30-challenge-194-p0-extension-design.md"
    )


def _p0_run_spec_path() -> Path:
    return _repo_root() / "results/challenge-194/pilot-p0-739880d/run_spec.json"


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _current_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_repo_root(),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("unable to resolve extension source revision") from error
    revision = result.stdout.strip()
    if len(revision) != 40 or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise RuntimeError("extension source revision is malformed")
    return revision


def _marked_components(indices: Sequence[int]) -> tuple[tuple[int, int], ...]:
    ordered = tuple(sorted(set(indices)))
    if tuple(indices) != ordered:
        raise RuntimeError("marked interval indices are not canonical")
    components: list[tuple[int, int]] = []
    for index in ordered:
        if components and index == components[-1][1] + 1:
            components[-1] = (components[-1][0], index)
        else:
            components.append((index, index))
    return tuple(components)


def _component_gap(left: tuple[int, int], right: tuple[int, int]) -> int:
    if left[1] < right[0]:
        return right[0] - left[1] - 1
    if right[1] < left[0]:
        return left[0] - right[1] - 1
    return 0


def _recursive_binary64_grid_17(lower: float, upper: float) -> tuple[float, ...]:
    if (
        not math.isfinite(lower)
        or not math.isfinite(upper)
        or lower <= 0.0
        or upper <= lower
    ):
        raise RuntimeError("extension grid endpoints are invalid")
    points = [lower, upper]
    for _level in range(4):
        previous = sorted(points)
        points.extend(left + (right - left) / 2.0 for left, right in pairwise(previous))
    ordered = tuple(sorted({value.hex(): value for value in points}.values()))
    if len(ordered) != 17 or ordered[0] != lower or ordered[-1] != upper:
        raise RuntimeError("extension span cannot produce 17 binary64 points")
    return ordered


def derive_p0_extension_ranges(
    p0_analysis: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    sigmas, lengths, kappas, values = _selector_estimates(p0_analysis)
    selected_lengths = (lengths[-2], lengths[-1])
    result: dict[str, dict[str, object]] = {}
    for sigma in EXTENSION_SIGMAS:
        if sigma not in sigmas:
            raise RuntimeError("blocked sigma is missing from P0 analysis")
        q_indices: list[int] = []
        crossing_indices: list[int] = []
        for interval_index in range(1, len(kappas) - 1):
            q_marked, crossing_marked, _evidence = _transition_evidence(
                sigma, selected_lengths, kappas, values, interval_index
            )
            q_indices.extend([interval_index] if q_marked else [])
            crossing_indices.extend([interval_index] if crossing_marked else [])
        q_components = _marked_components(q_indices)
        crossing_components = _marked_components(crossing_indices)
        if not q_components or not crossing_components:
            raise RuntimeError("extension estimator component is missing")
        crossing = crossing_components[0]
        q_component = min(
            q_components,
            key=lambda component: (_component_gap(component, crossing), component[0]),
        )
        union_lower = min(crossing[0], q_component[0])
        union_upper = max(crossing[1], q_component[1])
        guard_lower = union_lower - 1
        guard_upper = union_upper + 1
        if guard_lower < 1 or guard_upper + 1 >= len(kappas):
            raise RuntimeError("extension range lacks adjacent P0 guards")
        lower = kappas[guard_lower]
        upper = kappas[guard_upper + 1]
        grid = _recursive_binary64_grid_17(lower, upper)
        result[sigma.hex()] = {
            "sigma_hex": sigma.hex(),
            "lengths": list(selected_lengths),
            "q_g_components": [list(component) for component in q_components],
            "four_sector_components": [
                list(component) for component in crossing_components
            ],
            "selected_q_g_component": list(q_component),
            "selected_four_sector_component": list(crossing),
            "guard_interval_indices": [guard_lower, guard_upper],
            "lower_kappa_hex": lower.hex(),
            "upper_kappa_hex": upper.hex(),
            "kappas": [value.hex() for value in grid],
        }
    return result


def _validate_source(p0_analysis: Mapping[str, object]) -> None:
    if (
        p0_analysis.get("p0_run_spec_sha256") != P0_RUN_SPEC_SHA256
        or p0_analysis.get("p0_progress_sha256") != P0_PROGRESS_SHA256
        or p0_analysis.get("analysis_document_sha256") != P0_ANALYSIS_DOCUMENT_SHA256
        or p0_analysis.get("source_revision") != P0_SOURCE_REVISION
    ):
        raise RuntimeError("P0 source hashes or revision are not frozen")
    if _sha256(_canonical_bytes(p0_analysis)) != P0_ANALYSIS_FILE_SHA256:
        raise RuntimeError("P0 source canonical file hash mismatch")
    _selector_estimates(p0_analysis)


def _grid_id(entry: Mapping[str, object]) -> str:
    return (
        f"{EXTENSION_GRID_NAMESPACE}|sigma-f64={entry['sigma_hex']}"
        f"|source-analysis={P0_ANALYSIS_DOCUMENT_SHA256}"
        f"|range={entry['lower_kappa_hex']}:{entry['upper_kappa_hex']}"
    )


def _kernel_hash(length: int, sigma: float) -> str:
    kernel = periodic_kernel(length, sigma)
    return _sha256(kernel.astype("<f8", copy=False).tobytes(order="C"))


def _stream_hashes(
    *,
    master_seed: int,
    length: int,
    sigma_grid_id: str,
    replica: int,
) -> tuple[str, ...]:
    return tuple(
        derive_stream_material(
            StreamIdentity(
                master_seed=master_seed,
                phase=EXTENSION_PHASE,
                length=length,
                sigma_grid_id=sigma_grid_id,
                replica=replica,
                stream_id=stream,
            )
        ).material_sha256
        for stream in range(STREAM_COUNT)
    )


def _p0_identity_hashes() -> tuple[tuple[str, ...], tuple[str, ...]]:
    path = _p0_run_spec_path()
    payload = path.read_bytes()
    if _sha256(payload) != P0_RUN_SPEC_SHA256:
        raise RuntimeError("verified P0 run spec hash mismatch")
    try:
        document = json.loads(payload)
        cells = document["cells"]
        requests = tuple(str(cell["request_sha256"]) for cell in cells)
        streams = tuple(
            str(digest) for cell in cells for digest in cell["rng_material_sha256"]
        )
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("verified P0 identity registry is malformed") from error
    if len(requests) != 96 or len(streams) != 96 * STREAM_COUNT:
        raise RuntimeError("verified P0 identity registry is incomplete")
    return requests, streams


def _validate_identity_axes() -> None:
    replicas = tuple(EXTENSION_REPLICAS)
    if (
        EXTENSION_MASTER_SEED in {PILOT_MASTER_SEED, P1_MASTER_SEED}
        or len(replicas) != 16
        or len(set(replicas)) != len(replicas)
        or set(replicas) & set(PILOT_REPLICAS)
        or set(replicas) & set(P1_REPLICAS)
    ):
        raise RuntimeError("extension identities overlap P0 or reserved P1")


def _protocol_hash(protocol: Mapping[str, object]) -> str:
    unsigned = dict(protocol)
    unsigned.pop("protocol_sha256", None)
    return _sha256(_canonical_bytes(unsigned))


def build_p0_extension_protocol(
    p0_analysis: Mapping[str, object],
) -> dict[str, object]:
    _validate_source(p0_analysis)
    _validate_identity_axes()
    design_sha256 = _file_sha256(_design_path())
    if design_sha256 != DESIGN_SHA256:
        raise RuntimeError("extension design hash mismatch")

    ranges = derive_p0_extension_ranges(p0_analysis)
    sigma_entries: list[dict[str, object]] = []
    for sigma in EXTENSION_SIGMAS:
        entry = dict(ranges[sigma.hex()])
        grid_sha256 = _sha256(_canonical_bytes({"kappas": entry["kappas"]}))
        if grid_sha256 != EXTENSION_GRID_HASHES[sigma.hex()]:
            raise RuntimeError("derived extension grid hash mismatch")
        entry["grid_sha256"] = grid_sha256
        entry["sigma_grid_id"] = _grid_id(entry)
        sigma_entries.append(entry)

    p0_requests, p0_streams = _p0_identity_hashes()
    p0_request_set = set(p0_requests)
    p0_stream_set = set(p0_streams)
    cells: list[dict[str, object]] = []
    assignments: list[dict[str, object]] = []
    seen_requests: set[str] = set()
    seen_streams: set[str] = set()
    for sigma, entry in zip(EXTENSION_SIGMAS, sigma_entries, strict=True):
        kappas_hex = list(entry["kappas"])
        kappas = np.asarray(
            [float.fromhex(value) for value in kappas_hex], dtype=np.float64
        )
        grid_id = str(entry["sigma_grid_id"])
        for length in EXTENSION_LENGTHS:
            kernel_sha256 = _kernel_hash(length, sigma)
            for replica in EXTENSION_REPLICAS:
                request = TrajectoryRequest(
                    length=length,
                    sigma=sigma,
                    sigma_grid_id=grid_id,
                    kappas=kappas,
                    master_seed=EXTENSION_MASTER_SEED,
                    phase=EXTENSION_PHASE,
                    replica=replica,
                    kernel_sha256=kernel_sha256,
                )
                request_sha256 = request_digest(request)
                streams = _stream_hashes(
                    master_seed=EXTENSION_MASTER_SEED,
                    length=length,
                    sigma_grid_id=grid_id,
                    replica=replica,
                )
                if (
                    request_sha256 in seen_requests
                    or request_sha256 in p0_request_set
                    or any(
                        digest in seen_streams or digest in p0_stream_set
                        for digest in streams
                    )
                ):
                    raise RuntimeError("extension request or RNG identity collision")
                seen_requests.add(request_sha256)
                seen_streams.update(streams)
                index = len(cells)
                identity = {
                    "cell_index": index,
                    "sigma": sigma.hex(),
                    "length": length,
                    "replica": replica,
                    "request_sha256": request_sha256,
                }
                cell_id = f"{index:03d}-{_sha256(_canonical_bytes(identity))[:16]}"
                cell_path = f"cells/{cell_id}"
                cells.append(
                    {
                        **identity,
                        "cell_id": cell_id,
                        "sigma_grid_id": grid_id,
                        "kappas": kappas_hex,
                        "kernel_sha256": kernel_sha256,
                        "rng_material_sha256": list(streams),
                        "cell_path": cell_path,
                        "run_path": f"{cell_path}/run",
                        "manifest_path": f"{cell_path}/manifest.json",
                    }
                )
                assignments.append(
                    {
                        "cell_index": index,
                        "request_sha256": request_sha256,
                        "streams": list(streams),
                    }
                )

    protocol: dict[str, object] = {
        "schema_version": EXTENSION_PROTOCOL_SCHEMA,
        "source_p0_run_spec_sha256": P0_RUN_SPEC_SHA256,
        "source_p0_progress_sha256": P0_PROGRESS_SHA256,
        "source_p0_analysis_document_sha256": P0_ANALYSIS_DOCUMENT_SHA256,
        "source_p0_bracket_document_sha256": P0_BRACKET_DOCUMENT_SHA256,
        "design_sha256": design_sha256,
        "source_revision": _current_revision(),
        "grid_namespace": EXTENSION_GRID_NAMESPACE,
        "master_seed": EXTENSION_MASTER_SEED,
        "phase": EXTENSION_PHASE,
        "purpose": "exploratory-p0-extension-only",
        "lengths": list(EXTENSION_LENGTHS),
        "replicas": list(EXTENSION_REPLICAS),
        "loop_order": ["sigma", "length", "replica"],
        "sigma_entries": sigma_entries,
        "cells": cells,
        "cell_count": 96,
        "rng_assignment_sha256": _sha256(
            _canonical_bytes({"assignments": assignments})
        ),
    }
    protocol["protocol_sha256"] = _protocol_hash(protocol)
    validate_p0_extension_protocol(p0_analysis, protocol)
    return protocol


def _exact_hex(raw: object) -> float:
    if not isinstance(raw, str):
        _malformed("extension binary64 value is malformed")
    try:
        value = float.fromhex(raw)
    except ValueError as error:
        raise RuntimeError("extension binary64 value is malformed") from error
    if not math.isfinite(value) or value.hex() != raw:
        raise RuntimeError("extension binary64 value is not canonical")
    return value


def validate_p0_extension_protocol(
    p0_analysis: Mapping[str, object],
    protocol: Mapping[str, object],
) -> None:
    _validate_source(p0_analysis)
    _validate_identity_axes()
    if set(protocol) != _PROTOCOL_FIELDS:
        raise RuntimeError("extension protocol fields are invalid")
    if protocol.get("protocol_sha256") != _protocol_hash(protocol):
        raise RuntimeError("extension protocol hash mismatch")
    if (
        protocol.get("schema_version") != EXTENSION_PROTOCOL_SCHEMA
        or protocol.get("source_p0_run_spec_sha256") != P0_RUN_SPEC_SHA256
        or protocol.get("source_p0_progress_sha256") != P0_PROGRESS_SHA256
        or protocol.get("source_p0_analysis_document_sha256")
        != P0_ANALYSIS_DOCUMENT_SHA256
        or protocol.get("source_p0_bracket_document_sha256")
        != P0_BRACKET_DOCUMENT_SHA256
    ):
        raise RuntimeError("extension source bindings are invalid")
    if (
        protocol.get("design_sha256") != DESIGN_SHA256
        or _file_sha256(_design_path()) != DESIGN_SHA256
    ):
        raise RuntimeError("extension design hash mismatch")
    if (
        protocol.get("grid_namespace") != EXTENSION_GRID_NAMESPACE
        or protocol.get("master_seed") != EXTENSION_MASTER_SEED
        or protocol.get("phase") != EXTENSION_PHASE
        or protocol.get("purpose") != "exploratory-p0-extension-only"
        or protocol.get("lengths") != list(EXTENSION_LENGTHS)
        or protocol.get("loop_order") != ["sigma", "length", "replica"]
    ):
        raise RuntimeError("extension protocol axes are invalid")
    replicas = protocol.get("replicas")
    if replicas != list(EXTENSION_REPLICAS):
        raise RuntimeError("extension replica axis is missing, duplicate, or reordered")
    if protocol.get("source_revision") != _current_revision():
        raise RuntimeError("extension source revision mismatch")

    expected_ranges = derive_p0_extension_ranges(p0_analysis)
    raw_entries = protocol.get("sigma_entries")
    if not isinstance(raw_entries, list) or len(raw_entries) != 2:
        raise RuntimeError("extension sigma entries are malformed")
    entries: list[Mapping[str, object]] = []
    for sigma, raw in zip(EXTENSION_SIGMAS, raw_entries, strict=True):
        if not isinstance(raw, Mapping) or set(raw) != _SIGMA_ENTRY_FIELDS:
            raise RuntimeError("extension sigma entry fields are invalid")
        expected_range = expected_ranges[sigma.hex()]
        for field in (
            "sigma_hex",
            "lengths",
            "q_g_components",
            "four_sector_components",
            "selected_q_g_component",
            "selected_four_sector_component",
            "guard_interval_indices",
            "lower_kappa_hex",
            "upper_kappa_hex",
        ):
            if raw.get(field) != expected_range[field]:
                raise RuntimeError("extension component range is invalid")
        kappas = raw.get("kappas")
        if not isinstance(kappas, list):
            _malformed("extension grid is malformed")
        parsed = tuple(_exact_hex(value) for value in kappas)
        expected_grid = _recursive_binary64_grid_17(
            _exact_hex(raw["lower_kappa_hex"]),
            _exact_hex(raw["upper_kappa_hex"]),
        )
        if parsed != expected_grid:
            raise RuntimeError("extension grid order or values are invalid")
        grid_sha256 = _sha256(_canonical_bytes({"kappas": kappas}))
        if (
            raw.get("grid_sha256") != grid_sha256
            or grid_sha256 != EXTENSION_GRID_HASHES[sigma.hex()]
            or raw.get("sigma_grid_id") != _grid_id(raw)
        ):
            raise RuntimeError("extension grid hash or identity is invalid")
        entries.append(raw)

    cells = protocol.get("cells")
    if (
        not isinstance(cells, list)
        or protocol.get("cell_count") != 96
        or len(cells) != 96
    ):
        raise RuntimeError("extension cell count is invalid")
    p0_requests, p0_streams = _p0_identity_hashes()
    p0_request_set = set(p0_requests)
    p0_stream_set = set(p0_streams)
    seen_requests: set[str] = set()
    seen_streams: set[str] = set()
    assignments: list[dict[str, object]] = []
    expected_positions = (
        (sigma, length, replica, entry)
        for sigma, entry in zip(EXTENSION_SIGMAS, entries, strict=True)
        for length in EXTENSION_LENGTHS
        for replica in EXTENSION_REPLICAS
    )
    for index, (raw, expected) in enumerate(
        zip(cells, expected_positions, strict=True)
    ):
        if not isinstance(raw, Mapping) or set(raw) != _CELL_FIELDS:
            raise RuntimeError("extension cell fields are invalid")
        sigma, length, replica, entry = expected
        if (
            raw.get("cell_index") != index
            or raw.get("sigma") != sigma.hex()
            or raw.get("length") != length
            or raw.get("replica") != replica
        ):
            raise RuntimeError("extension cells are not in canonical order")
        request_sha256 = raw.get("request_sha256")
        streams = raw.get("rng_material_sha256")
        if request_sha256 in p0_request_set or (
            isinstance(streams, list)
            and any(digest in p0_stream_set for digest in streams)
        ):
            raise RuntimeError("extension identity collision with P0")
        kernel_sha256 = _kernel_hash(length, sigma)
        request = TrajectoryRequest(
            length=length,
            sigma=sigma,
            sigma_grid_id=str(entry["sigma_grid_id"]),
            kappas=np.asarray(
                [float.fromhex(value) for value in entry["kappas"]],
                dtype=np.float64,
            ),
            master_seed=EXTENSION_MASTER_SEED,
            phase=EXTENSION_PHASE,
            replica=replica,
            kernel_sha256=kernel_sha256,
        )
        expected_request = request_digest(request)
        expected_streams = _stream_hashes(
            master_seed=EXTENSION_MASTER_SEED,
            length=length,
            sigma_grid_id=str(entry["sigma_grid_id"]),
            replica=replica,
        )
        if request_sha256 != expected_request:
            raise RuntimeError("extension request digest mismatch")
        if streams != list(expected_streams):
            raise RuntimeError("extension RNG material digest mismatch")
        if request_sha256 in seen_requests or any(
            digest in seen_streams for digest in expected_streams
        ):
            raise RuntimeError("extension request or RNG identity collision")
        seen_requests.add(str(request_sha256))
        seen_streams.update(expected_streams)
        identity = {
            "cell_index": index,
            "sigma": sigma.hex(),
            "length": length,
            "replica": replica,
            "request_sha256": expected_request,
        }
        cell_id = f"{index:03d}-{_sha256(_canonical_bytes(identity))[:16]}"
        cell_path = f"cells/{cell_id}"
        if (
            raw.get("cell_id") != cell_id
            or raw.get("sigma_grid_id") != entry["sigma_grid_id"]
            or raw.get("kappas") != entry["kappas"]
            or raw.get("kernel_sha256") != kernel_sha256
            or raw.get("cell_path") != cell_path
            or raw.get("run_path") != f"{cell_path}/run"
            or raw.get("manifest_path") != f"{cell_path}/manifest.json"
        ):
            raise RuntimeError("extension cell identity or path mismatch")
        assignments.append(
            {
                "cell_index": index,
                "request_sha256": expected_request,
                "streams": list(expected_streams),
            }
        )
    expected_assignment_hash = _sha256(_canonical_bytes({"assignments": assignments}))
    if protocol.get("rng_assignment_sha256") != expected_assignment_hash:
        raise RuntimeError("extension aggregate RNG assignment hash mismatch")
