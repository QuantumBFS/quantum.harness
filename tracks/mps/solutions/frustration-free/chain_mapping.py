"""Deterministic finite star-to-chain bath mapping."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import platform
from pathlib import Path
import stat
import tempfile
from typing import Any

import numpy as np


MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = 1
BREAKDOWN_TOLERANCE_RULE = (
    "64 * eps(float64) * max(1, norm(E, inf)) * n_bath"
)

_CONVENTIONS = {
    "star_matrix": "E = diag(epsilon)",
    "coupling_gauge": "v is real and componentwise nonnegative",
    "initial_vector": "q0 = v / norm(v) when norm(v) > 0",
    "spin_transform": "the same real Q is used for up and down",
    "chemical_potential": "transform E before subtracting mu",
    "hopping_gauge": "chain hoppings are nonnegative",
    "breakdown": "deterministic canonical coordinate deflation",
    "decoupled": "v = 0 maps with Q = I",
}
_PAYLOAD_KEYS = {
    "schema_version",
    "source_bath_sha256",
    "source_bath_schema_version",
    "n_bath",
    "representation",
    "lambda",
    "Q",
    "chain_onsite",
    "chain_hopping",
    "deflation_boundaries",
    "conventions",
    "numerics",
    "provenance",
}
_NUMERICS_KEYS = {
    "algorithm",
    "breakdown_tolerance",
    "breakdown_tolerance_rule",
    "orthogonality_max_error",
    "off_tridiagonal_max_abs",
    "coupling_max_error",
}
_PROVENANCE_KEYS = {
    "module",
    "module_version",
    "python_version",
    "numpy_version",
    "schema_version",
}


def _load_bath_module():
    path = Path(__file__).with_name("bath.py")
    spec = importlib.util.spec_from_file_location(
        "challenge_81_chain_mapping_bath", path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load bath validation module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bath = _load_bath_module()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _breakdown_tolerance(epsilon: np.ndarray) -> float:
    return float(
        64.0
        * np.finfo(np.float64).eps
        * max(1.0, np.linalg.norm(epsilon, ord=np.inf))
        * epsilon.size
    )


def _reorthogonalize(
    vector: np.ndarray, columns: list[np.ndarray]
) -> np.ndarray:
    result = vector.copy()
    for _ in range(2):
        for column in columns:
            result -= float(column @ result) * column
    return result


def _canonical_deflation(
    columns: list[np.ndarray], tolerance: float, size: int
) -> np.ndarray:
    for coordinate in range(size):
        candidate = np.zeros(size, dtype=np.float64)
        candidate[coordinate] = 1.0
        candidate = _reorthogonalize(candidate, columns)
        norm = float(np.linalg.norm(candidate))
        if norm > tolerance:
            candidate /= norm
            first = next(
                index
                for index, value in enumerate(candidate)
                if abs(value) > tolerance
            )
            if candidate[first] < 0.0:
                candidate *= -1.0
            return candidate
    raise ValueError("canonical deflation could not complete the basis")


def _transformed_matrix(epsilon: np.ndarray, Q: np.ndarray) -> np.ndarray:
    transformed = Q.T @ np.diag(epsilon) @ Q
    return (transformed + transformed.T) / 2.0


def _lanczos(
    epsilon: np.ndarray, coupling: np.ndarray
) -> tuple[np.ndarray, np.ndarray, float, list[int], float]:
    size = epsilon.size
    tolerance = _breakdown_tolerance(epsilon)
    hybridization = float(np.linalg.norm(coupling))

    if hybridization == 0.0:
        Q = np.eye(size, dtype=np.float64)
        return Q, np.diag(epsilon), 0.0, list(range(size - 1)), tolerance

    columns = [coupling / hybridization]
    deflation_boundaries: list[int] = []
    previous_beta = 0.0

    while len(columns) < size:
        index = len(columns) - 1
        current = columns[index]
        alpha = float(current @ (epsilon * current))
        residual = epsilon * current - alpha * current
        if index > 0:
            residual -= previous_beta * columns[index - 1]
        residual = _reorthogonalize(residual, columns)
        beta = float(np.linalg.norm(residual))

        if beta > tolerance:
            columns.append(residual / beta)
            previous_beta = beta
        else:
            deflation_boundaries.append(index)
            columns.append(_canonical_deflation(columns, tolerance, size))
            previous_beta = 0.0

    Q = np.column_stack(columns)
    transformed = _transformed_matrix(epsilon, Q)

    # Correct a roundoff-level negative link without changing earlier blocks.
    boundaries = set(deflation_boundaries)
    validation_tolerance = 4.0 * tolerance
    for index in range(size - 1):
        if index in boundaries:
            continue
        value = float(transformed[index, index + 1])
        if value < -validation_tolerance:
            raise ValueError("Lanczos produced a negative chain hopping")
        if value < 0.0:
            block_end = next(
                (
                    boundary + 1
                    for boundary in deflation_boundaries
                    if boundary > index
                ),
                size,
            )
            Q[:, index + 1 : block_end] *= -1.0
            transformed = _transformed_matrix(epsilon, Q)

    return Q, transformed, hybridization, deflation_boundaries, tolerance


def _mapping_payload(bath_artifact: dict[str, Any]) -> dict[str, Any]:
    source = bath_artifact["payload"]
    epsilon = np.asarray(source["epsilon"], dtype=np.float64).copy()
    coupling = np.asarray(source["V"], dtype=np.float64).copy()
    if (
        epsilon.ndim != 1
        or coupling.shape != epsilon.shape
        or epsilon.size == 0
        or not np.all(np.isfinite(epsilon))
        or not np.all(np.isfinite(coupling))
        or np.any(coupling < 0.0)
    ):
        raise ValueError("verified bath arrays are invalid for chain mapping")

    Q, transformed, hybridization, boundaries, tolerance = _lanczos(
        epsilon, coupling
    )
    size = epsilon.size
    off_tridiagonal = transformed.copy()
    for index in range(size):
        off_tridiagonal[index, max(0, index - 1) : index + 2] = 0.0
    validation_tolerance = 4.0 * tolerance
    off_error = float(np.max(np.abs(off_tridiagonal), initial=0.0))
    orthogonality_error = float(
        np.max(np.abs(Q.T @ Q - np.eye(size)), initial=0.0)
    )
    target = np.zeros(size, dtype=np.float64)
    target[0] = hybridization
    coupling_error = float(np.max(np.abs(Q.T @ coupling - target), initial=0.0))
    if max(off_error, orthogonality_error, coupling_error) > validation_tolerance:
        raise ValueError("Lanczos mapping failed numerical validation")

    boundary_set = set(boundaries)
    chain_hopping = [
        0.0 if index in boundary_set else abs(float(transformed[index, index + 1]))
        for index in range(size - 1)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "source_bath_sha256": bath_artifact["sha256"],
        "source_bath_schema_version": source["schema_version"],
        "n_bath": size,
        "representation": "finite_chain",
        "lambda": hybridization,
        "Q": Q.tolist(),
        "chain_onsite": np.diag(transformed).tolist(),
        "chain_hopping": chain_hopping,
        "deflation_boundaries": boundaries,
        "conventions": dict(_CONVENTIONS),
        "numerics": {
            "algorithm": "two-pass fully reorthogonalized Lanczos",
            "breakdown_tolerance": tolerance,
            "breakdown_tolerance_rule": BREAKDOWN_TOLERANCE_RULE,
            "orthogonality_max_error": orthogonality_error,
            "off_tridiagonal_max_abs": off_error,
            "coupling_max_error": coupling_error,
        },
        "provenance": {
            "module": "chain_mapping",
            "module_version": MODULE_VERSION,
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "schema_version": SCHEMA_VERSION,
        },
    }


def derive_chain_mapping(bath_artifact: dict[str, Any]) -> dict[str, Any]:
    """Derive a canonical finite-chain mapping from a verified star bath."""
    bath.verify_bath_artifact(bath_artifact)
    payload = _mapping_payload(bath_artifact)
    return {
        "payload": payload,
        "sha256": hashlib.sha256(_canonical_json(payload)).hexdigest(),
    }


def _require_exact_keys(value: Any, expected: set[str], name: str) -> None:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a JSON object")
    if set(value) != expected:
        raise ValueError(f"{name} keys do not match schema")


def _verify_structure_and_digest(mapping: Any) -> None:
    _require_exact_keys(mapping, {"payload", "sha256"}, "mapping artifact")
    payload = mapping["payload"]
    _require_exact_keys(payload, _PAYLOAD_KEYS, "mapping payload")
    _require_exact_keys(
        payload["conventions"], set(_CONVENTIONS), "mapping conventions"
    )
    _require_exact_keys(
        payload["numerics"], _NUMERICS_KEYS, "mapping numerics"
    )
    _require_exact_keys(
        payload["provenance"], _PROVENANCE_KEYS, "mapping provenance"
    )
    digest = mapping["sha256"]
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("mapping SHA256 must be 64 lowercase hexadecimal digits")
    expected_digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    if not hmac.compare_digest(digest, expected_digest):
        raise ValueError("mapping payload SHA256 mismatch")


def verify_chain_mapping_artifact(
    mapping: Any, bath_artifact: dict[str, Any]
) -> None:
    """Verify mapping integrity, source linkage, and deterministic replay."""
    _verify_structure_and_digest(mapping)
    bath.verify_bath_artifact(bath_artifact)
    if mapping["payload"]["source_bath_sha256"] != bath_artifact["sha256"]:
        raise ValueError("mapping source bath SHA256 mismatch")
    expected = derive_chain_mapping(bath_artifact)
    if mapping != expected:
        raise ValueError("mapping scientific replay mismatch")


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    except BaseException:
        try:
            os.close(descriptor)
        except BaseException:
            pass
        raise
    os.close(descriptor)


def _hardlink_backup(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".backup",
    )
    os.close(descriptor)
    os.unlink(name)
    backup_path = Path(name)
    try:
        os.link(destination, backup_path, follow_symlinks=False)
        with backup_path.open("rb") as backup:
            os.fsync(backup.fileno())
    except BaseException:
        try:
            backup_path.unlink(missing_ok=True)
        except BaseException:
            pass
        raise
    return backup_path


def write_chain_mapping_json(
    path: str | os.PathLike[str],
    *,
    bath_artifact: dict[str, Any],
) -> dict[str, Any]:
    """Atomically write a canonical mapping artifact and return it."""
    destination = Path(path)
    mapping = derive_chain_mapping(bath_artifact)
    verify_chain_mapping_artifact(mapping, bath_artifact)
    encoded = _canonical_json(mapping) + b"\n"

    temporary_path: Path | None = None
    backup_path: Path | None = None
    published = False
    try:
        try:
            destination_status = destination.lstat()
        except FileNotFoundError:
            destination_status = None
        if destination_status is not None:
            if not stat.S_ISREG(destination_status.st_mode):
                raise ValueError(
                    "existing mapping destination must be a regular file, "
                    "not a directory, symlink, or special file"
                )
            backup_path = _hardlink_backup(destination)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, destination)
        published = True
        temporary_path = None
        _fsync_directory(destination.parent)
        if backup_path is not None:
            backup_path.unlink()
            backup_path = None
            _fsync_directory(destination.parent)
    except BaseException:
        if published:
            try:
                if backup_path is not None:
                    os.replace(backup_path, destination)
                    backup_path = None
                else:
                    destination.unlink(missing_ok=True)
                try:
                    _fsync_directory(destination.parent)
                except BaseException:
                    pass
            except BaseException:
                pass
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except BaseException:
                pass
        if backup_path is not None:
            try:
                backup_path.unlink(missing_ok=True)
            except BaseException:
                pass
        raise
    return mapping
