from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import uuid
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence, Set
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Never

import numpy as np

from . import artifacts as _artifacts
from .alias import build_distance_alias
from .artifacts import (
    CONVERSION_VERSION,
    load_verified_trajectory,
    publish_batch_manifest,
    publish_trajectory,
    reconstruct_progress,
)
from .counter_rng import (
    RNG_VERSION,
    STREAM_COUNT,
    StreamIdentity,
    derive_stream_material,
)
from .kernel import periodic_kernel
from .poisson_sweep import run_poisson_numba
from .runtime import runtime_capability
from .trajectory import TrajectoryRequest, TrajectoryResult, request_digest
from .validation import (
    ValidationProtocol,
    _protocol_document,
    _repository_state,
    validate_report_payload,
)
from .validation_shards import validate_run_spec as validate_validation_run_spec

RUN_SPEC_SCHEMA = "challenge-194-pilot-run-spec-v1"
TEST_RUN_SPEC_SCHEMA = "challenge-194-pilot-test-run-spec-v1"
CELL_MANIFEST_SCHEMA = "challenge-194-pilot-cell-manifest-v1"
MERGED_SCHEMA = "challenge-194-pilot-progress-v1"
APPROVAL_SCHEMA = "challenge-194-pilot-correctness-approval-v1"
CORRECTNESS_APPROVAL_REVISION = "877ab9393f320bfe31ff74a26c3db1fb205d7ef3"
APPROVAL_REGISTRY_SHA256 = (
    "29dc5d04fd18728ee46fffe90c70d98caa61032005974f354e2b4e0e6018a7ab"
)
PILOT_SIGMAS = (0.8, 0.9, 1.0, 1.1)
PILOT_LENGTHS = (2**10, 2**14, 2**18)
PILOT_REPLICAS = tuple(range(8))
PILOT_KAPPAS = (0.0,) + tuple(0.25 * 1.25**j for j in range(15))
PILOT_MASTER_SEED = 19_420_260_729
PILOT_PHASE = "pilot"
RUN_SPEC_NAME = "run_spec.json"
MERGED_NAME = "progress.json"
_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
APPROVAL_MAX_BYTES = 16 * 1024
PILOT_RUN_SPEC_MAX_BYTES = 1024 * 1024
PILOT_MARKER_MAX_BYTES = 16 * 1024
PILOT_PROGRESS_MAX_BYTES = 256 * 1024
CORRECTNESS_RUN_SPEC_MAX_BYTES = 128 * 1024 * 1024
CORRECTNESS_REPORT_MAX_BYTES = 256 * 1024 * 1024
PILOT_JSON_MAX_DEPTH = 32
PILOT_JSON_MAX_STRING = 4096
PILOT_JSON_MAX_CONTAINER = 100_000
PILOT_JSON_MAX_NODES = 20_000_000
CORRECTNESS_JSON_MAX_NODES = 64_000_000
PILOT_CELL_MAX_ENTRIES = 64

_read_descriptor_bounded = _artifacts._read_descriptor_bounded
_generation_tuple = _artifacts._generation_tuple
_hash_descriptor = _artifacts._hash_descriptor

# This is intentionally narrower than validation's implementation inventory.
# Drift in any module that defines the model, RNG, trajectory, or production
# engine invalidates the correctness evidence; orchestration files may differ.
SCIENTIFIC_ENGINE_MODULES = (
    "src/long_range_percolation/model.py",
    "src/long_range_percolation/kernel.py",
    "src/long_range_percolation/counter_rng.py",
    "src/long_range_percolation/alias.py",
    "src/long_range_percolation/edge_set.py",
    "src/long_range_percolation/observables.py",
    "src/long_range_percolation/production_union_find.py",
    "src/long_range_percolation/trajectory.py",
    "src/long_range_percolation/poisson_reference.py",
    "src/long_range_percolation/poisson_sweep.py",
)


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


def _document_hash(document: Mapping[str, object], field: str) -> str:
    unsigned = dict(document)
    unsigned.pop(field, None)
    return _sha256(_canonical_bytes(unsigned))


def _solution_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_root() -> Path:
    return _solution_root().parents[4]


def _validate_json_bounds(
    value: object, *, maximum_nodes: int = PILOT_JSON_MAX_NODES
) -> None:
    stack: list[tuple[object, int]] = [(value, 1)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > maximum_nodes:
            raise RuntimeError("JSON node count exceeds the frozen limit")
        if depth > PILOT_JSON_MAX_DEPTH:
            raise RuntimeError("JSON depth exceeds the frozen limit")
        if isinstance(item, str):
            if len(item) > PILOT_JSON_MAX_STRING:
                raise RuntimeError("JSON string exceeds the frozen limit")
        elif isinstance(item, dict):
            if len(item) > PILOT_JSON_MAX_CONTAINER:
                raise RuntimeError("JSON mapping exceeds the frozen limit")
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > PILOT_JSON_MAX_STRING:
                    raise RuntimeError("JSON key exceeds the frozen limit")
                stack.append((child, depth + 1))
        elif isinstance(item, list):
            if len(item) > PILOT_JSON_MAX_CONTAINER:
                raise RuntimeError("JSON sequence exceeds the frozen limit")
            stack.extend((child, depth + 1) for child in item)


DirectoryEntry = tuple[Path, int, os.stat_result]


def _directory_identity(metadata: object) -> tuple[int, int, int, int, int]:
    return (
        int(metadata.st_dev),
        int(metadata.st_ino),
        int(metadata.st_mode),
        int(metadata.st_uid),
        int(metadata.st_gid),
    )


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _open_directory_at(name: str, parent_fd: int) -> int:
    return os.open(name, _directory_flags(), dir_fd=parent_fd)


def _snapshot_existing_directories(path: Path) -> dict[Path, os.stat_result]:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    snapshots: dict[Path, os.stat_result] = {}
    for component in absolute.parts:
        if component == absolute.anchor:
            candidate = current
        else:
            current = current / component
            candidate = current
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            break
        except OSError as error:
            raise RuntimeError("unable to inspect directory ancestry") from error
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise RuntimeError("directory ancestry must contain only directories")
        snapshots[candidate] = metadata
    return snapshots


def _open_directory_chain(
    path: Path, *, create: bool, allow_final_mutation: bool = False
) -> list[DirectoryEntry]:
    absolute = path.absolute()
    snapshots = _snapshot_existing_directories(absolute)
    entries: list[DirectoryEntry] = []
    current_path = Path(absolute.anchor)
    try:
        descriptor = os.open(absolute.anchor, _directory_flags())
        root_status = os.fstat(descriptor)
        entries.append((current_path, descriptor, root_status))
        for component in absolute.parts[1:]:
            parent_fd = entries[-1][1]
            current_path = current_path / component
            try:
                descriptor = _open_directory_at(component, parent_fd)
            except FileNotFoundError:
                if not create:
                    raise RuntimeError("directory ancestry is missing")
                try:
                    os.mkdir(component, 0o755, dir_fd=parent_fd)
                except FileExistsError:
                    pass
                descriptor = _open_directory_at(component, parent_fd)
            status = os.fstat(descriptor)
            if not stat.S_ISDIR(status.st_mode):
                os.close(descriptor)
                raise RuntimeError("directory ancestry contains a non-directory")
            original = snapshots.get(current_path)
            if original is not None:
                if (
                    _directory_identity(status) != _directory_identity(original)
                    or status.st_nlink < 2
                ):
                    os.close(descriptor)
                    raise RuntimeError(
                        "directory ancestor identity changed before descriptor open"
                    )
            entries.append((current_path, descriptor, status))
        if create:
            entries = [
                (entry_path, entry_fd, os.fstat(entry_fd))
                for entry_path, entry_fd, _ in entries
            ]
        _require_directory_chain(entries, allow_final_mutation=allow_final_mutation)
        return entries
    except BaseException:
        _close_directory_chain(entries)
        raise


def _close_directory_chain(entries: Sequence[DirectoryEntry]) -> None:
    for _, descriptor, _ in reversed(entries):
        os.close(descriptor)


def _open_cell_directory_chain(root: Path, cell_id: str) -> list[DirectoryEntry]:
    entries = _open_directory_chain(root, create=False, allow_final_mutation=True)
    root_fd = entries[-1][1]
    cell_locked = False
    try:
        fcntl.flock(root_fd, fcntl.LOCK_EX)
        try:
            _require_directory_chain(entries, allow_final_mutation=True)
            parent_path = root
            parent_fd = root_fd
            for name in ("cells", cell_id):
                child_path = parent_path / name
                try:
                    child_fd = _open_directory_at(name, parent_fd)
                except FileNotFoundError:
                    try:
                        os.mkdir(name, 0o755, dir_fd=parent_fd)
                    except FileExistsError:
                        pass
                    child_fd = _open_directory_at(name, parent_fd)
                child_status = os.fstat(child_fd)
                entries.append((child_path, child_fd, child_status))
                parent_path = child_path
                parent_fd = child_fd
            fcntl.flock(parent_fd, fcntl.LOCK_EX)
            cell_locked = True
            entries = [
                (entry_path, entry_fd, os.fstat(entry_fd))
                for entry_path, entry_fd, _ in entries
            ]
            _require_directory_chain(entries, allow_final_mutation=False)
            return entries
        finally:
            fcntl.flock(root_fd, fcntl.LOCK_UN)
    except BaseException:
        if cell_locked:
            fcntl.flock(entries[-1][1], fcntl.LOCK_UN)
        _close_directory_chain(entries)
        raise


def _require_directory_chain(
    entries: Sequence[DirectoryEntry],
    *,
    allow_final_mutation: bool,
    mutable_indexes: Set[int] = frozenset(),
) -> None:
    del allow_final_mutation, mutable_indexes
    for path, descriptor, original in entries:
        try:
            path_status = path.lstat()
            descriptor_status = os.fstat(descriptor)
        except OSError as error:
            raise RuntimeError("directory ancestor identity changed") from error
        if (
            stat.S_ISLNK(path_status.st_mode)
            or not stat.S_ISDIR(path_status.st_mode)
            or _directory_identity(path_status)
            != _directory_identity(descriptor_status)
            or _directory_identity(descriptor_status) != _directory_identity(original)
            or descriptor_status.st_nlink < 2
        ):
            raise RuntimeError("directory identity changed")


def _directory_generation(path: Path, descriptor: int) -> tuple[int, ...]:
    try:
        path_status = path.lstat()
        descriptor_status = os.fstat(descriptor)
    except OSError as error:
        raise RuntimeError("pilot cell directory identity changed") from error
    if _generation_tuple(path_status) != _generation_tuple(descriptor_status):
        raise RuntimeError("pilot cell directory identity changed")
    return _generation_tuple(descriptor_status)


def _require_directory_generation(
    path: Path, descriptor: int, expected: tuple[int, ...]
) -> None:
    if _directory_generation(path, descriptor) != expected:
        raise RuntimeError("pilot cell directory generation changed during work")


def _open_regular_at(
    name: str,
    parent_fd: int,
    description: str,
    *,
    maximum_size: int | None = None,
) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if stat.S_ISLNK(before.st_mode):
            raise RuntimeError(f"{description} must not be a symlink")
        descriptor = os.open(name, flags, dir_fd=parent_fd)
        opened = os.fstat(descriptor)
    except RuntimeError:
        raise
    except OSError as error:
        raise RuntimeError(f"unable to open {description}") from error
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(opened.st_mode)
        or _generation_tuple(before) != _generation_tuple(opened)
    ):
        os.close(descriptor)
        raise RuntimeError(f"{description} identity changed before descriptor open")
    if maximum_size is not None and opened.st_size > maximum_size:
        os.close(descriptor)
        raise RuntimeError(f"{description} exceeds the byte-size limit")
    return descriptor, opened


