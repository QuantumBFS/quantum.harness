"""Checkpoint-level continuous symmetry verifier for Route D+ Phase 6C."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import expm

from route_d_plus.coordinate import linear_dplus0_amplitudes
from route_d_plus.lll import spinor
from route_d_plus.tensor import (
    angular_momentum_matrices,
    canonical_tensor,
    rotation_matrix,
)
from route_d_plus.train_dplus0 import (
    TWO_Q,
    ground_raw_channels,
    tower_raw_channels,
)
from route_d_plus.vmc import center_whiten_channels

TOLERANCES = {
    "lll_homogeneity": 1.0e-9,
    "exchange": 1.0e-9,
    "scalarity": 1.0e-9,
    "ladder": 1.0e-8,
    "finite_rotation": 1.0e-9,
}


def _relative_error(
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


def _coefficients(payload: dict[str, Any], key: str) -> np.ndarray:
    value = payload[key]
    return np.asarray(value["real"], dtype=np.float64) + 1.0j * np.asarray(
        value["imag"], dtype=np.float64
    )


def _fixed_spinors() -> np.ndarray:
    theta = np.array([0.21, 0.64, 1.08, 1.57, 2.19, 2.81])
    phi = np.array([0.17, 1.32, 2.73, 4.11, 5.27, 3.36])
    u, v = spinor(theta, phi)
    return np.column_stack((u, v))


def _ladder_error() -> float:
    jx, jy, _ = angular_momentum_matrices(TWO_Q)
    raising = jx + 1.0j * jy
    lowering = jx - 1.0j * jy
    error = 0.0
    for magnetic in range(-2, 3):
        tensor = canonical_tensor(TWO_Q, 2, magnetic)
        if magnetic < 2:
            coefficient = math.sqrt(6.0 - magnetic * (magnetic + 1.0))
            residual = (
                raising @ tensor
                - tensor @ raising
                - coefficient
                * canonical_tensor(TWO_Q, 2, magnetic + 1)
            )
            error = max(error, float(np.max(np.abs(residual))))
        if magnetic > -2:
            coefficient = math.sqrt(6.0 - magnetic * (magnetic - 1.0))
            residual = (
                lowering @ tensor
                - tensor @ lowering
                - coefficient
                * canonical_tensor(TWO_Q, 2, magnetic - 1)
            )
            error = max(error, float(np.max(np.abs(residual))))
    return error


def verify_checkpoint_symmetry(
    architecture: dict[str, Any],
    checkpoint: dict[str, Any],
) -> dict[str, Any]:
    """Recompute continuous symmetry identities from immutable artifacts."""

    architecture_hash = checkpoint["architecture_sha256"]
    mean = np.asarray(architecture["centering_mean"], dtype=np.float64)
    whitening = np.asarray(architecture["whitening"], dtype=np.float64)
    ground_coefficients = _coefficients(
        checkpoint, "ground_coefficients"
    )
    tower_coefficients = _coefficients(checkpoint, "tower_coefficients")

    def ground(configuration: np.ndarray) -> complex:
        channels = center_whiten_channels(
            ground_raw_channels(configuration), mean, whitening
        )
        return complex(
            linear_dplus0_amplitudes(channels, ground_coefficients)
        )

    def tower(configuration: np.ndarray) -> np.ndarray:
        channels = center_whiten_channels(
            tower_raw_channels(configuration), mean, whitening
        )
        return np.asarray(
            linear_dplus0_amplitudes(channels, tower_coefficients),
            dtype=np.complex128,
        )

    configuration = _fixed_spinors()
    ground_value = ground(configuration)
    tower_value = tower(configuration)

    scaled = configuration.copy()
    scale = 1.03 * np.exp(-0.11j)
    scaled[3] *= scale
    expected_scale = scale**TWO_Q
    lll_error = max(
        _relative_error(ground(scaled), expected_scale * ground_value),
        _relative_error(tower(scaled), expected_scale * tower_value),
    )

    swapped = configuration.copy()
    swapped[[0, 5]] = swapped[[5, 0]]
    exchange_error = max(
        _relative_error(ground(swapped), -ground_value),
        _relative_error(tower(swapped), -tower_value),
    )

    rotation_vector = np.array([0.31, -0.27, 0.19])
    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]])
    sigma_y = np.array([[0.0, -1.0j], [1.0j, 0.0]])
    sigma_z = np.diag([1.0, -1.0])
    fundamental = expm(
        -0.5j
        * (
            rotation_vector[0] * sigma_x
            + rotation_vector[1] * sigma_y
            + rotation_vector[2] * sigma_z
        )
    )
    rotated = configuration @ fundamental.T
    scalarity_error = _relative_error(
        ground(rotated),
        ground_value,
    )
    finite_rotation_error = _relative_error(
        tower(rotated),
        rotation_matrix(4, rotation_vector) @ tower_value,
    )
    errors = {
        "lll_homogeneity": lll_error,
        "exchange": exchange_error,
        "scalarity": scalarity_error,
        "ladder": _ladder_error(),
        "finite_rotation": finite_rotation_error,
    }
    return {
        "schema_version": "challenge-15-route-d-plus-symmetry-v1",
        "seed": checkpoint["seed"],
        "n_electrons": checkpoint["n_electrons"],
        "two_q": checkpoint["two_q"],
        "architecture_sha256": architecture_hash,
        "rotation_convention": "Phi_2(RX)=D2(R)@Phi_2(X)",
        "errors": errors,
        "tolerances": dict(TOLERANCES),
        "gates": {
            key: errors[key] < tolerance
            for key, tolerance in TOLERANCES.items()
        },
        "passed": all(
            errors[key] < tolerance
            for key, tolerance in TOLERANCES.items()
        ),
    }


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


__all__ = ["TOLERANCES", "load_json", "verify_checkpoint_symmetry"]
