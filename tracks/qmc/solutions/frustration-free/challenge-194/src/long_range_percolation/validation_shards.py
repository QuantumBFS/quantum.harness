from __future__ import annotations

from collections.abc import Callable, Mapping
import ctypes
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

from .runtime import runtime_capability
from .validation import (
    VALIDATION_PROTOCOL_VERSION,
    ValidationProtocol,
    _exact,
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


def _runtime_document() -> tuple[dict[str, object], str]:
    capability = runtime_capability()
    return capability, _sha256(_canonical_bytes(capability))


def _lock_hash() -> str:
    lockfile = _solution_root() / "uv.lock"
    if lockfile.is_symlink() or not lockfile.is_file():
        raise RuntimeError("challenge uv.lock must be a regular file")
    return _sha256(lockfile.read_bytes())


def _dependency_fields(spec: Mapping[str, object]) -> dict[str, object]:
    return {
        "run_spec_sha256": spec["run_spec_sha256"],
        "protocol_sha256": spec["protocol"]["sha256"],
        "source_revision": spec["source_revision"],
        "runtime_capability_sha256": spec["runtime_capability_sha256"],
        "uv_lock_sha256": spec["uv_lock_sha256"],
    }


def _assert_dependencies(spec: Mapping[str, object]) -> None:
    source = _repository_state()
    capability, capability_hash = _runtime_document()
    if source["source_revision"] != spec.get("source_revision"):
        raise RuntimeError("source revision does not match run spec")
    if capability_hash != spec.get("runtime_capability_sha256"):
        raise RuntimeError("runtime capability does not match run spec")
    if capability != spec.get("runtime_capability"):
        raise RuntimeError("runtime capability payload is stale")
    if _lock_hash() != spec.get("uv_lock_sha256"):
        raise RuntimeError("uv.lock does not match run spec")


def _protocol_from_document(document: Mapping[str, object]) -> ValidationProtocol:
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


def build_validation_run_spec(
    protocol: ValidationProtocol,
    output_root: Path,
) -> dict[str, object]:
    if not isinstance(protocol, ValidationProtocol):
        raise ValueError("protocol must be a ValidationProtocol")
    if not isinstance(output_root, Path):
        raise ValueError("output_root must be a pathlib.Path")
    protocol_document = _protocol_document(protocol)
    source = _repository_state()
    capability, capability_hash = _runtime_document()
    lock_hash = _lock_hash()
    cells = []
    for case_index, case in enumerate(protocol.case_registry):
        identity = {
            "case_index": case_index,
            "case_id": case.case_id,
            "protocol_sha256": protocol_document["sha256"],
            "source_revision": source["source_revision"],
            "runtime_capability_sha256": capability_hash,
            "uv_lock_sha256": lock_hash,
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
        "artifact_root": ".",
        "global_partial_path": "global/exact-checks.json",
        "global_manifest_path": "global/exact-checks.manifest.json",
        "cells": cells,
    }
    document["run_spec_sha256"] = _document_hash(document, "run_spec_sha256")
    validate_run_spec(document)
    return document


def validate_run_spec(document: Mapping[str, object]) -> None:
    if document.get("schema_version") != RUN_SPEC_SCHEMA:
        raise RuntimeError("run spec schema is invalid")
    if document.get("validation_schema_version") != VALIDATION_PROTOCOL_VERSION:
        raise RuntimeError("run spec validation schema is stale")
    actual_hash = _document_hash(document, "run_spec_sha256")
    if document.get("run_spec_sha256") != actual_hash:
        raise RuntimeError("run spec hash mismatch")
    protocol = _protocol_from_document(document["protocol"])
    cells = document.get("cells")
    if not isinstance(cells, list) or len(cells) != len(protocol.case_registry):
        raise RuntimeError("run spec cell count does not match protocol")
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for index, (cell, case) in enumerate(
        zip(cells, protocol.case_registry, strict=True)
    ):
        if not isinstance(cell, Mapping):
            raise RuntimeError("run spec cell is malformed")
        if cell.get("case_index") != index or cell.get("case_id") != case.case_id:
            raise RuntimeError("run spec cell registry is noncanonical")
        _relative_artifact_path(cell.get("partial_path"), "cells")
        _relative_artifact_path(cell.get("manifest_path"), "manifests")
        identity = {
            "case_index": index,
            "case_id": case.case_id,
            "protocol_sha256": document["protocol"]["sha256"],
            "source_revision": document["source_revision"],
            "runtime_capability_sha256": document[
                "runtime_capability_sha256"
            ],
            "uv_lock_sha256": document["uv_lock_sha256"],
        }
        expected_hash = _sha256(_canonical_bytes(identity))
        if cell.get("cell_sha256") != expected_hash:
            raise RuntimeError("run spec cell hash mismatch")
        seen_ids.add(case.case_id)
        seen_hashes.add(expected_hash)
    if len(seen_ids) != len(cells) or len(seen_hashes) != len(cells):
        raise RuntimeError("run spec contains duplicate cells")
    _relative_artifact_path(document.get("global_partial_path"), "global")
    _relative_artifact_path(document.get("global_manifest_path"), "global")


def _load_run_spec(path: Path) -> tuple[dict[str, object], ValidationProtocol]:
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise RuntimeError("run spec must be a regular non-symlink file")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"unable to load run spec: {error}") from error
    validate_run_spec(document)
    _assert_dependencies(document)
    return document, _protocol_from_document(document["protocol"])


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
        os.replace(temporary, path)
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


