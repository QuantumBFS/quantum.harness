#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import platform
import secrets
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

SOLUTION_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = SOLUTION_DIR / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from challenge148.acceptance import (  # noqa: E402
    revalidate_qmc_adapter_output_descriptor_snapshot,
    validate_qmc_adapter_output_descriptor,
)
from challenge148.extension import validate_directed_extension_plan  # noqa: E402
from challenge148.paper_scan import validate_paper_scan_plan  # noqa: E402
from challenge148.planning import validate_plan  # noqa: E402
from challenge148.provenance import canonical_json  # noqa: E402


_COMPLETION_KEYS = {
    "schema_version",
    "cell_id",
    "cell_index",
    "plan_sha256",
    "request_sha256",
    "graph_sha256",
    "build_info_sha256",
    "executable_sha256",
    "current_generation_sha256",
    "semantic_snapshot_sha256",
    "log_sha256",
}
_F_ADD_SEALS = getattr(fcntl, "F_ADD_SEALS", 1033)
_F_GET_SEALS = getattr(fcntl, "F_GET_SEALS", 1034)
_F_SEAL_SEAL = getattr(fcntl, "F_SEAL_SEAL", 0x0001)
_F_SEAL_SHRINK = getattr(fcntl, "F_SEAL_SHRINK", 0x0002)
_F_SEAL_GROW = getattr(fcntl, "F_SEAL_GROW", 0x0004)
_F_SEAL_WRITE = getattr(fcntl, "F_SEAL_WRITE", 0x0008)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _decode_object(payload: bytes, label: str) -> dict[str, Any]:
    def reject(token: str) -> None:
        raise ValueError(f"{label} contains non-finite JSON token {token}")

    try:
        value = json.loads(payload, parse_constant=reject)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid {label} JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _validate_plan_schema(plan: dict[str, Any]) -> None:
    schema_version = plan.get("schema_version")
    if schema_version == "challenge148-coarse-plan-v1":
        validate_plan(plan)
    elif schema_version == "challenge148-directed-extension-plan-v1":
        validate_directed_extension_plan(plan)
    elif schema_version == "challenge148-paper-scan-plan-v1":
        validate_paper_scan_plan(plan)
    else:
        raise ValueError(f"unknown plan schema_version: {schema_version!r}")


def _relative_parts(relative_text: object, label: str) -> tuple[str, ...]:
    if not isinstance(relative_text, str):
        raise ValueError(f"{label} path must be a string")
    relative = Path(relative_text)
    if relative.is_absolute() or not relative.parts or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise ValueError(f"{label} path escapes the plan root")
    return relative.parts


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _file_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


def _identity(descriptor: int) -> tuple[int, int]:
    metadata = os.fstat(descriptor)
    return metadata.st_dev, metadata.st_ino


def _read_fd(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while True:
        chunk = os.pread(descriptor, 1024 * 1024, offset)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        offset += len(chunk)


def _open_absolute_directory(path: Path, label: str) -> int:
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute")
    descriptor = os.open("/", _directory_flags())
    try:
        for component in path.parts[1:]:
            try:
                child = os.open(component, _directory_flags(), dir_fd=descriptor)
            except OSError as exc:
                raise ValueError(
                    f"{label} ancestry must contain only real directories"
                ) from exc
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_directory_at(parent: int, name: str, label: str) -> int:
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent)
    except OSError as exc:
        raise ValueError(f"{label} must be a real directory, not a symlink") from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"{label} must be a real directory")
    return descriptor


def _open_or_create_directory_at(
    parent: int, name: str, label: str, *, mode: int = 0o755
) -> int:
    try:
        os.mkdir(name, mode=mode, dir_fd=parent)
    except FileExistsError:
        pass
    return _open_directory_at(parent, name, label)


def _open_file_at(parent: int, name: str, label: str) -> int:
    try:
        descriptor = os.open(name, _file_flags(), dir_fd=parent)
    except OSError as exc:
        raise ValueError(f"{label} must be a regular non-symlink file") from exc
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"{label} must be a regular non-symlink file")
    return descriptor


def _open_relative_file(
    root: int, relative_text: object, label: str
) -> tuple[int, list[int]]:
    parts = _relative_parts(relative_text, label)
    parent = root
    directories: list[int] = []
    try:
        for component in parts[:-1]:
            parent = _open_directory_at(parent, component, f"{label} parent")
            directories.append(parent)
        return _open_file_at(parent, parts[-1], label), directories
    except BaseException:
        for descriptor in reversed(directories):
            os.close(descriptor)
        raise


def _assert_child_identity(
    parent: int, name: str, descriptor: int, label: str
) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except OSError as exc:
        raise ValueError(f"{label} identity changed") from exc
    if (metadata.st_dev, metadata.st_ino) != _identity(descriptor):
        raise ValueError(f"{label} identity changed")


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("short descriptor-relative write")
        view = view[written:]


def _write_new_file_at(parent: int, name: str, payload: bytes, label: str) -> int:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(name, flags, 0o600, dir_fd=parent)
    except OSError as exc:
        raise ValueError(f"{label} creation collided with existing path") from exc
    try:
        _write_all(descriptor, payload)
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        try:
            os.unlink(name, dir_fd=parent)
        except OSError:
            pass
        raise
    os.close(descriptor)
    return _open_file_at(parent, name, label)