def _require_regular_at_identity(
    name: str,
    parent_fd: int,
    descriptor: int,
    original: os.stat_result,
    description: str,
) -> None:
    try:
        path_status = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        descriptor_status = os.fstat(descriptor)
    except OSError as error:
        raise RuntimeError(f"{description} pathname identity changed") from error
    if (
        not stat.S_ISREG(path_status.st_mode)
        or _generation_tuple(path_status) != _generation_tuple(descriptor_status)
        or _generation_tuple(descriptor_status) != _generation_tuple(original)
    ):
        raise RuntimeError(f"{description} generation or identity changed")


def _read_canonical(
    path: Path,
    description: str,
    *,
    maximum_size: int,
    maximum_nodes: int = PILOT_JSON_MAX_NODES,
    allow_parent_mutation: bool = False,
) -> tuple[dict[str, object], bytes]:
    parent_chain = _open_directory_chain(
        path.parent,
        create=False,
        allow_final_mutation=allow_parent_mutation,
    )
    parent_fd = parent_chain[-1][1]
    descriptor, original = _open_regular_at(
        path.name, parent_fd, description, maximum_size=maximum_size
    )
    try:
        payload = _read_descriptor_bounded(descriptor, maximum_size, description)
        _require_regular_at_identity(
            path.name, parent_fd, descriptor, original, description
        )
        try:
            document = json.loads(payload)
        except (
            UnicodeError,
            json.JSONDecodeError,
            RecursionError,
            MemoryError,
            OverflowError,
            ValueError,
        ) as error:
            raise RuntimeError(f"{description} is not valid JSON") from error
        _validate_json_bounds(document, maximum_nodes=maximum_nodes)
        if not isinstance(document, dict) or payload != _canonical_bytes(document):
            raise RuntimeError(f"{description} is not canonical JSON")
        _require_regular_at_identity(
            path.name, parent_fd, descriptor, original, description
        )
        _require_directory_chain(
            parent_chain,
            allow_final_mutation=allow_parent_mutation,
        )
        return document, payload
    finally:
        os.close(descriptor)
        _close_directory_chain(parent_chain)


def _link_at(
    source: str, destination: str, source_fd: int, destination_fd: int
) -> None:
    os.link(
        source,
        destination,
        src_dir_fd=source_fd,
        dst_dir_fd=destination_fd,
        follow_symlinks=False,
    )


def _publish_once(path: Path, document: Mapping[str, object]) -> None:
    payload = _canonical_bytes(document)
    parent_chain = _open_directory_chain(path.parent, create=True)
    parent_fd = parent_chain[-1][1]
    temporary = f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o644,
        dir_fd=parent_fd,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            _link_at(temporary, path.name, parent_fd, parent_fd)
        except FileExistsError:
            existing, existing_payload = _read_canonical(
                path,
                "immutable output",
                maximum_size=max(len(payload), PILOT_MARKER_MAX_BYTES),
            )
            if existing_payload != payload or existing != dict(document):
                raise RuntimeError("immutable output already exists with other bytes")
        os.unlink(temporary, dir_fd=parent_fd)
        temporary = ""
        os.fsync(parent_fd)
        _require_directory_chain(parent_chain, allow_final_mutation=True)
    finally:
        if temporary:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        _close_directory_chain(parent_chain)


def _file_hash(path: Path) -> str:
    parent_chain = _open_directory_chain(path.parent, create=False)
    parent_fd = parent_chain[-1][1]
    descriptor, original = _open_regular_at(
        path.name, parent_fd, f"required source file {path}"
    )
    try:
        digest, size = _hash_descriptor(descriptor, f"required source file {path}")
        if size != original.st_size:
            raise RuntimeError(f"required source file size changed: {path}")
        _require_regular_at_identity(
            path.name,
            parent_fd,
            descriptor,
            original,
            f"required source file {path}",
        )
        _require_directory_chain(parent_chain, allow_final_mutation=False)
        return digest
    finally:
        os.close(descriptor)
        _close_directory_chain(parent_chain)


def _lock_hash() -> str:
    return _file_hash(_solution_root() / "uv.lock")


def _scientific_hashes() -> dict[str, str]:
    root = _solution_root()
    return {
        relative: _file_hash(root / relative) for relative in SCIENTIFIC_ENGINE_MODULES
    }


def _aggregate_hash(values: Mapping[str, str]) -> str:
    return _sha256(_canonical_bytes(dict(values)))


def _current_source(*, require_clean: bool) -> dict[str, object]:
    source = _repository_state()
    revision = source.get("source_revision")
    if not isinstance(revision, str) or _HEX40.fullmatch(revision) is None:
        raise RuntimeError("current orchestration revision is unavailable")
    if require_clean and (
        source.get("clean_tree") is not True
        or source.get("provenance_error") is not None
    ):
        raise RuntimeError("current repository must be clean")
    return source


def _runtime_document() -> tuple[dict[str, object], str]:
    document = runtime_capability()
    return document, _sha256(_canonical_bytes(document))


def _analysis_plan_hash() -> str:
    path = _solution_root() / "PILOT_PLAN.md"
    return _file_hash(path)


def _approval_registry_path() -> Path:
    return _solution_root() / "pilot_correctness_approval.json"


def _check_registry_document(
    validation_spec: Mapping[str, object],
) -> dict[str, object]:
    cells = validation_spec.get("cells")
    global_checks = validation_spec.get("global_expected_checks")
    if (
        not isinstance(cells, list)
        or len(cells) != 120
        or not isinstance(global_checks, list)
    ):
        raise RuntimeError("correctness check registry has invalid cardinality")
    registry_cells: list[dict[str, object]] = []
    for index, cell in enumerate(cells):
        if not isinstance(cell, Mapping):
            raise RuntimeError("correctness cell registry is malformed")
        checks = cell.get("expected_checks")
        if not isinstance(checks, list) or len(checks) > 100_000:
            raise RuntimeError("correctness cell check registry is unbounded")
        registry_cells.append(
            {
                "case_index": cell.get("case_index", index),
                "case_id": cell.get("case_id"),
                "expected_checks": checks,
            }
        )
    return {"global": global_checks, "cells": registry_cells}


