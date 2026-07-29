from __future__ import annotations

from collections.abc import Callable, Mapping
import ctypes
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import uuid

from .runtime import runtime_capability
from .validation import (
    VALIDATION_PROTOCOL_VERSION,
    EXACT_FAMILIES,
    PAIR_NAMES,
    SAMPLERS,
    SCALAR_COLUMNS,
    ValidationProtocol,
    _exact_checks,
    _protocol_document,
    _repository_state,
    _run_case_checks,
    assemble_validation_report,
    canonical_report_bytes,
)


RUN_SPEC_SCHEMA = "challenge-194-validation-run-spec-v1"
CELL_SCHEMA = "challenge-194-validation-cell-v1"
GLOBAL_SCHEMA = "challenge-194-validation-global-v1"
MANIFEST_SCHEMA = "challenge-194-validation-shard-manifest-v1"
FINAL_REPORT_PATH = "report/report.json"
RUN_SPEC_NAME = "run_spec.json"
GLOBAL_CHECK_CASES = (
    "published-random123",
    "four-streams",
    "finite-tape",
    "L8/sigma-1",
    "L256",
    "uint64-extremes",
    "L<=6",
    "L4",
    "L4",
    "L256",
    "tiny-huge-sigma",
    "L4/kappa-6",
    "scripted-unions",
    "replicas-1-2",
    "four-sampler-modules",
)


def _canonical_bytes(document: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8") + b"\n"
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"document is not canonical finite JSON: {error}") from error


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _rename_no_replace(source: Path, destination: Path) -> None:
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError:
        os.link(source, destination)
        source.unlink()
        return
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(destination),
        1,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), destination)
    if error_number in (errno.ENOSYS, errno.EINVAL):
        os.link(source, destination)
        source.unlink()
        return
    raise OSError(error_number, os.strerror(error_number), destination)


def _document_hash(document: Mapping[str, object], hash_field: str) -> str:
    unsigned = dict(document)
    unsigned.pop(hash_field, None)
    return _sha256(_canonical_bytes(unsigned))


def _repository_root() -> Path:
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("unable to locate repository root")


def _solution_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _verified_source_state() -> dict[str, object]:
    source = _repository_state()
    revision = source.get("source_revision")
    if (
        source.get("clean_tree") is not True
        or source.get("provenance_error") is not None
        or not isinstance(revision, str)
        or re.fullmatch(r"[0-9a-f]{40}", revision) is None
    ):
        raise RuntimeError(
            "repository must have an exact revision and clean source state"
        )
    return source


def _runtime_document() -> tuple[dict[str, object], str]:
    capability = runtime_capability()
    return capability, _sha256(_canonical_bytes(capability))


def _lock_hash() -> str:
    lockfile = _solution_root() / "uv.lock"
    if lockfile.is_symlink() or not lockfile.is_file():
        raise RuntimeError("challenge uv.lock must be a regular file")
    return _sha256(lockfile.read_bytes())


def _implementation_hashes() -> dict[str, str]:
    solution = _solution_root()
    paths = [
        *sorted((solution / "src" / "long_range_percolation").glob("*.py")),
        *sorted((solution / "scripts").glob("*.py")),
    ]
    modules: dict[str, str] = {}
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("implementation modules must be regular files")
        relative = str(path.relative_to(solution))
        modules[relative] = _sha256(path.read_bytes())
    if not modules:
        raise RuntimeError("no implementation modules were found")
    return modules


def _implementation_digest(modules: Mapping[str, str]) -> str:
    return _sha256(_canonical_bytes(dict(modules)))


def _dependency_fields(spec: Mapping[str, object]) -> dict[str, object]:
    return {
        "run_spec_sha256": spec["run_spec_sha256"],
        "protocol_sha256": spec["protocol"]["sha256"],
        "source_revision": spec["source_revision"],
        "runtime_capability_sha256": spec["runtime_capability_sha256"],
        "uv_lock_sha256": spec["uv_lock_sha256"],
        "implementation_sha256": spec["implementation_sha256"],
    }


def _assert_dependencies(spec: Mapping[str, object]) -> None:
    source = _verified_source_state()
    capability, capability_hash = _runtime_document()
    if source["source_revision"] != spec.get("source_revision"):
        raise RuntimeError("source revision does not match run spec")
    if capability_hash != spec.get("runtime_capability_sha256"):
        raise RuntimeError("runtime capability does not match run spec")
    if capability != spec.get("runtime_capability"):
        raise RuntimeError("runtime capability payload is stale")
    if _lock_hash() != spec.get("uv_lock_sha256"):
        raise RuntimeError("uv.lock does not match run spec")
    modules = _implementation_hashes()
    if modules != spec.get("implementation_modules"):
        raise RuntimeError("implementation module hashes do not match run spec")
    if _implementation_digest(modules) != spec.get("implementation_sha256"):
        raise RuntimeError("implementation aggregate hash does not match run spec")


