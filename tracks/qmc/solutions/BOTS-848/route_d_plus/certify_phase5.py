"""Produce the Route D+ Phase 5 scalar-generator certificate."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np

from route_d_plus.lll import spinor
from route_d_plus.mother import laughlin_amplitude
from route_d_plus.scalar import (
    FockSpace,
    coupled_pair_eigenvalues,
    one_body_casimir,
    one_body_fock_matrix,
    scalar_generator_pair,
    scalar_generator_proof,
    slater_matrix,
    whitening_transform,
)
from route_d_plus.tensor import angular_momentum_matrices, canonical_tensor

SCHEMA_VERSION = "challenge-15-route-d-plus-phase5-v1"
PHASE4_SCHEMA_VERSION = "challenge-15-route-d-plus-phase4-v1"
CERTIFICATION_N = 4
CERTIFICATION_TWO_Q = 9
GENERATOR_RANKS = (2, 3, 4)
TOLERANCES = {
    "casimir_residual": 1.0e-13,
    "hermiticity": 1.0e-12,
    "scalarity": 1.0e-11,
    "proof_production": 1.0e-10,
    "coupled_channel_spread": 1.0e-11,
    "mother_reconstruction": 1.0e-10,
    "whitening": 1.0e-8,
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


def require_phase4_certificate(path: Path) -> dict[str, Any]:
    certificate = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": PHASE4_SCHEMA_VERSION,
        "n_electrons": 6,
        "two_q": 15,
        "tower_components": 5,
        "passed": True,
        "git_dirty": False,
    }
    mismatches = {
        key: (certificate.get(key), value)
        for key, value in expected.items()
        if certificate.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"Phase 4 certificate mismatch: {mismatches}")
    return certificate


def random_spinor_batches(
    rng: np.random.Generator,
    n_samples: int,
    n_particles: int,
) -> np.ndarray:
    x = rng.uniform(-1.0, 1.0, size=(n_samples, n_particles))
    theta = np.arccos(x)
    phi = rng.uniform(0.0, 2.0 * np.pi, size=(n_samples, n_particles))
    u, v = spinor(theta, phi)
    return np.stack((u, v), axis=-1)


def reconstruct_mother(
    space: FockSpace,
    rng: np.random.Generator,
) -> tuple[np.ndarray, float]:
    batches = random_spinor_batches(
        rng,
        4 * space.dimension,
        space.n_particles,
    )
    basis = slater_matrix(CERTIFICATION_TWO_Q, space, batches)
    values = np.array(
        [laughlin_amplitude(configuration) for configuration in batches],
        dtype=np.complex128,
    )
    coefficients, *_ = np.linalg.lstsq(basis, values, rcond=None)
    residual = np.max(np.abs(basis @ coefficients - values))
    scale = max(float(np.max(np.abs(values))), np.finfo(float).tiny)
    coefficients /= np.linalg.norm(coefficients)
    return coefficients, float(residual / scale)


def weighted_local_statistics(
    basis_values: np.ndarray,
    state: np.ndarray,
    generators: list[np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    amplitude = basis_values @ state
    weights = np.abs(amplitude) ** 2
    weights /= np.sum(weights)
    safe = np.abs(amplitude) > 1.0e-14 * np.max(np.abs(amplitude))
    local = np.zeros((amplitude.size, len(generators)), np.complex128)
    for index, generator in enumerate(generators):
        dressed = basis_values @ (generator @ state)
        local[safe, index] = dressed[safe] / amplitude[safe]
    weights = np.where(safe, weights, 0.0)
    weights /= np.sum(weights)
    mean = np.sum(weights[:, None] * local, axis=0).real
    centered = local - mean
    covariance = np.einsum(
        "s,sa,sb->ab",
        weights,
        centered.conj(),
        centered,
        optimize=True,
    ).real
    return mean, 0.5 * (covariance + covariance.T)


def covariance_certificate(
    space: FockSpace,
    generators: list[np.ndarray],
    rng: np.random.Generator,
) -> dict[str, Any]:
    mother, reconstruction_error = reconstruct_mother(space, rng)
    tower = [
        one_body_fock_matrix(
            space,
            canonical_tensor(CERTIFICATION_TWO_Q, 2, m),
        )
        @ mother
        for m in range(-2, 3)
    ]
    tower = [state / np.linalg.norm(state) for state in tower]
    samples = random_spinor_batches(rng, 4096, space.n_particles)
    basis_values = slater_matrix(CERTIFICATION_TWO_Q, space, samples)
    ground_mean, ground_covariance = weighted_local_statistics(
        basis_values,
        mother,
        generators,
    )
    tower_statistics = [
        weighted_local_statistics(basis_values, state, generators)
        for state in tower
    ]
    tower_mean = np.mean(
        np.stack([statistics[0] for statistics in tower_statistics]), axis=0
    )
    tower_covariance = np.mean(
        np.stack([statistics[1] for statistics in tower_statistics]), axis=0
    )
    mixture_mean = 0.5 * (ground_mean + tower_mean)
    covariance = 0.5 * (ground_covariance + tower_covariance)
    retained, whitening = whitening_transform(covariance)
    whitened = whitening @ covariance @ whitening
    projector = whitening @ np.linalg.pinv(whitening)
    whitening_error = float(np.max(np.abs(whitened - projector)))
    return {
        "sample_count": samples.shape[0],
        "mixture_weights": [0.5, 0.5],
        "mean": mixture_mean.tolist(),
        "covariance": covariance.tolist(),
        "covariance_eigenvalues": np.linalg.eigvalsh(covariance).tolist(),
        "covariance_scale": float(np.max(np.linalg.eigvalsh(covariance))),
        "retained_directions": int(retained.size),
        "relative_cutoff": 1.0e-12,
        "mother_reconstruction_error": reconstruction_error,
        "whitening_error": whitening_error,
    }


def collect_certificate(
    *,
    repo_root: Path,
    phase4_certificate_path: Path,
) -> dict[str, Any]:
    phase4_certificate = require_phase4_certificate(phase4_certificate_path)
    commit = git_output(repo_root, "rev-parse", "HEAD")
    dirty = bool(git_output(repo_root, "status", "--porcelain"))
    if len(commit) != 40 or dirty:
        raise RuntimeError("Phase 5 requires a clean committed source revision")

    space = FockSpace.build(CERTIFICATION_TWO_Q + 1, CERTIFICATION_N)
    rotations = [
        one_body_fock_matrix(space, component)
        for component in angular_momentum_matrices(CERTIFICATION_TWO_Q)
    ]
    generators: list[np.ndarray] = []
    errors = {name: 0.0 for name in TOLERANCES}
    channel_eigenvalues: dict[str, dict[str, float]] = {}
    casimir_coefficients: dict[str, float] = {}
    for ell in GENERATOR_RANKS:
        proof = scalar_generator_proof(space, CERTIFICATION_TWO_Q, ell)
        production = scalar_generator_pair(space, CERTIFICATION_TWO_Q, ell)
        generators.append(production)
        coefficient, residual = one_body_casimir(
            CERTIFICATION_TWO_Q, ell
        )
        casimir_coefficients[str(ell)] = coefficient
        errors["casimir_residual"] = max(
            errors["casimir_residual"], residual
        )
        errors["hermiticity"] = max(
            errors["hermiticity"],
            float(np.max(np.abs(production - production.conj().T))),
        )
        errors["scalarity"] = max(
            errors["scalarity"],
            *[
                float(
                    np.max(
                        np.abs(production @ rotation - rotation @ production)
                    )
                )
                for rotation in rotations
            ],
        )
        denominator = max(float(np.max(np.abs(proof))), 1.0)
        errors["proof_production"] = max(
            errors["proof_production"],
            float(np.max(np.abs(proof - production)) / denominator),
        )
        channels, spread = coupled_pair_eigenvalues(
            CERTIFICATION_TWO_Q, ell
        )
        channel_eigenvalues[str(ell)] = {
            str(total_j): value for total_j, value in channels.items()
        }
        errors["coupled_channel_spread"] = max(
            errors["coupled_channel_spread"], spread
        )

    covariance = covariance_certificate(
        space,
        generators,
        np.random.default_rng(848_005),
    )
    errors["mother_reconstruction"] = covariance[
        "mother_reconstruction_error"
    ]
    errors["whitening"] = covariance["whitening_error"]
    passed = (
        covariance["retained_directions"] == 3
        and covariance["covariance_scale"] > 1.0e-8
        and all(
            errors[name] < tolerance
            for name, tolerance in TOLERANCES.items()
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "target_n_electrons": 6,
        "target_two_q": 15,
        "certification_n_electrons": CERTIFICATION_N,
        "certification_two_q": CERTIFICATION_TWO_Q,
        "generator_ranks": list(GENERATOR_RANKS),
        "fock_dimension": space.dimension,
        "casimir_coefficients": casimir_coefficients,
        "coupled_pair_eigenvalues": channel_eigenvalues,
        "covariance": covariance,
        "tolerances": TOLERANCES,
        "max_errors": errors,
        "passed": passed,
        "git_commit": commit,
        "git_dirty": dirty,
        "hostname": platform.node(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_cluster_name": os.environ.get("SLURM_CLUSTER_NAME"),
        "phase4_certificate_path": str(
            phase4_certificate_path.resolve()
        ),
        "phase4_certificate_sha256": sha256_file(
            phase4_certificate_path
        ),
        "phase4_git_commit": phase4_certificate["git_commit"],
    }


def validate_certificate(payload: dict[str, Any]) -> None:
    schema_path = Path(__file__).with_name("phase5.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    ).validate(payload)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--phase4-certificate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    payload = collect_certificate(
        repo_root=arguments.repo_root.resolve(),
        phase4_certificate_path=arguments.phase4_certificate.resolve(),
    )
    validate_certificate(payload)
    write_json_atomic(arguments.output.resolve(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