def _write_immutable_at(parent: int, name: str, payload: bytes, label: str) -> None:
    temporary = f".{name}.publish-{os.getpid()}-{secrets.token_hex(12)}"
    temp_fd = _write_new_file_at(parent, temporary, payload, f"temporary {label}")
    os.close(temp_fd)
    try:
        try:
            os.link(
                temporary,
                name,
                src_dir_fd=parent,
                dst_dir_fd=parent,
                follow_symlinks=False,
            )
            os.fsync(parent)
        except FileExistsError:
            existing = _open_file_at(parent, name, label)
            try:
                if _read_fd(existing) != payload:
                    raise ValueError(f"refusing to overwrite mismatched {label}")
            finally:
                os.close(existing)
    finally:
        os.unlink(temporary, dir_fd=parent)


def _output_fd_namespace(descriptor: int) -> str:
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("adapter output descriptor must name a directory")
    return f"qmc-sse-fd-output-v1:{metadata.st_dev}:{metadata.st_ino}"


def _open_or_create_relative_directory(root: int, parts: tuple[str, ...]) -> int:
    descriptor = os.dup(root)
    try:
        for component in parts:
            child = _open_or_create_directory_at(
                descriptor, component, "evidence snapshot directory", mode=0o700
            )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _remove_tree_at(parent: int, name: str) -> None:
    descriptor = _open_directory_at(parent, name, "temporary evidence snapshot")
    try:
        for child_name in os.listdir(descriptor):
            metadata = os.stat(child_name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                _remove_tree_at(descriptor, child_name)
            else:
                os.unlink(child_name, dir_fd=descriptor)
    finally:
        os.close(descriptor)
    os.rmdir(name, dir_fd=parent)


def _rename_noreplace(
    source_parent: int, source: str, target_parent: int, target: str
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    syscall_number = {
        "x86_64": 316,
        "amd64": 316,
        "aarch64": 276,
        "arm64": 276,
        "riscv64": 276,
    }.get(platform.machine().lower())
    if syscall_number is None:
        raise ValueError("atomic no-replace snapshot publication is unsupported")
    libc.syscall.restype = ctypes.c_long
    if libc.syscall(
        ctypes.c_long(syscall_number),
        ctypes.c_int(source_parent),
        os.fsencode(source),
        ctypes.c_int(target_parent),
        os.fsencode(target),
        ctypes.c_uint(1),
    ) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError(target)
        if error in {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP}:
            # CentOS 7 kernels and some NFS servers reject renameat2. Slurm
            # assigns one process per cell, so after an explicit descriptor-
            # relative existence check renameat retains the required
            # no-replace behavior for this compatibility path.
            try:
                os.stat(target, dir_fd=target_parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError(target)
            os.rename(
                source,
                target,
                src_dir_fd=source_parent,
                dst_dir_fd=target_parent,
            )
            return
        raise OSError(error, os.strerror(error))


def _completed_evidence_manifest(
    validation: dict[str, Any], completion_payload: bytes
) -> dict[str, Any]:
    descriptor_snapshot = validation["descriptor_snapshot"]
    files = [
        {
            "path": entry["path"],
            "sha256": _sha256(entry["payload"]),
            "size": len(entry["payload"]),
        }
        for entry in descriptor_snapshot["files"]
    ]
    directory_paths = {
        tuple(entry["path"]) for entry in descriptor_snapshot["directories"]
    }
    directory_paths.add(())
    for entry in files:
        path = tuple(entry["path"])
        directory_paths.update(path[:index] for index in range(len(path)))
    tree = []
    all_paths = directory_paths | {tuple(entry["path"]) for entry in files}
    for directory in sorted(directory_paths):
        names = sorted(
            path[len(directory)]
            for path in all_paths
            if len(path) == len(directory) + 1 and path[: len(directory)] == directory
        )
        tree.append({"path": list(directory), "names": names})
    enumerations = [
        {"path": entry["path"], "names": entry["names"]}
        for entry in descriptor_snapshot["enumerations"]
    ]
    return {
        "schema_version": "challenge148-completed-evidence-v1",
        "source_semantic_snapshot_sha256": validation[
            "semantic_snapshot_sha256"
        ],
        "completion_sha256": _sha256(completion_payload),
        "files": files,
        "enumerations": enumerations,
        "tree": tree,
    }


def _fsync_directories_bottom_up(
    root: int,
    paths: list[tuple[str, ...]] | set[tuple[str, ...]],
    *,
    observer: Callable[[tuple[str, ...]], None] | None = None,
) -> None:
    for path in sorted(set(paths), key=lambda value: (-len(value), value)):
        descriptor = -1
        parents: list[int] = []
        try:
            if path:
                descriptor, parents = _open_descriptor_path_for_runner(
                    root, list(path), "durability directory", directory=True
                )
            else:
                descriptor = os.dup(root)
            os.fsync(descriptor)
            if observer is not None:
                observer(path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            for parent in reversed(parents):
                os.close(parent)


def _validate_completed_evidence(
    completed: int,
    expected_sha256: str,
    plan: dict[str, Any],
    cell: dict[str, Any],
    cell_index: int,
    request: dict[str, Any],
    graph: dict[str, Any],
    executable_sha256: str,
    logs: int,
) -> dict[str, Any]:
    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_sha256
    ):
        raise ValueError("completed evidence content address is malformed")
    if sorted(os.listdir(completed)) != ["completion.json", "manifest.json", "output"]:
        raise ValueError("completed evidence root membership mismatch")
    output = manifest_fd = completion_fd = -1
    try:
        manifest_fd = _open_file_at(
            completed, "manifest.json", "completed evidence manifest"
        )
        manifest_payload = _read_fd(manifest_fd)
        manifest = _decode_object(manifest_payload, "completed evidence manifest")
        if (
            manifest_payload != canonical_json(manifest) + b"\n"
            or _sha256(canonical_json(manifest)) != expected_sha256
            or manifest.get("schema_version")
            != "challenge148-completed-evidence-v1"
        ):
            raise ValueError("completed evidence manifest hash mismatch")
        semantic_material = {
            "files": [
                {"path": entry["path"], "sha256": entry["sha256"]}
                for entry in manifest.get("files", [])
            ],
            "enumerations": manifest.get("enumerations", []),
        }
        if _sha256(canonical_json(semantic_material)) != manifest.get(
            "source_semantic_snapshot_sha256"
        ):
            raise ValueError("completed evidence semantic source hash mismatch")
        output = _open_directory_at(completed, "output", "completed evidence output")
        for entry in manifest.get("tree", []):
            path = entry.get("path")
            names = entry.get("names")
            if not isinstance(path, list) or not isinstance(names, list):
                raise ValueError("malformed completed evidence tree")
            descriptor, parents = (
                (os.dup(output), [])
                if not path
                else _open_descriptor_path_for_runner(
                    output, path, "completed evidence directory", directory=True
                )
            )
            try:
                if sorted(os.listdir(descriptor)) != names:
                    raise ValueError("completed evidence tree membership mismatch")
            finally:
                os.close(descriptor)
                for parent in reversed(parents):
                    os.close(parent)
        for entry in manifest.get("files", []):
            path = entry.get("path")
            descriptor, parents = _open_descriptor_path_for_runner(
                output, path, "evidence snapshot file", directory=False
            )
            try:
                payload = _read_fd(descriptor)
                if (
                    len(payload) != entry.get("size")
                    or _sha256(payload) != entry.get("sha256")
                ):
                    raise ValueError("completed evidence artifact hash mismatch")
            finally:
                os.close(descriptor)
                for parent in reversed(parents):
                    os.close(parent)
        validation = validate_qmc_adapter_output_descriptor(
            output,
            request,
            "QMC_SSE",
            graph=graph,
            output_namespace="archived-evidence",
            archival=True,
        )
        completion_fd = _open_file_at(
            completed, "completion.json", "completed evidence completion"
        )
        completion_payload = _read_fd(completion_fd)
        if _sha256(completion_payload) != manifest.get("completion_sha256"):
            raise ValueError("completed evidence completion hash mismatch")
        existing = _decode_object(completion_payload, "cell completion")
        expected = _completion_value(
            plan,
            cell,
            cell_index,
            validation["current_generation_payload"],
            existing.get("log_sha256"),
            executable_sha256,
            manifest["source_semantic_snapshot_sha256"],
        )
        _validate_completion(completion_payload, expected, logs)
        return {
            "completion": existing,
            "validation": validation,
            "manifest": manifest,
        }
    finally:
        for descriptor in (completion_fd, manifest_fd, output):
            if descriptor >= 0:
                os.close(descriptor)


def _open_descriptor_path_for_runner(
    root: int, parts: object, label: str, *, directory: bool
) -> tuple[int, list[int]]:
    if not isinstance(parts, list) or not parts:
        raise ValueError(f"{label} path is malformed")
    parent = root
    opened: list[int] = []
    try:
        for component in parts[:-1]:
            if not isinstance(component, str):
                raise ValueError(f"{label} path is malformed")
            parent = _open_directory_at(parent, component, f"{label} parent")
            opened.append(parent)
        name = parts[-1]
        if not isinstance(name, str):
            raise ValueError(f"{label} path is malformed")
        descriptor = (
            _open_directory_at(parent, name, label)
            if directory
            else _open_file_at(parent, name, label)
        )
        return descriptor, opened
    except BaseException:
        for descriptor in reversed(opened):
            os.close(descriptor)
        raise


def _publish_completed_evidence(
    cell: int,
    validation: dict[str, Any],
    plan: dict[str, Any],
    cell_value: dict[str, Any],
    cell_index: int,
    request: dict[str, Any],
    graph: dict[str, Any],
    log_sha256: list[str],
    executable_sha256: str,
    logs: int,
    race_hook: Callable[[str, dict[str, Any]], None] | None,
    cell_root: Path,
    publication_guard: Callable[[], None],
) -> tuple[str, dict[str, Any]]:
    completion = _completion_value(
        plan,
        cell_value,
        cell_index,
        validation["current_generation_payload"],
        log_sha256,
        executable_sha256,
        validation["semantic_snapshot_sha256"],
    )
    completion_payload = canonical_json(completion) + b"\n"
    manifest = _completed_evidence_manifest(validation, completion_payload)
    digest = _sha256(canonical_json(manifest))
    published_root = _open_or_create_directory_at(
        cell, "completed-evidence", "completed evidence root", mode=0o700
    )
    os.fsync(published_root)
    os.fsync(cell)
    temporary = f".completed-evidence-{digest}-{secrets.token_hex(12)}"
    temporary_fd = output = -1
    published = False
    try:
        existing_names = sorted(os.listdir(published_root))
        if existing_names:
            if existing_names != [digest]:
                raise ValueError("completed evidence root membership mismatch")
            existing = _open_directory_at(
                published_root, digest, "completed evidence"
            )
            try:
                result = _validate_completed_evidence(
                    existing,
                    digest,
                    plan,
                    cell_value,
                    cell_index,
                    request,
                    graph,
                    executable_sha256,
                    logs,
                )
            finally:
                os.close(existing)
            return digest, result
        os.mkdir(temporary, mode=0o700, dir_fd=cell)
        temporary_fd = _open_directory_at(
            cell, temporary, "temporary completed evidence"
        )
        output = _open_or_create_directory_at(
            temporary_fd, "output", "temporary completed evidence output", mode=0o700
        )
        descriptor_snapshot = validation["descriptor_snapshot"]
        directories = {
            tuple(entry["path"]) for entry in descriptor_snapshot["directories"]
        }
        for entry in descriptor_snapshot["files"]:
            path = tuple(entry["path"])
            directories.update(path[:index] for index in range(1, len(path)))
        for path in sorted(directories, key=lambda value: (len(value), value)):
            descriptor = _open_or_create_relative_directory(output, path)
            os.close(descriptor)
        for entry in descriptor_snapshot["files"]:
            path = tuple(entry["path"])
            parent = _open_or_create_relative_directory(output, path[:-1])
            try:
                descriptor = _write_new_file_at(
                    parent,
                    path[-1],
                    entry["payload"],
                    "completed evidence artifact",
                )
                os.close(descriptor)
            finally:
                os.close(parent)
        manifest_fd = _write_new_file_at(
            temporary_fd,
            "manifest.json",
            canonical_json(manifest) + b"\n",
            "completed evidence manifest",
        )
        os.close(manifest_fd)
        completion_fd = _write_new_file_at(
            temporary_fd,
            "completion.json",
            completion_payload,
            "completed evidence completion",
        )
        os.close(completion_fd)
        directory_paths = {
            (),
            ("output",),
            *{("output", *path) for path in directories},
        }
        _validate_completed_evidence(
            temporary_fd,
            digest,
            plan,
            cell_value,
            cell_index,
            request,
            graph,
            executable_sha256,
            logs,
        )
        _fsync_directories_bottom_up(temporary_fd, directory_paths)
        _call_hook(
            race_hook,
            "before_completed_evidence_publish",
            {
                "staged_path": str(cell_root / temporary),
                "completed_evidence_sha256": digest,
            },
        )
        publication_guard()
        result = _validate_completed_evidence(
            temporary_fd,
            digest,
            plan,
            cell_value,
            cell_index,
            request,
            graph,
            executable_sha256,
            logs,
        )
        _fsync_directories_bottom_up(temporary_fd, directory_paths)
        os.close(output)
        output = -1
        os.close(temporary_fd)
        temporary_fd = -1
        try:
            _rename_noreplace(cell, temporary, published_root, digest)
            published = True
            os.fsync(published_root)
            os.fsync(cell)
        except FileExistsError:
            existing = _open_directory_at(
                published_root, digest, "competing completed evidence"
            )
            try:
                result = _validate_completed_evidence(
                    existing,
                    digest,
                    plan,
                    cell_value,
                    cell_index,
                    request,
                    graph,
                    executable_sha256,
                    logs,
                )
            finally:
                os.close(existing)
        if sorted(os.listdir(published_root)) != [digest]:
            raise ValueError("completed evidence root membership mismatch")
        return digest, result
    finally:
        for descriptor in (output, temporary_fd):
            if descriptor >= 0:
                os.close(descriptor)
        if not published:
            try:
                _remove_tree_at(cell, temporary)
            except (FileNotFoundError, ValueError):
                pass
        os.close(published_root)


def _create_snapshot_file(
    snapshot: int, relative_text: object, payload: bytes, label: str
) -> tuple[int, list[tuple[int, str, int]]]:
    parts = _relative_parts(relative_text, label)
    parent = snapshot
    directories: list[tuple[int, str, int]] = []
    for component in parts[:-1]:
        child = _open_or_create_directory_at(parent, component, f"{label} parent", mode=0o700)
        directories.append((parent, component, child))
        parent = child
    descriptor = _write_new_file_at(parent, parts[-1], payload, label)
    return descriptor, directories


def _remove_snapshot(
    cell: int,
    name: str,
    snapshot: int,
    files: list[tuple[int, str, int]],
    directories: list[tuple[int, str, int]],
) -> None:
    for parent, filename, descriptor in files:
        _assert_child_identity(parent, filename, descriptor, "snapshot file")
        os.close(descriptor)
        os.unlink(filename, dir_fd=parent)
    seen: set[int] = set()
    for parent, dirname, descriptor in reversed(directories):
        if descriptor in seen:
            continue
        seen.add(descriptor)
        _assert_child_identity(parent, dirname, descriptor, "snapshot directory")
        os.close(descriptor)
        os.rmdir(dirname, dir_fd=parent)
    _assert_child_identity(cell, name, snapshot, "snapshot root")
    os.close(snapshot)
    os.rmdir(name, dir_fd=cell)


def _memfd_create(name: str) -> int:
    flags = getattr(os, "MFD_CLOEXEC", 0x0001) | getattr(
        os, "MFD_ALLOW_SEALING", 0x0002
    )
    if hasattr(os, "memfd_create"):
        return os.memfd_create(name, flags)
    syscall_number = {
        "x86_64": 319,
        "amd64": 319,
        "aarch64": 279,
        "arm64": 279,
        "riscv64": 279,
    }.get(platform.machine().lower())
    if syscall_number is None:
        raise ValueError("sealed executable memfd is unavailable on this architecture")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    descriptor = libc.syscall(
        ctypes.c_long(syscall_number),
        ctypes.c_char_p(os.fsencode(name)),
        ctypes.c_uint(flags),
    )
    if descriptor < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return int(descriptor)


def _open_executable(path: Path) -> tuple[int, str]:
    try:
        source = os.open(path, _file_flags())
    except OSError as exc:
        raise ValueError("QMC_SSE executable must be a readable regular file") from exc
    metadata = os.fstat(source)
    if not stat.S_ISREG(metadata.st_mode) or not metadata.st_mode & 0o111:
        os.close(source)
        raise ValueError("QMC_SSE executable must be an executable regular file")
    payload = _read_fd(source)
    after = os.fstat(source)
    if (
        _identity(source) != (after.st_dev, after.st_ino)
        or metadata.st_size != after.st_size
        or metadata.st_mtime_ns != after.st_mtime_ns
        or len(payload) != after.st_size
    ):
        os.close(source)
        raise ValueError("QMC_SSE executable changed while hashing")
    os.close(source)
    try:
        descriptor = _memfd_create("challenge148-qmc-sse")
    except OSError as exc:
        raise ValueError("sealed executable memfd creation failed") from exc
    try:
        _write_all(descriptor, payload)
        os.fchmod(descriptor, metadata.st_mode & 0o777)
        required_seals = (
            _F_SEAL_WRITE
            | _F_SEAL_GROW
            | _F_SEAL_SHRINK
            | _F_SEAL_SEAL
        )
        fcntl.fcntl(descriptor, _F_ADD_SEALS, required_seals)
        if fcntl.fcntl(descriptor, _F_GET_SEALS) & required_seals != required_seals:
            raise ValueError("sealed executable memfd did not retain required seals")
        if _read_fd(descriptor) != payload:
            raise ValueError("sealed executable memfd bytes mismatch")
        return descriptor, _sha256(payload)
    except BaseException:
        os.close(descriptor)
        raise


def _publish_log(logs: int, evidence: dict[str, Any]) -> str:
    payload = canonical_json(evidence) + b"\n"
    digest = _sha256(payload)
    _write_immutable_at(logs, f"{digest}.json", payload, "immutable subprocess log")
    return digest


def _process_group_has_live_members(process_group: int) -> bool:
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            stat_text = Path(f"/proc/{name}/stat").read_text(encoding="utf-8")
            fields = stat_text.rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if len(fields) > 2 and int(fields[2]) == process_group and fields[0] != "Z":
            return True
    return False


def _run_process(
    executable_fd: int,
    executable: Path,
    arguments: list[str],
    *,
    phase: str,
    timeout: int,
    cwd: Path,
    logs: int,
    executable_sha256: str,
    extra_pass_fds: tuple[int, ...] = (),
) -> tuple[subprocess.CompletedProcess[str], str]:
    diagnostic_command = [str(executable), *arguments]
    command = [f"/proc/self/fd/{executable_fd}", *arguments]
    if _sha256(_read_fd(executable_fd)) != executable_sha256:
        raise ValueError("QMC_SSE executable bytes changed after identity binding")
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            pass_fds=(executable_fd, *extra_pass_fds),
            start_new_session=True,
        )
    except OSError as exc:
        evidence = {
            "schema_version": "challenge148-production-cell-log-v1",
            "phase": phase,
            "command": diagnostic_command,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "timeout_seconds": timeout,
            "executable_sha256": executable_sha256,
            "spawn_error": f"{type(exc).__name__}: {exc}",
            "process_group_terminated": True,
            "stdout_drained": True,
        }
        _publish_log(logs, evidence)
        raise RuntimeError(f"QMC_SSE {phase} spawn failed: {exc}") from exc
    timed_out = False
    process_group_terminated = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=1.0)
        except subprocess.TimeoutExpired:
            stdout = stderr = ""
        if _process_group_has_live_members(process.pid):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        drained_stdout, drained_stderr = process.communicate()
        stdout = stdout or drained_stdout
        stderr = stderr or drained_stderr
        deadline = time.monotonic() + 1.0
        while (
            _process_group_has_live_members(process.pid)
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        process_group_terminated = not _process_group_has_live_members(process.pid)
    evidence = {
        "schema_version": "challenge148-production-cell-log-v1",
        "phase": phase,
        "command": diagnostic_command,
        "returncode": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "timeout_seconds": timeout,
        "executable_sha256": executable_sha256,
        "spawn_error": None,
        "process_group_terminated": (
            process_group_terminated if timed_out else True
        ),
        "stdout_drained": True,
    }
    digest = _publish_log(logs, evidence)
    if timed_out:
        if not process_group_terminated:
            raise RuntimeError(f"QMC_SSE {phase} timed out and process group survived")
        raise RuntimeError(f"QMC_SSE {phase} timed out after {timeout} seconds")
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if process.returncode != 0:
        raise RuntimeError(f"QMC_SSE {phase} exited with exit {process.returncode}")
    return completed, digest


def _validate_partial_binding(output: int, request_sha256: str) -> None:
    try:
        state_metadata = os.stat(
            ".qmc-sse-lock-state", dir_fd=output, follow_symlinks=False
        )
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(state_metadata.st_mode):
        raise ValueError("partial lock state must be a real directory")
    state = _open_directory_at(output, ".qmc-sse-lock-state", "partial lock state")
    try:
        try:
            identity_metadata = os.stat(
                "identity.json", dir_fd=state, follow_symlinks=False
            )
        except FileNotFoundError:
            return
        if not stat.S_ISREG(identity_metadata.st_mode):
            raise ValueError("partial lock identity must be a regular file")
        identity = _open_file_at(state, "identity.json", "partial lock identity")
        try:
            value = _decode_object(_read_fd(identity), "partial lock identity")
        finally:
            os.close(identity)
        if value.get("request_sha256") != request_sha256:
            raise ValueError("partial request hash mismatch")
    finally:
        os.close(state)


def _completion_value(
    plan: dict[str, Any],
    cell: dict[str, Any],
    cell_index: int,
    current_generation_payload: bytes,
    log_sha256: list[str],
    executable_sha256: str,
    semantic_snapshot_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "challenge148-production-cell-completion-v3",
        "cell_id": cell["cell_id"],
        "cell_index": cell_index,
        "plan_sha256": plan["plan_sha256"],
        "request_sha256": cell["request_sha256"],
        "graph_sha256": cell["graph_sha256"],
        "build_info_sha256": _sha256(canonical_json(plan["build_info"])),
        "executable_sha256": executable_sha256,
        "current_generation_sha256": _sha256(current_generation_payload),
        "semantic_snapshot_sha256": semantic_snapshot_sha256,
        "log_sha256": log_sha256,
    }


def _validate_completion(
    completion_payload: bytes,
    expected: dict[str, Any],
    logs_descriptor: int,
) -> None:
    completion = _decode_object(completion_payload, "cell completion")
    if completion_payload != canonical_json(completion) + b"\n":
        raise ValueError("cell completion is not canonical newline-terminated JSON")
    if set(completion) != _COMPLETION_KEYS or completion != expected:
        raise ValueError("cell completion binding mismatch")
    log_hashes = completion["log_sha256"]
    if (
        not isinstance(log_hashes, list)
        or len(log_hashes) != 2
        or any(
            not isinstance(digest, str) or len(digest) != 64
            for digest in log_hashes
        )
    ):
        raise ValueError("cell completion log binding mismatch")
    for digest in log_hashes:
        descriptor = _open_file_at(
            logs_descriptor, f"{digest}.json", "immutable subprocess log"
        )
        try:
            log_payload = _read_fd(descriptor)
            if _sha256(log_payload) != digest:
                raise ValueError("immutable subprocess log hash mismatch")
            log = _decode_object(log_payload, "immutable subprocess log")
            if log_payload != canonical_json(log) + b"\n":
                raise ValueError("immutable subprocess log is not canonical")
        finally:
            os.close(descriptor)


def _validate_pointer_identity(output: int, validation: dict[str, Any]) -> None:
    descriptor = _open_file_at(
        output, "current-generation.json", "current generation pointer"
    )
    try:
        if list(_identity(descriptor)) != validation["current_generation_identity"]:
            raise ValueError("current generation pointer identity changed")
        if _read_fd(descriptor) != validation["current_generation_payload"]:
            raise ValueError("current generation pointer bytes changed")
    finally:
        os.close(descriptor)


def _revalidate_semantic_snapshot(output: int, validation: dict[str, Any]) -> None:
    revalidate_qmc_adapter_output_descriptor_snapshot(
        output, validation["descriptor_snapshot"]
    )


def _call_hook(
    race_hook: Callable[[str, dict[str, Any]], None] | None,
    event: str,
    details: dict[str, Any],
) -> None:
    if race_hook is not None:
        race_hook(event, details)


def _assert_absolute_directory_identity(path: Path, descriptor: int, label: str) -> None:
    reopened = _open_absolute_directory(path, label)
    try:
        if _identity(reopened) != _identity(descriptor):
            raise ValueError(f"{label} identity changed")
    finally:
        os.close(reopened)


def run_cell(
    plan_path: Path,
    cell_index: int,
    executable: Path,
    *,
    timeout: int = 600,
    race_hook: Callable[[str, dict[str, Any]], None] | None = None,
) -> Path:
    if not isinstance(cell_index, int) or isinstance(cell_index, bool):
        raise TypeError("cell index must be an integer")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout must be a positive integer")

    plan_path = Path(plan_path).absolute()
    plan_root = plan_path.parent
    plan_root_fd = _open_absolute_directory(plan_root, "plan root")
    request_directories: list[int] = []
    graph_directories: list[int] = []
    plan_fd = request_fd = graph_fd = -1
    cells_fd = cell_fd = logs_fd = output_fd = -1
    completed_root_fd = completed_fd = -1
    executable_fd = -1
    snapshot_fd = -1
    snapshot_files: list[tuple[int, str, int]] = []
    snapshot_directories: list[tuple[int, str, int]] = []
    snapshot_name = ""
    try:
        plan_fd = _open_file_at(plan_root_fd, plan_path.name, "canonical plan")
        plan_payload = _read_fd(plan_fd)
        plan = _decode_object(plan_payload, "canonical plan")
        if plan_payload != (
            json.dumps(plan, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"):
            raise ValueError("plan.json is not canonical sorted indented JSON")
        _validate_plan_schema(plan)
        cells = plan["cells"]
        if cell_index < 0 or cell_index >= len(cells):
            raise ValueError(f"cell index must be between 0 and {len(cells) - 1}")
        cell = cells[cell_index]

        request_fd, request_directories = _open_relative_file(
            plan_root_fd, cell["request_path"], "cell request"
        )
        request_payload = _read_fd(request_fd)
        request = _decode_object(request_payload, "cell request")
        if (
            request != cell["request"]
            or _sha256(canonical_json(request)) != cell["request_sha256"]
        ):
            raise ValueError("request hash or embedded request mismatch")

        graph_fd, graph_directories = _open_relative_file(
            plan_root_fd, cell["graph_path"], "cell graph"
        )
        graph_payload = _read_fd(graph_fd)
        graph = _decode_object(graph_payload, "cell graph")
        expected_graph = next(
            (
                entry
                for entry in plan["graphs"]
                if entry["path"] == cell["graph_path"]
            ),
            None,
        )
        if (
            expected_graph is None
            or graph != expected_graph["content"]
            or graph.get("sha256") != cell["graph_sha256"]
        ):
            raise ValueError("graph hash or embedded graph mismatch")

        cells_fd = _open_or_create_directory_at(
            plan_root_fd, "cells", "cells directory"
        )
        cell_fd = _open_or_create_directory_at(
            cells_fd, cell["cell_id"], "cell root"
        )
        logs_fd = _open_or_create_directory_at(cell_fd, "logs", "logs directory")
        cell_root = plan_root / "cells" / cell["cell_id"]
        output = cell_root / "adapter-output"

        try:
            output_metadata = os.stat(
                "adapter-output", dir_fd=cell_fd, follow_symlinks=False
            )
        except FileNotFoundError:
            output_metadata = None
        if output_metadata is not None:
            if not stat.S_ISDIR(output_metadata.st_mode):
                raise ValueError("adapter output must be a real directory, not a symlink")
            output_fd = _open_directory_at(
                cell_fd, "adapter-output", "adapter output"
            )

        try:
            completed_metadata = os.stat(
                "completed-evidence", dir_fd=cell_fd, follow_symlinks=False
            )
        except FileNotFoundError:
            completed_metadata = None
        if completed_metadata is not None and not stat.S_ISDIR(
            completed_metadata.st_mode
        ):
            raise ValueError("completed evidence root must be a real directory")
        completed_digest: str | None = None
        if completed_metadata is not None:
            inspected_completed_root = _open_directory_at(
                cell_fd, "completed-evidence", "completed evidence root"
            )
            try:
                completed_names = sorted(os.listdir(inspected_completed_root))
            finally:
                os.close(inspected_completed_root)
            if completed_names:
                if (
                    len(completed_names) != 1
                    or len(completed_names[0]) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in completed_names[0]
                    )
                ):
                    raise ValueError("completed evidence root membership mismatch")
                completed_digest = completed_names[0]
        if completed_digest is None and output_fd >= 0:
            _validate_partial_binding(output_fd, cell["request_sha256"])

        executable = Path(executable).absolute()
        executable_fd, executable_sha256 = _open_executable(executable)
        _call_hook(
            race_hook,
            "after_executable_open",
            {"path": str(executable), "sha256": executable_sha256},
        )
        build_completed, build_log = _run_process(
            executable_fd,
            executable,
            ["--build-info"],
            phase="build-info",
            timeout=timeout,
            cwd=Path(f"/proc/self/fd/{plan_root_fd}"),
            logs=logs_fd,
            executable_sha256=executable_sha256,
            extra_pass_fds=(plan_root_fd,),
        )
        try:
            actual_build = _decode_object(
                build_completed.stdout.encode("utf-8"), "QMC_SSE build info"
            )
        except ValueError as exc:
            raise ValueError("build info is malformed") from exc
        if actual_build != plan["build_info"]:
            raise ValueError("build info does not exactly match plan build binding")

        snapshot_name = f".cell-input-{secrets.token_hex(12)}"
        _call_hook(
            race_hook,
            "before_snapshot_create",
            {"cell_root": str(cell_root), "name": snapshot_name},
        )
        try:
            os.mkdir(snapshot_name, mode=0o700, dir_fd=cell_fd)
        except OSError as exc:
            raise ValueError("snapshot root creation collided with existing path") from exc
        snapshot_fd = _open_directory_at(cell_fd, snapshot_name, "snapshot root")
        snapshot_request_fd, request_snapshot_directories = _create_snapshot_file(
            snapshot_fd, cell["request_path"], request_payload, "snapshot request"
        )
        request_parent = (
            request_snapshot_directories[-1][2]
            if request_snapshot_directories
            else snapshot_fd
        )
        snapshot_files.append(
            (
                request_parent,
                _relative_parts(cell["request_path"], "request")[-1],
                snapshot_request_fd,
            )
        )
        snapshot_directories.extend(request_snapshot_directories)
        snapshot_graph_fd, graph_snapshot_directories = _create_snapshot_file(
            snapshot_fd, cell["graph_path"], graph_payload, "snapshot graph"
        )
        graph_parent = (
            graph_snapshot_directories[-1][2]
            if graph_snapshot_directories
            else snapshot_fd
        )
        snapshot_files.append(
            (
                graph_parent,
                _relative_parts(cell["graph_path"], "graph")[-1],
                snapshot_graph_fd,
            )
        )
        snapshot_directories.extend(graph_snapshot_directories)

        if completed_digest is not None:
            completed_root_fd = _open_directory_at(
                cell_fd, "completed-evidence", "completed evidence root"
            )
            completed_names = sorted(os.listdir(completed_root_fd))
            if completed_names != [completed_digest]:
                raise ValueError("completed evidence root membership mismatch")
            digest = completed_digest
            completed_fd = _open_directory_at(
                completed_root_fd, digest, "completed evidence"
            )
            _validate_completed_evidence(
                completed_fd,
                digest,
                plan,
                cell,
                cell_index,
                request,
                graph,
                executable_sha256,
                logs_fd,
            )
            _call_hook(
                race_hook,
                "after_completed_evidence_validation",
                {"cell_root": str(cell_root), "completed": True},
            )
            _assert_absolute_directory_identity(plan_root, plan_root_fd, "plan root")
            _assert_child_identity(plan_root_fd, "cells", cells_fd, "cells directory")
            _assert_child_identity(cells_fd, cell["cell_id"], cell_fd, "cell root")
            _assert_child_identity(cell_fd, "logs", logs_fd, "logs directory")
            _assert_child_identity(
                cell_fd,
                "completed-evidence",
                completed_root_fd,
                "completed evidence root",
            )
            _assert_child_identity(
                completed_root_fd, digest, completed_fd, "completed evidence"
            )
            if sorted(os.listdir(completed_root_fd)) != [digest]:
                raise ValueError("completed evidence root membership changed")
            _validate_completed_evidence(
                completed_fd,
                digest,
                plan,
                cell,
                cell_index,
                request,
                graph,
                executable_sha256,
                logs_fd,
            )
            return cell_root

        if output_fd < 0:
            output_fd = _open_or_create_directory_at(
                cell_fd, "adapter-output", "adapter output", mode=0o700
            )
        _validate_partial_binding(output_fd, cell["request_sha256"])
        _call_hook(
            race_hook,
            "before_adapter_launch",
            {"cell_root": str(cell_root)},
        )
        _, launch_log = _run_process(
            executable_fd,
            executable,
            [
                "--request-fd",
                str(snapshot_request_fd),
                "--output-directory-fd",
                str(output_fd),
            ],
            phase="adapter",
            timeout=timeout,
            cwd=Path(f"/proc/self/fd/{snapshot_fd}"),
            logs=logs_fd,
            executable_sha256=executable_sha256,
            extra_pass_fds=(
                snapshot_fd,
                snapshot_request_fd,
                snapshot_graph_fd,
                output_fd,
            ),
        )
        _assert_child_identity(cell_fd, "adapter-output", output_fd, "adapter output")
        validation = validate_qmc_adapter_output_descriptor(
            output_fd,
            request,
            "QMC_SSE",
            graph=graph,
            output_namespace=_output_fd_namespace(output_fd),
        )
        _call_hook(
            race_hook,
            "after_output_validation",
            {"output": str(output), "completed": False},
        )
        _revalidate_semantic_snapshot(output_fd, validation)
        _validate_pointer_identity(output_fd, validation)

        def publication_guard() -> None:
            _assert_absolute_directory_identity(plan_root, plan_root_fd, "plan root")
            _assert_child_identity(
                plan_root_fd, "cells", cells_fd, "cells directory"
            )
            _assert_child_identity(
                cells_fd, cell["cell_id"], cell_fd, "cell root"
            )
            _assert_child_identity(cell_fd, "logs", logs_fd, "logs directory")

        digest, _ = _publish_completed_evidence(
            cell_fd,
            validation,
            plan,
            cell,
            cell_index,
            request,
            graph,
            [build_log, launch_log],
            executable_sha256,
            logs_fd,
            race_hook,
            cell_root,
            publication_guard,
        )
        publication_guard()
        completed_root_fd = _open_directory_at(
            cell_fd, "completed-evidence", "completed evidence root"
        )
        completed_fd = _open_directory_at(
            completed_root_fd, digest, "completed evidence"
        )
        if sorted(os.listdir(completed_root_fd)) != [digest]:
            raise ValueError("completed evidence root membership mismatch")
        _validate_completed_evidence(
            completed_fd,
            digest,
            plan,
            cell,
            cell_index,
            request,
            graph,
            executable_sha256,
            logs_fd,
        )
        _assert_absolute_directory_identity(plan_root, plan_root_fd, "plan root")
        _assert_child_identity(plan_root_fd, "cells", cells_fd, "cells directory")
        _assert_child_identity(cells_fd, cell["cell_id"], cell_fd, "cell root")
        _assert_child_identity(cell_fd, "logs", logs_fd, "logs directory")
        _assert_child_identity(
            cell_fd,
            "completed-evidence",
            completed_root_fd,
            "completed evidence root",
        )
        _assert_child_identity(
            completed_root_fd, digest, completed_fd, "completed evidence"
        )
        return cell_root
    finally:
        if snapshot_fd >= 0:
            try:
                _remove_snapshot(
                    cell_fd,
                    snapshot_name,
                    snapshot_fd,
                    snapshot_files,
                    snapshot_directories,
                )
            except FileNotFoundError:
                pass
        for descriptor in (
            output_fd,
            completed_fd,
            completed_root_fd,
            executable_fd,
            logs_fd,
            cell_fd,
            cells_fd,
            graph_fd,
            request_fd,
            plan_fd,
        ):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        for descriptor in reversed(graph_directories + request_directories):
            try:
                os.close(descriptor)
            except OSError:
                pass
        os.close(plan_root_fd)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run or resume one immutable Challenge 148 production cell."
    )
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--cell-index", required=True, type=int)
    parser.add_argument("--qmc-sse", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    arguments = parser.parse_args()
    result = run_cell(
        arguments.plan,
        arguments.cell_index,
        arguments.qmc_sse,
        timeout=arguments.timeout_seconds,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