def _protocol_from_document(
    document: Mapping[str, object],
    *,
    enforce_production: bool,
) -> ValidationProtocol:
    try:
        lengths = tuple(int(value) for value in document["lengths"])
        samples = {
            int(length): int(count)
            for length, count in document["samples_by_length"].items()
        }
        protocol = ValidationProtocol(
            lengths=lengths,
            sigmas=tuple(float.fromhex(value) for value in document["sigmas"]),
            kappas=tuple(float.fromhex(value) for value in document["kappas"]),
            samples_by_length=samples,
            master_seeds=tuple(int(value) for value in document["master_seeds"]),
            familywise_alpha=float.fromhex(document["familywise_alpha"]),
            permutation_replicates=int(document["permutation_replicates"]),
            multinomial_replicates=int(document["multinomial_replicates"]),
            jobs=1,
            name=str(document["name"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"run spec protocol is malformed: {error}") from error
    if _protocol_document(protocol) != dict(document):
        raise RuntimeError("run spec protocol is not canonical")
    if enforce_production:
        try:
            protocol.require_production()
        except ValueError as error:
            raise RuntimeError("run spec is not exact production-v1") from error
    return protocol


def _relative_artifact_path(value: object, prefix: str) -> Path:
    if not isinstance(value, str):
        raise RuntimeError("artifact path must be a string")
    path = Path(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != prefix
    ):
        raise RuntimeError("artifact path escapes its immutable namespace")
    return path


def _assert_no_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"path contains a symlink component: {current}")
        if not current.exists():
            break


def _canonical_run_root(output_root: Path) -> Path:
    if (
        not output_root.is_absolute()
        or ".." in output_root.parts
        or output_root != output_root.resolve(strict=False)
    ):
        raise RuntimeError("run root must be an absolute canonical path")
    _assert_no_symlink_components(output_root)
    return output_root


def _expected_path(root: Path, relative: object, prefix: str) -> Path:
    path = _relative_artifact_path(relative, prefix)
    candidate = root / path
    _assert_no_symlink_components(candidate)
    if candidate != candidate.resolve(strict=False):
        raise RuntimeError("artifact path is aliased or noncanonical")
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise RuntimeError("artifact path escapes bound run root") from error
    return candidate


def _check_registry_entry(
    *,
    ordinal: int,
    scope: str,
    case_id: str | None,
    family: str,
    check_case_id: str,
    backends: tuple[str, ...] = (),
) -> dict[str, object]:
    identity = {
        "ordinal": ordinal,
        "scope": scope,
        "case_id": case_id,
        "family": family,
        "check_case_id": check_case_id,
        "backends": list(backends),
    }
    return {
        "check_id": _sha256(_canonical_bytes(identity)),
        **identity,
    }


def _global_check_registry() -> list[dict[str, object]]:
    return [
        _check_registry_entry(
            ordinal=index,
            scope="global",
            case_id=None,
            family=family,
            check_case_id=check_case_id,
        )
        for index, (family, check_case_id) in enumerate(
            zip(EXACT_FAMILIES, GLOBAL_CHECK_CASES, strict=True)
        )
    ]


def _case_check_registry(case: object) -> list[dict[str, object]]:
    case_id = str(case.case_id)
    records: list[tuple[str, str, tuple[str, ...]]] = []
    if case.length <= 6:
        records.extend(
            (
                "all-graph-probability",
                f"{case_id}/{backend}",
                (backend,),
            )
            for backend in SAMPLERS
        )
    records.extend(
        (
            "edge-class-frequency",
            f"{case_id}/{backend}/d{distance}",
            (backend,),
        )
        for backend in SAMPLERS
        for distance in range(1, case.length // 2 + 1)
    )
    records.extend(
        (
            "poisson-event-count",
            f"{case_id}/{backend}",
            (backend,),
        )
        for backend in ("poisson-reference", "poisson-numba")
    )
    records.extend(
        ("no-edge", f"{case_id}/{backend}", (backend,))
        for backend in SAMPLERS
    )
    for left, right in PAIR_NAMES:
        pair_id = f"{case_id}/{left}-vs-{right}"
        records.extend(
            (family, pair_id, (left, right))
            for family in SCALAR_COLUMNS
        )
        records.extend(
            (family, pair_id, (left, right))
            for family in ("bond-length", "component-partition")
        )
    return [
        _check_registry_entry(
            ordinal=index,
            scope="cell",
            case_id=case_id,
            family=family,
            check_case_id=check_case_id,
            backends=backends,
        )
        for index, (family, check_case_id, backends) in enumerate(records)
    ]


def _build_validation_run_spec(
    protocol: ValidationProtocol,
    output_root: Path,
    *,
    enforce_production: bool,
) -> dict[str, object]:
    if not isinstance(protocol, ValidationProtocol):
        raise ValueError("protocol must be a ValidationProtocol")
    if not isinstance(output_root, Path):
        raise ValueError("output_root must be a pathlib.Path")
    if enforce_production:
        protocol.require_production()
    output_root = _canonical_run_root(output_root)
    protocol_document = _protocol_document(protocol)
    source = _verified_source_state()
    capability, capability_hash = _runtime_document()
    lock_hash = _lock_hash()
    modules = _implementation_hashes()
    implementation_hash = _implementation_digest(modules)
    cells = []
    for case_index, case in enumerate(protocol.case_registry):
        expected_checks = _case_check_registry(case)
        registry_hash = _sha256(_canonical_bytes({"checks": expected_checks}))
        identity = {
            "case_index": case_index,
            "case_id": case.case_id,
            "protocol_sha256": protocol_document["sha256"],
            "source_revision": source["source_revision"],
            "runtime_capability_sha256": capability_hash,
            "uv_lock_sha256": lock_hash,
            "implementation_sha256": implementation_hash,
            "expected_check_registry_sha256": registry_hash,
        }
        cell_hash = _sha256(_canonical_bytes(identity))
        cells.append(
            {
                **identity,
                "cell_sha256": cell_hash,
                "partial_path": f"cells/{case_index:03d}-{cell_hash[:16]}.json",
                "manifest_path": (
                    f"manifests/{case_index:03d}-{cell_hash[:16]}.json"
                ),
                "expected_checks": expected_checks,
            }
        )
    document: dict[str, object] = {
        "schema_version": RUN_SPEC_SCHEMA,
        "validation_schema_version": VALIDATION_PROTOCOL_VERSION,
        "protocol": protocol_document,
        "source": source,
        "source_revision": source["source_revision"],
        "runtime_capability": capability,
        "runtime_capability_sha256": capability_hash,
        "uv_lock_sha256": lock_hash,
        "implementation_modules": modules,
        "implementation_sha256": implementation_hash,
        "run_root": str(output_root),
        "artifact_root": ".",
        "global_partial_path": "global/exact-checks.json",
        "global_manifest_path": "global/exact-checks.manifest.json",
        "global_expected_checks": _global_check_registry(),
        "final_report_path": FINAL_REPORT_PATH,
        "logs_path": "logs",
        "cells": cells,
    }
    document["run_spec_sha256"] = _document_hash(document, "run_spec_sha256")
    validate_run_spec(document, enforce_production=enforce_production)
    return document


def build_validation_run_spec(
    protocol: ValidationProtocol,
    output_root: Path,
) -> dict[str, object]:
    return _build_validation_run_spec(
        protocol, output_root, enforce_production=True
    )


def validate_run_spec(
    document: Mapping[str, object],
    *,
    enforce_production: bool = True,
) -> None:
    expected_top_level = {
        "schema_version",
        "validation_schema_version",
        "protocol",
        "source",
        "source_revision",
        "runtime_capability",
        "runtime_capability_sha256",
        "uv_lock_sha256",
        "implementation_modules",
        "implementation_sha256",
        "run_root",
        "artifact_root",
        "global_partial_path",
        "global_manifest_path",
        "global_expected_checks",
        "final_report_path",
        "logs_path",
        "cells",
        "run_spec_sha256",
    }
    if set(document) != expected_top_level:
        raise RuntimeError("run spec fields are not exact")
    if document.get("schema_version") != RUN_SPEC_SCHEMA:
        raise RuntimeError("run spec schema is invalid")
    if document.get("validation_schema_version") != VALIDATION_PROTOCOL_VERSION:
        raise RuntimeError("run spec validation schema is stale")
    actual_hash = _document_hash(document, "run_spec_sha256")
    if document.get("run_spec_sha256") != actual_hash:
        raise RuntimeError("run spec hash mismatch")
    protocol = _protocol_from_document(
        document["protocol"], enforce_production=enforce_production
    )
    cells = document.get("cells")
    if not isinstance(cells, list) or len(cells) != len(protocol.case_registry):
        raise RuntimeError("run spec cell count does not match protocol")
    if enforce_production and len(cells) != 120:
        raise RuntimeError("production run spec must contain exactly 120 cells")
    root = _canonical_run_root(Path(str(document.get("run_root", ""))))
    source = document.get("source")
    if (
        not isinstance(source, Mapping)
        or set(source)
        != {"source_revision", "clean_tree", "provenance_error"}
        or source.get("clean_tree") is not True
        or source.get("provenance_error") is not None
        or source.get("source_revision") != document.get("source_revision")
    ):
        raise RuntimeError("run spec source state is not exactly clean")
    capability = document.get("runtime_capability")
    if (
        not isinstance(capability, Mapping)
        or document.get("runtime_capability_sha256")
        != _sha256(_canonical_bytes(capability))
    ):
        raise RuntimeError("run spec runtime capability hash is malformed")
    if document.get("artifact_root") != ".":
        raise RuntimeError("artifact root is not frozen")
    if (
        document.get("global_partial_path") != "global/exact-checks.json"
        or document.get("global_manifest_path")
        != "global/exact-checks.manifest.json"
    ):
        raise RuntimeError("global artifact paths are not frozen")
    if document.get("final_report_path") != FINAL_REPORT_PATH:
        raise RuntimeError("final report path is not frozen")
    if document.get("logs_path") != "logs":
        raise RuntimeError("logs path is not frozen")
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    artifact_paths: set[str] = {
        RUN_SPEC_NAME,
        str(document.get("global_partial_path")),
        str(document.get("global_manifest_path")),
        str(document.get("final_report_path")),
    }
    expected_global = _global_check_registry()
    if document.get("global_expected_checks") != expected_global:
        raise RuntimeError("global expected check registry is not frozen")
    for index, (cell, case) in enumerate(
        zip(cells, protocol.case_registry, strict=True)
    ):
        if not isinstance(cell, Mapping):
            raise RuntimeError("run spec cell is malformed")
        if set(cell) != {
            "case_index",
            "case_id",
            "protocol_sha256",
            "source_revision",
            "runtime_capability_sha256",
            "uv_lock_sha256",
            "implementation_sha256",
            "expected_check_registry_sha256",
            "cell_sha256",
            "partial_path",
            "manifest_path",
            "expected_checks",
        }:
            raise RuntimeError("run spec cell fields are not exact")
        if cell.get("case_index") != index or cell.get("case_id") != case.case_id:
            raise RuntimeError("run spec cell registry is noncanonical")
        expected_checks = _case_check_registry(case)
        if cell.get("expected_checks") != expected_checks:
            raise RuntimeError("cell expected check registry is not frozen")
        registry_hash = _sha256(_canonical_bytes({"checks": expected_checks}))
        identity = {
            "case_index": index,
            "case_id": case.case_id,
            "protocol_sha256": document["protocol"]["sha256"],
            "source_revision": document["source_revision"],
            "runtime_capability_sha256": document[
                "runtime_capability_sha256"
            ],
            "uv_lock_sha256": document["uv_lock_sha256"],
            "implementation_sha256": document["implementation_sha256"],
            "expected_check_registry_sha256": registry_hash,
        }
        expected_hash = _sha256(_canonical_bytes(identity))
        if cell.get("cell_sha256") != expected_hash:
            raise RuntimeError("run spec cell hash mismatch")
        seen_ids.add(case.case_id)
        seen_hashes.add(expected_hash)
        expected_partial = f"cells/{index:03d}-{expected_hash[:16]}.json"
        expected_manifest = f"manifests/{index:03d}-{expected_hash[:16]}.json"
        if (
            cell.get("partial_path") != expected_partial
            or cell.get("manifest_path") != expected_manifest
        ):
            raise RuntimeError("cell artifact paths are not canonical")
        artifact_paths.add(expected_partial)
        artifact_paths.add(expected_manifest)
    if len(seen_ids) != len(cells) or len(seen_hashes) != len(cells):
        raise RuntimeError("run spec contains duplicate cells")
    if len(artifact_paths) != 4 + 2 * len(cells):
        raise RuntimeError("run spec contains duplicate or overlapping paths")
    for relative in artifact_paths:
        prefix = relative.split("/", 1)[0]
        if relative == RUN_SPEC_NAME:
            candidate = root / relative
            _assert_no_symlink_components(candidate)
        elif prefix in {"global", "cells", "manifests", "report"}:
            _expected_path(root, relative, prefix)
        else:
            raise RuntimeError("run spec artifact namespace is invalid")
    modules = document.get("implementation_modules")
    if (
        not isinstance(modules, Mapping)
        or document.get("implementation_sha256")
        != _implementation_digest(modules)
    ):
        raise RuntimeError("implementation module hashes are malformed")
    _expected_path(root, "logs", "logs")


def _load_run_spec(
    path: Path,
    *,
    enforce_production: bool,
) -> tuple[dict[str, object], ValidationProtocol]:
    if not isinstance(path, Path):
        raise RuntimeError("run spec path must be a pathlib.Path")
    if (
        not path.is_absolute()
        or ".." in path.parts
        or path != path.resolve(strict=False)
    ):
        raise RuntimeError("run spec path must be absolute and canonical")
    _assert_no_symlink_components(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("run spec must be a regular non-symlink file")
    try:
        payload = path.read_bytes()
        document = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"unable to load run spec: {error}") from error
    if payload != _canonical_bytes(document):
        raise RuntimeError("run spec is not canonical JSON")
    validate_run_spec(document, enforce_production=enforce_production)
    root = Path(document["run_root"])
    if path != root / RUN_SPEC_NAME:
        raise RuntimeError("run spec path does not match its bound run root")
    _assert_dependencies(document)
    return document, _protocol_from_document(
        document["protocol"], enforce_production=enforce_production
    )


def _write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink_components(path)
    if path.is_symlink():
        raise RuntimeError("refusing to publish through a symlink")
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            _rename_no_replace(temporary, path)
        except FileExistsError:
            if path.is_symlink() or not path.is_file():
                raise RuntimeError("immutable output is not a regular file")
            if path.read_bytes() != payload:
                raise RuntimeError("immutable output already exists with other bytes")
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_validation_run_spec(
    protocol: ValidationProtocol,
    output_root: Path,
    run_spec_path: Path,
    *,
    enforce_production: bool,
) -> dict[str, object]:
    output_root = _canonical_run_root(output_root)
    expected_spec_path = output_root / RUN_SPEC_NAME
    if (
        not run_spec_path.is_absolute()
        or run_spec_path != run_spec_path.resolve(strict=False)
        or run_spec_path != expected_spec_path
    ):
        raise RuntimeError("run spec path must be fixed under the bound run root")
    if run_spec_path.exists():
        existing, _ = _load_run_spec(
            run_spec_path, enforce_production=enforce_production
        )
        expected = _build_validation_run_spec(
            protocol,
            output_root,
            enforce_production=enforce_production,
        )
        if existing != expected:
            raise RuntimeError("existing run spec differs from requested spec")
        return existing
    document = _build_validation_run_spec(
        protocol,
        output_root,
        enforce_production=enforce_production,
    )
    _write_once(run_spec_path, _canonical_bytes(document))
    reloaded, _ = _load_run_spec(
        run_spec_path, enforce_production=enforce_production
    )
    return reloaded


def write_validation_run_spec(
    protocol: ValidationProtocol,
    output_root: Path,
    run_spec_path: Path,
) -> dict[str, object]:
    return _write_validation_run_spec(
        protocol,
        output_root,
        run_spec_path,
        enforce_production=True,
    )


def _write_test_run_spec(
    protocol: ValidationProtocol,
    output_root: Path,
    run_spec_path: Path,
) -> dict[str, object]:
    return _write_validation_run_spec(
        protocol,
        output_root,
        run_spec_path,
        enforce_production=False,
    )


def _manifest_document(
    spec: Mapping[str, object],
    artifact_path: str,
    artifact_payload: bytes,
) -> dict[str, object]:
    return {
        "schema_version": MANIFEST_SCHEMA,
        "status": "success",
        **_dependency_fields(spec),
        "artifact_path": artifact_path,
        "artifact_sha256": _sha256(artifact_payload),
        "artifact_size": len(artifact_payload),
    }


def _validate_manifest(
    manifest: Mapping[str, object],
    spec: Mapping[str, object],
    artifact_path: str,
    artifact_payload: bytes,
) -> None:
    expected = _manifest_document(
        spec, artifact_path, artifact_payload
    )
    if dict(manifest) != expected:
        raise RuntimeError("artifact manifest is stale or corrupt")


def _load_json_payload(path: Path) -> tuple[dict[str, object], bytes]:
    _assert_no_symlink_components(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("artifact must be a regular non-symlink file")
    payload = path.read_bytes()
    try:
        document = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"artifact is not valid JSON: {error}") from error
    if payload != _canonical_bytes(document):
        raise RuntimeError("artifact is not canonical JSON")
    return document, payload


def _validate_shard_document(
    document: Mapping[str, object],
    spec: Mapping[str, object],
    *,
    schema: str,
    case: Mapping[str, object] | None,
    expected_checks: list[dict[str, object]],
) -> None:
    if document.get("schema_version") != schema:
        raise RuntimeError("shard artifact schema is invalid")
    expected_document_fields = {
        "schema_version",
        *_dependency_fields(spec),
        "check_records",
        "elapsed_seconds",
    }
    if case is not None:
        expected_document_fields.update(
            {"case_index", "case_id", "cell_sha256"}
        )
    if set(document) != expected_document_fields:
        raise RuntimeError("shard artifact fields are not exact")
    for key, value in _dependency_fields(spec).items():
        if document.get(key) != value:
            raise RuntimeError(f"shard dependency mismatch: {key}")
    records = document.get("check_records")
    if not isinstance(records, list) or not records:
        raise RuntimeError("shard artifact has no check registry")
    if len(records) != len(expected_checks):
        raise RuntimeError("shard check registry length mismatch")
    required = {
        "family",
        "case_id",
        "raw",
        "expected",
        "threshold",
        "margin",
        "passed",
    }
    seen: set[str] = set()
    for record, expected in zip(records, expected_checks, strict=True):
        if not isinstance(record, Mapping):
            raise RuntimeError("shard check registry contains malformed records")
        metadata = dict(record)
        check = metadata.pop("check", None)
        if metadata != expected:
            raise RuntimeError("shard check registry identity or order mismatch")
        check_id = str(record.get("check_id"))
        if check_id in seen:
            raise RuntimeError("shard check registry contains duplicate IDs")
        seen.add(check_id)
        if not isinstance(check, Mapping) or set(check) != required:
            raise RuntimeError("shard check registry contains a malformed check")
        if (
            not isinstance(check["family"], str)
            or not isinstance(check["case_id"], str)
            or not isinstance(check["passed"], bool)
            or not math.isfinite(float(check["threshold"]))
            or not math.isfinite(float(check["margin"]))
        ):
            raise RuntimeError("shard check registry contains invalid check fields")
        if (
            check["family"] != expected["family"]
            or check["case_id"] != expected["check_case_id"]
        ):
            raise RuntimeError("shard check registry check association mismatch")
    elapsed = document.get("elapsed_seconds")
    if (
        isinstance(elapsed, bool)
        or not isinstance(elapsed, (int, float))
        or not math.isfinite(float(elapsed))
        or float(elapsed) < 0.0
    ):
        raise RuntimeError("shard artifact elapsed time is invalid")
    if case is not None and (
        document.get("case_index") != case["case_index"]
        or document.get("case_id") != case["case_id"]
        or document.get("cell_sha256") != case["cell_sha256"]
    ):
        raise RuntimeError("cell artifact identity mismatch")


def _bind_check_records(
    checks: list[dict[str, object]],
    expected_checks: list[dict[str, object]],
) -> list[dict[str, object]]:
    if len(checks) != len(expected_checks):
        raise RuntimeError("computed checks do not match frozen check registry")
    records = []
    for check, expected in zip(checks, expected_checks, strict=True):
        if (
            check.get("family") != expected["family"]
            or check.get("case_id") != expected["check_case_id"]
        ):
            raise RuntimeError("computed check identity is not frozen")
        records.append({**expected, "check": check})
    return records


def _reuse_shard_if_present(
    spec_path: Path,
    spec: Mapping[str, object],
    *,
    artifact_relative: str,
    manifest_relative: str,
    schema: str,
    case: Mapping[str, object] | None,
    expected_checks: list[dict[str, object]],
) -> dict[str, object] | None:
    root = Path(spec["run_root"])
    artifact_path = _expected_path(
        root, artifact_relative, artifact_relative.split("/", 1)[0]
    )
    manifest_path = _expected_path(
        root, manifest_relative, manifest_relative.split("/", 1)[0]
    )
    if not artifact_path.exists():
        if manifest_path.exists():
            raise RuntimeError("success manifest exists without its artifact")
        return None
    artifact, payload = _load_json_payload(artifact_path)
    _validate_shard_document(
        artifact,
        spec,
        schema=schema,
        case=case,
        expected_checks=expected_checks,
    )
    if manifest_path.exists():
        manifest, _ = _load_json_payload(manifest_path)
        _validate_manifest(manifest, spec, artifact_relative, payload)
        return manifest
    manifest = _manifest_document(spec, artifact_relative, payload)
    _write_once(manifest_path, _canonical_bytes(manifest))
    return manifest


def _publish_shard(
    spec_path: Path,
    spec: Mapping[str, object],
    *,
    artifact_relative: str,
    manifest_relative: str,
    document: Mapping[str, object],
    schema: str,
    case: Mapping[str, object] | None,
    expected_checks: list[dict[str, object]],
    crash_hook: Callable[[str], None] | None,
) -> dict[str, object]:
    root = Path(spec["run_root"])
    artifact_path = _expected_path(
        root, artifact_relative, artifact_relative.split("/", 1)[0]
    )
    manifest_path = _expected_path(
        root, manifest_relative, manifest_relative.split("/", 1)[0]
    )
    payload = _canonical_bytes(document)
    if artifact_path.exists():
        existing, existing_payload = _load_json_payload(artifact_path)
        _validate_shard_document(
            existing,
            spec,
            schema=schema,
            case=case,
            expected_checks=expected_checks,
        )
        if manifest_path.exists():
            manifest, _ = _load_json_payload(manifest_path)
            _validate_manifest(
                manifest, spec, artifact_relative, existing_payload
            )
            return manifest
        manifest = _manifest_document(
            spec, artifact_relative, existing_payload
        )
        _write_once(manifest_path, _canonical_bytes(manifest))
        return manifest
    if manifest_path.exists():
        raise RuntimeError("success manifest exists without its artifact")

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink_components(artifact_path)
    temporary = artifact_path.parent / (
        f".{artifact_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        reloaded = json.loads(temporary.read_text(encoding="utf-8"))
        if temporary.read_bytes() != _canonical_bytes(reloaded):
            raise RuntimeError("temporary shard failed canonical reload")
        _validate_shard_document(
            reloaded,
            spec,
            schema=schema,
            case=case,
            expected_checks=expected_checks,
        )
        if crash_hook is not None:
            crash_hook("before-artifact-rename")
        try:
            _rename_no_replace(temporary, artifact_path)
        except FileExistsError:
            # A concurrent duplicate task won publication. Never overwrite it;
            # the semantic/hash checks below decide whether it is reusable.
            pass
        directory = os.open(artifact_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    published, published_payload = _load_json_payload(artifact_path)
    _validate_shard_document(
        published,
        spec,
        schema=schema,
        case=case,
        expected_checks=expected_checks,
    )
    manifest = _manifest_document(
        spec, artifact_relative, published_payload
    )
    if manifest_path.exists():
        existing_manifest, _ = _load_json_payload(manifest_path)
        _validate_manifest(
            existing_manifest, spec, artifact_relative, published_payload
        )
        return existing_manifest
    _write_once(manifest_path, _canonical_bytes(manifest))
    return manifest


def _run_validation_global_checks(
    run_spec_path: Path,
    *,
    enforce_production: bool,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    spec, protocol = _load_run_spec(
        run_spec_path, enforce_production=enforce_production
    )
    expected_checks = spec["global_expected_checks"]
    reused = _reuse_shard_if_present(
        run_spec_path,
        spec,
        artifact_relative=str(spec["global_partial_path"]),
        manifest_relative=str(spec["global_manifest_path"]),
        schema=GLOBAL_SCHEMA,
        case=None,
        expected_checks=expected_checks,
    )
    if reused is not None:
        return reused
    started = time.perf_counter()
    checks = _exact_checks(protocol)
    document = {
        "schema_version": GLOBAL_SCHEMA,
        **_dependency_fields(spec),
        "check_records": _bind_check_records(checks, expected_checks),
        "elapsed_seconds": time.perf_counter() - started,
    }
    return _publish_shard(
        run_spec_path,
        spec,
        artifact_relative=str(spec["global_partial_path"]),
        manifest_relative=str(spec["global_manifest_path"]),
        document=document,
        schema=GLOBAL_SCHEMA,
        case=None,
        expected_checks=expected_checks,
        crash_hook=crash_hook,
    )


def run_validation_global_checks(
    run_spec_path: Path,
    *,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    return _run_validation_global_checks(
        run_spec_path,
        enforce_production=True,
        crash_hook=crash_hook,
    )


def _run_test_global_checks(
    run_spec_path: Path,
    *,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    return _run_validation_global_checks(
        run_spec_path,
        enforce_production=False,
        crash_hook=crash_hook,
    )


def _run_validation_cell(
    run_spec_path: Path,
    case_index: int,
    *,
    enforce_production: bool,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    spec, protocol = _load_run_spec(
        run_spec_path, enforce_production=enforce_production
    )
    if (
        isinstance(case_index, bool)
        or not isinstance(case_index, int)
        or not 0 <= case_index < len(spec["cells"])
    ):
        raise ValueError("case_index is outside the run spec")
    cell = spec["cells"][case_index]
    expected_checks = cell["expected_checks"]
    reused = _reuse_shard_if_present(
        run_spec_path,
        spec,
        artifact_relative=str(cell["partial_path"]),
        manifest_relative=str(cell["manifest_path"]),
        schema=CELL_SCHEMA,
        case=cell,
        expected_checks=expected_checks,
    )
    if reused is not None:
        return {
            "case_index": case_index,
            "case_id": cell["case_id"],
            "partial_path": cell["partial_path"],
            "manifest_path": cell["manifest_path"],
            "artifact_sha256": reused["artifact_sha256"],
        }
    started = time.perf_counter()
    checks = _run_case_checks(
        protocol, (case_index, protocol.case_registry[case_index])
    )
    document = {
        "schema_version": CELL_SCHEMA,
        **_dependency_fields(spec),
        "case_index": case_index,
        "case_id": cell["case_id"],
        "cell_sha256": cell["cell_sha256"],
        "check_records": _bind_check_records(checks, expected_checks),
        "elapsed_seconds": time.perf_counter() - started,
    }
    manifest = _publish_shard(
        run_spec_path,
        spec,
        artifact_relative=str(cell["partial_path"]),
        manifest_relative=str(cell["manifest_path"]),
        document=document,
        schema=CELL_SCHEMA,
        case=cell,
        expected_checks=expected_checks,
        crash_hook=crash_hook,
    )
    return {
        "case_index": case_index,
        "case_id": cell["case_id"],
        "partial_path": cell["partial_path"],
        "manifest_path": cell["manifest_path"],
        "artifact_sha256": manifest["artifact_sha256"],
    }


def run_validation_cell(
    run_spec_path: Path,
    case_index: int,
    *,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    return _run_validation_cell(
        run_spec_path,
        case_index,
        enforce_production=True,
        crash_hook=crash_hook,
    )


def _run_test_cell(
    run_spec_path: Path,
    case_index: int,
    *,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    return _run_validation_cell(
        run_spec_path,
        case_index,
        enforce_production=False,
        crash_hook=crash_hook,
    )


def _verify_exact_directory(
    root: Path,
    directory: str,
    expected: set[str],
) -> None:
    path = root / directory
    _assert_no_symlink_components(path)
    actual = (
        {
            str(item.relative_to(root))
            for item in path.iterdir()
        }
        if path.is_dir()
        else set()
    )
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise RuntimeError(
            f"{directory} artifact set mismatch; missing={missing}, extra={extra}"
        )


def _load_verified_shard(
    spec_path: Path,
    spec: Mapping[str, object],
    artifact_relative: str,
    manifest_relative: str,
    *,
    schema: str,
    case: Mapping[str, object] | None,
    expected_checks: list[dict[str, object]],
) -> dict[str, object]:
    root = Path(spec["run_root"])
    artifact_path = _expected_path(
        root, artifact_relative, artifact_relative.split("/", 1)[0]
    )
    manifest_path = _expected_path(
        root, manifest_relative, manifest_relative.split("/", 1)[0]
    )
    artifact, payload = _load_json_payload(artifact_path)
    _validate_shard_document(
        artifact,
        spec,
        schema=schema,
        case=case,
        expected_checks=expected_checks,
    )
    manifest, _ = _load_json_payload(manifest_path)
    _validate_manifest(manifest, spec, artifact_relative, payload)
    return artifact


def canonical_scientific_report_bytes(
    report: Mapping[str, object],
) -> bytes:
    scientific = dict(report)
    scientific.pop("elapsed_seconds", None)
    return canonical_report_bytes(scientific)


def _merge_validation_shards(
    run_spec_path: Path,
    output: Path | None,
    *,
    enforce_production: bool,
) -> dict[str, object]:
    spec, protocol = _load_run_spec(
        run_spec_path, enforce_production=enforce_production
    )
    root = Path(spec["run_root"])
    fixed_output = _expected_path(root, spec["final_report_path"], "report")
    if output is not None and (
        not output.is_absolute()
        or output != output.resolve(strict=False)
        or output != fixed_output
    ):
        raise RuntimeError("merge output must equal the fixed run-spec report path")
    expected_cells = {str(cell["partial_path"]) for cell in spec["cells"]}
    expected_manifests = {
        str(cell["manifest_path"]) for cell in spec["cells"]
    }
    _verify_exact_directory(
        root, "cells", expected_cells
    )
    _verify_exact_directory(
        root, "manifests", expected_manifests
    )
    global_expected = {
        str(spec["global_partial_path"]),
        str(spec["global_manifest_path"]),
    }
    _verify_exact_directory(
        root, "global", global_expected
    )

    global_artifact = _load_verified_shard(
        run_spec_path,
        spec,
        str(spec["global_partial_path"]),
        str(spec["global_manifest_path"]),
        schema=GLOBAL_SCHEMA,
        case=None,
        expected_checks=spec["global_expected_checks"],
    )
    checks = [
        record["check"] for record in global_artifact["check_records"]
    ]
    elapsed = float(global_artifact["elapsed_seconds"])
    for cell in spec["cells"]:
        artifact = _load_verified_shard(
            run_spec_path,
            spec,
            str(cell["partial_path"]),
            str(cell["manifest_path"]),
            schema=CELL_SCHEMA,
            case=cell,
            expected_checks=cell["expected_checks"],
        )
        checks.extend(
            record["check"] for record in artifact["check_records"]
        )
        elapsed += float(artifact["elapsed_seconds"])
    report = assemble_validation_report(
        protocol,
        checks,
        elapsed_seconds=elapsed,
        runtime_capability_value=spec["runtime_capability"],
        source=spec["source"],
    )
    payload = canonical_report_bytes(report)
    _assert_no_symlink_components(fixed_output)
    _write_once(fixed_output, payload)
    return report


def merge_validation_shards(
    run_spec_path: Path,
    output: Path | None = None,
) -> dict[str, object]:
    return _merge_validation_shards(
        run_spec_path,
        output,
        enforce_production=True,
    )


def _merge_test_shards(
    run_spec_path: Path,
    output: Path | None = None,
) -> dict[str, object]:
    return _merge_validation_shards(
        run_spec_path,
        output,
        enforce_production=False,
    )