def _write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def write_validation_run_spec(
    protocol: ValidationProtocol,
    output_root: Path,
    run_spec_path: Path,
) -> dict[str, object]:
    if run_spec_path.exists():
        existing, _ = _load_run_spec(run_spec_path)
        expected = build_validation_run_spec(protocol, output_root)
        if existing != expected:
            raise RuntimeError("existing run spec differs from requested spec")
        return existing
    document = build_validation_run_spec(protocol, output_root)
    _write_once(run_spec_path, _canonical_bytes(document))
    reloaded, _ = _load_run_spec(run_spec_path)
    return reloaded


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
) -> None:
    if document.get("schema_version") != schema:
        raise RuntimeError("shard artifact schema is invalid")
    for key, value in _dependency_fields(spec).items():
        if document.get(key) != value:
            raise RuntimeError(f"shard dependency mismatch: {key}")
    checks = document.get("checks")
    if not isinstance(checks, list) or not checks:
        raise RuntimeError("shard artifact has no checks")
    required = {
        "family",
        "case_id",
        "raw",
        "expected",
        "threshold",
        "margin",
        "passed",
    }
    for check in checks:
        if not isinstance(check, Mapping) or not required <= set(check):
            raise RuntimeError("shard artifact contains a malformed check")
        if (
            not isinstance(check["family"], str)
            or not isinstance(check["case_id"], str)
            or not isinstance(check["passed"], bool)
            or not math.isfinite(float(check["threshold"]))
            or not math.isfinite(float(check["margin"]))
        ):
            raise RuntimeError("shard artifact contains invalid check fields")
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


