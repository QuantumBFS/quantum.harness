from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from collections.abc import Mapping, Sequence
from itertools import pairwise
from pathlib import Path
from types import MappingProxyType
from typing import Never

import numpy as np

from .counter_rng import STREAM_COUNT, StreamIdentity, derive_stream_material
from .kernel import periodic_kernel
from .pilot import (
    PILOT_KAPPAS,
    PILOT_LENGTHS,
    PILOT_MASTER_SEED,
    PILOT_PROGRESS_MAX_BYTES,
    PILOT_REPLICAS,
    PILOT_RUN_SPEC_MAX_BYTES,
    PILOT_SIGMAS,
    _close_directory_chain,
    _file_hash,
    _open_directory_chain,
    _open_regular_at,
    _read_canonical,
    _read_descriptor_bounded,
    _require_directory_chain,
    _require_regular_at_identity,
)
from .pilot_analysis import (
    ANALYSIS_SCHEMA,
    OBSERVABLE_COLUMNS,
    P1_MASTER_SEED,
    P1_REPLICAS,
    _pool_estimates,
    _selector_estimates,
    _transition_evidence,
    select_p1_brackets,
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
P0_ANALYSIS_MAX_BYTES = 16 * 1024 * 1024
DESIGN_MAX_BYTES = 1024 * 1024
P0_PROGRESS_MAX_BYTES = PILOT_PROGRESS_MAX_BYTES
P0_RUN_SPEC_MAX_BYTES = PILOT_RUN_SPEC_MAX_BYTES

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


def _file_sha256(path: Path) -> str:
    return _file_hash(
        path,
        maximum_size=DESIGN_MAX_BYTES,
        description="P0 extension design",
    )


def load_frozen_p0_analysis(path: Path) -> dict[str, object]:
    document, _ = _read_canonical(
        path,
        "frozen P0 analysis artifact",
        maximum_size=P0_ANALYSIS_MAX_BYTES,
    )
    _validate_source(document)
    return document


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
    _validate_recomputed_brackets(p0_analysis)


def _read_evidence_document_at(
    root_fd: int,
    name: str,
    description: str,
    maximum_size: int,
) -> tuple[dict[str, object], bytes]:
    descriptor, original = _open_regular_at(
        name,
        root_fd,
        description,
        maximum_size=maximum_size,
    )
    try:
        payload = _read_descriptor_bounded(descriptor, maximum_size, description)
        _require_regular_at_identity(
            name,
            root_fd,
            descriptor,
            original,
            description,
        )
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError(f"{description} is not canonical JSON") from error
        if not isinstance(document, dict) or payload != _canonical_bytes(document):
            raise RuntimeError(f"{description} is not canonical JSON")
        _require_regular_at_identity(
            name,
            root_fd,
            descriptor,
            original,
            description,
        )
        return document, payload
    finally:
        os.close(descriptor)


def _load_p0_evidence(
    p0_evidence_root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(p0_evidence_root, Path) or not p0_evidence_root.is_absolute():
        raise RuntimeError("p0_evidence_root must be an absolute canonical directory")
    try:
        if p0_evidence_root.resolve(strict=True) != p0_evidence_root:
            raise RuntimeError(
                "p0_evidence_root must be canonical and contain no symlink components"
            )
        chain = _open_directory_chain(p0_evidence_root, create=False)
    except RuntimeError:
        raise
    except OSError as error:
        raise RuntimeError("p0_evidence_root is missing or unsafe") from error
    try:
        root_fd = chain[-1][1]
        run_spec, run_payload = _read_evidence_document_at(
            root_fd,
            "run_spec.json",
            "frozen P0 run spec evidence",
            P0_RUN_SPEC_MAX_BYTES,
        )
        progress, progress_payload = _read_evidence_document_at(
            root_fd,
            "progress.json",
            "frozen P0 progress evidence",
            P0_PROGRESS_MAX_BYTES,
        )
        _require_directory_chain(chain, allow_final_mutation=False)
        if _sha256(run_payload) != P0_RUN_SPEC_SHA256:
            raise RuntimeError("frozen P0 run spec evidence hash mismatch")
        if _sha256(progress_payload) != P0_PROGRESS_SHA256:
            raise RuntimeError("frozen P0 progress evidence hash mismatch")
        return run_spec, progress
    finally:
        _close_directory_chain(chain)


def _validate_recomputed_brackets(p0_analysis: Mapping[str, object]) -> None:
    bracket = select_p1_brackets(p0_analysis)
    if not isinstance(bracket, Mapping):
        _malformed("recomputed P0 bracket document is malformed")
    unsigned = dict(bracket)
    digest = unsigned.pop("bracket_document_sha256", None)
    if (
        digest != P0_BRACKET_DOCUMENT_SHA256
        or _sha256(_canonical_bytes(unsigned)) != digest
    ):
        raise RuntimeError("recomputed P0 bracket document hash mismatch")


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
    length: int,
    sigma_grid_id: str,
    replica: int,
    *,
    master_seed: int,
    phase: str,
) -> tuple[str, ...]:
    return tuple(
        derive_stream_material(
            StreamIdentity(
                master_seed=master_seed,
                phase=phase,
                length=length,
                sigma_grid_id=sigma_grid_id,
                replica=replica,
                stream_id=stream,
            )
        ).material_sha256
        for stream in range(STREAM_COUNT)
    )


def _p0_identity_hashes(
    p0_evidence_root: Path,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    document, _ = _load_p0_evidence(p0_evidence_root)
    try:
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


def _validate_bound_p0_extension_protocol_for_revision(
    protocol: Mapping[str, object],
    *,
    expected_source_revision: str,
) -> None:
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
        or protocol.get("design_sha256") != DESIGN_SHA256
        or _file_sha256(_design_path()) != DESIGN_SHA256
        or protocol.get("source_revision") != expected_source_revision
        or protocol.get("grid_namespace") != EXTENSION_GRID_NAMESPACE
        or protocol.get("master_seed") != EXTENSION_MASTER_SEED
        or protocol.get("phase") != EXTENSION_PHASE
        or protocol.get("purpose") != "exploratory-p0-extension-only"
        or protocol.get("lengths") != list(EXTENSION_LENGTHS)
        or protocol.get("replicas") != list(EXTENSION_REPLICAS)
        or protocol.get("loop_order") != ["sigma", "length", "replica"]
        or protocol.get("cell_count") != 96
    ):
        raise RuntimeError("extension bound protocol contract is invalid")


def build_p0_extension_protocol(
    p0_analysis: Mapping[str, object],
    p0_evidence_root: Path,
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

    p0_requests, p0_streams = _p0_identity_hashes(p0_evidence_root)
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
                    length=length,
                    sigma_grid_id=grid_id,
                    replica=replica,
                    master_seed=EXTENSION_MASTER_SEED,
                    phase=EXTENSION_PHASE,
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
    validate_p0_extension_protocol(p0_analysis, protocol, p0_evidence_root)
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


def _exact_digest(raw: object, name: str) -> str:
    if (
        not isinstance(raw, str)
        or len(raw) != 64
        or any(character not in "0123456789abcdef" for character in raw)
    ):
        _malformed(f"extension {name} digest is malformed")
    return raw


def _validate_p0_extension_protocol_for_revision(
    p0_analysis: Mapping[str, object],
    protocol: Mapping[str, object],
    p0_evidence_root: Path,
    *,
    expected_source_revision: str,
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
    if (
        not isinstance(expected_source_revision, str)
        or len(expected_source_revision) != 40
        or any(
            character not in "0123456789abcdef"
            for character in expected_source_revision
        )
        or protocol.get("source_revision") != expected_source_revision
    ):
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
    p0_requests, p0_streams = _p0_identity_hashes(p0_evidence_root)
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
        request_sha256 = _exact_digest(raw.get("request_sha256"), "request")
        raw_streams = raw.get("rng_material_sha256")
        if not isinstance(raw_streams, list) or len(raw_streams) != STREAM_COUNT:
            _malformed("extension RNG material digest list is malformed")
        streams = tuple(_exact_digest(digest, "RNG material") for digest in raw_streams)
        if request_sha256 in p0_request_set or any(
            digest in p0_stream_set for digest in streams
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
            length=length,
            sigma_grid_id=str(entry["sigma_grid_id"]),
            replica=replica,
            master_seed=EXTENSION_MASTER_SEED,
            phase=EXTENSION_PHASE,
        )
        if request_sha256 != expected_request:
            raise RuntimeError("extension request digest mismatch")
        if streams != expected_streams:
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


def validate_p0_extension_protocol(
    p0_analysis: Mapping[str, object],
    protocol: Mapping[str, object],
    p0_evidence_root: Path,
) -> None:
    _validate_p0_extension_protocol_for_revision(
        p0_analysis,
        protocol,
        p0_evidence_root,
        expected_source_revision=_current_revision(),
    )


_ESTIMATE_FIELDS = {
    "sigma_hex",
    "length",
    "kappa_hex",
    "replica_count",
    "means",
    "standard_errors",
    "request_sha256",
}
_P0_ANALYSIS_FIELDS = {
    "schema_version",
    "p0_run_spec_sha256",
    "p0_progress_sha256",
    "source_revision",
    "analysis_plan_sha256",
    "observable_columns",
    "estimates",
    "analysis_document_sha256",
}
_EXTENSION_ANALYSIS_FIELDS = {
    "schema_version",
    "source_extension_protocol_sha256",
    "extension_run_spec_sha256",
    "extension_progress_sha256",
    "source_revision",
    "analysis_plan_sha256",
    "observable_columns",
    "estimates",
    "analysis_document_sha256",
}
_COMBINED_FIELDS = {
    "schema_version",
    "source_p0_analysis_document_sha256",
    "source_extension_analysis_document_sha256",
    "p0_run_spec_sha256",
    "p0_progress_sha256",
    "extension_run_spec_sha256",
    "extension_progress_sha256",
    "p0_source_revision",
    "extension_source_revision",
    "observable_columns",
    "sigma_entries",
    "estimate_count",
    "analysis_document_sha256",
}
_COMBINED_SIGMA_FIELDS = {"sigma_hex", "kappas", "lengths", "estimates"}


def _exact_revision(raw: object, name: str) -> str:
    if (
        not isinstance(raw, str)
        or len(raw) != 40
        or any(character not in "0123456789abcdef" for character in raw)
    ):
        _malformed(f"{name} source revision is malformed")
    return raw


def _require_builtin_int(raw: object, name: str) -> int:
    if type(raw) is not int:
        _malformed(f"{name} must be a built-in integer")
    return raw


def _analysis_hash(analysis: Mapping[str, object]) -> str:
    digest = _exact_digest(analysis.get("analysis_document_sha256"), "analysis")
    unsigned = dict(analysis)
    unsigned.pop("analysis_document_sha256", None)
    if _sha256(_canonical_bytes(unsigned)) != digest:
        raise RuntimeError("source analysis document digest mismatch")
    return digest


def _validated_combination_rows(
    source: Mapping[str, object],
    *,
    schema: str,
    sigmas: tuple[float, ...],
    grids: Mapping[float, tuple[float, ...]],
    replica_count: int,
    source_name: str,
    expected_fields: set[str],
) -> tuple[
    dict[tuple[float, int, float], Mapping[str, object]],
    dict[tuple[float, int], tuple[str, ...]],
    set[str],
]:
    if (
        not isinstance(source, Mapping)
        or set(source) != expected_fields
        or source.get("schema_version") != schema
    ):
        raise RuntimeError(f"{source_name} analysis schema is invalid")
    raw_columns = source.get("observable_columns")
    if not isinstance(raw_columns, Mapping) or set(raw_columns) != set(
        OBSERVABLE_COLUMNS
    ):
        raise RuntimeError(f"{source_name} observable columns are invalid")
    for name, expected_index in OBSERVABLE_COLUMNS.items():
        index = _require_builtin_int(
            raw_columns[name], f"{source_name} observable column index"
        )
        if index != expected_index:
            raise RuntimeError(f"{source_name} observable columns are invalid")
    raw_rows = source.get("estimates")
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        _malformed(f"{source_name} estimates are malformed")
    expected_identities = [
        (sigma, length, kappa)
        for sigma in sigmas
        for length in PILOT_LENGTHS
        for kappa in grids[sigma]
    ]
    if len(raw_rows) != len(expected_identities):
        raise RuntimeError(f"{source_name} estimate cardinality is invalid")

    rows: dict[tuple[float, int, float], Mapping[str, object]] = {}
    group_requests: dict[tuple[float, int], tuple[str, ...]] = {}
    request_owners: dict[str, tuple[float, int]] = {}
    for raw, expected in zip(raw_rows, expected_identities, strict=True):
        if not isinstance(raw, Mapping) or set(raw) != _ESTIMATE_FIELDS:
            raise RuntimeError(f"{source_name} estimate shape is invalid")
        sigma = _exact_hex(raw.get("sigma_hex"))
        kappa = _exact_hex(raw.get("kappa_hex"))
        length = _require_builtin_int(
            raw.get("length"), f"{source_name} estimate length"
        )
        identity = (sigma, length, kappa)
        if identity != expected:
            raise RuntimeError(
                f"{source_name} grid estimates are not in canonical order"
            )
        raw_replica_count = _require_builtin_int(
            raw.get("replica_count"), f"{source_name} replica count"
        )
        if raw_replica_count != replica_count:
            raise RuntimeError(f"{source_name} replica count is invalid")
        means = raw.get("means")
        errors = raw.get("standard_errors")
        if (
            not isinstance(means, Mapping)
            or not isinstance(errors, Mapping)
            or set(means) != set(OBSERVABLE_COLUMNS)
            or set(errors) != set(OBSERVABLE_COLUMNS)
        ):
            raise RuntimeError(f"{source_name} observable moments are invalid")
        for name in OBSERVABLE_COLUMNS:
            mean = means[name]
            error = errors[name]
            if (
                not isinstance(mean, (int, float))
                or isinstance(mean, bool)
                or not isinstance(error, (int, float))
                or isinstance(error, bool)
                or not math.isfinite(float(mean))
                or not math.isfinite(float(error))
                or float(error) < 0.0
            ):
                raise RuntimeError(f"{source_name} observable moments must be finite")
        raw_requests = raw.get("request_sha256")
        if not isinstance(raw_requests, list) or len(raw_requests) != replica_count:
            raise RuntimeError(f"{source_name} request replica list is invalid")
        requests = tuple(_exact_digest(value, "request") for value in raw_requests)
        if len(set(requests)) != replica_count:
            raise RuntimeError(f"{source_name} request identities are duplicate")
        group = (sigma, length)
        previous = group_requests.setdefault(group, requests)
        if previous != requests:
            raise RuntimeError(
                f"{source_name} ordered request bindings are inconsistent"
            )
        for request in requests:
            owner = request_owners.setdefault(request, group)
            if owner != group:
                raise RuntimeError(
                    f"{source_name} request identity is bound to multiple groups"
                )
        rows[(sigma, length, kappa)] = raw
    _analysis_hash(source)
    return rows, group_requests, set(request_owners)


def _validated_combination_sources(
    p0_analysis: Mapping[str, object],
    extension_analysis: Mapping[str, object],
) -> tuple[
    dict[tuple[float, int, float], Mapping[str, object]],
    dict[tuple[float, int, float], Mapping[str, object]],
    dict[float, tuple[float, ...]],
]:
    if not isinstance(p0_analysis, Mapping) or not isinstance(
        extension_analysis, Mapping
    ):
        _malformed("combination source analysis is malformed")
    for field in (
        "p0_run_spec_sha256",
        "p0_progress_sha256",
        "analysis_plan_sha256",
    ):
        _exact_digest(p0_analysis.get(field), f"P0 {field}")
    _exact_revision(p0_analysis.get("source_revision"), "P0")
    for field in (
        "source_extension_protocol_sha256",
        "extension_run_spec_sha256",
        "extension_progress_sha256",
        "analysis_plan_sha256",
    ):
        _exact_digest(extension_analysis.get(field), f"extension {field}")
    _exact_revision(extension_analysis.get("source_revision"), "extension")
    p0_grids = {sigma: tuple(PILOT_KAPPAS) for sigma in PILOT_SIGMAS}
    p0_rows, _p0_groups, p0_requests = _validated_combination_rows(
        p0_analysis,
        schema=ANALYSIS_SCHEMA,
        sigmas=tuple(PILOT_SIGMAS),
        grids=p0_grids,
        replica_count=len(PILOT_REPLICAS),
        source_name="P0",
        expected_fields=_P0_ANALYSIS_FIELDS,
    )
    extension_grids = {
        0.9: _recursive_binary64_grid_17(PILOT_KAPPAS[4], PILOT_KAPPAS[8]),
        1.0: _recursive_binary64_grid_17(PILOT_KAPPAS[5], PILOT_KAPPAS[10]),
    }
    for sigma, grid in extension_grids.items():
        digest = _sha256(_canonical_bytes({"kappas": [value.hex() for value in grid]}))
        if digest != EXTENSION_GRID_HASHES[sigma.hex()]:
            raise RuntimeError("extension grid binding is invalid")
    extension_rows, _extension_groups, extension_requests = _validated_combination_rows(
        extension_analysis,
        schema=EXTENSION_ANALYSIS_SCHEMA,
        sigmas=EXTENSION_SIGMAS,
        grids=extension_grids,
        replica_count=len(EXTENSION_REPLICAS),
        source_name="extension",
        expected_fields=_EXTENSION_ANALYSIS_FIELDS,
    )
    if p0_requests & extension_requests:
        raise RuntimeError("P0 and extension request identities overlap")
    return p0_rows, extension_rows, extension_grids


def _pooled_row(
    p0_row: Mapping[str, object],
    extension_row: Mapping[str, object],
) -> dict[str, object]:
    left_n = _require_builtin_int(p0_row["replica_count"], "P0 replica count")
    right_n = _require_builtin_int(
        extension_row["replica_count"], "extension replica count"
    )
    left_means = p0_row["means"]
    right_means = extension_row["means"]
    left_errors = p0_row["standard_errors"]
    right_errors = extension_row["standard_errors"]
    if not all(
        isinstance(value, Mapping)
        for value in (left_means, right_means, left_errors, right_errors)
    ):
        _malformed("source observable moments are malformed")
    means: dict[str, float] = {}
    standard_errors: dict[str, float] = {}
    total = 0
    for name in OBSERVABLE_COLUMNS:
        total, mean, standard_error = _pool_estimates(
            left_n,
            float(left_means[name]),
            float(left_errors[name]),
            right_n,
            float(right_means[name]),
            float(right_errors[name]),
        )
        means[name] = mean
        standard_errors[name] = standard_error
    requests = list(p0_row["request_sha256"]) + list(extension_row["request_sha256"])
    if len(requests) != total or len(set(requests)) != total:
        raise RuntimeError("combined request identities are invalid")
    return {
        "sigma_hex": p0_row["sigma_hex"],
        "length": p0_row["length"],
        "kappa_hex": p0_row["kappa_hex"],
        "replica_count": total,
        "means": means,
        "standard_errors": standard_errors,
        "request_sha256": requests,
    }


def _build_combined_p0_evidence(
    p0_analysis: Mapping[str, object],
    extension_analysis: Mapping[str, object],
) -> dict[str, object]:
    p0_rows, extension_rows, extension_grids = _validated_combination_sources(
        p0_analysis, extension_analysis
    )
    sigma_entries: list[dict[str, object]] = []
    estimate_count = 0
    for sigma in PILOT_SIGMAS:
        kappas = (
            tuple(PILOT_KAPPAS)
            if sigma not in extension_grids
            else tuple(sorted(set(PILOT_KAPPAS) | set(extension_grids[sigma])))
        )
        expected_count = 16 if sigma in (0.8, 1.1) else 31
        if len(kappas) != expected_count:
            raise RuntimeError("combined grid overlap or cardinality is invalid")
        estimates: list[dict[str, object]] = []
        for length in PILOT_LENGTHS:
            for kappa in kappas:
                identity = (sigma, length, kappa)
                p0_row = p0_rows.get(identity)
                extension_row = extension_rows.get(identity)
                if p0_row is not None and extension_row is not None:
                    row = _pooled_row(p0_row, extension_row)
                elif p0_row is not None:
                    row = dict(p0_row)
                elif extension_row is not None:
                    row = dict(extension_row)
                else:
                    raise RuntimeError("combined estimate is missing")
                estimates.append(row)
        estimate_count += len(estimates)
        sigma_entries.append(
            {
                "sigma_hex": sigma.hex(),
                "kappas": [value.hex() for value in kappas],
                "lengths": list(PILOT_LENGTHS),
                "estimates": estimates,
            }
        )
    if estimate_count != 282:
        raise RuntimeError("combined estimate cardinality is invalid")
    document: dict[str, object] = {
        "schema_version": COMBINED_ANALYSIS_SCHEMA,
        "source_p0_analysis_document_sha256": _analysis_hash(p0_analysis),
        "source_extension_analysis_document_sha256": _analysis_hash(extension_analysis),
        "p0_run_spec_sha256": _exact_digest(
            p0_analysis.get("p0_run_spec_sha256"), "P0 run spec"
        ),
        "p0_progress_sha256": _exact_digest(
            p0_analysis.get("p0_progress_sha256"), "P0 progress"
        ),
        "extension_run_spec_sha256": _exact_digest(
            extension_analysis.get("extension_run_spec_sha256"),
            "extension run spec",
        ),
        "extension_progress_sha256": _exact_digest(
            extension_analysis.get("extension_progress_sha256"),
            "extension progress",
        ),
        "p0_source_revision": _exact_revision(p0_analysis.get("source_revision"), "P0"),
        "extension_source_revision": _exact_revision(
            extension_analysis.get("source_revision"), "extension"
        ),
        "observable_columns": dict(OBSERVABLE_COLUMNS),
        "sigma_entries": sigma_entries,
        "estimate_count": estimate_count,
    }
    document["analysis_document_sha256"] = _sha256(_canonical_bytes(document))
    return document


def validate_combined_p0_evidence(
    p0_analysis: Mapping[str, object],
    extension_analysis: Mapping[str, object],
    combined_analysis: Mapping[str, object],
) -> None:
    if (
        not isinstance(combined_analysis, Mapping)
        or set(combined_analysis) != _COMBINED_FIELDS
    ):
        raise RuntimeError("combined analysis fields are invalid")
    estimate_count = _require_builtin_int(
        combined_analysis.get("estimate_count"), "combined estimate count"
    )
    if estimate_count != 282:
        raise RuntimeError("combined estimate cardinality is invalid")
    raw_columns = combined_analysis.get("observable_columns")
    if not isinstance(raw_columns, Mapping) or set(raw_columns) != set(
        OBSERVABLE_COLUMNS
    ):
        raise RuntimeError("combined observable columns are invalid")
    for name, expected_index in OBSERVABLE_COLUMNS.items():
        index = _require_builtin_int(
            raw_columns[name], "combined observable column index"
        )
        if index != expected_index:
            raise RuntimeError("combined observable columns are invalid")
    raw_entries = combined_analysis.get("sigma_entries")
    if (
        not isinstance(raw_entries, list)
        or len(raw_entries) != len(PILOT_SIGMAS)
        or any(
            not isinstance(entry, Mapping) or set(entry) != _COMBINED_SIGMA_FIELDS
            for entry in raw_entries
        )
    ):
        raise RuntimeError("combined analysis sigma entries are malformed")
    for entry in raw_entries:
        raw_lengths = entry.get("lengths")
        if not isinstance(raw_lengths, list) or len(raw_lengths) != len(PILOT_LENGTHS):
            raise RuntimeError("combined length axis is invalid")
        lengths = tuple(
            _require_builtin_int(value, "combined length axis value")
            for value in raw_lengths
        )
        if lengths != tuple(PILOT_LENGTHS):
            raise RuntimeError("combined length axis is invalid")
        raw_estimates = entry.get("estimates")
        if not isinstance(raw_estimates, list):
            raise RuntimeError("combined estimates are malformed")
        for raw in raw_estimates:
            if not isinstance(raw, Mapping) or set(raw) != _ESTIMATE_FIELDS:
                raise RuntimeError("combined estimate shape is invalid")
            _require_builtin_int(raw.get("length"), "combined estimate length")
            _require_builtin_int(raw.get("replica_count"), "combined replica count")
    expected = _build_combined_p0_evidence(p0_analysis, extension_analysis)
    if _canonical_bytes(combined_analysis) != _canonical_bytes(expected):
        raise RuntimeError("combined analysis semantic recomputation mismatch")


def combine_p0_evidence(
    p0_analysis: Mapping[str, object],
    extension_analysis: Mapping[str, object],
) -> dict[str, object]:
    document = _build_combined_p0_evidence(p0_analysis, extension_analysis)
    validate_combined_p0_evidence(p0_analysis, extension_analysis, document)
    return document
