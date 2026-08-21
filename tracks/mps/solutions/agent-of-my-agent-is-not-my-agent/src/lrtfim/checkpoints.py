"""Atomic, provenance-checked TeNPy MPS checkpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from tenpy.networks.mps import MPS
from tenpy.tools import hdf5_io


CHECKPOINT_FORMAT_VERSION = 1


class CheckpointMismatch(ValueError):
    """Raised when a checkpoint cannot initialize the requested calculation."""


@dataclass(frozen=True)
class CheckpointProvenance:
    sigma: float | None
    length: int
    gamma: float
    num_exponentials: int
    alpha: float
    r_fit: int
    sector: str
    requested_chi: int
    reached_chi: int
    sweep_statistics: dict[str, Any]
    code_hash: str
    fit_hash: str
    active_channels: tuple[int, ...]


def code_tree_hash(
    project_root: Path,
    source_directories: tuple[str, ...] = ("src", "scripts"),
) -> str:
    """Hash runnable source content, including files not yet tracked by git."""
    root = Path(project_root)
    digest = hashlib.sha256()
    files = sorted(
        path
        for directory in source_directories
        for path in (root / directory).rglob("*.py")
        if path.is_file()
    )
    for path in files:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _canonical_provenance(provenance: CheckpointProvenance) -> dict:
    return _json_safe(asdict(provenance))


def _provenance_id(provenance: dict) -> str:
    payload = json.dumps(provenance, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def mps_lattice_fingerprint(psi: MPS) -> str:
    """Hash the finite-chain site and charge structure of an MPS."""
    sites = []
    for site in psi.sites:
        sites.append(
            {
                "class": type(site).__name__,
                "dimension": int(site.dim),
                "conserve": site.conserve,
                "charge_info": repr(site.leg.chinfo),
                "state_labels": sorted(
                    (str(label), int(index))
                    for label, index in site.state_labels.items()
                ),
            }
        )
    payload = {
        "length": int(psi.L),
        "boundary_condition": psi.bc,
        "sites": sites,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def save_checkpoint(
    directory: Path,
    psi: MPS,
    provenance: CheckpointProvenance,
    diagnostics: dict,
) -> None:
    """Atomically publish an MPS and its complete provenance sidecar."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    state_path = directory / "state.h5"
    metadata_path = directory / "checkpoint.json"
    state_tmp = directory / "state.tmp.h5"
    metadata_tmp = directory / "checkpoint.json.tmp"
    stored = _canonical_provenance(provenance)
    metadata = {
        "format_version": CHECKPOINT_FORMAT_VERSION,
        "status": "success",
        "provenance_id": _provenance_id(stored),
        "provenance": stored,
        "diagnostics": _json_safe(diagnostics),
    }
    try:
        hdf5_io.save(psi, state_tmp)
        metadata_tmp.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        state_tmp.replace(state_path)
        metadata_tmp.replace(metadata_path)
    finally:
        state_tmp.unlink(missing_ok=True)
        metadata_tmp.unlink(missing_ok=True)


def _validate_provenance(
    stored: dict,
    expected: CheckpointProvenance,
    *,
    allow_gamma_continuation: bool,
) -> None:
    requested = _canonical_provenance(expected)
    invariant_fields = (
        "sigma",
        "length",
        "num_exponentials",
        "alpha",
        "r_fit",
        "sector",
        "code_hash",
        "fit_hash",
        "active_channels",
    )
    if not allow_gamma_continuation and stored.get("gamma") != requested["gamma"]:
        raise CheckpointMismatch(
            f"gamma mismatch: stored={stored.get('gamma')!r}, "
            f"requested={requested['gamma']!r}"
        )
    for field in invariant_fields:
        if stored.get(field) != requested[field]:
            raise CheckpointMismatch(
                f"{field} mismatch: stored={stored.get(field)!r}, "
                f"requested={requested[field]!r}"
            )
    if int(requested["requested_chi"]) < int(stored["reached_chi"]):
        raise CheckpointMismatch(
            "requested_chi is below the checkpoint's reached chi: "
            f"{requested['requested_chi']} < {stored['reached_chi']}"
        )


