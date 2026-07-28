from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

import numba


_CAPABILITY_KEYS = {
    "schema_version",
    "python",
    "implementation",
    "platform",
    "machine",
    "numpy",
    "scipy",
    "h5py",
    "numba",
    "llvmlite",
    "cpu_name",
    "cpu_features",
    "threading_layer",
    "numba_disable_jit",
    "fastmath",
    "boundscheck",
}


def runtime_capability() -> dict[str, object]:
    return {
        "schema_version": "challenge-194-runtime-v1",
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "h5py": importlib.metadata.version("h5py"),
        "numba": importlib.metadata.version("numba"),
        "llvmlite": importlib.metadata.version("llvmlite"),
        "cpu_name": numba.config.CPU_NAME or "",
        "cpu_features": numba.config.CPU_FEATURES or "",
        "threading_layer": os.environ.get("NUMBA_THREADING_LAYER", ""),
        "numba_disable_jit": bool(numba.config.DISABLE_JIT),
        "fastmath": False,
        "boundscheck": True,
    }


def _git_output(repository_root: Path, *arguments: str) -> str:
    command = ["git", *arguments]
    operation = "git " + " ".join(arguments)
    try:
        completed = subprocess.run(
            command,
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        message = f"{operation} failed"
        if detail:
            message += f": {detail}"
        raise RuntimeError(message) from error
    except OSError as error:
        raise RuntimeError(f"unable to execute {operation}: {error}") from error
    return completed.stdout.strip()


def _canonical_capability_bytes() -> bytes:
    capability = runtime_capability()
    if not isinstance(capability, dict) or set(capability) != _CAPABILITY_KEYS:
        raise RuntimeError("runtime capability is not canonical JSON")
    try:
        encoded = json.dumps(
            capability,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        decoded = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("runtime capability is not canonical JSON") from error
    if decoded != capability:
        raise RuntimeError("runtime capability is not canonical JSON")
    return encoded


def runtime_provenance(repository_root: Path) -> dict[str, str]:
    lockfile = repository_root / "uv.lock"
    if lockfile.is_symlink() or not lockfile.is_file():
        raise RuntimeError("uv.lock must be a regular non-symlink file")
    try:
        lock_bytes = lockfile.read_bytes()
    except OSError as error:
        raise RuntimeError(f"unable to read uv.lock: {error}") from error

    if _git_output(repository_root, "status", "--porcelain"):
        raise RuntimeError("repository is dirty")
    revision = _git_output(repository_root, "rev-parse", "HEAD")
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise RuntimeError("malformed Git revision")

    capability_bytes = _canonical_capability_bytes()
    return {
        "schema_version": "challenge-194-runtime-provenance-v1",
        "source_revision": revision,
        "uv_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "runtime_capability_sha256": hashlib.sha256(
            capability_bytes
        ).hexdigest(),
    }
