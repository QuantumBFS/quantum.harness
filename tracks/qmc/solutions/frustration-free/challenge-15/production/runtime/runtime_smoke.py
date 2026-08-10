#!/usr/bin/env python3
"""Local candidate-runtime fingerprinting; this does not issue an attestation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

import jax
import jax.numpy as jnp


_EXPECTED = {
    "jax": "0.4.38",
    "jaxlib": "0.4.38",
    "flax": "0.10.2",
    "optax": "0.2.4",
    "numpy": "1.26.4",
    "scipy": "1.12.0",
    "sympy": "1.13.3",
    "h5py": "3.10.0",
    "pytest": "8.3.4",
}


class RuntimeSmoke:
    __slots__ = (
        "profile",
        "backend",
        "python_version",
        "python_abi",
        "minimum_glibc",
        "x64_enabled",
        "device_platforms",
        "packages",
        "source_manifest_sha256",
    )

    def __init__(
        self,
        *,
        profile: str,
        backend: str,
        device_platforms: tuple[str, ...],
        packages: dict[str, str],
        source_manifest_sha256: str | None,
    ) -> None:
        self.profile = profile
        self.backend = backend
        self.python_version = platform.python_version()
        self.python_abi = "cp312"
        self.minimum_glibc = "2.17"
        self.x64_enabled = bool(jax.config.x64_enabled)
        self.device_platforms = device_platforms
        self.packages = packages
        self.source_manifest_sha256 = source_manifest_sha256

    def to_json(self) -> str:
        return json.dumps(
            {
                "kind": "candidate-runtime-smoke",
                "profile": self.profile,
                "backend": self.backend,
                "python_version": self.python_version,
                "python_abi": self.python_abi,
                "minimum_glibc": self.minimum_glibc,
                "x64_enabled": self.x64_enabled,
                "device_platforms": list(self.device_platforms),
                "packages": self.packages,
                "source_manifest_sha256": self.source_manifest_sha256,
                "status": "CANDIDATE_OK",
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def validate_profile_devices(
    profile: str,
    expected_backend: str,
    reported_backend: str,
    reported_platforms: tuple[str, ...],
) -> None:
    if profile not in {"cpu", "cuda12"}:
        raise ValueError(f"unknown candidate profile: {profile}")
    if expected_backend not in {"cpu", "gpu"}:
        raise ValueError(f"unsupported expected backend: {expected_backend}")
    required_backend = {"cpu": "cpu", "cuda12": "gpu"}[profile]
    if expected_backend != required_backend:
        raise RuntimeError(
            f"{profile} profile requires expected backend {required_backend}, "
            f"got {expected_backend}"
        )
    if reported_backend != expected_backend:
        raise RuntimeError(
            f"expected JAX backend {expected_backend}, got reported backend "
            f"{reported_backend}"
        )
    platforms = set(reported_platforms)
    if not platforms:
        raise RuntimeError("JAX reported no devices")
    if profile == "cpu" and platforms != {"cpu"}:
        raise RuntimeError(
            f"cpu profile requires only CPU devices, got {sorted(platforms)!r}"
        )
    if profile == "cuda12" and "gpu" not in platforms:
        raise RuntimeError(
            f"cuda12 profile requires a reported GPU device, got "
            f"{sorted(platforms)!r}"
        )


def runtime_smoke(
    profile: str, expected_backend: str, source_manifest: Path | None
) -> RuntimeSmoke:
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(f"candidate runtime requires CPython 3.12, got {sys.version}")

    jax.config.update("jax_enable_x64", True)
    packages = {
        name: importlib.metadata.version(name)
        for name in _EXPECTED
    }
    mismatches = {
        name: (version, _EXPECTED[name])
        for name, version in packages.items()
        if version != _EXPECTED[name]
    }
    if mismatches:
        raise RuntimeError(f"candidate package version mismatch: {mismatches}")

    backend = jax.default_backend()
    device_platforms = tuple(
        sorted({device.platform for device in jax.devices()})
    )
    validate_profile_devices(profile, expected_backend, backend, device_platforms)
    if not jax.config.x64_enabled:
        raise RuntimeError("JAX x64 mode is not enabled")
    compiled = jax.jit(lambda value: value * (1.0 + 2.0j))(
        jnp.asarray(3.0 - 1.0j, dtype=jnp.complex128)
    )
    if compiled.dtype != jnp.complex128 or not bool(jnp.isfinite(compiled)):
        raise RuntimeError("JIT complex128 smoke failed")

    source_hash = None
    if source_manifest is not None:
        if not source_manifest.is_file():
            raise ValueError(f"source manifest is not a file: {source_manifest}")
        with source_manifest.open("rb") as manifest_file:
            source_hash = hashlib.file_digest(manifest_file, "sha256").hexdigest()
    return RuntimeSmoke(
        profile=profile,
        backend=backend,
        device_platforms=device_platforms,
        packages=packages,
        source_manifest_sha256=source_hash,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("cpu", "cuda12"), required=True)
    parser.add_argument("--expected-backend", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--source-manifest", type=Path)
    args = parser.parse_args()
    print(
        runtime_smoke(
            args.profile, args.expected_backend, args.source_manifest
        ).to_json()
    )
    print("CANDIDATE_OK")


if __name__ == "__main__":
    main()
