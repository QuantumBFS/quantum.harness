"""Machine-readable provenance for reproducible chiral-graviton runs.

The collector deliberately has no dependency on the numerical implementation.  It
can therefore be called before an expensive calculation starts and its output can
be embedded verbatim in a result JSON document.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from . import __version__


_SCHEMA_VERSION = 1
_DEPENDENCIES = ("numpy", "scipy", "sympy")


def _json_snapshot(value: Mapping[str, Any], *, field: str) -> dict[str, Any]:
    """Return a detached, finite, JSON-compatible copy of a mapping."""

    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be a mapping")
    try:
        encoded = json.dumps(value, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must contain only finite JSON values") from error
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):  # Defensive: Mapping should always encode to an object.
        raise ValueError(f"{field} must encode to a JSON object")
    return decoded


def _distribution_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution in _DEPENDENCIES:
        try:
            versions[distribution] = version(distribution)
        except PackageNotFoundError:
            versions[distribution] = "not-installed"
    return versions


def _discover_repository() -> Path | None:
    """Find a checkout without assuming that the package is run from its root."""

    starts = (Path.cwd().resolve(), Path(__file__).resolve().parent)
    seen: set[Path] = set()
    for start in starts:
        for candidate in (start, *start.parents):
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / ".git").exists():
                return candidate
    return None


def _run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repository}",
            "-C",
            str(repository),
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    return completed.stdout.strip()


def _git_metadata(repository: str | Path | None) -> dict[str, Any]:
    checkout = Path(repository).expanduser().resolve() if repository is not None else None
    checkout = checkout or _discover_repository()
    if checkout is None:
        return {
            "available": False,
            "commit": None,
            "dirty": None,
            "root": None,
            "error": "repository not found",
        }

    try:
        root = _run_git(checkout, "rev-parse", "--show-toplevel")
        commit = _run_git(checkout, "rev-parse", "HEAD")
        branch = _run_git(checkout, "rev-parse", "--abbrev-ref", "HEAD")
        status = _run_git(checkout, "status", "--porcelain", "--untracked-files=normal")
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        return {
            "available": False,
            "commit": None,
            "dirty": None,
            "root": str(checkout),
            "error": type(error).__name__,
        }

    return {
        "available": True,
        "commit": commit,
        "dirty": bool(status),
        "branch": branch,
        "root": root,
    }


def collect_provenance(
    run_config: Mapping[str, Any],
    tolerances: Mapping[str, Any],
    *,
    repository: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Capture the environment and numerical contract for one calculation.

    ``run_config`` should include all physics and optimizer inputs (including the
    seed and iteration limit). ``tolerances`` is separate so acceptance thresholds
    remain distinguishable from model inputs in archived result files.
    """

    if now is None:
        local_time = datetime.now().astimezone()
    else:
        if now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        local_time = now
    utc_time = local_time.astimezone(timezone.utc)

    return {
        "schema_version": _SCHEMA_VERSION,
        "timestamps": {
            "utc": utc_time.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "local": local_time.isoformat(timespec="microseconds"),
        },
        "software": {
            "chiral_graviton": __version__,
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "compiler": platform.python_compiler(),
                "executable": sys.executable,
            },
            "dependencies": _distribution_versions(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "git": _git_metadata(repository),
        "run_config": _json_snapshot(run_config, field="run_config"),
        "tolerances": _json_snapshot(tolerances, field="tolerances"),
    }
