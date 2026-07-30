"""Analytic semicircular hybridization for the CT-HYB production runner."""

from __future__ import annotations

import math
import numbers
from collections.abc import Sequence
from typing import Any

import numpy as np

from artifacts import canonical_json, sha256_bytes


COMMON_REAL_FREQUENCY = {
    "omega": [-1.0, 0.0, 1.0],
    "Gamma": [0.0, 0.1, 0.0],
}
COMMON_REAL_FREQUENCY_SHA256 = (
    "d424a7438f1b7da8938256f2cae9812a2b52c737d34f6026453ca4aa15f55b0f"
)


def _positive_finite_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return converted


def delta_iw(
    omega: np.ndarray,
    *,
    gamma: float,
    bandwidth: float,
) -> np.ndarray:
    """Evaluate the branch-safe semicircular hybridization on the imaginary axis."""
    if not isinstance(omega, np.ndarray):
        raise TypeError("omega must be a numpy.ndarray")
    if omega.dtype != np.dtype(np.float64):
        raise TypeError("omega must have dtype float64")
    if omega.ndim != 1:
        raise ValueError("omega must be one-dimensional")
    if not np.all(np.isfinite(omega)):
        raise ValueError("omega values must be finite")
    if np.any(omega == 0.0):
        raise ValueError("fermionic Matsubara frequencies cannot be zero")
    gamma_value = _positive_finite_float(gamma, "gamma")
    bandwidth_value = _positive_finite_float(bandwidth, "bandwidth")
    values = (
        1j
        * gamma_value
        / bandwidth_value
        * (
            omega
            - np.sign(omega)
            * np.sqrt(omega * omega + bandwidth_value * bandwidth_value)
        )
    )
    return np.asarray(values, dtype=np.complex128)


def serialize_complex128(values: np.ndarray) -> dict[str, object]:
    """Serialize a finite one-dimensional complex128 array with a canonical digest."""
    if not isinstance(values, np.ndarray) or values.dtype != np.dtype(np.complex128):
        raise TypeError("values must be a complex128 numpy.ndarray")
    if values.ndim != 1:
        raise ValueError("complex128 values must be one-dimensional")
    if not np.all(np.isfinite(values.real)) or not np.all(np.isfinite(values.imag)):
        raise ValueError("complex128 values must be finite")
    split: dict[str, object] = {
        "real": values.real.tolist(),
        "imag": values.imag.tolist(),
    }
    split["sha256"] = sha256_bytes(canonical_json(split))
    return split


def _exact_float_list(value: object, expected: list[float], name: str) -> None:
    if not isinstance(value, list) or len(value) != len(expected):
        raise ValueError(f"{name} must contain exactly {len(expected)} values")
    if any(type(actual) is not float for actual in value):
        raise TypeError(f"{name} values must use canonical JSON floats")
    if value != expected:
        raise ValueError(f"{name} does not match the common comparison surface")


def verify_common_real_frequency(payload: object) -> None:
    """Verify the exact digest-bound MPS/CT-HYB real-frequency surface."""
    if not isinstance(payload, dict) or set(payload) != {"omega", "Gamma", "sha256"}:
        raise ValueError("common real-frequency payload has unexpected keys")
    _exact_float_list(payload["omega"], COMMON_REAL_FREQUENCY["omega"], "omega")
    _exact_float_list(payload["Gamma"], COMMON_REAL_FREQUENCY["Gamma"], "Gamma")
    digest = payload["sha256"]
    if not isinstance(digest, str):
        raise TypeError("common real-frequency SHA256 must be a string")
    actual = sha256_bytes(
        canonical_json({"omega": payload["omega"], "Gamma": payload["Gamma"]})
    )
    if (
        digest != COMMON_REAL_FREQUENCY_SHA256
        or actual != COMMON_REAL_FREQUENCY_SHA256
    ):
        raise ValueError("common real-frequency SHA256 mismatch")


def reported_tau_indices(
    beta: float,
    n_tau: int,
    tau: Sequence[float],
) -> list[int]:
    """Return exact uniform-mesh indices; interpolation is forbidden."""
    beta_value = _positive_finite_float(beta, "beta")
    if isinstance(n_tau, bool) or not isinstance(n_tau, numbers.Integral):
        raise TypeError("n_tau must be an integer")
    n_tau_value = int(n_tau)
    if n_tau_value < 2:
        raise ValueError("n_tau must be at least two")
    if isinstance(tau, (str, bytes)) or not isinstance(tau, Sequence):
        raise TypeError("tau must be a sequence")

    result: list[int] = []
    for value in tau:
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError("reported tau values must be real numbers")
        converted = float(value)
        if not math.isfinite(converted) or converted < 0.0 or converted > beta_value:
            raise ValueError("reported tau values must lie in [0, beta]")
        position = converted * (n_tau_value - 1) / beta_value
        index = round(position)
        if not math.isclose(position, index, rel_tol=0.0, abs_tol=1.0e-12):
            raise ValueError(f"reported tau is not an exact mesh node: {converted}")
        result.append(index)
    return result


