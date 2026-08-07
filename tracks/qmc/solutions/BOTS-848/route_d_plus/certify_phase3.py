"""Produce the Route D+ Phase 3 projected tensor algebra certificate."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np

from route_d_plus.lll import monopole_orbitals, sphere_quadrature, spinor
from route_d_plus.tensor import (
    apply_one_body_tensor,
    canonical_tensor,
    one_body_tensor_kernel,
    quadrature_reconstruction_error,
    rotation_matrix,
)

SCHEMA_VERSION = "challenge-15-route-d-plus-phase3-v1"
PHASE2_SCHEMA_VERSION = "challenge-15-route-d-plus-phase2-v1"
TOLERANCES = {
    "hilbert_schmidt": 1.0e-12,
    "hermiticity": 1.0e-12,
    "finite_rotation": 1.0e-6,
    "quadrature_reconstruction": 1.0e-12,
    "one_body_kernel": 1.0e-12,
    "one_body_action": 1.0e-12,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        capture_output=True,
        check=True,
        cwd=repo_root,
        text=True,
    )
    return completed.stdout.strip()


def require_phase2_certificate(path: Path) -> dict[str, Any]:
    certificate = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": PHASE2_SCHEMA_VERSION,
        "two_q": 15,
        "orbital_count": 16,
        "passed": True,
        "git_dirty": False,
    }
    mismatches = {
        key: (certificate.get(key), value)
        for key, value in expected.items()
        if certificate.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"Phase 2 certificate mismatch: {mismatches}")
    return certificate


def collect_certificate(
    *,
    repo_root: Path,
    phase2_certificate_path: Path,
    two_q: int,
) -> dict[str, Any]:
    phase2_certificate = require_phase2_certificate(phase2_certificate_path)
    commit = git_output(repo_root, "rev-parse", "HEAD")
    dirty = bool(git_output(repo_root, "status", "--porcelain"))
    if len(commit) != 40 or dirty:
        raise RuntimeError("Phase 3 requires a clean committed source revision")

    tensor_labels = [
        (ell, m)
        for ell in range(two_q + 1)
        for m in range(-ell, ell + 1)
    ]
    tensors = [
        canonical_tensor(two_q, ell, m) for ell, m in tensor_labels
    ]
    flattened = np.stack([tensor.reshape(-1) for tensor in tensors])
    gram = flattened.conj() @ flattened.T
    hilbert_schmidt_error = float(
        np.max(np.abs(gram - np.eye(len(tensors))))
    )
    hermiticity_error = max(
        float(
            np.max(
                np.abs(
                    tensor.conj().T
                    - ((-1) ** m) * canonical_tensor(two_q, ell, -m)
                )
            )
        )
        for (ell, m), tensor in zip(tensor_labels, tensors, strict=True)
    )

    rotation_vector = np.array([0.31, -0.27, 0.19])
    single_particle_rotation = rotation_matrix(two_q, rotation_vector)
    finite_rotation_error = 0.0
    for ell in range(two_q + 1):
        tensor_rotation = rotation_matrix(2 * ell, rotation_vector)
        multiplet = [
            canonical_tensor(two_q, ell, m)
            for m in range(-ell, ell + 1)
        ]
        for column, tensor in enumerate(multiplet):
            rotated = (
                single_particle_rotation
                @ tensor
                @ single_particle_rotation.conj().T
            )
            expected = sum(
                tensor_rotation[row, column] * component
                for row, component in enumerate(multiplet)
            )
            finite_rotation_error = max(
                finite_rotation_error,
                float(np.max(np.abs(rotated - expected))),
            )

    grid = sphere_quadrature(two_q)
    reconstruction_error = quadrature_reconstruction_error(two_q, grid)
    target_u, target_v = spinor(
        np.array([0.23, 1.41, 2.77]),
        np.array([0.71, 3.19, 5.41]),
    )
    source_u, source_v = spinor(
        np.array([0.62, 1.88, 2.31]),
        np.array([5.73, 0.37, 2.22]),
    )
    probe_tensor = canonical_tensor(two_q, 4, -2)
    target_orbitals = monopole_orbitals(two_q, target_u, target_v)
    source_orbitals = monopole_orbitals(two_q, source_u, source_v)
    explicit_kernel = np.einsum(
        "pa,ab,pb->p",
        target_orbitals,
        probe_tensor,
        source_orbitals.conj(),
    )
    kernel_error = float(
        np.max(
            np.abs(
                one_body_tensor_kernel(
                    two_q,
                    probe_tensor,
                    target_u,
                    target_v,
                    source_u,
                    source_v,
                )
                - explicit_kernel
            )
        )
    )

    action_target_u, action_target_v = spinor(1.13, 2.71)
    action_spinors = np.array(
        [[action_target_u, action_target_v]],
        dtype=np.complex128,
    )
    coefficients = np.arange(1, two_q + 2, dtype=np.float64)
    coefficients = coefficients + 0.25j * coefficients[::-1]
    action_tensor = canonical_tensor(two_q, 2, 1)

    def psi_fn(particle_spinors: np.ndarray) -> complex:
        orbitals = monopole_orbitals(
            two_q,
            particle_spinors[0, 0],
            particle_spinors[0, 1],
        )
        return complex(orbitals @ coefficients)

    expected_action = monopole_orbitals(
        two_q,
        action_target_u,
        action_target_v,
    ) @ (action_tensor @ coefficients)
    actual_action = apply_one_body_tensor(
        psi_fn,
        action_spinors,
        0,
        action_tensor,
        grid,
    )
    action_error = float(abs(actual_action - expected_action))
    errors = {
        "hilbert_schmidt": hilbert_schmidt_error,
        "hermiticity": hermiticity_error,
        "finite_rotation": finite_rotation_error,
        "quadrature_reconstruction": reconstruction_error,
        "one_body_kernel": kernel_error,
        "one_body_action": action_error,
    }
    passed = all(
        errors[name] < tolerance for name, tolerance in TOLERANCES.items()
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "two_q": two_q,
        "tensor_count": len(tensors),
        "tolerances": TOLERANCES,
        "max_errors": errors,
        "passed": passed,
        "git_commit": commit,
        "git_dirty": dirty,
        "hostname": platform.node(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_cluster_name": os.environ.get("SLURM_CLUSTER_NAME"),
        "phase2_certificate_path": str(phase2_certificate_path.resolve()),
        "phase2_certificate_sha256": sha256_file(phase2_certificate_path),
        "phase2_git_commit": phase2_certificate["git_commit"],
    }


def validate_certificate(payload: dict[str, Any]) -> None:
    schema_path = Path(__file__).with_name("phase3.schema.json")
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
    parser.add_argument("--phase2-certificate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--two-q", type=int, default=15)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = collect_certificate(
        repo_root=args.repo_root.resolve(),
        phase2_certificate_path=args.phase2_certificate.resolve(),
        two_q=args.two_q,
    )
    validate_certificate(payload)
    write_json_atomic(args.output.resolve(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
