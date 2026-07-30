"""Produce the Route D+ Phase 4 analytic mother-state certificate."""

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
from scipy.linalg import expm

from route_d_plus.lll import sphere_quadrature, spinor
from route_d_plus.mother import gmp_quadrupole_tower, laughlin_amplitude
from route_d_plus.tensor import (
    angular_momentum_matrices,
    canonical_tensor,
    rotation_matrix,
)

SCHEMA_VERSION = "challenge-15-route-d-plus-phase4-v1"
PHASE3_SCHEMA_VERSION = "challenge-15-route-d-plus-phase3-v1"
TOLERANCES = {
    "mother_exchange": 1.0e-12,
    "mother_degree": 1.0e-12,
    "mother_rotation": 1.0e-12,
    "tower_exchange": 1.0e-10,
    "tower_degree": 1.0e-10,
    "ladder": 1.0e-8,
    "finite_rotation": 1.0e-6,
    "equal_norm": 1.0e-12,
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


def require_phase3_certificate(path: Path) -> dict[str, Any]:
    certificate = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": PHASE3_SCHEMA_VERSION,
        "two_q": 15,
        "tensor_count": 256,
        "passed": True,
        "git_dirty": False,
    }
    mismatches = {
        key: (certificate.get(key), value)
        for key, value in expected.items()
        if certificate.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"Phase 3 certificate mismatch: {mismatches}")
    return certificate


def relative_error(
    actual: np.ndarray | complex,
    expected: np.ndarray | complex,
) -> float:
    actual_array = np.asarray(actual, dtype=np.complex128)
    expected_array = np.asarray(expected, dtype=np.complex128)
    scale = max(
        float(np.max(np.abs(actual_array))),
        float(np.max(np.abs(expected_array))),
        np.finfo(np.float64).tiny,
    )
    return float(np.max(np.abs(actual_array - expected_array)) / scale)


def fixed_spinors() -> np.ndarray:
    theta = np.array([0.21, 0.64, 1.08, 1.57, 2.19, 2.81])
    phi = np.array([0.17, 1.32, 2.73, 4.11, 5.27, 3.36])
    u, v = spinor(theta, phi)
    return np.column_stack((u, v))


