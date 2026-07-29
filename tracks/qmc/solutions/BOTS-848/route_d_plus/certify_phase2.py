#!/usr/bin/env python3
"""Produce the Route D+ Phase 2 one-particle LLL certificate."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Sequence

import jsonschema
import numpy as np
import scipy

from route_d_plus.lll import (
    monopole_orbitals,
    orbital_overlap_matrix,
    reconstruct_lll,
    reproducing_kernel,
    sphere_quadrature,
    spinor,
)

SCHEMA_VERSION = "challenge-15-route-d-plus-phase2-v1"
PHASE1_SCHEMA_VERSION = "challenge-15-route-d-plus-environment-v1"
RECONSTRUCTION_TOLERANCE = 1.0e-12


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def require_phase1_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": PHASE1_SCHEMA_VERSION,
        "python_version": "3.11.15",
        "jax_version": "0.4.38",
        "jaxlib_version": "0.4.38",
        "jax_enable_x64": True,
        "requested_platform": "gpu",
        "git_dirty": False,
    }
    mismatches = {
        key: (manifest.get(key), value)
        for key, value in expected.items()
        if manifest.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"Phase 1 manifest mismatch: {mismatches}")
    if "gpu" not in manifest.get("device_platforms", []):
        raise RuntimeError("Phase 1 manifest does not certify a GPU device")
    return manifest


def collect_certificate(
    *,
    repo_root: Path,
    phase1_manifest_path: Path,
    two_q: int,
    n_theta: int | None,
    n_phi: int | None,
) -> dict[str, Any]:
    phase1_manifest = require_phase1_manifest(phase1_manifest_path)
    commit = git_output(repo_root, "rev-parse", "HEAD")
    dirty = bool(git_output(repo_root, "status", "--porcelain"))
    if len(commit) != 40 or dirty:
        raise RuntimeError("Phase 2 requires a clean committed source revision")

    grid = sphere_quadrature(
        two_q,
        n_theta=n_theta,
        n_phi=n_phi,
    )
    spinor_norm_error = float(
        np.max(np.abs(np.abs(grid.u) ** 2 + np.abs(grid.v) ** 2 - 1.0))
    )

    overlap = orbital_overlap_matrix(two_q, grid)
    overlap_error = float(
        np.max(np.abs(overlap - np.eye(two_q + 1, dtype=np.complex128)))
    )

    target_theta = np.array(
        [0.07, 0.51, 1.02, 1.68, 2.49, 3.03],
        dtype=np.float64,
    )
    target_phi = np.array(
        [5.91, 0.33, 2.72, 4.81, 1.39, 3.57],
        dtype=np.float64,
    )
    target_u, target_v = spinor(target_theta, target_phi)
    target_orbitals = monopole_orbitals(two_q, target_u, target_v)
    source_orbitals = monopole_orbitals(two_q, grid.u, grid.v)

    closed_kernel = reproducing_kernel(
        two_q,
        target_u[:, None],
        target_v[:, None],
        grid.u[None, :],
        grid.v[None, :],
    )
    orbital_sum_kernel = target_orbitals @ source_orbitals.conj().T
    kernel_sum_error = float(
        np.max(np.abs(closed_kernel - orbital_sum_kernel))
    )

    rng = np.random.default_rng(848)
    coefficients = rng.normal(size=two_q + 1) + 1.0j * rng.normal(
        size=two_q + 1
    )
    sampled_values = source_orbitals @ coefficients
    expected_values = target_orbitals @ coefficients
    reconstructed_values = reconstruct_lll(
        two_q,
        grid,
        sampled_values,
        target_u,
        target_v,
    )
    reconstruction_error = float(
        np.max(np.abs(reconstructed_values - expected_values))
    )

    errors = {
        "spinor_norm": spinor_norm_error,
        "orbital_overlap": overlap_error,
        "kernel_orbital_sum": kernel_sum_error,
        "orbital_reconstruction": reconstruction_error,
    }
    passed = all(error < RECONSTRUCTION_TOLERANCE for error in errors.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "two_q": two_q,
        "orbital_count": two_q + 1,
        "quadrature": {
            "kind": "gauss-legendre-x-uniform-fourier",
            "n_theta": grid.n_theta,
            "n_phi": grid.n_phi,
            "point_count": grid.size,
        },
        "tolerance": RECONSTRUCTION_TOLERANCE,
        "max_errors": errors,
        "passed": passed,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "git_commit": commit,
        "git_dirty": dirty,
        "hostname": platform.node(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_cluster_name": os.environ.get("SLURM_CLUSTER_NAME"),
        "phase1_manifest_path": str(phase1_manifest_path.resolve()),
        "phase1_manifest_sha256": sha256_file(phase1_manifest_path),
        "phase1_git_commit": phase1_manifest["git_commit"],
    }


def validate_certificate(payload: dict[str, Any]) -> None:
    schema_path = Path(__file__).with_name("phase2.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    validator.validate(payload)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--phase1-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--two-q", type=int, default=15)
    parser.add_argument("--n-theta", type=int)
    parser.add_argument("--n-phi", type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = collect_certificate(
        repo_root=args.repo_root.resolve(),
        phase1_manifest_path=args.phase1_manifest.resolve(),
        two_q=args.two_q,
        n_theta=args.n_theta,
        n_phi=args.n_phi,
    )
    validate_certificate(payload)
    write_json_atomic(args.output.resolve(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
