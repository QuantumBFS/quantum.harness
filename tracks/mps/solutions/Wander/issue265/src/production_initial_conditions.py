"""Production-only initial profiles and immutable source-closure checks."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .production_v2_manifest import (
    BASE_BACKEND_SHA256,
    BASE_MANIFEST_SHA256,
    BASE_RUNNER_SHA256,
    sha256_file,
)
from .tenpy_research_backend import (
    condition_initial_magnetization as _base_initial,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CLOSURE_PATHS = (
    "scripts/run_tenpy_production_job.py",
    "src/production_initial_conditions.py",
    "scripts/run_tenpy_research_job.py",
    "src/tenpy_research_backend.py",
    "src/research_dataset.py",
    "src/research_protocol.py",
    "results_research_program/production_manifest_v2.json",
)


def production_initial_magnetization(
    x: np.ndarray,
    condition: Mapping[str, Any],
) -> np.ndarray:
    """Return the exact uniform-zero state or delegate to the frozen backend."""

    x = np.asarray(x, dtype=float)
    if str(condition.get("profile")) != "uniform_zero":
        return _base_initial(x, condition)
    if abs(float(condition.get("background_m", 0.0))) > 1e-15:
        raise ValueError("uniform_zero requires exactly zero background_m")
    if str(condition.get("temperature")) != "infinite":
        raise ValueError("uniform_zero is registered only at infinite temperature")
    return np.zeros_like(x)


def production_source_closure(root: str | Path = ROOT) -> dict[str, Any]:
    """Hash the complete production wrapper source closure."""

    root_path = Path(root)
    files: dict[str, str] = {}
    for relative in SOURCE_CLOSURE_PATHS:
        path = root_path / relative
        if not path.is_file():
            raise FileNotFoundError(f"production source closure is missing {relative}")
        files[relative] = sha256_file(path)
    payload = "\n".join(f"{key}:{files[key]}" for key in sorted(files)).encode()
    closure_hash = hashlib.sha256(payload).hexdigest()
    frozen = {
        "scripts/run_tenpy_research_job.py": BASE_RUNNER_SHA256,
        "src/tenpy_research_backend.py": BASE_BACKEND_SHA256,
        "results_research_program/manifest.json": BASE_MANIFEST_SHA256,
    }
    actual_frozen = {
        "scripts/run_tenpy_research_job.py": files[
            "scripts/run_tenpy_research_job.py"
        ],
        "src/tenpy_research_backend.py": files["src/tenpy_research_backend.py"],
        "results_research_program/manifest.json": sha256_file(
            root_path / "results_research_program" / "manifest.json"
        ),
    }
    if actual_frozen != frozen:
        raise RuntimeError("immutable convergence source hashes changed")
    return {
        "schema_version": 1,
        "files": files,
        "source_closure_sha256": closure_hash,
        "immutable_convergence_hashes": actual_frozen,
        "valid": True,
    }
