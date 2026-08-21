from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import math
import os
from pathlib import Path
import subprocess

import numpy as np
import quimb.tensor as qtn

from .pepo import FinitePEPO


_SCHEMA_VERSION = 1
_MODES = {"ordinary", "thermodynamic"}


@dataclass(frozen=True)
class Checkpoint:
    pepo: FinitePEPO
    beta: float
    mode: str
    log_scale: float
    config_sha256: str
    diagnostics: dict[str, object]
    path: Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_value(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _package_versions() -> dict[str, str]:
    result = {"numpy": np.__version__}
    for package in ("scipy", "quimb", "jax"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "unknown"
    return result


def _tensor_records(pepo: FinitePEPO):
    arrays = {}
    records = []
    for index, (x, y) in enumerate(
        (x, y) for x in range(pepo.lx) for y in range(pepo.ly)
    ):
        key = f"tensor_{index:04d}"
        tensor = pepo.tn[f"I{x},{y}"]
        arrays[key] = np.asarray(tensor.data)
        records.append(
            {
                "key": key,
                "site": [x, y],
                "inds": list(tensor.inds),
                "tags": sorted(tensor.tags),
            }
        )
    return arrays, records


def save_checkpoint(
    path: Path,
    pepo: FinitePEPO,
    *,
    beta: float,
    mode: str,
    log_scale: float,
    config_sha256: str,
    diagnostics: dict[str, object],
) -> Checkpoint:
    path = Path(path)
    marker = path / "metadata.json"
    if marker.exists():
        raise FileExistsError(f"completed checkpoint already exists: {path}")
    if not math.isfinite(beta) or beta <= 0:
        raise ValueError("checkpoint beta must be finite and positive")
    if mode not in _MODES:
        raise ValueError("checkpoint mode must be ordinary or thermodynamic")
    if not math.isfinite(log_scale):
        raise ValueError("checkpoint log scale must be finite")
    if not config_sha256:
        raise ValueError("configuration hash must be non-empty")
    if not isinstance(diagnostics, dict):
        raise TypeError("checkpoint diagnostics must be a dictionary")

    path.mkdir(parents=True, exist_ok=True)
    tensor_path = path / "tensors.npz"
    temporary_tensor = path / "tensors.npz.tmp"
    arrays, records = _tensor_records(pepo)
    with temporary_tensor.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
    os.replace(temporary_tensor, tensor_path)

    metadata = {
        "schema_version": _SCHEMA_VERSION,
        "lattice": {"lx": pepo.lx, "ly": pepo.ly},
        "beta": beta,
        "mode": mode,
        "log_scale": log_scale,
        "config_sha256": config_sha256,
        "tensor_sha256": _sha256(tensor_path),
        "tensors": records,
        "diagnostics": _json_value(diagnostics),
        "provenance": {
            "git_commit": _git_commit(),
            "packages": _package_versions(),
        },
    }
    temporary_marker = path / "metadata.json.tmp"
    temporary_marker.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_marker, marker)
    return load_checkpoint(path, expected_config_sha256=config_sha256)


def load_checkpoint(
    path: Path,
    *,
    expected_config_sha256: str,
) -> Checkpoint:
    path = Path(path)
    marker = path / "metadata.json"
    if not marker.exists():
        raise FileNotFoundError(f"checkpoint completion marker is missing: {path}")
    metadata = json.loads(marker.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("unsupported checkpoint schema")
    if metadata.get("config_sha256") != expected_config_sha256:
        raise ValueError("configuration hash mismatch")

    tensor_path = path / "tensors.npz"
    if not tensor_path.exists() or _sha256(tensor_path) != metadata.get(
        "tensor_sha256"
    ):
        raise ValueError("tensor hash mismatch")

    records = metadata.get("tensors")
    if not isinstance(records, list):
        raise ValueError("checkpoint tensor records are invalid")
    expected_keys = {record["key"] for record in records}
    tensors = []
    with np.load(tensor_path, allow_pickle=False) as payload:
        if set(payload.files) != expected_keys:
            raise ValueError("checkpoint tensor set mismatch")
        for record in records:
            tensors.append(
                qtn.Tensor(
                    np.array(payload[record["key"]], copy=True),
                    inds=tuple(record["inds"]),
                    tags=set(record["tags"]),
                )
            )

    lattice = metadata.get("lattice", {})
    lx = int(lattice["lx"])
    ly = int(lattice["ly"])
    if len(tensors) != lx * ly:
        raise ValueError("checkpoint lattice and tensor count disagree")
    mode = metadata.get("mode")
    if mode not in _MODES:
        raise ValueError("checkpoint mode is invalid")
    beta = float(metadata["beta"])
    log_scale = float(metadata["log_scale"])
    if not math.isfinite(beta) or beta <= 0 or not math.isfinite(log_scale):
        raise ValueError("checkpoint scalar metadata is invalid")
    diagnostics = metadata.get("diagnostics")
    if not isinstance(diagnostics, dict):
        raise ValueError("checkpoint diagnostics are invalid")

    return Checkpoint(
        pepo=FinitePEPO(lx=lx, ly=ly, tn=qtn.TensorNetwork(tensors)),
        beta=beta,
        mode=mode,
        log_scale=log_scale,
        config_sha256=expected_config_sha256,
        diagnostics=diagnostics,
        path=path,
    )


def latest_checkpoint(
    root: Path,
    *,
    expected_config_sha256: str,
) -> Checkpoint | None:
    root = Path(root)
    if not root.exists():
        return None
    completed = []
    for path in root.iterdir():
        if path.is_dir() and (path / "metadata.json").is_file():
            completed.append(
                load_checkpoint(
                    path,
                    expected_config_sha256=expected_config_sha256,
                )
            )
    if not completed:
        return None
    return max(completed, key=lambda checkpoint: checkpoint.beta)
