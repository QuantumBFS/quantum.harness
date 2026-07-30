"""Environment policy for isolated JAX worker processes."""

from __future__ import annotations

import os


def worker_environment() -> dict[str, str]:
    """Return an inherited environment with exact-safe matmul precision."""

    environment = dict(os.environ)
    environment.setdefault(
        "JAX_DEFAULT_MATMUL_PRECISION",
        "highest",
    )
    return environment