def load_checkpoint(
    directory: Path,
    expected: CheckpointProvenance,
    *,
    allow_gamma_continuation: bool = False,
) -> tuple[MPS, dict]:
    """Load a compatible successful checkpoint or fail closed."""
    directory = Path(directory)
    metadata_path = directory / "checkpoint.json"
    state_path = directory / "state.h5"
    if not metadata_path.is_file() or not state_path.is_file():
        raise CheckpointMismatch("checkpoint files are incomplete")
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("format_version") != CHECKPOINT_FORMAT_VERSION:
        raise CheckpointMismatch("checkpoint format_version mismatch")
    if metadata.get("status") != "success":
        raise CheckpointMismatch("checkpoint status is not success")
    stored = metadata.get("provenance", {})
    if metadata.get("provenance_id") != _provenance_id(stored):
        raise CheckpointMismatch("checkpoint provenance_id mismatch")
    _validate_provenance(
        stored,
        expected,
        allow_gamma_continuation=allow_gamma_continuation,
    )
    psi = hdf5_io.load(state_path)
    if not isinstance(psi, MPS):
        raise CheckpointMismatch("state.h5 does not contain a TeNPy MPS")
    if psi.L != expected.length:
        raise CheckpointMismatch(
            f"length mismatch in MPS: stored={psi.L}, requested={expected.length}"
        )
    expected_charge = 0 if expected.sector == "even" else 1
    total_charge = np.asarray(
        psi.get_total_charge(only_physical_legs=True),
        dtype=int,
    )
    if len(total_charge) != 1 or int(total_charge[0]) % 2 != expected_charge:
        raise CheckpointMismatch("sector mismatch in serialized MPS")
    return psi, metadata


def load_initialization_checkpoint(
    directory: Path,
    expected: CheckpointProvenance,
    *,
    coefficient_hash: str,
    operator_convention: str,
    lattice_fingerprint: str,
) -> tuple[MPS, dict]:
    """Load a physically identical state while auditing a code-hash change."""
    directory = Path(directory)
    metadata_path = directory / "checkpoint.json"
    state_path = directory / "state.h5"
    if not metadata_path.is_file() or not state_path.is_file():
        raise CheckpointMismatch("checkpoint files are incomplete")
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("format_version") != CHECKPOINT_FORMAT_VERSION:
        raise CheckpointMismatch("checkpoint format_version mismatch")
    if metadata.get("status") != "success":
        raise CheckpointMismatch("checkpoint status is not success")
    stored = metadata.get("provenance", {})
    if metadata.get("provenance_id") != _provenance_id(stored):
        raise CheckpointMismatch("checkpoint provenance_id mismatch")

    requested = _canonical_provenance(expected)
    physical_fields = (
        "sigma",
        "length",
        "gamma",
        "num_exponentials",
        "alpha",
        "r_fit",
        "sector",
        "fit_hash",
        "active_channels",
    )
    for field in physical_fields:
        if stored.get(field) != requested[field]:
            raise CheckpointMismatch(
                f"{field} mismatch: stored={stored.get(field)!r}, "
                f"requested={requested[field]!r}"
            )
    if int(requested["requested_chi"]) < int(stored["reached_chi"]):
        raise CheckpointMismatch(
            "requested_chi is below the checkpoint's reached chi: "
            f"{requested['requested_chi']} < {stored['reached_chi']}"
        )

    psi = hdf5_io.load(state_path)
    if not isinstance(psi, MPS):
        raise CheckpointMismatch("state.h5 does not contain a TeNPy MPS")
    actual_lattice = mps_lattice_fingerprint(psi)
    if actual_lattice != lattice_fingerprint:
        raise CheckpointMismatch(
            "lattice fingerprint mismatch: "
            f"stored={actual_lattice!r}, requested={lattice_fingerprint!r}"
        )
    expected_charge = 0 if expected.sector == "even" else 1
    total_charge = np.asarray(
        psi.get_total_charge(only_physical_legs=True),
        dtype=int,
    )
    if len(total_charge) != 1 or int(total_charge[0]) % 2 != expected_charge:
        raise CheckpointMismatch("sector mismatch in serialized MPS")

    audit = {
        "mode": "audited_initialization_only",
        "source_provenance_id": metadata["provenance_id"],
        "checkpoint_code_hash": stored.get("code_hash"),
        "current_code_hash": requested["code_hash"],
        "coefficient_hash": coefficient_hash,
        "operator_convention": operator_convention,
        "lattice_fingerprint": actual_lattice,
        "fully_reoptimize_required": True,
    }
    return psi, audit
