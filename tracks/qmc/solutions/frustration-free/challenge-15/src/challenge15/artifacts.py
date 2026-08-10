"""Fail-closed publication of provenance-bound JSON artifacts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import ctypes
import errno
from typing import Any, Callable
import uuid


_ARTIFACT_SCHEMA = "challenge15.artifact.v1"
_TOP_LEVEL_KEYS = frozenset({"schema", "payload", "payload_sha256"})


class _UndurableUnlinkError(OSError):
    """An unlink completed, but its directory durability is unknown."""

    def __init__(self, name: str, cause: BaseException) -> None:
        self.name = name
        self.cause = cause
        super().__init__(
            getattr(cause, "errno", errno.EIO) or errno.EIO,
            f"unlink durability failed for {name}: {cause}",
        )


class ArtifactRecoveryError(RuntimeError):
    """A failed rollback with a fully inspected, surfaced recovery state."""

    def __init__(
        self,
        backup_path: Path,
        publication_error: BaseException,
        recovery_error: BaseException,
        *,
        recovery_paths: tuple[Path, ...] | None = None,
        state: str = "recovery_only",
        destination_path: Path | None = None,
        destination_exists: bool | None = None,
        possible_recovery_paths: tuple[Path, ...] = (),
    ) -> None:
        self.backup_path = backup_path
        self.publication_error = publication_error
        self.recovery_error = recovery_error
        self.recovery_paths = (
            (backup_path,) if recovery_paths is None else recovery_paths
        )
        self.state = state
        self.destination_path = destination_path
        self.destination_exists = destination_exists
        self.possible_recovery_paths = possible_recovery_paths
        self.cleanup_error: BaseException | None = None
        surfaced = ", ".join(str(path) for path in self.recovery_paths) or "none"
        possible = (
            ", ".join(str(path) for path in possible_recovery_paths)
            or "none"
        )
        super().__init__(
            "artifact rollback was not durably completed; "
            f"recoverable backup state={state}; recovery_paths={surfaced}; "
            f"possible_recovery_paths={possible}"
        )


def publish_json_atomic(
    path: Path | str,
    payload: dict[str, Any],
    *,
    validator: Callable[[Path], Any] | None = None,
) -> None:
    """Publish with renameat2 no-replace/exchange and ownership-checked rollback."""

    destination = Path(path)
    if destination.name in {"", ".", ".."} or "/" in destination.name:
        raise ValueError("artifact destination name is invalid")
    _validate_payload(payload)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema": _ARTIFACT_SCHEMA,
        "payload": payload,
        "payload_sha256": _sha256(_canonical_json(payload)),
    }
    encoded = _canonical_json(document) + b"\n"
    parent_fd = _open_directory_fd(parent)
    token = uuid.uuid4().hex
    lock_name = f".{destination.name}.transaction.lock"
    stage_name = f".{destination.name}.transaction.{token}.partial"
    backup_name = f".{destination.name}.transaction.{token}.backup"
    lock_identity: tuple[int, int, str] | None = None
    stage_identity: tuple[int, int, str] | None = None
    backup_identity: tuple[int, int, str] | None = None
    old_descriptor: int | None = None
    retain_backup = False
    pending_recovery_error: ArtifactRecoveryError | None = None
    pending_publication_error: BaseException | None = None
    try:
        lock_identity = _write_name_at(parent_fd, lock_name, token.encode())
        try:
            old_descriptor = os.open(
                destination.name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_fd,
            )
        except FileNotFoundError:
            old_descriptor = None
        old_identity = (
            None
            if old_descriptor is None
            else _descriptor_identity(old_descriptor)
        )
        old_bytes = (
            None
            if old_descriptor is None
            else _read_descriptor(old_descriptor)
        )
        if old_descriptor is not None:
            verify_artifact(Path(f"/proc/self/fd/{old_descriptor}"))
            backup_identity = _write_name_at(
                parent_fd,
                backup_name,
                old_bytes,
            )
            verify_artifact(parent / backup_name)

        stage_identity = _write_name_at(parent_fd, stage_name, encoded)
        published_identity = stage_identity
        stage_path = parent / stage_name
        verify_artifact(stage_path)
        if validator is not None:
            validator(stage_path)

        if old_identity is None:
            _rename_noreplace_strict(
                parent_fd,
                stage_name,
                destination.name,
            )
            stage_identity = None
            try:
                _fsync_directory_fd(parent_fd)
                _validate_published_name(
                    parent_fd,
                    destination,
                    published_identity,
                    validator,
                )
            except BaseException as publication_error:
                _rollback_created_name(
                    parent_fd,
                    destination,
                    stage_name,
                    published_identity,
                    publication_error,
                )
                raise
        else:
            _rename_exchange_strict(
                parent_fd,
                stage_name,
                destination.name,
            )
            try:
                _fsync_directory_fd(parent_fd)
            except BaseException as publication_error:
                if _name_matches(parent_fd, destination.name, stage_identity):
                    assert backup_identity is not None
                    _rollback_exchanged_name(
                        parent_fd,
                        destination,
                        stage_name,
                        published_identity,
                        backup_name,
                        backup_identity,
                        publication_error,
                    )
                    stage_identity = None
                    backup_identity = None
                    raise
                assert backup_identity is not None
                retain_backup = True
                recovery_error = RuntimeError("destination ownership CAS mismatch")
                raise _inspected_recovery_error(
                    parent_fd,
                    destination,
                    (backup_name, stage_name),
                    publication_error,
                    recovery_error,
                ) from publication_error
            if not _name_matches(parent_fd, stage_name, old_identity):
                recovery_error = RuntimeError(
                    "concurrent existing destination replacement detected"
                )
                if _name_matches(
                    parent_fd,
                    destination.name,
                    stage_identity,
                ):
                    try:
                        _rename_exchange_strict(
                            parent_fd,
                            stage_name,
                            destination.name,
                        )
                        _fsync_directory_fd(parent_fd)
                        _unlink_owned_name(
                            parent_fd,
                            stage_name,
                            stage_identity,
                        )
                    except BaseException as rollback_error:
                        assert backup_identity is not None
                        raise _inspected_recovery_error(
                            parent_fd,
                            destination,
                            (backup_name, stage_name),
                            recovery_error,
                            rollback_error,
                        ) from rollback_error
                assert backup_identity is not None
                retain_backup = True
                raise _inspected_recovery_error(
                    parent_fd,
                    destination,
                    (backup_name, stage_name),
                    recovery_error,
                    recovery_error,
                )
            try:
                _validate_published_name(
                    parent_fd,
                    destination,
                    published_identity,
                    validator,
                )
            except BaseException as publication_error:
                if _name_matches(
                    parent_fd,
                    destination.name,
                    published_identity,
                ):
                    assert backup_identity is not None
                    _rollback_exchanged_name(
                        parent_fd,
                        destination,
                        stage_name,
                        published_identity,
                        backup_name,
                        backup_identity,
                        publication_error,
                    )
                    stage_identity = None
                    backup_identity = None
                    raise
                assert backup_identity is not None
                retain_backup = True
                recovery_error = RuntimeError("destination ownership CAS mismatch")
                raise _inspected_recovery_error(
                    parent_fd,
                    destination,
                    (backup_name, stage_name),
                    publication_error,
                    recovery_error,
                ) from publication_error
            _unlink_owned_name(parent_fd, stage_name, old_identity)
            stage_identity = None
            if backup_identity is not None:
                _unlink_owned_name(parent_fd, backup_name, backup_identity)
                backup_identity = None
        _verify_directory_identity(parent, parent_fd)
    except ArtifactRecoveryError as recovery_error:
        retain_backup = True
        stage_identity = None
        backup_identity = None
        pending_recovery_error = recovery_error
    except BaseException as publication_error:
        pending_publication_error = publication_error
    finally:
        cleanup_error: BaseException | None = None
        if old_descriptor is not None:
            os.close(old_descriptor)
        try:
            if stage_identity is not None:
                _unlink_owned_name(parent_fd, stage_name, stage_identity)
            if backup_identity is not None and not retain_backup:
                _unlink_owned_name(parent_fd, backup_name, backup_identity)
            if lock_identity is not None:
                _unlink_owned_name(parent_fd, lock_name, lock_identity)
        except BaseException as error:
            cleanup_error = error
        if cleanup_error is not None and pending_recovery_error is not None:
            pending_recovery_error = _inspected_recovery_error(
                parent_fd,
                destination,
                tuple(
                    path.name
                    for path in (
                        pending_recovery_error.recovery_paths
                        + pending_recovery_error.possible_recovery_paths
                    )
                ),
                pending_recovery_error.publication_error,
                pending_recovery_error.recovery_error,
                possible_recovery_names=tuple(
                    path.name
                    for path in pending_recovery_error.possible_recovery_paths
                ),
            )
            pending_recovery_error.cleanup_error = cleanup_error
        elif cleanup_error is not None and pending_publication_error is not None:
            pending_recovery_error = _inspected_recovery_error(
                parent_fd,
                destination,
                (stage_name, backup_name),
                pending_publication_error,
                cleanup_error,
            )
        os.close(parent_fd)
        if cleanup_error is not None and pending_recovery_error is None:
            raise cleanup_error
    if pending_recovery_error is not None:
        raise pending_recovery_error from pending_recovery_error.recovery_error
    if pending_publication_error is not None:
        raise pending_publication_error


def verify_artifact(path: Path | str) -> dict[str, Any]:
    """Validate an artifact's exact schema and payload digest, then return it."""

    artifact_path = Path(path)
    try:
        document = json.loads(
            artifact_path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
            object_pairs_hook=_object_without_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("artifact is not strict UTF-8 JSON") from exc

    if not isinstance(document, dict) or set(document) != _TOP_LEVEL_KEYS:
        raise ValueError("artifact does not match the required schema")
    if document["schema"] != _ARTIFACT_SCHEMA:
        raise ValueError("artifact does not match the required schema")
    payload = document["payload"]
    if not isinstance(payload, dict):
        raise ValueError("artifact payload must be a JSON object")
    _validate_payload(payload)
    digest = document["payload_sha256"]
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("artifact payload SHA256 is malformed")
    if not _is_lower_hex(digest):
        raise ValueError("artifact payload SHA256 is malformed")
    if not hashlib.sha256(_canonical_json(payload)).hexdigest() == digest:
        raise ValueError("artifact payload SHA256 mismatch")
    return payload


def publish_create_only(path: Path | str, encoded: bytes) -> Path:
    """Stage and atomically publish bytes through a trusted directory descriptor."""

    destination = Path(path)
    if destination.name in {"", ".", ".."} or "/" in destination.name:
        raise ValueError("create-only destination name is invalid")
    parent_fd = _open_directory_fd(destination.parent)
    staging_name = f".{destination.name}.partial.{uuid.uuid4().hex}"
    descriptor: int | None = None
    try:
        descriptor = os.open(
            staging_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        _rename_noreplace(parent_fd, staging_name, destination.name)
        _fsync_directory_fd(parent_fd)
        _verify_directory_identity(destination.parent, parent_fd)
    except BaseException:
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        # Never unlink a staging *name* after failure: an adversary may have
        # replaced the inode between the failed operation and cleanup.
        # Hidden partial names are outside every production selector.
        os.close(parent_fd)
    return destination


def _open_directory_fd(directory: Path) -> int:
    absolute = directory.absolute()
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open("/", flags)
    try:
        for part in absolute.parts[1:]:
            try:
                child = os.open(part, flags, dir_fd=descriptor)
            except OSError as exc:
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise ValueError(
                        f"symlink path component is forbidden: {directory}"
                    ) from exc
                raise
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _rename_noreplace(
    directory_fd: int,
    source: str,
    destination: str,
    destination_directory_fd: int | None = None,
) -> None:
    destination_fd = (
        directory_fd
        if destination_directory_fd is None
        else destination_directory_fd
    )
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:  # pragma: no cover - Linux production hosts provide it
        os.link(
            source,
            destination,
            src_dir_fd=directory_fd,
            dst_dir_fd=destination_fd,
            follow_symlinks=False,
        )
        os.unlink(source, dir_fd=directory_fd)
        return
    result = renameat2(
        directory_fd,
        os.fsencode(source),
        destination_fd,
        os.fsencode(destination),
        1,  # RENAME_NOREPLACE
    )
    if result != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError(error, os.strerror(error), destination)
        raise OSError(error, os.strerror(error), destination)


def _renameat2_strict(
    directory_fd: int,
    source: str,
    destination: str,
    flags: int,
) -> None:
    """Invoke Linux renameat2 without any non-atomic fallback."""

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise OSError(errno.ENOSYS, "renameat2 is unavailable")
    result = renameat2(
        directory_fd,
        os.fsencode(source),
        directory_fd,
        os.fsencode(destination),
        flags,
    )
    if result != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError(error, os.strerror(error), destination)
        raise OSError(error, os.strerror(error), destination)


def _rename_noreplace_strict(
    directory_fd: int,
    source: str,
    destination: str,
) -> None:
    _renameat2_strict(directory_fd, source, destination, 1)


def _rename_exchange_strict(
    directory_fd: int,
    source: str,
    destination: str,
) -> None:
    _renameat2_strict(directory_fd, source, destination, 2)


def _read_descriptor(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while True:
        chunk = os.pread(descriptor, 1024 * 1024, offset)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        offset += len(chunk)


def _descriptor_identity(descriptor: int) -> tuple[int, int, str]:
    status = os.fstat(descriptor)
    return status.st_dev, status.st_ino, _sha256(_read_descriptor(descriptor))


def _write_name_at(
    directory_fd: int,
    name: str,
    encoded: bytes,
) -> tuple[int, int, str]:
    descriptor = os.open(
        name,
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory_fd,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(descriptor)
        return _descriptor_identity(descriptor)
    finally:
        os.close(descriptor)


def _name_matches(
    directory_fd: int,
    name: str,
    identity: tuple[int, int, str],
) -> bool:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
    except (FileNotFoundError, OSError):
        return False
    try:
        return _descriptor_identity(descriptor) == identity
    finally:
        os.close(descriptor)


def _unlink_owned_name(
    directory_fd: int,
    name: str,
    identity: tuple[int, int, str],
) -> None:
    if not _name_matches(directory_fd, name, identity):
        return
    os.unlink(name, dir_fd=directory_fd)
    try:
        _fsync_directory_fd(directory_fd)
    except BaseException as error:
        raise _UndurableUnlinkError(name, error) from error


def _validate_published_name(
    directory_fd: int,
    destination: Path,
    expected_identity: tuple[int, int, str],
    validator: Callable[[Path], Any] | None,
) -> None:
    if not _name_matches(directory_fd, destination.name, expected_identity):
        raise ValueError("published artifact ownership/readback mismatch")
    verify_artifact(destination)
    if validator is not None:
        validator(destination)
    if not _name_matches(directory_fd, destination.name, expected_identity):
        raise ValueError("published artifact changed during verification")


def _rollback_created_name(
    directory_fd: int,
    destination: Path,
    recovery_name: str,
    expected_identity: tuple[int, int, str],
    publication_error: BaseException,
) -> None:
    try:
        _rename_noreplace_strict(
            directory_fd,
            destination.name,
            recovery_name,
        )
        _fsync_directory_fd(directory_fd)
    except BaseException as recovery_error:
        raise _inspected_recovery_error(
            directory_fd,
            destination,
            (recovery_name,),
            publication_error,
            recovery_error,
        ) from recovery_error
    if _name_matches(directory_fd, recovery_name, expected_identity):
        recovery_bytes = _read_name(directory_fd, recovery_name)
        try:
            os.unlink(recovery_name, dir_fd=directory_fd)
            _fsync_directory_fd(directory_fd)
        except BaseException as recovery_error:
            if not _name_exists(directory_fd, recovery_name):
                try:
                    _write_name_at(
                        directory_fd,
                        recovery_name,
                        recovery_bytes,
                    )
                except BaseException:
                    pass
            raise _inspected_recovery_error(
                directory_fd,
                destination,
                (recovery_name,),
                publication_error,
                recovery_error,
            ) from recovery_error
        return
    try:
        _rename_noreplace_strict(
            directory_fd,
            recovery_name,
            destination.name,
        )
        _fsync_directory_fd(directory_fd)
    except BaseException as recovery_error:
        raise _inspected_recovery_error(
            directory_fd,
            destination,
            (recovery_name,),
            publication_error,
            recovery_error,
        ) from recovery_error
    recovery_error = RuntimeError("destination ownership CAS mismatch")
    raise _inspected_recovery_error(
        directory_fd,
        destination,
        (recovery_name,),
        publication_error,
        recovery_error,
    )


def _rollback_exchanged_name(
    directory_fd: int,
    destination: Path,
    stage_name: str,
    published_identity: tuple[int, int, str],
    backup_name: str,
    backup_identity: tuple[int, int, str],
    publication_error: BaseException,
) -> None:
    try:
        _rename_exchange_strict(
            directory_fd,
            stage_name,
            destination.name,
        )
        _fsync_directory_fd(directory_fd)
        _unlink_owned_name(directory_fd, stage_name, published_identity)
        _unlink_owned_name(directory_fd, backup_name, backup_identity)
    except BaseException as recovery_error:
        raise _inspected_recovery_error(
            directory_fd,
            destination,
            (backup_name, stage_name),
            publication_error,
            recovery_error,
        ) from recovery_error


def _identity_for_name(
    directory_fd: int,
    name: str,
) -> tuple[int, int, str]:
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_fd,
    )
    try:
        return _descriptor_identity(descriptor)
    finally:
        os.close(descriptor)


def _read_name(directory_fd: int, name: str) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_fd,
    )
    try:
        return _read_descriptor(descriptor)
    finally:
        os.close(descriptor)


def _name_exists(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _name_is_valid_artifact(directory_fd: int, name: str) -> bool:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
    except OSError:
        return False
    try:
        verify_artifact(Path(f"/proc/self/fd/{descriptor}"))
    except (OSError, ValueError):
        return False
    finally:
        os.close(descriptor)
    return True


def _inspected_recovery_error(
    directory_fd: int,
    destination: Path,
    recovery_names: tuple[str, ...],
    publication_error: BaseException,
    recovery_error: BaseException,
    *,
    possible_recovery_names: tuple[str, ...] = (),
) -> ArtifactRecoveryError:
    destination_exists = _name_exists(directory_fd, destination.name)
    recovery_paths = tuple(
        destination.parent / name
        for name in dict.fromkeys(recovery_names)
        if _name_is_valid_artifact(directory_fd, name)
    )
    possible_names = list(dict.fromkeys(possible_recovery_names))
    if (
        isinstance(recovery_error, _UndurableUnlinkError)
        and recovery_error.name in recovery_names
        and recovery_error.name not in possible_names
    ):
        possible_names.append(recovery_error.name)
    possible_recovery_paths = tuple(
        destination.parent / name for name in possible_names
    )
    if destination_exists and recovery_paths:
        state = "destination_and_recovery"
    elif destination_exists and possible_recovery_paths:
        state = "destination_and_possible_recovery"
    elif destination_exists:
        state = "destination_only"
    elif recovery_paths:
        state = "recovery_only"
    elif possible_recovery_paths:
        state = "possible_recovery_only"
    else:
        state = "neither"
    backup_path = (
        recovery_paths[0] if recovery_paths else destination
    )
    return ArtifactRecoveryError(
        backup_path,
        publication_error,
        recovery_error,
        recovery_paths=recovery_paths,
        state=state,
        destination_path=destination,
        destination_exists=destination_exists,
        possible_recovery_paths=possible_recovery_paths,
    )


def _fsync_directory_fd(descriptor: int) -> None:
    os.fsync(descriptor)


def _verify_directory_identity(path: Path, descriptor: int) -> None:
    opened = os.fstat(descriptor)
    try:
        current = os.lstat(path)
    except FileNotFoundError as exc:
        raise ValueError("publication parent identity changed") from exc
    if stat.S_ISLNK(current.st_mode) or (
        current.st_dev,
        current.st_ino,
    ) != (opened.st_dev, opened.st_ino):
        raise ValueError("publication parent identity changed")


def publish_production_envelope(
    path: Path | str,
    schema: str,
    payload: Any,
    *,
    context: dict[str, Any] | None = None,
) -> str:
    """Exclusively publish one strict production envelope and return its digest."""

    from .production_schema import (
        CONTEXT_REQUIRED_SCHEMAS,
        canonical_json,
        envelope_for,
        validate_envelope,
    )

    if schema in CONTEXT_REQUIRED_SCHEMAS and context is None:
        raise ValueError(f"{schema} publication requires complete context")
    envelope = envelope_for(schema, payload)
    # Context validation is part of admission, not post-publication auditing.
    # A rejected receipt must never consume its create-only destination.
    validated_before = validate_envelope(envelope, schema, context=context)
    if validated_before != envelope["payload"]:
        raise ValueError("in-memory production envelope changed during validation")
    encoded = canonical_json(envelope) + b"\n"
    destination = publish_create_only(path, encoded)
    validated = validate_envelope(destination, schema, context=context)
    digest = envelope["payload_sha256"]
    if validated != envelope["payload"]:
        raise ValueError("published production envelope changed during verification")
    assert isinstance(digest, str)
    return digest


def _write_unique_sibling(destination: Path, encoded: bytes, *, suffix: str) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f"{destination.name}.",
        suffix=suffix,
        dir=destination.parent,
    )
    sibling = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        _unlink_and_fsync(sibling)
        raise
    return sibling


def _restore_from_backup(destination: Path, backup: Path) -> None:
    verify_artifact(backup)
    rollback_partial = _write_unique_sibling(
        destination,
        backup.read_bytes(),
        suffix=".rollback.partial",
    )
    try:
        verify_artifact(rollback_partial)
        os.replace(rollback_partial, destination)
        _fsync_directory(destination.parent)
        verify_artifact(destination)
        backup.unlink()
        _fsync_directory(destination.parent)
    finally:
        _unlink_and_fsync(rollback_partial)


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _reject_symlink_components(path: Path) -> None:
    """Reject any existing symlink component without resolving through it."""

    current = Path(path.anchor) if path.is_absolute() else Path()
    for part in path.parts[1:] if path.is_absolute() else path.parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink path component is forbidden: {current}")


def _unlink_and_fsync(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    _fsync_directory(path.parent)


def _canonical_json(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("artifact payload must contain strict finite JSON values") from exc
    return text.encode("utf-8")


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("artifact payload must be a JSON object")
    _canonical_json(payload)
    manifest = payload.get("manifest")
    if manifest is not None:
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be a JSON object")
        for manifest_path, digest in manifest.items():
            _validate_manifest_entry(manifest_path, digest)
    source_hashes = payload.get("source_hashes")
    if source_hashes is not None:
        if not isinstance(source_hashes, dict):
            raise ValueError("source_hashes must be a JSON object")
        for source_path, digest in source_hashes.items():
            _validate_manifest_entry(source_path, digest)


def _validate_manifest_entry(path: Any, digest: Any) -> None:
    if not isinstance(path, str) or not path:
        raise ValueError("manifest path must be a nonempty relative path")
    pure_path = PurePosixPath(path)
    if pure_path.is_absolute() or ".." in pure_path.parts or "\\" in path:
        raise ValueError("manifest path must not be absolute or parent-traversing")
    if not isinstance(digest, str) or len(digest) != 64 or not _is_lower_hex(digest):
        raise ValueError("manifest digest must be a lowercase SHA256")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"JSON numeric value must be finite: {value}")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_lower_hex(value: str) -> bool:
    return all(character in "0123456789abcdef" for character in value)
