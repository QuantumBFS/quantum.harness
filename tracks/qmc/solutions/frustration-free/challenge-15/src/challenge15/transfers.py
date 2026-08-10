"""Create-only, verified transfer primitives.

Network transport is deliberately left to the audited remote wrapper.  These
functions implement the destination-side filesystem transaction and are small
enough to exercise with local mocks.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid


def file_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_tree_manifest(root: Path | str) -> dict[str, str]:
    """Hash every regular member byte in stable relative-path order."""
    base = Path(root)
    if not base.is_dir() or base.is_symlink():
        raise ValueError("transfer tree must be a regular directory")
    manifest: dict[str, str] = {}
    for path in sorted(base.rglob("*")):
        if path.is_symlink():
            raise ValueError("transfer tree symlinks are forbidden")
        if path.is_file():
            manifest[path.relative_to(base).as_posix()] = file_sha256(path)
    return manifest


def canonical_tree_sha256(root: Path | str) -> str:
    encoded = json.dumps(
        canonical_tree_manifest(root),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_sha256sums(bundle: Path | str) -> Path:
    root = Path(bundle)
    members = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink() and path.name != "SHA256SUMS"
    ]
    lines = [
        f"{file_sha256(path)}  {path.relative_to(root).as_posix()}\n"
        for path in members
    ]
    destination = root / "SHA256SUMS"
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.writelines(lines)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def verify_bundle(bundle: Path | str) -> dict[str, str]:
    root = Path(bundle)
    sums = root / "SHA256SUMS"
    if not root.is_dir() or root.is_symlink() or not sums.is_file():
        raise ValueError("bundle or SHA256SUMS is missing")
    expected: dict[str, str] = {}
    previous = ""
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if separator != "  " or len(digest) != 64 or relative <= previous:
            raise ValueError("SHA256SUMS is malformed or unsorted")
        path = root / relative
        resolved = path.resolve(strict=True)
        if root.resolve() not in resolved.parents or path.is_symlink() or not path.is_file():
            raise ValueError("SHA256SUMS member escapes bundle")
        if file_sha256(path) != digest:
            raise ValueError(f"bundle member SHA256 mismatch: {relative}")
        expected[relative] = digest
        previous = relative
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path.name != "SHA256SUMS"
    }
    if actual != set(expected):
        raise ValueError("SHA256SUMS member set mismatch")
    return expected


def verify_export_bundle(
    bundle: Path | str, exported: dict[str, object]
) -> dict[str, str]:
    root = Path(bundle)
    members = verify_bundle(root / "members")
    declared = exported.get("member_manifest")
    if declared != members:
        raise ValueError("export member manifest does not match member bytes")
    sums = root / "members" / "SHA256SUMS"
    if file_sha256(sums) != exported.get("sha256sums_sha256"):
        raise ValueError("export SHA256SUMS digest mismatch")
    encoded = json.dumps(
        members,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != exported.get("bundle_sha256"):
        raise ValueError("export canonical bundle SHA256 mismatch")
    return members


def copy_bundle_create_only(
    source: Path | str,
    destination: Path | str,
    *,
    expected_controller_root: Path | str,
) -> Path:
    source_path = Path(source)
    destination_path = Path(destination)
    controller_root = Path(expected_controller_root).resolve()
    destination_parent = destination_path.parent.resolve()
    if controller_root != destination_parent and controller_root not in destination_parent.parents:
        raise ValueError("destination is outside the approved controller root")
    if destination_path.exists() or destination_path.is_symlink():
        raise FileExistsError(destination_path)
    verify_bundle(source_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    partial = destination_path.parent / (
        f".partial.{destination_path.name}.{uuid.uuid4()}"
    )
    partial.mkdir(mode=0o700)
    try:
        for path in sorted(source_path.rglob("*")):
            relative = path.relative_to(source_path)
            target = partial / relative
            if path.is_symlink():
                raise ValueError("bundle symlinks are forbidden")
            if path.is_dir():
                target.mkdir()
            elif path.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                with path.open("rb") as reader:
                    descriptor = os.open(
                        target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400
                    )
                    with os.fdopen(descriptor, "wb") as writer:
                        shutil.copyfileobj(reader, writer)
                        writer.flush()
                        os.fsync(writer.fileno())
        verify_bundle(partial)
        os.rename(partial, destination_path)
        descriptor = os.open(destination_path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return destination_path
