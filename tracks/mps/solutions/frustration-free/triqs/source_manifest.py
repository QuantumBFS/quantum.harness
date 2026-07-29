"""Complete transitive source inventory for Challenge 81 CT-HYB."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import re

from artifacts import sha256_file


_TRIQS = "tracks/mps/solutions/frustration-free/triqs"
_SOLUTION = "tracks/mps/solutions/frustration-free"
REQUIRED_SOURCE_PATHS = (
    f"{_TRIQS}/artifacts.py",
    f"{_TRIQS}/make_input.py",
    f"{_TRIQS}/hybridization.py",
    f"{_TRIQS}/source_manifest.py",
    f"{_TRIQS}/run_chain.py",
    f"{_TRIQS}/calibrate.py",
    f"{_TRIQS}/reduce.py",
    f"{_TRIQS}/publication.py",
    f"{_TRIQS}/validate_existing.py",
    f"{_TRIQS}/compare_mps.py",
    f"{_TRIQS}/cthyb_slurm_array.sh",
    f"{_TRIQS}/cthyb_calibration_slurm_array.sh",
    f"{_TRIQS}/cthyb-production-input.schema.json",
    f"{_TRIQS}/cthyb-chain.schema.json",
    f"{_TRIQS}/cthyb-summary.schema.json",
    f"{_TRIQS}/smoke_test.py",
    f"{_SOLUTION}/model.json",
    f"{_TRIQS}/environment.yml",
    f"{_TRIQS}/conda-linux-64.lock",
    f"{_TRIQS}/cthyb-production.schema.json",
    f"{_SOLUTION}/bath.py",
    f"{_SOLUTION}/chain_mapping.py",
    f"{_SOLUTION}/finite_bath_ed.py",
    f"{_SOLUTION}/acceptance.py",
    f"{_SOLUTION}/convergence.py",
    f"{_SOLUTION}/convergence.schema.json",
    f"{_TRIQS}/tests/test_lock.py",
    f"{_SOLUTION}/julia/Project.toml",
    f"{_SOLUTION}/julia/Manifest.toml",
    f"{_SOLUTION}/julia/finite_bath_mps_runner.jl",
    f"{_SOLUTION}/julia/finite_bath_checkpoint.jl",
    f"{_SOLUTION}/julia/finite_bath_purification.jl",
    f"{_SOLUTION}/julia/finite_bath_observables.jl",
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _safe_repository_path(repository_root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or str(pure) != relative:
        raise ValueError(f"invalid repository-relative source path: {relative}")
    return repository_root / Path(*pure.parts)


def build_source_manifest(repository_root: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for relative in REQUIRED_SOURCE_PATHS:
        path = _safe_repository_path(repository_root, relative)
        if not path.exists():
            raise FileNotFoundError(f"required source is absent: {relative}")
        manifest[relative] = sha256_file(path)
    return manifest


def verify_source_manifest(manifest: object, repository_root: Path) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("source manifest must be an object")
    if set(manifest) != set(REQUIRED_SOURCE_PATHS):
        missing = sorted(set(REQUIRED_SOURCE_PATHS) - set(manifest))
        extra = sorted(set(manifest) - set(REQUIRED_SOURCE_PATHS))
        raise ValueError(f"source manifest inventory mismatch: missing={missing}, extra={extra}")
    for path, digest in manifest.items():
        if not isinstance(path, str) or not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ValueError("source manifest contains an invalid path or hash")
    current = build_source_manifest(repository_root)
    if manifest != current:
        changed = sorted(path for path in manifest if manifest[path] != current[path])
        raise ValueError(f"source hash mismatch: {changed}")