def collect_certificate(
    *,
    repo_root: Path,
    phase3_certificate_path: Path,
    n_electrons: int,
    two_q: int,
) -> dict[str, Any]:
    phase3_certificate = require_phase3_certificate(phase3_certificate_path)
    commit = git_output(repo_root, "rev-parse", "HEAD")
    dirty = bool(git_output(repo_root, "status", "--porcelain"))
    if len(commit) != 40 or dirty:
        raise RuntimeError("Phase 4 requires a clean committed source revision")
    if two_q != 3 * (n_electrons - 1):
        raise RuntimeError("Phase 4 requires two_q = 3 * (N - 1)")

    spinors = fixed_spinors()
    mother = laughlin_amplitude(spinors)
    swapped = spinors.copy()
    swapped[[1, 4]] = swapped[[4, 1]]
    mother_exchange_error = relative_error(
        laughlin_amplitude(swapped),
        -mother,
    )
    scale = 1.07 * np.exp(0.19j)
    scaled = spinors.copy()
    scaled[2] *= scale
    mother_degree_error = relative_error(
        laughlin_amplitude(scaled),
        (scale**two_q) * mother,
    )

    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]])
    sigma_y = np.array([[0.0, -1.0j], [1.0j, 0.0]])
    sigma_z = np.diag([1.0, -1.0])
    rotation_vector = np.array([0.31, -0.27, 0.19])
    fundamental_rotation = expm(
        -0.5j
        * (
            rotation_vector[0] * sigma_x
            + rotation_vector[1] * sigma_y
            + rotation_vector[2] * sigma_z
        )
    )
    mother_rotation_error = relative_error(
        laughlin_amplitude(spinors @ fundamental_rotation.T),
        mother,
    )

    grid = sphere_quadrature(two_q)
    tower = gmp_quadrupole_tower(spinors, grid, two_q=two_q)
    minimum_component_magnitude = float(np.min(np.abs(tower)))
    tower_swapped = spinors.copy()
    tower_swapped[[0, 5]] = tower_swapped[[5, 0]]
    tower_exchange_error = relative_error(
        gmp_quadrupole_tower(tower_swapped, grid, two_q=two_q),
        -tower,
    )
    tower_scale = 1.03 * np.exp(-0.11j)
    tower_scaled = spinors.copy()
    tower_scaled[3] *= tower_scale
    tower_degree_error = relative_error(
        gmp_quadrupole_tower(tower_scaled, grid, two_q=two_q),
        (tower_scale**two_q) * tower,
    )

    jx, jy, _ = angular_momentum_matrices(two_q)
    raising = jx + 1.0j * jy
    lowering = jx - 1.0j * jy
    ladder_error = 0.0
    tensors = [canonical_tensor(two_q, 2, m) for m in range(-2, 3)]
    for m, tensor in zip(range(-2, 3), tensors, strict=True):
        if m < 2:
            coefficient = np.sqrt(6.0 - m * (m + 1.0))
            ladder_error = max(
                ladder_error,
                float(
                    np.max(
                        np.abs(
                            raising @ tensor
                            - tensor @ raising
                            - coefficient
                            * canonical_tensor(two_q, 2, m + 1)
                        )
                    )
                ),
            )
        if m > -2:
            coefficient = np.sqrt(6.0 - m * (m - 1.0))
            ladder_error = max(
                ladder_error,
                float(
                    np.max(
                        np.abs(
                            lowering @ tensor
                            - tensor @ lowering
                            - coefficient
                            * canonical_tensor(two_q, 2, m - 1)
                        )
                    )
                ),
            )

    single_particle_rotation = rotation_matrix(two_q, rotation_vector)
    tensor_rotation = rotation_matrix(4, rotation_vector)
    finite_rotation_error = 0.0
    for column, tensor in enumerate(tensors):
        expected = sum(
            tensor_rotation[row, column] * component
            for row, component in enumerate(tensors)
        )
        finite_rotation_error = max(
            finite_rotation_error,
            float(
                np.max(
                    np.abs(
                        single_particle_rotation
                        @ tensor
                        @ single_particle_rotation.conj().T
                        - expected
                    )
                )
            ),
        )
    norms = np.array([np.vdot(tensor, tensor).real for tensor in tensors])
    equal_norm_error = float(np.max(np.abs(norms - np.mean(norms))))

    errors = {
        "mother_exchange": mother_exchange_error,
        "mother_degree": mother_degree_error,
        "mother_rotation": mother_rotation_error,
        "tower_exchange": tower_exchange_error,
        "tower_degree": tower_degree_error,
        "ladder": ladder_error,
        "finite_rotation": finite_rotation_error,
        "equal_norm": equal_norm_error,
    }
    passed = (
        minimum_component_magnitude > 1.0e-14
        and all(
            errors[name] < tolerance
            for name, tolerance in TOLERANCES.items()
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "n_electrons": n_electrons,
        "two_q": two_q,
        "tower_components": len(tower),
        "minimum_component_magnitude": minimum_component_magnitude,
        "tolerances": TOLERANCES,
        "max_errors": errors,
        "passed": passed,
        "git_commit": commit,
        "git_dirty": dirty,
        "hostname": platform.node(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_cluster_name": os.environ.get("SLURM_CLUSTER_NAME"),
        "phase3_certificate_path": str(phase3_certificate_path.resolve()),
        "phase3_certificate_sha256": sha256_file(phase3_certificate_path),
        "phase3_git_commit": phase3_certificate["git_commit"],
    }


def validate_certificate(payload: dict[str, Any]) -> None:
    schema_path = Path(__file__).with_name("phase4.schema.json")
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
    parser.add_argument("--phase3-certificate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-electrons", type=int, default=6)
    parser.add_argument("--two-q", type=int, default=15)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = collect_certificate(
        repo_root=args.repo_root.resolve(),
        phase3_certificate_path=args.phase3_certificate.resolve(),
        n_electrons=args.n_electrons,
        two_q=args.two_q,
    )
    validate_certificate(payload)
    write_json_atomic(args.output.resolve(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
