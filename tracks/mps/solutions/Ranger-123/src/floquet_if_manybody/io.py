"""Result serialization and provenance."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np

from . import __version__


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write_result(path: Path, payload: dict[str, Any]) -> None:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    envelope = {
        "schema_version": 1,
        "config_hash": hashlib.sha256(canonical.encode()).hexdigest()[:16],
        "created_utc": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "package": __version__,
            "git_commit": _git_commit(),
        },
        **payload,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")


def read_result(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "config_hash",
        "created_utc",
        "environment",
        "method",
        "converged",
        "diagnostics",
        "data",
    }
    missing = required - set(result)
    if missing:
        raise ValueError(f"{path} is missing keys: {sorted(missing)}")
    return cast(dict[str, Any], result)
