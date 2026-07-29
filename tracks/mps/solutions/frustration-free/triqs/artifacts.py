"""Strict canonical JSON and atomic artifact primitives."""

from __future__ import annotations

import errno
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import stat
from typing import Any


def canonical_json(value: object) -> bytes:
    """Return compact, sorted UTF-8 JSON bytes without a trailing newline."""
    try:
        text = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except ValueError as error:
        raise ValueError("canonical JSON requires finite numbers") from error
    return text.encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = sha256()
    descriptor = _open_regular_file(path)
    try:
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def strict_json_load(path: Path) -> object:
    try:
        text = _read_regular_file(path).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"JSON is not UTF-8: {path}") from error
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_pairs,
        parse_constant=_reject_constant,
    )


def _directory_descriptor(path: Path, *, create: bool = False) -> int:
    absolute = path.absolute()
    descriptor = os.open(
        "/",
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
    )
    try:
        for component in absolute.parts[1:]:
            try:
                child = os.open(
                    component,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(component, mode=0o700, dir_fd=descriptor)
                os.fsync(descriptor)
                child = os.open(
                    component,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_regular_at(directory_descriptor: int, name: str, path: Path) -> int:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_descriptor,
        )
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise ValueError(f"symlink is forbidden: {path}") from error
        raise
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"regular file required: {path}")
    return descriptor


def _open_regular_file(path: Path) -> int:
    directory_descriptor = _directory_descriptor(path.parent)
    try:
        return _open_regular_at(directory_descriptor, path.name, path)
    finally:
        os.close(directory_descriptor)


def _read_regular_at(directory_descriptor: int, name: str, path: Path) -> bytes:
    descriptor = _open_regular_at(directory_descriptor, name, path)
    chunks: list[bytes] = []
    try:
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    return b"".join(chunks)


def _read_regular_file(path: Path) -> bytes:
    directory_descriptor = _directory_descriptor(path.parent)
    try:
        return _read_regular_at(directory_descriptor, path.name, path)
    finally:
        os.close(directory_descriptor)


def _write_all(descriptor: int, value: bytes) -> None:
    view = memoryview(value)
    while view:
        written = os.write(descriptor, view)
        view = view[written:]


def atomic_write_bytes(path: Path, value: bytes) -> None:
    """Durably publish bytes once; identical content is reusable."""
    directory_descriptor = _directory_descriptor(path.parent, create=True)
    lock_name = f".{path.name}.lock"
    temporary_name: str | None = None
    lock_descriptor = -1
    try:
        try:
            lock_descriptor = os.open(
                lock_name,
                os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_descriptor,
            )
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise ValueError(f"symlink lock is forbidden: {path}") from error
            raise
        if not stat.S_ISREG(os.fstat(lock_descriptor).st_mode):
            raise ValueError(f"regular lock file required: {path}")
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)

        try:
            existing = _read_regular_at(directory_descriptor, path.name, path)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing == value:
                return
            raise FileExistsError(f"existing artifact has different content: {path}")

        for _ in range(100):
            candidate = f".{path.name}.{secrets.token_hex(16)}.tmp"
            try:
                temporary_descriptor = os.open(
                    candidate,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=directory_descriptor,
                )
            except FileExistsError:
                continue
            temporary_name = candidate
            break
        else:
            raise FileExistsError(f"cannot allocate staging file for: {path}")

        try:
            _write_all(temporary_descriptor, value)
            os.fsync(temporary_descriptor)
        finally:
            os.close(temporary_descriptor)

        try:
            os.link(
                temporary_name,
                path.name,
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except FileExistsError:
            existing = _read_regular_at(directory_descriptor, path.name, path)
            if existing != value:
                raise FileExistsError(
                    f"concurrent artifact has different content: {path}"
                )
        os.fsync(directory_descriptor)
    except BaseException:
        raise
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=directory_descriptor)
                os.fsync(directory_descriptor)
            except FileNotFoundError:
                pass
        if lock_descriptor >= 0:
            os.close(lock_descriptor)
        os.close(directory_descriptor)