def _load_approval_registry() -> dict[str, object]:
    document, payload = _read_canonical(
        _approval_registry_path(),
        "Pilot correctness approval registry",
        maximum_size=APPROVAL_MAX_BYTES,
    )
    if _sha256(payload) != APPROVAL_REGISTRY_SHA256:
        raise RuntimeError(
            "Pilot correctness approval registry does not match pinned SHA256"
        )
    expected = {
        "schema_version",
        "approval_revision",
        "validation_source_revision",
        "report_sha256",
        "run_spec_sha256",
        "protocol_sha256",
        "check_registry_sha256",
        "check_count",
        "cell_count",
        "scientific_engine_sha256",
    }
    if set(document) != expected or document.get("schema_version") != APPROVAL_SCHEMA:
        raise RuntimeError("Pilot correctness approval registry is not exact")
    for field in (
        "report_sha256",
        "run_spec_sha256",
        "protocol_sha256",
        "check_registry_sha256",
        "scientific_engine_sha256",
    ):
        if (
            not isinstance(document.get(field), str)
            or _HEX64.fullmatch(str(document[field])) is None
        ):
            raise RuntimeError(f"approval registry {field} is malformed")
    if (
        document.get("approval_revision") != CORRECTNESS_APPROVAL_REVISION
        or not isinstance(document.get("validation_source_revision"), str)
        or _HEX40.fullmatch(str(document["validation_source_revision"])) is None
        or document.get("cell_count") != 120
        or document.get("check_count") != 22_755
    ):
        raise RuntimeError("Pilot correctness approval identity is invalid")
    return document


def _approval_registry_digest() -> str:
    _load_approval_registry()
    return APPROVAL_REGISTRY_SHA256


def _validation_spec_path(report: Path) -> Path:
    candidate = report.parent.parent / RUN_SPEC_NAME
    if candidate.is_file() and not candidate.is_symlink():
        return candidate
    raise RuntimeError("approved correctness report lacks adjacent immutable run spec")


def _verified_correctness(report_path: Path) -> dict[str, object]:
    approval = _load_approval_registry()
    report, report_payload = _read_canonical(
        report_path,
        "correctness report",
        maximum_size=CORRECTNESS_REPORT_MAX_BYTES,
        maximum_nodes=CORRECTNESS_JSON_MAX_NODES,
    )
    if _sha256(report_payload) != approval["report_sha256"]:
        raise RuntimeError("approved correctness report SHA256 mismatch")
    protocol = ValidationProtocol.production_v1()
    validate_report_payload(report, protocol)
    if report.get("passed") is not True:
        raise RuntimeError("correctness report did not pass")
    source = report.get("source")
    validation_source_revision = (
        source.get("source_revision") if isinstance(source, Mapping) else None
    )
    if (
        not isinstance(source, Mapping)
        or not isinstance(validation_source_revision, str)
        or _HEX40.fullmatch(validation_source_revision) is None
        or source.get("clean_tree") is not True
        or source.get("provenance_error") is not None
    ):
        raise RuntimeError("correctness report source evidence is not approved")

    validation_spec_path = _validation_spec_path(report_path)
    validation_spec, validation_spec_payload = _read_canonical(
        validation_spec_path,
        "correctness run spec",
        maximum_size=CORRECTNESS_RUN_SPEC_MAX_BYTES,
        maximum_nodes=CORRECTNESS_JSON_MAX_NODES,
    )
    if _sha256(validation_spec_payload) != approval["run_spec_sha256"]:
        raise RuntimeError("approved correctness run spec SHA256 mismatch")
    validate_validation_run_spec(validation_spec, enforce_production=True)
    cells = validation_spec.get("cells")
    if not isinstance(cells, list) or len(cells) != 120:
        raise RuntimeError("correctness run spec must contain exactly 120 cells")
    if (
        validation_source_revision != approval["validation_source_revision"]
        or validation_spec.get("source_revision") != validation_source_revision
        or validation_spec.get("uv_lock_sha256") != _lock_hash()
        or validation_spec.get("runtime_capability") != report.get("runtime_capability")
    ):
        raise RuntimeError("correctness source/runtime/lock evidence is inconsistent")
    if (
        validation_spec.get("protocol", {}).get("sha256") != approval["protocol_sha256"]
        or _sha256(_canonical_bytes(_check_registry_document(validation_spec)))
        != approval["check_registry_sha256"]
        or len(report.get("checks", [])) != approval["check_count"]
    ):
        raise RuntimeError("approved correctness protocol/check registry mismatch")

    expected_identities = Counter(
        (str(check["family"]), str(check["check_case_id"]))
        for check in validation_spec["global_expected_checks"]
    )
    for cell in cells:
        expected_identities.update(
            (str(check["family"]), str(check["check_case_id"]))
            for check in cell["expected_checks"]
        )
    actual_identities = Counter(
        (str(check.get("family")), str(check.get("case_id")))
        for check in report["checks"]
    )
    if actual_identities != expected_identities:
        raise RuntimeError(
            "correctness report check registry is incomplete or reordered"
        )

    recorded_modules = validation_spec.get("implementation_modules")
    if not isinstance(recorded_modules, Mapping):
        raise RuntimeError("correctness run spec lacks implementation hashes")
    current = _scientific_hashes()
    approved = {path: recorded_modules.get(path) for path in SCIENTIFIC_ENGINE_MODULES}
    if (
        approved != current
        or _aggregate_hash(current) != approval["scientific_engine_sha256"]
    ):
        raise RuntimeError("scientific engine module drift from correctness report")
    return {
        "correctness_report_sha256": _sha256(report_payload),
        "correctness_run_spec_sha256": _sha256(validation_spec_payload),
        "correctness_approval_registry_sha256": _sha256(_canonical_bytes(approval)),
        "validation_source_revision": validation_source_revision,
        "validated_engine_modules": current,
        "validated_engine_sha256": _aggregate_hash(current),
        "validation_runtime_capability_sha256": validation_spec[
            "runtime_capability_sha256"
        ],
    }


