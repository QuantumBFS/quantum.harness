from __future__ import annotations

import importlib.metadata
import os
import platform
import sys

import numba


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