def _split_complex128(payload: object, expected_length: int) -> np.ndarray:
    if not isinstance(payload, dict) or set(payload) != {"real", "imag", "sha256"}:
        raise ValueError("delta_iw split array has unexpected keys")
    real = payload["real"]
    imag = payload["imag"]
    if (
        not isinstance(real, list)
        or not isinstance(imag, list)
        or len(real) != expected_length
        or len(imag) != expected_length
    ):
        raise ValueError("delta_iw split arrays have the wrong length")
    for name, values in (("real", real), ("imag", imag)):
        if any(type(value) is not float for value in values):
            raise TypeError(f"delta_iw {name} values must be canonical JSON floats")
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"delta_iw {name} values must be finite")
    digest = payload["sha256"]
    expected_digest = sha256_bytes(canonical_json({"real": real, "imag": imag}))
    if not isinstance(digest, str) or digest != expected_digest:
        raise ValueError("delta_iw split-array SHA256 mismatch")
    return np.asarray(real, dtype=np.float64) + 1j * np.asarray(
        imag, dtype=np.float64
    )


def _block_mesh_omega(block: Any) -> np.ndarray:
    try:
        values = np.array(
            [complex(point).imag for point in block.mesh],
            dtype=np.float64,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("solver G0_iw block has an unsupported mesh") from error
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("solver G0_iw mesh is malformed")
    return values


def install_g0(solver: Any, input_payload: dict[str, object]) -> None:
    """Validate the canonical bath and install G0 without bath discretization."""
    if not isinstance(input_payload, dict):
        raise TypeError("input_payload must be a dictionary")
    try:
        model = input_payload["model"]
        hybridization = input_payload["hybridization"]
        meshes = input_payload["meshes"]
    except KeyError as error:
        raise ValueError(f"production input is missing {error.args[0]}") from error
    if not isinstance(model, dict) or not isinstance(hybridization, dict):
        raise ValueError("production model and hybridization must be objects")
    if not isinstance(meshes, dict):
        raise ValueError("production meshes must be an object")

    required_model = {"D", "Gamma", "epsilon_d", "mu", "beta"}
    if not required_model.issubset(model):
        raise ValueError("production model is incomplete")
    bandwidth = _positive_finite_float(model["D"], "model.D")
    gamma = _positive_finite_float(model["Gamma"], "model.Gamma")
    beta = _positive_finite_float(model["beta"], "model.beta")
    epsilon_d = model["epsilon_d"]
    mu = model["mu"]
    for value, name in ((epsilon_d, "epsilon_d"), (mu, "mu")):
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"model.{name} must be a real number")
        if not math.isfinite(float(value)):
            raise ValueError(f"model.{name} must be finite")

    if hybridization.get("dtype") != "complex128":
        raise ValueError("hybridization dtype must be complex128")
    n_iw = hybridization.get("n_iw")
    if isinstance(n_iw, bool) or not isinstance(n_iw, numbers.Integral) or n_iw < 1:
        raise ValueError("hybridization n_iw must be a positive integer")
    expected_length = 2 * int(n_iw)
    omega_raw = hybridization.get("matsubara_omega")
    if not isinstance(omega_raw, list) or len(omega_raw) != expected_length:
        raise ValueError("Matsubara frequency array has the wrong length")
    if any(type(value) is not float for value in omega_raw):
        raise TypeError("Matsubara frequencies must be canonical JSON floats")
    omega = np.asarray(omega_raw, dtype=np.float64)
    if not np.all(np.isfinite(omega)) or np.any(omega == 0.0):
        raise ValueError("Matsubara frequencies must be finite and nonzero")
    serialized_delta = _split_complex128(
        hybridization.get("delta_iw"),
        expected_length,
    )
    analytic_delta = delta_iw(omega, gamma=gamma, bandwidth=bandwidth)
    if not np.allclose(
        serialized_delta,
        analytic_delta,
        rtol=2.0e-14,
        atol=2.0e-15,
    ):
        raise ValueError("serialized delta_iw disagrees with the analytic bath")
    verify_common_real_frequency(hybridization.get("common_real_frequency"))

    n_tau = meshes.get("n_tau")
    reported_tau_indices(beta, n_tau, meshes.get("reported_tau"))

    try:
        blocks = {name: solver.G0_iw[name] for name in solver.G0_iw.indices}
    except (AttributeError, KeyError, TypeError) as error:
        raise ValueError("solver must expose indexed G0_iw blocks") from error
    if set(blocks) != {"up", "down"}:
        raise ValueError("solver G0_iw must contain exactly up and down blocks")
    for name, block in blocks.items():
        data = np.asarray(block.data)
        if data.shape != (expected_length, 1, 1):
            raise ValueError(f"solver {name} G0_iw block has the wrong shape")
        mesh_omega = _block_mesh_omega(block)
        if not np.allclose(mesh_omega, omega, rtol=0.0, atol=2.0e-14):
            raise ValueError(f"solver {name} Matsubara mesh disagrees with input")
        mesh_beta = float(block.mesh.beta)
        if mesh_beta != beta:
            raise ValueError(f"solver {name} beta disagrees with input")

    inverse_g0 = (
        1j * omega + float(mu) - float(epsilon_d) - serialized_delta
    )
    if np.any(inverse_g0 == 0.0) or not np.all(np.isfinite(inverse_g0)):
        raise ValueError("G0 inverse is singular or non-finite")
    installed = np.asarray(1.0 / inverse_g0, dtype=np.complex128)
    for block in blocks.values():
        block.data[:, 0, 0] = installed
