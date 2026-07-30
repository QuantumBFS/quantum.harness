#!/usr/bin/env python3
"""Executable checks for the v3 Wick and topology derivations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import expm

from lgeth.bundle_geometry import analyze_ambient_frame_mesh
from lgeth.wick_channels import covariance_matched_wick


SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT = SCRIPT_ROOT / "output" / "matrix_element_topology_theory_v3.json"


def _seeded_unitary(dimension: int, rng: np.random.Generator) -> np.ndarray:
    matrix = rng.normal(size=(dimension, dimension))
    matrix = matrix + 1j * rng.normal(size=matrix.shape)
    q, r = np.linalg.qr(matrix)
    phases = np.diag(r)
    return q * (phases / np.abs(phases)).conj()[None, :]


def wick_identity_check(
    D: int = 4,
    M: int = 7,
    channels: int = 4,
    samples: int = 20_000,
    seed: int = 20260729500,
) -> dict[str, float]:
    """Compare the two analytic Wick contractions with direct sampling."""

    rng = np.random.default_rng(seed)
    left = np.linspace(0.7, 1.6, D)
    right = np.linspace(0.5, 1.7, M)
    right *= D / (np.sum(left) * np.sum(right))
    A_left = D * np.sum(left**2) / np.sum(left) ** 2
    B_right = D * np.sum(right**2) / np.sum(right) ** 2
    identity = np.eye(channels)
    expected = (
        A_left * np.einsum("mn,rs->mnrs", identity, identity)
        + B_right * np.einsum("ms,rn->mnrs", identity, identity)
    )
    accumulated = np.zeros_like(expected, dtype=complex)
    batch = 250
    completed = 0
    while completed < samples:
        count = min(batch, samples - completed)
        gaussian = (
            rng.normal(size=(count, channels, M, D))
            + 1j * rng.normal(size=(count, channels, M, D))
        ) / np.sqrt(2.0)
        values = (
            np.sqrt(right)[None, None, :, None]
            * gaussian
            * np.sqrt(left)[None, None, None, :]
        )
        pair = np.einsum(
            "zmai,znaj->zmnij",
            values.conj(),
            values,
            optimize=True,
        )
        tensor = np.einsum(
            "zmnij,zrsji->zmnrs",
            pair,
            pair,
            optimize=True,
        ) / D
        accumulated += np.sum(tensor, axis=0)
        completed += count
    observed = accumulated / samples
    return {
        "A_left": float(A_left),
        "B_right": float(B_right),
        "relative_error": float(
            np.linalg.norm(observed - expected) / np.linalg.norm(expected)
        ),
        "maximum_absolute_error": float(
            np.max(np.abs(observed - expected))
        ),
    }


def gauge_and_gram_check(
    seed: int = 20260729501,
) -> dict[str, float]:
    """Check gauge invariance and the nonzero Gram-spectrum reduction."""

    rng = np.random.default_rng(seed)
    channels = (
        rng.normal(size=(5, 9, 4))
        + 1j * rng.normal(size=(5, 9, 4))
    ) / np.sqrt(18.0)
    original = covariance_matched_wick(channels)
    external = _seeded_unitary(9, rng)
    target = _seeded_unitary(4, rng)
    transformed = np.einsum(
        "ab,mbi,ij->maj",
        external.conj().T,
        channels,
        target,
        optimize=True,
    )
    gauged = covariance_matched_wick(transformed)
    matrix = channels.transpose(1, 0, 2).reshape(9, -1)
    R = matrix @ matrix.conj().T / channels.shape[0]
    G = matrix.conj().T @ matrix / channels.shape[0]
    eigen_R = np.linalg.eigvalsh(0.5 * (R + R.conj().T))
    eigen_G = np.linalg.eigvalsh(0.5 * (G + G.conj().T))
    nonzero_R = eigen_R[eigen_R > 1e-12 * eigen_R[-1]]
    nonzero_G = eigen_G[eigen_G > 1e-12 * eigen_G[-1]]
    return {
        "R4_error": abs(original.R4 - gauged.R4),
        "tensor_error": float(
            np.max(np.abs(original.tensor - gauged.tensor))
        ),
        "gram_spectrum_error": float(
            np.max(np.abs(nonzero_R - nonzero_G))
        ),
    }


def _qiwuzhang_mesh(mesh: int, mass: float = -1.0) -> np.ndarray:
    frames = np.empty((mesh, mesh, 2, 1), dtype=complex)
    momenta = 2.0 * np.pi * np.arange(mesh) / mesh
    for ix, kx in enumerate(momenta):
        for iy, ky in enumerate(momenta):
            hamiltonian = np.array(
                [
                    [
                        mass + np.cos(kx) + np.cos(ky),
                        np.sin(kx) - 1j * np.sin(ky),
                    ],
                    [
                        np.sin(kx) + 1j * np.sin(ky),
                        -mass - np.cos(kx) - np.cos(ky),
                    ],
                ],
                dtype=complex,
            )
            _, vectors = np.linalg.eigh(hamiltonian)
            frames[ix, iy, :, 0] = vectors[:, 0]
    return frames


def periodic_unitary_chern_check(mesh: int = 24) -> dict[str, float]:
    """Check Chern invariance under a smooth periodic ambient unitary."""

    frames = _qiwuzhang_mesh(mesh)
    deformed = np.empty_like(frames)
    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
    sigma_z = np.diag([1.0, -1.0]).astype(complex)
    angles = 2.0 * np.pi * np.arange(mesh) / mesh
    for ix, theta_x in enumerate(angles):
        for iy, theta_y in enumerate(angles):
            unitary = expm(0.7j * np.sin(theta_x) * sigma_x)
            unitary = unitary @ expm(
                0.5j * np.sin(theta_y) * sigma_z
            )
            deformed[ix, iy] = unitary @ frames[ix, iy]
    before = analyze_ambient_frame_mesh(frames)
    after = analyze_ambient_frame_mesh(deformed)
    return {
        "chern_before": before.chern_determinant,
        "chern_after": after.chern_determinant,
        "chern_error": abs(
            before.chern_determinant - after.chern_determinant
        ),
        "minimum_branch_margin": min(
            before.determinant_branch_margin,
            after.determinant_branch_margin,
        ),
    }


def run_checks() -> dict[str, Any]:
    wick = wick_identity_check()
    gauge = gauge_and_gram_check()
    topology = periodic_unitary_chern_check()
    checks = {
        "wick_monte_carlo": wick["relative_error"] < 0.04,
        "gauge_tensor": gauge["tensor_error"] < 1e-10,
        "gauge_R4": gauge["R4_error"] < 1e-10,
        "gram_reduction": gauge["gram_spectrum_error"] < 1e-10,
        "chern_isomorphism": topology["chern_error"] < 1e-10,
        "chern_branch": topology["minimum_branch_margin"] > 0.0,
    }
    result = {
        "version": "v3",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "passed": all(checks.values()),
        "checks": checks,
        "wick": wick,
        "gauge_and_gram": gauge,
        "topology": topology,
    }
    if not result["passed"]:
        raise RuntimeError(f"v3 theory checks failed: {result}")
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(OUTPUT)
    return result


def main() -> None:
    print(json.dumps(run_checks(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
