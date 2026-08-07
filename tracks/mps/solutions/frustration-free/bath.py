"""Deterministic discretization and serialization of a semicircular bath.

The JSON artifact's Gaussian broadening is a normalized visualization of the
finite-bath delta peaks.  Its deterministic width is ``D / (N_b + 1)``; it is
not the fitted semicircular continuum itself.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import numbers
import os
import platform
from pathlib import Path
import re
import stat
import tempfile
from types import MappingProxyType
from typing import Any, Sequence

import numpy as np


MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = 2
MODEL_PATH = Path(__file__).with_name("model.json")
BROADENING_KERNEL = "normalized_gaussian"
BROADENING_WIDTH_RULE = "bandwidth / (n_bath + 1)"
BROADENING_INTERPRETATION = (
    "broadened finite-bath realization; not the fitted continuum"
)
def load_model_definition() -> dict[str, Any]:
    raw = MODEL_PATH.read_bytes()
    if len(raw) > 64 * 1024:
        raise ValueError("model definition exceeds 64 KiB")
    definition = json.loads(raw)
    if not isinstance(definition, dict) or set(definition) != {
        "schema_version",
        "model_id",
        "parameters",
        "assertions",
        "conventions",
    }:
        raise ValueError("model definition keys do not match schema")
    if definition["schema_version"] != 1:
        raise ValueError("unsupported model definition schema")
    return definition


MODEL_DEFINITION = load_model_definition()
SUPPORTED_BATH_CONVENTIONS = MappingProxyType(
    {
        name: MODEL_DEFINITION["conventions"][name]
        for name in (
            "hybridization",
            "quadrature",
            "target_continuum",
            "ordering",
            "epsilon",
            "V_squared",
        )
    }
)
_VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+(?:[A-Za-z0-9_.+-]*)?")
_SEMANTIC_REL_TOLERANCE = 1e-13
_SEMANTIC_ABS_TOLERANCE = 1e-15


def _validate_parameters(
    gamma: float, bandwidth: float, n_bath: int
) -> tuple[float, float, int]:
    if isinstance(gamma, bool) or not isinstance(gamma, numbers.Real):
        raise TypeError("gamma must be a real number")
    if isinstance(bandwidth, bool) or not isinstance(bandwidth, numbers.Real):
        raise TypeError("bandwidth must be a real number")
    if isinstance(n_bath, bool) or not isinstance(n_bath, numbers.Integral):
        raise TypeError("n_bath must be a positive integer")

    gamma = float(gamma)
    bandwidth = float(bandwidth)
    n_bath = int(n_bath)
    if not math.isfinite(gamma) or gamma < 0.0:
        raise ValueError("gamma must be finite and nonnegative")
    if not math.isfinite(bandwidth) or bandwidth <= 0.0:
        raise ValueError("bandwidth must be finite and positive")
    if n_bath <= 0:
        raise ValueError("n_bath must be a positive integer")
    return gamma, bandwidth, n_bath


def discretize_semicircular_bath(
    *, gamma: float, bandwidth: float, n_bath: int
) -> tuple[list[float], list[float]]:
    """Return energies and nonnegative couplings in descending-energy order."""
    gamma, bandwidth, n_bath = _validate_parameters(
        gamma, bandwidth, n_bath
    )
    return _expected_discretization(gamma, bandwidth, n_bath)


def _expected_discretization(
    gamma: float, bandwidth: float, n_bath: int
) -> tuple[list[float], list[float]]:
    scale = gamma * bandwidth / (n_bath + 1)
    epsilon: list[float] = []
    coupling: list[float] = []
    for k in range(1, n_bath + 1):
        angle = k * math.pi / (n_bath + 1)
        epsilon.append(bandwidth * math.cos(angle))
        coupling.append(math.sqrt(scale * math.sin(angle) ** 2))
    return epsilon, coupling


def _validate_frequency_grid(frequency_grid: Sequence[float]) -> list[float]:
    if isinstance(frequency_grid, (str, bytes)) or not isinstance(
        frequency_grid, Sequence
    ):
        raise TypeError("frequency_grid must be a sequence of real numbers")
    if len(frequency_grid) < 2:
        raise ValueError("frequency_grid must contain at least two points")

    grid: list[float] = []
    for value in frequency_grid:
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError("frequency_grid values must be real numbers")
        converted = float(value)
        if not math.isfinite(converted):
            raise ValueError("frequency_grid values must be finite")
        grid.append(converted)
    if any(right <= left for left, right in zip(grid, grid[1:])):
        raise ValueError("frequency_grid must be strictly increasing")
    return grid


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _semicircular_target(
    gamma: float, bandwidth: float, grid: Sequence[float]
) -> list[float]:
    return [
        gamma * math.sqrt(max(0.0, 1.0 - (omega / bandwidth) ** 2))
        if abs(omega) <= bandwidth
        else 0.0
        for omega in grid
    ]


def _broadened_hybridization(
    epsilon: Sequence[float],
    coupling: Sequence[float],
    width: float,
    grid: Sequence[float],
) -> list[float]:
    normalization = 1.0 / (math.sqrt(2.0 * math.pi) * width)
    return [
        math.pi
        * math.fsum(
            value**2
            * normalization
            * math.exp(-0.5 * ((omega - energy) / width) ** 2)
            for energy, value in zip(epsilon, coupling)
        )
        for omega in grid
    ]


def make_bath_artifact(
    *,
    gamma: float,
    bandwidth: float,
    n_bath: int,
    frequency_grid: Sequence[float],
) -> dict[str, Any]:
    """Build a deterministic, integrity-auditable finite-bath artifact."""
    gamma, bandwidth, n_bath = _validate_parameters(
        gamma, bandwidth, n_bath
    )
    grid = _validate_frequency_grid(frequency_grid)
    epsilon, coupling = discretize_semicircular_bath(
        gamma=gamma, bandwidth=bandwidth, n_bath=n_bath
    )

    width = bandwidth / (n_bath + 1)
    broadened_finite_bath_hybridization = _broadened_hybridization(
        epsilon, coupling, width, grid
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "parameters": {
            "gamma": gamma,
            "bandwidth": bandwidth,
            "n_bath": n_bath,
        },
        "conventions": dict(SUPPORTED_BATH_CONVENTIONS),
        "provenance": {
            "module": "bath",
            "module_version": MODULE_VERSION,
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "schema_version": SCHEMA_VERSION,
        },
        "epsilon": epsilon,
        "V": coupling,
        "frequency_grid": grid,
        "target_continuum_hybridization": _semicircular_target(
            gamma, bandwidth, grid
        ),
        "broadening": {
            "kernel": BROADENING_KERNEL,
            "width": width,
            "width_rule": BROADENING_WIDTH_RULE,
            "interpretation": BROADENING_INTERPRETATION,
        },
        "broadened_finite_bath_hybridization": (
            broadened_finite_bath_hybridization
        ),
    }
    return {
        "payload": payload,
        "sha256": hashlib.sha256(_canonical_json(payload)).hexdigest(),
    }


def _require_keys(mapping: Any, keys: set[str], name: str) -> None:
    if not isinstance(mapping, dict):
        raise TypeError(f"{name} must be a JSON object")
    missing = keys - mapping.keys()
    if missing:
        raise ValueError(f"{name} missing required keys: {sorted(missing)}")


def _validate_numeric_array(
    values: Any, expected_length: int, name: str, *, nonnegative: bool = False
) -> None:
    if not isinstance(values, list) or len(values) != expected_length:
        raise ValueError(f"{name} must be a list of length {expected_length}")
    for value in values:
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"{name} values must be real numbers")
        if not math.isfinite(float(value)):
            raise ValueError(f"{name} values must be finite")
        if nonnegative and value < 0:
            raise ValueError(f"{name} values must be nonnegative")


def _validate_derived_array(
    actual: list[float], expected: list[float], name: str
) -> None:
    if any(
        not math.isclose(
            float(actual_value),
            expected_value,
            rel_tol=_SEMANTIC_REL_TOLERANCE,
            abs_tol=_SEMANTIC_ABS_TOLERANCE,
        )
        for actual_value, expected_value in zip(actual, expected)
    ):
        raise ValueError(f"{name} does not match the supported bath formulas")


def verify_bath_artifact(artifact: Any) -> None:
    """Validate artifact structure, schema, and canonical payload SHA256."""
    _require_keys(artifact, {"payload", "sha256"}, "artifact")
    payload = artifact["payload"]
    if not isinstance(payload, dict):
        raise TypeError("artifact payload must be a JSON object")
    digest = artifact["sha256"]
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("artifact SHA256 must be 64 lowercase hexadecimal digits")
    expected_digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    if not hmac.compare_digest(digest, expected_digest):
        raise ValueError("artifact payload SHA256 mismatch")

    required_payload_keys = {
        "schema_version",
        "parameters",
        "conventions",
        "provenance",
        "epsilon",
        "V",
        "frequency_grid",
        "target_continuum_hybridization",
        "broadening",
        "broadened_finite_bath_hybridization",
    }
    _require_keys(payload, required_payload_keys, "payload")
    if (
        type(payload["schema_version"]) is not int
        or payload["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError(
            f"unsupported schema version: {payload['schema_version']!r}"
        )

    _require_keys(
        payload["parameters"], {"gamma", "bandwidth", "n_bath"}, "parameters"
    )
    gamma, bandwidth, n_bath = _validate_parameters(
        payload["parameters"]["gamma"],
        payload["parameters"]["bandwidth"],
        payload["parameters"]["n_bath"],
    )
    grid = _validate_frequency_grid(payload["frequency_grid"])
    _require_keys(
        payload["conventions"],
        {
            "hybridization",
            "quadrature",
            "target_continuum",
            "ordering",
            "epsilon",
            "V_squared",
        },
        "conventions",
    )
    if payload["conventions"] != SUPPORTED_BATH_CONVENTIONS:
        raise ValueError("artifact conventions are malformed or unsupported")
    _require_keys(
        payload["provenance"],
        {
            "module",
            "module_version",
            "python_version",
            "numpy_version",
            "schema_version",
        },
        "provenance",
    )
    provenance = payload["provenance"]
    if (
        provenance["module"] != "bath"
        or type(provenance["schema_version"]) is not int
        or provenance["schema_version"] != SCHEMA_VERSION
        or any(
            not isinstance(provenance[name], str)
            or _VERSION_PATTERN.fullmatch(provenance[name]) is None
            for name in (
                "module_version",
                "python_version",
                "numpy_version",
            )
        )
    ):
        raise ValueError("artifact provenance is malformed or unsupported")
    _require_keys(
        payload["broadening"],
        {"kernel", "width", "width_rule", "interpretation"},
        "broadening",
    )
    broadening = payload["broadening"]
    width = broadening["width"]
    if (
        broadening["kernel"] != BROADENING_KERNEL
        or broadening["width_rule"] != BROADENING_WIDTH_RULE
        or broadening["interpretation"] != BROADENING_INTERPRETATION
        or isinstance(width, bool)
        or not isinstance(width, numbers.Real)
        or not math.isfinite(float(width))
        or width <= 0.0
        or float(width) != bandwidth / (n_bath + 1)
    ):
        raise ValueError("artifact broadening is malformed or unsupported")
    _validate_numeric_array(payload["epsilon"], n_bath, "epsilon")
    _validate_numeric_array(payload["V"], n_bath, "V", nonnegative=True)
    _validate_numeric_array(
        payload["target_continuum_hybridization"],
        len(grid),
        "target_continuum_hybridization",
        nonnegative=True,
    )
    _validate_numeric_array(
        payload["broadened_finite_bath_hybridization"],
        len(grid),
        "broadened_finite_bath_hybridization",
        nonnegative=True,
    )
    expected_epsilon, expected_coupling = _expected_discretization(
        gamma, bandwidth, n_bath
    )
    expected_target = _semicircular_target(gamma, bandwidth, grid)
    expected_broadened = _broadened_hybridization(
        expected_epsilon,
        expected_coupling,
        bandwidth / (n_bath + 1),
        grid,
    )
    _validate_derived_array(payload["epsilon"], expected_epsilon, "epsilon")
    _validate_derived_array(payload["V"], expected_coupling, "V")
    _validate_derived_array(
        payload["target_continuum_hybridization"],
        expected_target,
        "target_continuum_hybridization",
    )
    _validate_derived_array(
        payload["broadened_finite_bath_hybridization"],
        expected_broadened,
        "broadened_finite_bath_hybridization",
    )


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


def write_bath_json(
    path: str | os.PathLike[str],
    *,
    gamma: float,
    bandwidth: float,
    n_bath: int,
    frequency_grid: Sequence[float],
) -> dict[str, Any]:
    """Atomically write a canonical JSON bath artifact and return it."""
    destination = Path(path)
    artifact = make_bath_artifact(
        gamma=gamma,
        bandwidth=bandwidth,
        n_bath=n_bath,
        frequency_grid=frequency_grid,
    )
    encoded = _canonical_json(artifact) + b"\n"

    verify_bath_artifact(artifact)
    temporary_path: Path | None = None
    backup_path: Path | None = None
    published = False
    publication_irreversible = False
    try:
        try:
            destination_status = destination.lstat()
        except FileNotFoundError:
            destination_status = None
        if destination_status is not None:
            if not stat.S_ISREG(destination_status.st_mode):
                raise ValueError(
                    "existing destination must be a regular file, "
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
            publication_irreversible = True
            _fsync_directory(destination.parent)
    except BaseException:
        if published and not publication_irreversible:
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
    return artifact
