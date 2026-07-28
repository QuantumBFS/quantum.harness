"""Atomic PEPO validation records and reproducibility identifiers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
from typing import Any


_CORE_SOURCE_PATHS = tuple(
    sorted(
        (
            "pepo/uv.lock",
            "pepo/src/ole_pepo/qasm.py",
            "pepo/src/ole_pepo/gates.py",
            "pepo/src/ole_pepo/exact.py",
            "pepo/src/ole_pepo/engine.py",
            "pepo/src/ole_pepo/contraction.py",
        )
    )
)


@dataclass(frozen=True, slots=True)
class SmallOracleStatus:
    success: bool
    qasm_sha256: str
    quimb_commit: str
    core_source_digest: str
    dense_delta_zero: float
    pepo_delta_zero: float
    dense_delta_015: float
    pepo_delta_015: float
    max_absolute_error: float


def atomic_write_json(path: str | Path, document: Any) -> None:
    """Write JSON via a synced sibling temporary file and atomic replacement."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)


def confirmation_token(document: Any) -> str:
    """Return the short stable SHA-256 confirmation token for a JSON document."""
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def core_source_digest(ole_root: str | Path) -> str:
    """Hash the fixed numerical core, excluding CLI and report-only changes."""
    root = Path(ole_root)
    digest = hashlib.sha256()
    for relative_path in _CORE_SOURCE_PATHS:
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / relative_path).read_bytes())
    return digest.hexdigest()


def peak_rss_bytes() -> int:
    """Return peak RSS in bytes (Linux ru_maxrss is KiB; macOS is already bytes)."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)
