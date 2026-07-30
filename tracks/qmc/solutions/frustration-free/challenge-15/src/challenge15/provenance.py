"""Current-code execution fingerprints for restart-safe artifacts."""

from __future__ import annotations

import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess
from dataclasses import dataclass
from typing import Any, Mapping

import jax


FINGERPRINT_SCHEMA = "challenge15.execution-fingerprint.v1"

SOURCE_PATTERNS = (
    "src/**/*.py",
    "production/**/*.py",
    "production/**/*.json",
    "production/**/*.sh",
    "production/**/*.sbatch",
    "production/runtime/**/*.txt",
    "production/runtime/**/*.in",
    "tests/**/*.py",
    "tests/fixtures/*.json",
    "pyproject.toml",
    "uv.lock",
)


@dataclass(frozen=True, slots=True)
class SourceManifest:
    git_revision: str
    members: Mapping[str, str]
    policy_sha256: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "git_revision": self.git_revision,
            "members": dict(self.members),
            "policy_sha256": self.policy_sha256,
        }


def build_source_manifest(
    repo_root: Path | str,
    *,
    require_clean: bool = False,
) -> SourceManifest:
    """Hash every tracked production executable/test input deterministically."""

    from .production_policy import policy_sha256

    root = Path(repo_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("source manifest root must be an existing non-symlink directory")
    revision = _git(root, "rev-parse", "HEAD").strip()
    tracked = _git(root, "ls-files", "-z", "--", *SOURCE_PATTERNS).split("\0")
    paths = sorted(path for path in tracked if path)
    if require_clean:
        changed = _git(
            root,
            "status",
            "--porcelain",
            "--untracked-files=all",
        )
        if changed:
            raise ValueError("source manifest requires a clean tracked source tree")
    members: dict[str, str] = {}
    for relative in paths:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"source manifest member is not a regular file: {relative}")
        members[Path(relative).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return SourceManifest(
        git_revision=revision,
        members=members,
        policy_sha256=policy_sha256(),
    )


def validate_source_manifest(manifest: SourceManifest, repo_root: Path | str) -> None:
    current = build_source_manifest(repo_root, require_clean=True)
    if manifest != current:
        raise ValueError("source manifest is stale or has missing/extra members")


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(f"git source-manifest query failed: {completed.stderr.strip()}")
    return completed.stdout


def execution_fingerprint() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    source_paths = [
        *sorted((root / "src" / "challenge15").glob("*.py")),
        root / "pyproject.toml",
        root / "uv.lock",
    ]
    source_hashes = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_paths
    }
    document = {
        "schema": FINGERPRINT_SCHEMA,
        "source_hashes": source_hashes,
        "runtime": {
            "python": platform.python_version(),
            **{
                package: metadata.version(package)
                for package in (
                    "jax",
                    "jaxlib",
                    "flax",
                    "optax",
                    "numpy",
                    "scipy",
                    "sympy",
                    "h5py",
                )
            },
        },
        "policy": {
            "jax_enable_x64": bool(jax.config.x64_enabled),
            "backend": jax.default_backend(),
            "platform": platform.platform(),
            "device_platforms": sorted({device.platform for device in jax.devices()}),
        },
    }
    encoded = json.dumps(
        document,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {**document, "digest": hashlib.sha256(encoded).hexdigest()}


def validate_fingerprint(
    stored: Any,
    *,
    current: dict[str, Any] | None = None,
    context: str = "artifact",
) -> None:
    if not isinstance(stored, dict):
        raise ValueError(f"{context} execution fingerprint is missing")
    candidate = dict(stored)
    digest = candidate.pop("digest", None)
    encoded = json.dumps(
        candidate,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if digest != hashlib.sha256(encoded).hexdigest():
        raise ValueError(f"{context} execution fingerprint digest is invalid")
    active = execution_fingerprint() if current is None else current
    if stored != active:
        raise ValueError(f"{context} has a stale execution fingerprint")


def _response_file_sha256(path: Path | str | None, label: str) -> str | None:
    if path is None:
        return None
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError(f"chiral response {label} must be a regular file")
    return hashlib.sha256(candidate.read_bytes()).hexdigest()


def response_provenance(
    *,
    fixture_path: Path | str,
    configuration_path: Path | str,
    oracle_artifact_path: Path | str | None = None,
    oracle_cache_path: Path | str | None = None,
    nqs_generation_path: Path | str | None = None,
    nqs_checkpoint_path: Path | str | None = None,
) -> dict[str, Any]:
    """Hash every immutable input used to produce a chiral-response artifact."""

    if (oracle_artifact_path is None) == (oracle_cache_path is None):
        raise ValueError(
            "chiral response provenance requires exactly one oracle artifact/cache"
        )
    if (nqs_generation_path is None) != (nqs_checkpoint_path is None):
        raise ValueError(
            "chiral response NQS generation/checkpoint must be supplied together"
        )
    return {
        "input_sha256": {
            "fixture": _response_file_sha256(fixture_path, "fixture"),
            "oracle_artifact": _response_file_sha256(
                oracle_artifact_path, "oracle artifact"
            ),
            "oracle_cache": _response_file_sha256(oracle_cache_path, "oracle cache"),
            "nqs_generation": _response_file_sha256(
                nqs_generation_path, "NQS generation"
            ),
            "nqs_checkpoint": _response_file_sha256(
                nqs_checkpoint_path, "NQS checkpoint"
            ),
            "configuration": _response_file_sha256(
                configuration_path, "configuration"
            ),
        },
        "execution_fingerprint": execution_fingerprint(),
    }


def validate_response_provenance(
    stored: Any,
    *,
    fixture_path: Path | str,
    configuration_path: Path | str,
    oracle_artifact_path: Path | str | None = None,
    oracle_cache_path: Path | str | None = None,
    nqs_generation_path: Path | str | None = None,
    nqs_checkpoint_path: Path | str | None = None,
) -> None:
    """Rehash response inputs and reject stale code or substituted bytes."""

    if not isinstance(stored, Mapping) or set(stored) != {
        "input_sha256",
        "execution_fingerprint",
    }:
        raise ValueError("chiral response provenance fields mismatch")
    current = response_provenance(
        fixture_path=fixture_path,
        configuration_path=configuration_path,
        oracle_artifact_path=oracle_artifact_path,
        oracle_cache_path=oracle_cache_path,
        nqs_generation_path=nqs_generation_path,
        nqs_checkpoint_path=nqs_checkpoint_path,
    )
    if stored.get("input_sha256") != current["input_sha256"]:
        raise ValueError("chiral response provenance input bytes mismatch")
    validate_fingerprint(
        stored.get("execution_fingerprint"),
        current=current["execution_fingerprint"],
        context="chiral response provenance",
    )
