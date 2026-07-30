"""Deterministic hashes and atomic artifact writes for Issue #28 runs."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np


def canonical_json_bytes(value: object) -> bytes:
    """Serialize JSON deterministically, including a final newline."""
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def atomic_write_json(path: str | Path, value: object) -> None:
    _atomic_bytes(Path(path), canonical_json_bytes(value))


def atomic_write_npz(
    path: str | Path,
    arrays: Mapping[str, np.ndarray],
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized: dict[str, np.ndarray] = {}
    for name, value in arrays.items():
        array = np.asarray(value)
        if array.dtype.hasobject:
            raise ValueError(f"array {name!r} has object dtype")
        normalized[str(name)] = array

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".npz",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            np.savez_compressed(handle, **normalized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def verified_promote_directory(
    staging: str | Path,
    final: str | Path,
    expected: Mapping[str, str],
) -> None:
    """Atomically promote a staging directory after verifying every hash."""
    staging_path = Path(staging)
    final_path = Path(final)
    if not staging_path.is_dir():
        raise FileNotFoundError(f"staging directory does not exist: {staging_path}")
    if final_path.exists():
        if not final_path.is_dir() or any(final_path.iterdir()):
            raise FileExistsError(f"refusing to replace nonempty destination: {final_path}")

    for relative, expected_hash in expected.items():
        candidate = staging_path / relative
        if not candidate.is_file():
            raise FileNotFoundError(f"staged artifact is missing: {candidate}")
        actual_hash = sha256_file(candidate)
        if actual_hash != expected_hash:
            raise ValueError(
                f"hash mismatch for {relative}: expected {expected_hash}, got {actual_hash}"
            )

    final_path.parent.mkdir(parents=True, exist_ok=True)
    if final_path.exists():
        final_path.rmdir()
    os.replace(staging_path, final_path)