def _reuse_shard_if_present(
    spec_path: Path,
    spec: Mapping[str, object],
    *,
    artifact_relative: str,
    manifest_relative: str,
    schema: str,
    case: Mapping[str, object] | None,
) -> dict[str, object] | None:
    artifact_path = spec_path.parent / artifact_relative
    manifest_path = spec_path.parent / manifest_relative
    if not artifact_path.exists():
        if manifest_path.exists():
            raise RuntimeError("success manifest exists without its artifact")
        return None
    artifact, payload = _load_json_payload(artifact_path)
    _validate_shard_document(artifact, spec, schema=schema, case=case)
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
    crash_hook: Callable[[str], None] | None,
) -> dict[str, object]:
    artifact_path = spec_path.parent / artifact_relative
    manifest_path = spec_path.parent / manifest_relative
    payload = _canonical_bytes(document)
    if artifact_path.exists():
        existing, existing_payload = _load_json_payload(artifact_path)
        _validate_shard_document(
            existing, spec, schema=schema, case=case
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
            reloaded, spec, schema=schema, case=case
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
        published, spec, schema=schema, case=case
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


def run_validation_global_checks(
    run_spec_path: Path,
    *,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    spec, protocol = _load_run_spec(run_spec_path)
    reused = _reuse_shard_if_present(
        run_spec_path,
        spec,
        artifact_relative=str(spec["global_partial_path"]),
        manifest_relative=str(spec["global_manifest_path"]),
        schema=GLOBAL_SCHEMA,
        case=None,
    )
    if reused is not None:
        return reused
    started = time.perf_counter()
    try:
        checks = _exact_checks(protocol)
    except Exception as error:
        checks = [
            _exact(
                "backend-integrity",
                "exact-checks",
                {"error": f"{type(error).__name__}: {error}"},
                "all exact checks completed",
                False,
            )
        ]
    document = {
        "schema_version": GLOBAL_SCHEMA,
        **_dependency_fields(spec),
        "checks": checks,
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
        crash_hook=crash_hook,
    )


def run_validation_cell(
    run_spec_path: Path,
    case_index: int,
    *,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    spec, protocol = _load_run_spec(run_spec_path)
    if (
        isinstance(case_index, bool)
        or not isinstance(case_index, int)
        or not 0 <= case_index < len(spec["cells"])
    ):
        raise ValueError("case_index is outside the run spec")
    cell = spec["cells"][case_index]
    reused = _reuse_shard_if_present(
        run_spec_path,
        spec,
        artifact_relative=str(cell["partial_path"]),
        manifest_relative=str(cell["manifest_path"]),
        schema=CELL_SCHEMA,
        case=cell,
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
        "checks": checks,
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
        crash_hook=crash_hook,
    )
    return {
        "case_index": case_index,
        "case_id": cell["case_id"],
        "partial_path": cell["partial_path"],
        "manifest_path": cell["manifest_path"],
        "artifact_sha256": manifest["artifact_sha256"],
    }


def _verify_exact_directory(
    root: Path,
    directory: str,
    expected: set[str],
) -> None:
    path = root / directory
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
) -> dict[str, object]:
    artifact, payload = _load_json_payload(
        spec_path.parent / artifact_relative
    )
    _validate_shard_document(artifact, spec, schema=schema, case=case)
    manifest, _ = _load_json_payload(
        spec_path.parent / manifest_relative
    )
    _validate_manifest(manifest, spec, artifact_relative, payload)
    return artifact


def canonical_scientific_report_bytes(
    report: Mapping[str, object],
) -> bytes:
    scientific = dict(report)
    scientific.pop("elapsed_seconds", None)
    return canonical_report_bytes(scientific)


def merge_validation_shards(
    run_spec_path: Path,
    output: Path,
) -> dict[str, object]:
    started = time.perf_counter()
    spec, protocol = _load_run_spec(run_spec_path)
    expected_cells = {str(cell["partial_path"]) for cell in spec["cells"]}
    expected_manifests = {
        str(cell["manifest_path"]) for cell in spec["cells"]
    }
    _verify_exact_directory(
        run_spec_path.parent, "cells", expected_cells
    )
    _verify_exact_directory(
        run_spec_path.parent, "manifests", expected_manifests
    )
    global_expected = {
        str(spec["global_partial_path"]),
        str(spec["global_manifest_path"]),
    }
    _verify_exact_directory(
        run_spec_path.parent, "global", global_expected
    )

    global_artifact = _load_verified_shard(
        run_spec_path,
        spec,
        str(spec["global_partial_path"]),
        str(spec["global_manifest_path"]),
        schema=GLOBAL_SCHEMA,
        case=None,
    )
    checks = list(global_artifact["checks"])
    elapsed = float(global_artifact["elapsed_seconds"])
    for cell in spec["cells"]:
        artifact = _load_verified_shard(
            run_spec_path,
            spec,
            str(cell["partial_path"]),
            str(cell["manifest_path"]),
            schema=CELL_SCHEMA,
            case=cell,
        )
        checks.extend(artifact["checks"])
        elapsed += float(artifact["elapsed_seconds"])
    elapsed += time.perf_counter() - started
    report = assemble_validation_report(
        protocol,
        checks,
        elapsed_seconds=elapsed,
        runtime_capability_value=spec["runtime_capability"],
        source=spec["source"],
    )
    _write_atomic(output, canonical_report_bytes(report))
    return report