@dataclass(frozen=True)
class PilotCell:
    cell_index: int
    cell_id: str
    sigma: float
    length: int
    replica: int
    sigma_grid_id: str
    kappas: tuple[float, ...]
    kernel_sha256: str
    request_sha256: str
    cell_path: str
    run_path: str
    manifest_path: str
    rng_material_sha256: tuple[str, ...]

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> PilotCell:
        try:
            return cls(
                cell_index=int(document["cell_index"]),
                cell_id=str(document["cell_id"]),
                sigma=float.fromhex(str(document["sigma"])),
                length=int(document["length"]),
                replica=int(document["replica"]),
                sigma_grid_id=str(document["sigma_grid_id"]),
                kappas=tuple(float.fromhex(str(value)) for value in document["kappas"]),
                kernel_sha256=str(document["kernel_sha256"]),
                request_sha256=str(document["request_sha256"]),
                cell_path=str(document["cell_path"]),
                run_path=str(document["run_path"]),
                manifest_path=str(document["manifest_path"]),
                rng_material_sha256=tuple(
                    str(value) for value in document["rng_material_sha256"]
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("pilot cell is malformed") from error

    def request(self) -> TrajectoryRequest:
        return TrajectoryRequest(
            length=self.length,
            sigma=self.sigma,
            sigma_grid_id=self.sigma_grid_id,
            kappas=np.asarray(self.kappas, dtype=np.float64),
            master_seed=PILOT_MASTER_SEED,
            phase=PILOT_PHASE,
            replica=self.replica,
            kernel_sha256=self.kernel_sha256,
        )


def _stream_hashes(length: int, sigma_grid_id: str, replica: int) -> tuple[str, ...]:
    return tuple(
        derive_stream_material(
            StreamIdentity(
                master_seed=PILOT_MASTER_SEED,
                phase=PILOT_PHASE,
                length=length,
                sigma_grid_id=sigma_grid_id,
                replica=replica,
                stream_id=stream,
            )
        ).material_sha256
        for stream in range(STREAM_COUNT)
    )


def _build_document(
    *,
    lengths: Sequence[int],
    sigmas: Sequence[float],
    replicas: Sequence[int],
    kappas: Sequence[float],
    source: Mapping[str, object],
    runtime: Mapping[str, object],
    runtime_sha256: str,
    correctness: Mapping[str, object],
    waiver_timestamp: str,
    analysis_plan_sha256: str,
    schema_version: str,
    enforce_production: bool,
) -> dict[str, object]:
    protocol = {
        "lengths": list(lengths),
        "sigmas": [float(value).hex() for value in sigmas],
        "replicas": list(replicas),
        "kappas": [float(value).hex() for value in kappas],
        "master_seed": PILOT_MASTER_SEED,
        "phase": PILOT_PHASE,
        "loop_order": ["sigma", "length", "replica"],
        "purpose": "exploratory-window-selection-only",
    }
    protocol["sha256"] = _sha256(_canonical_bytes(protocol))
    cells: list[dict[str, object]] = []
    all_assignments: list[dict[str, object]] = []
    for sigma in sigmas:
        sigma_value = float(sigma)
        grid_id = f"pilot-p0-v1|sigma-f64={sigma_value.hex()}"
        for length in lengths:
            kernel = periodic_kernel(int(length), sigma_value)
            kernel_sha256 = _sha256(kernel.astype("<f8", copy=False).tobytes(order="C"))
            for replica in replicas:
                request = TrajectoryRequest(
                    length=int(length),
                    sigma=sigma_value,
                    sigma_grid_id=grid_id,
                    kappas=np.asarray(kappas, dtype=np.float64),
                    master_seed=PILOT_MASTER_SEED,
                    phase=PILOT_PHASE,
                    replica=int(replica),
                    kernel_sha256=kernel_sha256,
                )
                request_sha256 = request_digest(request)
                stream_hashes = _stream_hashes(int(length), grid_id, int(replica))
                index = len(cells)
                identity = {
                    "cell_index": index,
                    "sigma": sigma_value.hex(),
                    "length": int(length),
                    "replica": int(replica),
                    "request_sha256": request_sha256,
                }
                cell_id = f"{index:03d}-{_sha256(_canonical_bytes(identity))[:16]}"
                cell_path = f"cells/{cell_id}"
                cells.append(
                    {
                        **identity,
                        "cell_id": cell_id,
                        "sigma_grid_id": grid_id,
                        "kappas": [float(value).hex() for value in kappas],
                        "kernel_sha256": kernel_sha256,
                        "rng_material_sha256": list(stream_hashes),
                        "cell_path": cell_path,
                        "run_path": f"{cell_path}/run",
                        "manifest_path": f"{cell_path}/manifest.json",
                    }
                )
                all_assignments.append(
                    {
                        "cell_index": index,
                        "request_sha256": request_sha256,
                        "streams": list(stream_hashes),
                    }
                )
    rng_hash = _sha256(_canonical_bytes({"assignments": all_assignments}))
    engine_modules = dict(correctness["validated_engine_modules"])
    document: dict[str, object] = {
        "schema_version": schema_version,
        "artifact_root": ".",
        "protocol": protocol,
        "cells": cells,
        "cell_count": len(cells),
        "correctness_report_sha256": correctness["correctness_report_sha256"],
        "correctness_run_spec_sha256": correctness["correctness_run_spec_sha256"],
        "correctness_approval_registry_sha256": correctness[
            "correctness_approval_registry_sha256"
        ],
        "correctness_approval_revision": CORRECTNESS_APPROVAL_REVISION,
        "validation_source_revision": correctness["validation_source_revision"],
        "validated_engine_modules": engine_modules,
        "validated_engine_sha256": correctness["validated_engine_sha256"],
        "validation_runtime_capability_sha256": correctness[
            "validation_runtime_capability_sha256"
        ],
        "orchestration_revision": source["source_revision"],
        "clean_tree": True,
        "uv_lock_sha256": _lock_hash(),
        "runtime_capability": dict(runtime),
        "runtime_capability_sha256": runtime_sha256,
        "analysis_plan_sha256": analysis_plan_sha256,
        "rng_assignment_sha256": rng_hash,
        "capability_waiver": {
            "reason": "user-waived-after-correctness-gate",
            "benchmark_status": "cancelled-without-capability-report",
            "utc_timestamp": waiver_timestamp,
        },
        "merged_progress_path": MERGED_NAME,
    }
    document["run_spec_sha256"] = _document_hash(document, "run_spec_sha256")
    _validate_pilot_spec(
        document,
        enforce_production=enforce_production,
        expected_schema=schema_version,
    )
    return document


def build_pilot_run_spec(
    output_root: Path, validation_report: Path
) -> dict[str, object]:
    if not isinstance(output_root, Path) or not output_root.is_absolute():
        raise RuntimeError("output_root must be an absolute path")
    source = _current_source(require_clean=True)
    correctness = _verified_correctness(validation_report)
    runtime, runtime_hash = _runtime_document()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    document = _build_document(
        lengths=PILOT_LENGTHS,
        sigmas=PILOT_SIGMAS,
        replicas=PILOT_REPLICAS,
        kappas=PILOT_KAPPAS,
        source=source,
        runtime=runtime,
        runtime_sha256=runtime_hash,
        correctness=correctness,
        waiver_timestamp=timestamp,
        analysis_plan_sha256=_analysis_plan_hash(),
        schema_version=RUN_SPEC_SCHEMA,
        enforce_production=True,
    )
    _publish_once(output_root / RUN_SPEC_NAME, document)
    return document


def _relative_path(root: Path, value: object, prefix: str) -> Path:
    if not isinstance(value, str):
        raise RuntimeError("artifact path must be a string")
    relative = Path(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not relative.parts
        or relative.parts[0] != prefix
    ):
        raise RuntimeError("artifact path escapes its portable namespace")
    candidate = root / relative
    if candidate.resolve(strict=False) != candidate:
        raise RuntimeError("artifact path contains a symlink or alias")
    return candidate


def _validate_pilot_spec(
    document: Mapping[str, object],
    *,
    enforce_production: bool,
    expected_schema: str,
) -> None:
    expected_fields = {
        "schema_version",
        "artifact_root",
        "protocol",
        "cells",
        "cell_count",
        "correctness_report_sha256",
        "correctness_run_spec_sha256",
        "correctness_approval_registry_sha256",
        "correctness_approval_revision",
        "validation_source_revision",
        "validated_engine_modules",
        "validated_engine_sha256",
        "validation_runtime_capability_sha256",
        "orchestration_revision",
        "clean_tree",
        "uv_lock_sha256",
        "runtime_capability",
        "runtime_capability_sha256",
        "analysis_plan_sha256",
        "rng_assignment_sha256",
        "capability_waiver",
        "merged_progress_path",
        "run_spec_sha256",
    }
    if (
        set(document) != expected_fields
        or document.get("schema_version") != expected_schema
    ):
        raise RuntimeError("pilot run spec fields or schema are invalid")
    if document.get("run_spec_sha256") != _document_hash(document, "run_spec_sha256"):
        raise RuntimeError("pilot run spec hash mismatch")
    if (
        document.get("artifact_root") != "."
        or document.get("merged_progress_path") != MERGED_NAME
    ):
        raise RuntimeError("pilot portable paths are not frozen")
    for field in (
        "correctness_report_sha256",
        "correctness_run_spec_sha256",
        "correctness_approval_registry_sha256",
        "validated_engine_sha256",
        "validation_runtime_capability_sha256",
        "uv_lock_sha256",
        "runtime_capability_sha256",
        "analysis_plan_sha256",
        "rng_assignment_sha256",
    ):
        if (
            not isinstance(document.get(field), str)
            or _HEX64.fullmatch(str(document[field])) is None
        ):
            raise RuntimeError(f"pilot {field} is malformed")
    if (
        document.get("clean_tree") is not True
        or not isinstance(document.get("orchestration_revision"), str)
        or _HEX40.fullmatch(str(document["orchestration_revision"])) is None
        or document.get("correctness_approval_revision")
        != CORRECTNESS_APPROVAL_REVISION
        or not isinstance(document.get("validation_source_revision"), str)
        or _HEX40.fullmatch(str(document["validation_source_revision"])) is None
    ):
        raise RuntimeError("pilot orchestration source evidence is invalid")
    runtime = document.get("runtime_capability")
    if not isinstance(runtime, Mapping) or _sha256(
        _canonical_bytes(runtime)
    ) != document.get("runtime_capability_sha256"):
        raise RuntimeError("pilot runtime capability hash mismatch")
    modules = document.get("validated_engine_modules")
    if (
        not isinstance(modules, Mapping)
        or set(modules) != set(SCIENTIFIC_ENGINE_MODULES)
        or _aggregate_hash({str(k): str(v) for k, v in modules.items()})
        != document.get("validated_engine_sha256")
    ):
        raise RuntimeError("pilot scientific engine binding is invalid")
    waiver = document.get("capability_waiver")
    if (
        not isinstance(waiver, Mapping)
        or set(waiver) != {"reason", "benchmark_status", "utc_timestamp"}
        or waiver.get("reason") != "user-waived-after-correctness-gate"
        or waiver.get("benchmark_status") != "cancelled-without-capability-report"
        or not isinstance(waiver.get("utc_timestamp"), str)
        or not str(waiver["utc_timestamp"]).endswith("Z")
    ):
        raise RuntimeError("pilot capability waiver is invalid")
    if enforce_production:
        approval = _load_approval_registry()
        if (
            document.get("correctness_report_sha256") != approval["report_sha256"]
            or document.get("correctness_run_spec_sha256")
            != approval["run_spec_sha256"]
            or document.get("validation_source_revision")
            != approval["validation_source_revision"]
            or document.get("validated_engine_sha256")
            != approval["scientific_engine_sha256"]
            or document.get("correctness_approval_registry_sha256")
            != _sha256(_canonical_bytes(approval))
        ):
            raise RuntimeError("pilot run spec is not bound to approved correctness")

    protocol = document.get("protocol")
    if not isinstance(protocol, Mapping):
        raise RuntimeError("pilot protocol is malformed")
    unsigned_protocol = dict(protocol)
    protocol_hash = unsigned_protocol.pop("sha256", None)
    if protocol_hash != _sha256(_canonical_bytes(unsigned_protocol)):
        raise RuntimeError("pilot protocol hash mismatch")
    if enforce_production and unsigned_protocol != {
        "lengths": list(PILOT_LENGTHS),
        "sigmas": [value.hex() for value in PILOT_SIGMAS],
        "replicas": list(PILOT_REPLICAS),
        "kappas": [value.hex() for value in PILOT_KAPPAS],
        "master_seed": PILOT_MASTER_SEED,
        "phase": PILOT_PHASE,
        "loop_order": ["sigma", "length", "replica"],
        "purpose": "exploratory-window-selection-only",
    }:
        raise RuntimeError("pilot P0 protocol is not frozen")
    cells = document.get("cells")
    if (
        not isinstance(cells, list)
        or document.get("cell_count") != len(cells)
        or (enforce_production and len(cells) != 96)
    ):
        raise RuntimeError("pilot cell count is invalid")
    seen_ids: set[str] = set()
    seen_requests: set[str] = set()
    assignments: list[dict[str, object]] = []
    expected_positions = (
        [
            (sigma, length, replica)
            for sigma in PILOT_SIGMAS
            for length in PILOT_LENGTHS
            for replica in PILOT_REPLICAS
        ]
        if enforce_production
        else None
    )
    for index, raw in enumerate(cells):
        if not isinstance(raw, Mapping):
            raise RuntimeError("pilot cell is malformed")
        expected_keys = {
            "cell_index",
            "cell_id",
            "sigma",
            "length",
            "replica",
            "sigma_grid_id",
            "kappas",
            "kernel_sha256",
            "request_sha256",
            "rng_material_sha256",
            "cell_path",
            "run_path",
            "manifest_path",
        }
        raw_kappas = raw.get("kappas")
        raw_rng = raw.get("rng_material_sha256")
        expected_kappa_count = len(PILOT_KAPPAS) if enforce_production else None
        if (
            set(raw) != expected_keys
            or not isinstance(raw_kappas, list)
            or not 1 <= len(raw_kappas) <= len(PILOT_KAPPAS)
            or (
                expected_kappa_count is not None
                and len(raw_kappas) != expected_kappa_count
            )
            or not isinstance(raw_rng, list)
            or len(raw_rng) != STREAM_COUNT
        ):
            raise RuntimeError("pilot cell bounded fields are invalid")
        cell = PilotCell.from_document(raw)
        if cell.cell_index != index:
            raise RuntimeError("pilot cell registry is noncanonical")
        if (
            expected_positions is not None
            and (
                cell.sigma,
                cell.length,
                cell.replica,
            )
            != expected_positions[index]
        ):
            raise RuntimeError("pilot positional cell registry is not frozen")
        if enforce_production and cell.kappas != PILOT_KAPPAS:
            raise RuntimeError("pilot cell kappas are not frozen")
        if (
            cell.sigma_grid_id != f"pilot-p0-v1|sigma-f64={cell.sigma.hex()}"
            or request_digest(cell.request()) != cell.request_sha256
            or _HEX64.fullmatch(cell.kernel_sha256) is None
            or len(cell.rng_material_sha256) != STREAM_COUNT
            or tuple(cell.rng_material_sha256)
            != _stream_hashes(cell.length, cell.sigma_grid_id, cell.replica)
        ):
            raise RuntimeError("pilot cell request or RNG identity is stale")
        identity = {
            "cell_index": index,
            "sigma": cell.sigma.hex(),
            "length": cell.length,
            "replica": cell.replica,
            "request_sha256": cell.request_sha256,
        }
        expected_id = f"{index:03d}-{_sha256(_canonical_bytes(identity))[:16]}"
        expected_cell_path = f"cells/{expected_id}"
        if (
            cell.cell_id != expected_id
            or cell.cell_path != expected_cell_path
            or cell.run_path != f"{expected_cell_path}/run"
            or cell.manifest_path != f"{expected_cell_path}/manifest.json"
        ):
            raise RuntimeError("pilot cell paths are noncanonical")
        if cell.cell_id in seen_ids or cell.request_sha256 in seen_requests:
            raise RuntimeError("pilot cells contain duplicate identities")
        seen_ids.add(cell.cell_id)
        seen_requests.add(cell.request_sha256)
        assignments.append(
            {
                "cell_index": index,
                "request_sha256": cell.request_sha256,
                "streams": list(cell.rng_material_sha256),
            }
        )
    if _sha256(_canonical_bytes({"assignments": assignments})) != document.get(
        "rng_assignment_sha256"
    ):
        raise RuntimeError("pilot complete RNG assignment hash mismatch")


def _load_pilot_spec(
    path: Path,
    *,
    verify_current_environment: bool,
    production: bool,
) -> dict[str, object]:
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or path.name != RUN_SPEC_NAME
    ):
        raise RuntimeError("pilot run spec path must be absolute and canonical")
    document, _ = _read_canonical(
        path,
        "pilot run spec",
        maximum_size=PILOT_RUN_SPEC_MAX_BYTES,
        allow_parent_mutation=True,
    )
    _validate_pilot_spec(
        document,
        enforce_production=production,
        expected_schema=RUN_SPEC_SCHEMA if production else TEST_RUN_SPEC_SCHEMA,
    )
    if _lock_hash() != document["uv_lock_sha256"]:
        raise RuntimeError("uv.lock drift from pilot run spec")
    modules = _scientific_hashes()
    if (
        modules != document["validated_engine_modules"]
        or _aggregate_hash(modules) != document["validated_engine_sha256"]
    ):
        raise RuntimeError("scientific engine module drift from pilot run spec")
    if _analysis_plan_hash() != document["analysis_plan_sha256"]:
        raise RuntimeError("analysis plan drift from pilot run spec")
    if _approval_registry_digest() != document["correctness_approval_registry_sha256"]:
        raise RuntimeError("correctness approval registry drift from pilot run spec")
    if verify_current_environment:
        source = _current_source(require_clean=True)
        if source["source_revision"] != document["orchestration_revision"]:
            raise RuntimeError("orchestration revision drift from pilot run spec")
        runtime, runtime_hash = _runtime_document()
        if (
            runtime != document["runtime_capability"]
            or runtime_hash != document["runtime_capability_sha256"]
        ):
            raise RuntimeError("compute-node runtime capability drift")
    return document


def load_pilot_run_spec(
    path: Path, verify_current_environment: bool
) -> dict[str, object]:
    return _load_pilot_spec(
        path,
        verify_current_environment=verify_current_environment,
        production=True,
    )


def _expected(spec: Mapping[str, object], cell: PilotCell) -> dict[str, str]:
    return {
        "request_sha256": cell.request_sha256,
        "kernel_sha256": cell.kernel_sha256,
        "source_revision": str(spec["orchestration_revision"]),
        "uv_lock_sha256": str(spec["uv_lock_sha256"]),
        "runtime_capability_sha256": str(spec["runtime_capability_sha256"]),
        "analysis_plan_sha256": str(spec["analysis_plan_sha256"]),
        "rng_sha256": str(spec["rng_assignment_sha256"]),
        "conversion_version": CONVERSION_VERSION,
        "rng_version": RNG_VERSION,
    }


def _provenance(spec: Mapping[str, object]) -> dict[str, object]:
    return {
        "source_revision": spec["orchestration_revision"],
        "clean_tree": True,
        "uv_lock_sha256": spec["uv_lock_sha256"],
        "runtime_capability_sha256": spec["runtime_capability_sha256"],
        "analysis_plan_sha256": spec["analysis_plan_sha256"],
        "rng_sha256": spec["rng_assignment_sha256"],
        "conversion_version": CONVERSION_VERSION,
        "rng_version": RNG_VERSION,
    }


def _reject_markers(cell_root: Path) -> None:
    if not cell_root.exists():
        return
    chain = _open_directory_chain(cell_root, create=False)
    try:
        for count, path in enumerate(cell_root.rglob("*"), start=1):
            if count > PILOT_CELL_MAX_ENTRIES:
                raise RuntimeError("pilot cell artifact count exceeds frozen bound")
            if path.is_symlink():
                raise RuntimeError("pilot cell contains a symlink")
            if path.name.endswith((".partial", ".intent")):
                raise RuntimeError(f"surviving publication marker: {path.name}")
        _require_directory_chain(chain, allow_final_mutation=False)
    finally:
        _close_directory_chain(chain)


def _initialize_run(
    run: Path, spec: Mapping[str, object], cell: PilotCell, kernel: np.ndarray
) -> None:
    if run.exists():
        return
    run.mkdir()
    kernel_dir = run / "kernel"
    kernel_dir.mkdir()
    (kernel_dir / "kernel-f64le.bin").write_bytes(
        kernel.astype("<f8", copy=False).tobytes(order="C")
    )
    documents = {
        "request.json": {
            "schema_version": "challenge-194-pilot-request-v1",
            "request_sha256": cell.request_sha256,
            "kernel_sha256": cell.kernel_sha256,
            "length": cell.length,
            "sigma": cell.sigma.hex(),
            "sigma_grid_id": cell.sigma_grid_id,
            "kappas": [value.hex() for value in cell.kappas],
            "master_seed": PILOT_MASTER_SEED,
            "phase": PILOT_PHASE,
            "replica": cell.replica,
        },
        "environment.json": {
            "schema_version": "challenge-194-pilot-environment-v1",
            "source_revision": spec["orchestration_revision"],
            "clean_tree": True,
            "uv_lock_sha256": spec["uv_lock_sha256"],
            "runtime_capability_sha256": spec["runtime_capability_sha256"],
            "conversion_version": CONVERSION_VERSION,
            "rng_version": RNG_VERSION,
        },
        "seed-manifest.json": {
            "schema_version": "challenge-194-pilot-seed-manifest-v1",
            "rng_sha256": spec["rng_assignment_sha256"],
            "cell_stream_material_sha256": list(cell.rng_material_sha256),
        },
        "capability.json": {
            "schema_version": "challenge-194-pilot-capability-v1",
            "runtime_capability_sha256": spec["runtime_capability_sha256"],
            "runtime_capability": spec["runtime_capability"],
            "capability_waiver": spec["capability_waiver"],
        },
        "manifest.json": {
            "schema_version": "challenge-194-pilot-inner-manifest-v1",
            "source_revision": spec["orchestration_revision"],
            "analysis_plan_sha256": spec["analysis_plan_sha256"],
            "run_spec_sha256": spec["run_spec_sha256"],
            "cell_id": cell.cell_id,
        },
    }
    for name, document in documents.items():
        _publish_once(run / name, document)


def _trajectory_path(run: Path, cell: PilotCell) -> Path:
    return run / "trajectories" / f"trajectory-{cell.request_sha256}.h5"


def _cell_manifest_document(
    spec: Mapping[str, object], cell: PilotCell, run: Path
) -> dict[str, object]:
    progress, progress_payload = _read_canonical(
        run / "progress.json",
        "cell progress",
        maximum_size=PILOT_PROGRESS_MAX_BYTES,
    )
    trajectory = _trajectory_path(run, cell)
    sidecar, _ = _read_canonical(
        trajectory.with_suffix(".sha256.json"),
        "trajectory digest",
        maximum_size=PILOT_MARKER_MAX_BYTES,
    )
    if progress.get("trajectory_count") != 1 or progress.get("batch_count") != 1:
        raise RuntimeError("cell progress does not contain one complete trajectory")
    return {
        "schema_version": CELL_MANIFEST_SCHEMA,
        "status": "success",
        "run_spec_sha256": spec["run_spec_sha256"],
        "cell_index": cell.cell_index,
        "cell_id": cell.cell_id,
        "request_sha256": cell.request_sha256,
        "kernel_sha256": cell.kernel_sha256,
        "trajectory_path": (
            f"{cell.run_path}/trajectories/trajectory-{cell.request_sha256}.h5"
        ),
        "trajectory_sha256": sidecar["trajectory_sha256"],
        "progress_sha256": _sha256(progress_payload),
    }


def _verify_success_cell(
    root: Path, spec: Mapping[str, object], cell: PilotCell
) -> dict[str, object]:
    cell_root = _relative_path(root, cell.cell_path, "cells")
    _reject_markers(cell_root)
    run = _relative_path(root, cell.run_path, "cells")
    marker = _relative_path(root, cell.manifest_path, "cells")
    if not marker.is_file():
        raise RuntimeError("cell success manifest is missing")
    expected = _expected(spec, cell)
    progress = reconstruct_progress(run, expected)
    trajectory = _trajectory_path(run, cell)
    load_verified_trajectory(trajectory, expected)
    manifest, _ = _read_canonical(
        marker,
        "cell success manifest",
        maximum_size=PILOT_MARKER_MAX_BYTES,
    )
    required = _cell_manifest_document(spec, cell, run)
    if manifest != required:
        raise RuntimeError("cell success manifest is stale or corrupt")
    if progress.get("trajectory_count") != 1:
        raise RuntimeError("cell has duplicate trajectories")
    return manifest


def _run_cell(
    run_spec_path: Path,
    cell_index: int,
    *,
    verify_current_environment: bool,
    production: bool,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    spec = _load_pilot_spec(
        run_spec_path,
        verify_current_environment=verify_current_environment,
        production=production,
    )
    cells = spec["cells"]
    if (
        isinstance(cell_index, bool)
        or not isinstance(cell_index, int)
        or not 0 <= cell_index < len(cells)
    ):
        raise ValueError("cell_index is outside the pilot run spec")
    cell = PilotCell.from_document(cells[cell_index])
    root = run_spec_path.parent
    cell_root = _relative_path(root, cell.cell_path, "cells")
    cell_chain = _open_cell_directory_chain(root, cell.cell_id)
    descriptor = cell_chain[-1][1]
    shared_cells_index = len(cell_chain) - 2
    locked = True
    try:
        _require_directory_chain(
            cell_chain,
            allow_final_mutation=True,
            mutable_indexes={shared_cells_index},
        )
        generation = _directory_generation(cell_root, descriptor)
        _reject_markers(cell_root)
        _require_directory_generation(cell_root, descriptor, generation)
        marker = _relative_path(root, cell.manifest_path, "cells")
        if marker.exists():
            manifest = _verify_success_cell(root, spec, cell)
            _require_directory_generation(cell_root, descriptor, generation)
            _require_directory_chain(
                cell_chain,
                allow_final_mutation=True,
                mutable_indexes={shared_cells_index},
            )
            return {
                "cell_index": cell_index,
                "cell_id": cell.cell_id,
                "manifest_path": cell.manifest_path,
                "trajectory_sha256": manifest["trajectory_sha256"],
            }
        _reject_markers(cell_root)
        kernel = periodic_kernel(cell.length, cell.sigma)
        actual_kernel_hash = _sha256(
            kernel.astype("<f8", copy=False).tobytes(order="C")
        )
        if actual_kernel_hash != cell.kernel_sha256:
            raise RuntimeError("reconstructed kernel hash mismatch")
        run = _relative_path(root, cell.run_path, "cells")
        _initialize_run(run, spec, cell, kernel)
        generation = _directory_generation(cell_root, descriptor)
        expected = _expected(spec, cell)
        trajectory = _trajectory_path(run, cell)
        if trajectory.exists():
            load_verified_trajectory(trajectory, expected)
        else:
            trajectories = run / "trajectories"
            if trajectories.exists() and any(trajectories.iterdir()):
                raise RuntimeError("trajectory namespace is incomplete or noncanonical")
            request = cell.request()
            alias = build_distance_alias(
                cell.length, cell.sigma, kernel, cell.kernel_sha256
            )
            result = run_poisson_numba(request, kernel, alias)
            trajectory = publish_trajectory(run, request, result, _provenance(spec))
        if crash_hook is not None:
            crash_hook("after-trajectory")
        _require_directory_generation(cell_root, descriptor, generation)
        batch = run / "batches" / f"batch-cell-{cell.cell_index:03d}.json"
        if not batch.exists():
            if (run / "batches").exists() and any((run / "batches").iterdir()):
                raise RuntimeError("batch namespace is noncanonical")
            publish_batch_manifest(run, f"cell-{cell.cell_index:03d}", [trajectory])
        reconstruct_progress(run, expected)
        if crash_hook is not None:
            crash_hook("after-progress")
        _require_directory_generation(cell_root, descriptor, generation)
        manifest = _cell_manifest_document(spec, cell, run)
        _publish_once(marker, manifest)
        generation = _directory_generation(cell_root, descriptor)
        verified = _verify_success_cell(root, spec, cell)
        _require_directory_generation(cell_root, descriptor, generation)
        _require_directory_chain(
            cell_chain,
            allow_final_mutation=True,
            mutable_indexes={shared_cells_index},
        )
        return {
            "cell_index": cell_index,
            "cell_id": cell.cell_id,
            "manifest_path": cell.manifest_path,
            "trajectory_sha256": verified["trajectory_sha256"],
        }
    finally:
        if locked:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        _close_directory_chain(cell_chain)


def run_pilot_cell(run_spec_path: Path, cell_index: int) -> dict[str, object]:
    return _run_cell(
        run_spec_path,
        cell_index,
        verify_current_environment=True,
        production=True,
    )


def pending_pilot_cells(
    run_spec_path: Path, *, verify_current_environment: bool = True
) -> list[int]:
    spec = load_pilot_run_spec(run_spec_path, verify_current_environment)
    root = run_spec_path.parent
    pending: list[int] = []
    for raw in spec["cells"]:
        cell = PilotCell.from_document(raw)
        marker = _relative_path(root, cell.manifest_path, "cells")
        if marker.exists():
            _verify_success_cell(root, spec, cell)
        else:
            cell_root = _relative_path(root, cell.cell_path, "cells")
            _reject_markers(cell_root)
            pending.append(cell.cell_index)
    return pending


def _merged_document(
    run_spec_path: Path,
    *,
    verify_current_environment: bool,
    production: bool,
) -> dict[str, object]:
    spec = _load_pilot_spec(
        run_spec_path,
        verify_current_environment=verify_current_environment,
        production=production,
    )
    root = run_spec_path.parent
    cells_root = root / "cells"
    expected_names = {PilotCell.from_document(raw).cell_id for raw in spec["cells"]}
    cells_chain = _open_directory_chain(cells_root, create=False)
    try:
        actual_names: set[str] = set()
        with os.scandir(cells_chain[-1][1]) as stream:
            for count, entry in enumerate(stream, start=1):
                if count > len(expected_names) + 1:
                    raise RuntimeError(
                        "pilot cell directory count exceeds frozen bound"
                    )
                metadata = entry.stat(follow_symlinks=False)
                if not stat.S_ISDIR(metadata.st_mode):
                    raise RuntimeError("pilot cells root contains a non-directory")
                actual_names.add(entry.name)
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        if missing or extra:
            raise RuntimeError(
                f"pilot cell set mismatch; missing={missing}, extra={extra}"
            )
        records = []
        requests: set[str] = set()
        for raw in spec["cells"]:
            cell = PilotCell.from_document(raw)
            manifest = _verify_success_cell(root, spec, cell)
            if cell.request_sha256 in requests:
                raise RuntimeError("merged pilot contains duplicate request identity")
            requests.add(cell.request_sha256)
            records.append(
                {
                    "cell_index": cell.cell_index,
                    "cell_id": cell.cell_id,
                    "manifest_path": cell.manifest_path,
                    "request_sha256": cell.request_sha256,
                    "trajectory_sha256": manifest["trajectory_sha256"],
                }
            )
        _require_directory_chain(cells_chain, allow_final_mutation=False)
    finally:
        _close_directory_chain(cells_chain)
    return {
        "schema_version": MERGED_SCHEMA,
        "run_spec_sha256": spec["run_spec_sha256"],
        "cell_count": len(records),
        "trajectory_count": len(records),
        "cells": records,
        "purpose": "exploratory-window-selection-only",
        "physics_claims_authorized": False,
    }


def merge_pilot_progress(
    run_spec_path: Path, output: Path | None = None
) -> dict[str, object]:
    document = _merged_document(
        run_spec_path,
        verify_current_environment=True,
        production=True,
    )
    fixed = run_spec_path.parent / MERGED_NAME
    if output is not None and output != fixed:
        raise RuntimeError("merge output must be the portable run-spec progress path")
    _publish_once(fixed, document)
    return document


def verify_pilot_download(run_spec_path: Path) -> dict[str, object]:
    document = _merged_document(
        run_spec_path,
        verify_current_environment=False,
        production=True,
    )
    progress = run_spec_path.parent / MERGED_NAME
    if not progress.exists():
        raise RuntimeError("merged pilot progress is missing")
    existing, _ = _read_canonical(
        progress,
        "merged pilot progress",
        maximum_size=PILOT_PROGRESS_MAX_BYTES,
    )
    if existing != document:
        raise RuntimeError("merged pilot progress is stale or corrupt")
    return document


_PILOT_ANALYSIS_SNAPSHOT_TOKEN = object()


def _copy_regular_snapshot_at(
    name: str,
    parent_fd: int,
    destination: Path,
    *,
    maximum_size: int,
    description: str,
) -> bytes | None:
    descriptor, original = _open_regular_at(
        name,
        parent_fd,
        description,
        maximum_size=maximum_size,
    )
    captured: list[bytes] | None = (
        [] if maximum_size <= PILOT_RUN_SPEC_MAX_BYTES else None
    )
    copied = 0
    try:
        with destination.open("xb") as output:
            while block := os.read(descriptor, 1024 * 1024):
                copied += len(block)
                if copied > maximum_size:
                    raise RuntimeError(f"{description} exceeds the byte-size limit")
                output.write(block)
                if captured is not None:
                    captured.append(block)
        current = os.fstat(descriptor)
        if copied != original.st_size or _generation_tuple(
            current
        ) != _generation_tuple(original):
            raise RuntimeError(f"{description} changed during snapshot")
    finally:
        os.close(descriptor)
    return b"".join(captured) if captured is not None else None


def _copy_cell_tree_snapshot(
    source_fd: int,
    destination: Path,
    *,
    remaining_entries: list[int],
    depth: int = 0,
) -> None:
    if depth > 6:
        raise RuntimeError("pilot cell snapshot depth exceeds frozen bound")
    destination.mkdir()
    with os.scandir(source_fd) as stream:
        names = sorted(entry.name for entry in stream)
    for name in names:
        remaining_entries[0] -= 1
        if remaining_entries[0] < 0:
            raise RuntimeError("pilot cell artifact count exceeds frozen bound")
        metadata = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
        target = destination / name
        if stat.S_ISLNK(metadata.st_mode):
            raise RuntimeError("pilot cell snapshot contains a symlink")
        if stat.S_ISDIR(metadata.st_mode):
            child = _open_directory_at(name, source_fd)
            try:
                _copy_cell_tree_snapshot(
                    child,
                    target,
                    remaining_entries=remaining_entries,
                    depth=depth + 1,
                )
            finally:
                os.close(child)
        elif stat.S_ISREG(metadata.st_mode):
            maximum_size = (
                _artifacts.MAX_HDF5_BYTES
                if name.endswith(".h5")
                else max(_artifacts.MAX_JSON_BYTES, _artifacts.MAX_KERNEL_FILE_BYTES)
            )
            _copy_regular_snapshot_at(
                name,
                source_fd,
                target,
                maximum_size=maximum_size,
                description="pilot cell snapshot file",
            )
        else:
            raise RuntimeError("pilot cell snapshot contains a special file")


def _load_analysis_trajectory(
    path: Path,
    expected: dict[str, str],
    required_digest: str,
) -> TrajectoryResult:
    result, _, actual_digest, _ = _artifacts._verify_trajectory(
        path,
        expected["request_sha256"],
        expected,
    )
    if actual_digest != required_digest:
        raise RuntimeError("trajectory digest differs from verified pilot progress")
    return result


def _snapshot_malformed(message: str) -> Never:
    raise RuntimeError(message)


@dataclass(frozen=True)
class _PilotAnalysisSnapshot:
    run_spec_path: Path
    run_spec_payload: bytes
    progress_payload: bytes
    spec: Mapping[str, object]
    progress: Mapping[str, object]
    _token: object

    def load_trajectory(self, cell_index: int) -> TrajectoryResult:
        if self._token is not _PILOT_ANALYSIS_SNAPSHOT_TOKEN:
            raise RuntimeError("invalid pilot analysis snapshot capability")
        raw_cells = self.spec["cells"]
        raw_progress = self.progress["cells"]
        if not isinstance(raw_cells, Sequence) or not isinstance(
            raw_progress, Sequence
        ):
            _snapshot_malformed("verified pilot snapshot is malformed")
        raw_cell = raw_cells[cell_index]
        progress_cell = raw_progress[cell_index]
        if not isinstance(raw_cell, Mapping) or not isinstance(progress_cell, Mapping):
            _snapshot_malformed("verified pilot snapshot cell is malformed")
        cell = PilotCell.from_document(raw_cell)
        trajectory = _trajectory_path(
            self.run_spec_path.parent / cell.run_path,
            cell,
        )
        return _load_analysis_trajectory(
            trajectory,
            _expected(self.spec, cell),
            str(progress_cell["trajectory_sha256"]),
        )


@contextmanager
def _open_verified_pilot_analysis_snapshot(
    run_spec_path: Path,
    *,
    production: bool,
    _snapshot_hook: Callable[[str], None] | None = None,
) -> Iterator[_PilotAnalysisSnapshot]:
    if (
        not isinstance(run_spec_path, Path)
        or not run_spec_path.is_absolute()
        or run_spec_path.name != RUN_SPEC_NAME
    ):
        raise RuntimeError("pilot run spec path must be absolute and canonical")
    source_chain = _open_directory_chain(
        run_spec_path.parent,
        create=False,
        allow_final_mutation=True,
    )
    source_root_fd = source_chain[-1][1]
    try:
        with tempfile.TemporaryDirectory(
            prefix="challenge-194-p0-snapshot-"
        ) as temporary:
            snapshot_root = Path(temporary)
            snapshot_run_spec = snapshot_root / RUN_SPEC_NAME
            run_spec_payload = _copy_regular_snapshot_at(
                RUN_SPEC_NAME,
                source_root_fd,
                snapshot_run_spec,
                maximum_size=PILOT_RUN_SPEC_MAX_BYTES,
                description="pilot run spec snapshot",
            )
            assert run_spec_payload is not None
            if _snapshot_hook is not None:
                _snapshot_hook("run-spec-copied")
            spec = _load_pilot_spec(
                snapshot_run_spec,
                verify_current_environment=False,
                production=production,
            )
            progress_payload = _copy_regular_snapshot_at(
                MERGED_NAME,
                source_root_fd,
                snapshot_root / MERGED_NAME,
                maximum_size=PILOT_PROGRESS_MAX_BYTES,
                description="merged pilot progress snapshot",
            )
            assert progress_payload is not None
            if _snapshot_hook is not None:
                _snapshot_hook("progress-copied")

            cells_descriptor = _open_directory_at("cells", source_root_fd)
            try:
                with os.scandir(cells_descriptor) as stream:
                    cell_names = sorted(entry.name for entry in stream)
                if len(cell_names) > len(spec["cells"]) + 1:
                    raise RuntimeError(
                        "pilot cell directory count exceeds frozen bound"
                    )
                cells_destination = snapshot_root / "cells"
                cells_destination.mkdir()
                for name in cell_names:
                    cell_descriptor = _open_directory_at(name, cells_descriptor)
                    try:
                        _copy_cell_tree_snapshot(
                            cell_descriptor,
                            cells_destination / name,
                            remaining_entries=[PILOT_CELL_MAX_ENTRIES],
                        )
                    finally:
                        os.close(cell_descriptor)
            finally:
                os.close(cells_descriptor)
            if _snapshot_hook is not None:
                _snapshot_hook("source-copied")

            reconstructed = _merged_document(
                snapshot_run_spec,
                verify_current_environment=False,
                production=production,
            )
            existing, verified_progress_payload = _read_canonical(
                snapshot_root / MERGED_NAME,
                "merged pilot progress snapshot",
                maximum_size=PILOT_PROGRESS_MAX_BYTES,
            )
            if (
                existing != reconstructed
                or verified_progress_payload != progress_payload
            ):
                raise RuntimeError("merged pilot progress snapshot is stale or corrupt")
            snapshot = _PilotAnalysisSnapshot(
                run_spec_path=snapshot_run_spec,
                run_spec_payload=run_spec_payload,
                progress_payload=progress_payload,
                spec=spec,
                progress=reconstructed,
                _token=_PILOT_ANALYSIS_SNAPSHOT_TOKEN,
            )
            if _snapshot_hook is not None:
                _snapshot_hook("snapshot-verified")
            try:
                yield snapshot
            finally:
                if _snapshot_hook is not None:
                    _snapshot_hook("snapshot-closed")
    finally:
        _close_directory_chain(source_chain)


def _test_source() -> dict[str, object]:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "source_revision": completed.stdout.strip(),
        "clean_tree": True,
        "provenance_error": None,
    }


def _build_test_pilot_run_spec(
    output_root: Path,
    *,
    lengths: Sequence[int] = PILOT_LENGTHS,
    sigmas: Sequence[float] = PILOT_SIGMAS,
    replicas: Sequence[int] = PILOT_REPLICAS,
    kappas: Sequence[float] = PILOT_KAPPAS,
    production: bool = False,
) -> dict[str, object]:
    runtime, runtime_hash = _runtime_document()
    modules = _scientific_hashes()
    correctness = {
        "correctness_report_sha256": "1" * 64,
        "correctness_run_spec_sha256": "2" * 64,
        "correctness_approval_registry_sha256": _approval_registry_digest(),
        "validation_source_revision": "b" * 40,
        "validated_engine_modules": modules,
        "validated_engine_sha256": _aggregate_hash(modules),
        "validation_runtime_capability_sha256": "3" * 64,
    }
    if production:
        approval = _load_approval_registry()
        correctness.update(
            {
                "correctness_report_sha256": approval["report_sha256"],
                "correctness_run_spec_sha256": approval["run_spec_sha256"],
                "validation_source_revision": approval["validation_source_revision"],
                "validated_engine_sha256": approval["scientific_engine_sha256"],
            }
        )
    plan = _solution_root() / "PILOT_PLAN.md"
    analysis_hash = (
        _file_hash(plan)
        if plan.exists()
        else _sha256(_canonical_bytes({"protocol": "P0/P1-test"}))
    )
    return _build_document(
        lengths=lengths,
        sigmas=sigmas,
        replicas=replicas,
        kappas=kappas,
        source=_test_source(),
        runtime=runtime,
        runtime_sha256=runtime_hash,
        correctness=correctness,
        waiver_timestamp="2026-07-29T00:00:00Z",
        analysis_plan_sha256=analysis_hash,
        schema_version=RUN_SPEC_SCHEMA if production else TEST_RUN_SPEC_SCHEMA,
        enforce_production=production,
    )


def _write_test_pilot_run_spec(output_root: Path, **kwargs: object) -> Path:
    document = _build_test_pilot_run_spec(output_root, **kwargs)
    path = output_root / RUN_SPEC_NAME
    _publish_once(path, document)
    return path


def _write_test_frozen_pilot_run_spec(output_root: Path) -> Path:
    return _write_test_pilot_run_spec(output_root, production=True)


def _run_test_pilot_cell(
    run_spec_path: Path,
    cell_index: int,
    *,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    return _run_cell(
        run_spec_path,
        cell_index,
        verify_current_environment=False,
        production=False,
        crash_hook=crash_hook,
    )


def _merge_test_pilot_progress(
    run_spec_path: Path, output: Path | None = None
) -> dict[str, object]:
    document = _merged_document(
        run_spec_path,
        verify_current_environment=False,
        production=False,
    )
    fixed = run_spec_path.parent / MERGED_NAME
    if output is not None and output != fixed:
        raise RuntimeError("merge output must be the portable run-spec progress path")
    _publish_once(fixed, document)
    return document


def _verify_test_pilot_download(run_spec_path: Path) -> dict[str, object]:
    document = _merged_document(
        run_spec_path,
        verify_current_environment=False,
        production=False,
    )
    progress = run_spec_path.parent / MERGED_NAME
    if not progress.exists():
        raise RuntimeError("merged pilot progress is missing")
    existing, _ = _read_canonical(
        progress,
        "test merged pilot progress",
        maximum_size=PILOT_PROGRESS_MAX_BYTES,
    )
    if existing != document:
        raise RuntimeError("merged test pilot progress is stale or corrupt")
    return document


def _pending_test_pilot_cells(run_spec_path: Path) -> list[int]:
    spec = _load_pilot_spec(
        run_spec_path,
        verify_current_environment=False,
        production=False,
    )
    root = run_spec_path.parent
    pending: list[int] = []
    for raw in spec["cells"]:
        cell = PilotCell.from_document(raw)
        marker = _relative_path(root, cell.manifest_path, "cells")
        if marker.exists():
            _verify_success_cell(root, spec, cell)
        else:
            _reject_markers(_relative_path(root, cell.cell_path, "cells"))
            pending.append(cell.cell_index)
    return pending


def _test_approval_document(
    report_path: Path,
    validation_spec_path: Path,
    modules: Mapping[str, str],
) -> dict[str, object]:
    report, report_payload = _read_canonical(
        report_path, "test report", maximum_size=CORRECTNESS_REPORT_MAX_BYTES
    )
    spec, spec_payload = _read_canonical(
        validation_spec_path,
        "test validation spec",
        maximum_size=CORRECTNESS_RUN_SPEC_MAX_BYTES,
    )
    return {
        "schema_version": APPROVAL_SCHEMA,
        "approval_revision": CORRECTNESS_APPROVAL_REVISION,
        "validation_source_revision": spec["source_revision"],
        "report_sha256": _sha256(report_payload),
        "run_spec_sha256": _sha256(spec_payload),
        "protocol_sha256": str(spec.get("protocol_sha256", "0" * 64)),
        "check_registry_sha256": _sha256(
            _canonical_bytes(_check_registry_document(spec))
        ),
        "check_count": len(report.get("checks", [])),
        "cell_count": len(spec.get("cells", [])),
        "scientific_engine_sha256": _aggregate_hash(modules),
    }
