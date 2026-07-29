from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Never

import numpy as np

from .artifacts import CONVERSION_VERSION, load_verified_trajectory
from .counter_rng import RNG_VERSION
from .pilot import (
    PILOT_PROGRESS_MAX_BYTES,
    PILOT_RUN_SPEC_MAX_BYTES,
    PilotCell,
    load_pilot_run_spec,
)

ANALYSIS_SCHEMA = "challenge-194-p0-analysis-v1"
OBSERVABLE_COLUMNS: Mapping[str, int] = MappingProxyType(
    {
        "s1_fraction": 4,
        "s2_fraction": 5,
        "q_g": 8,
        "four_sector_crossing": 9,
    }
)
_OBSERVABLE_INDICES = tuple(OBSERVABLE_COLUMNS.values())


def _canonical_bytes(document: object) -> bytes:
    try:
        return (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("analysis document is not canonical finite JSON") from error


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _malformed(message: str) -> Never:
    raise RuntimeError(message)


def _bounded_payload(path: Path, maximum_size: int, description: str) -> bytes:
    if not path.is_file():
        raise RuntimeError(f"{description} is missing")
    size = path.stat().st_size
    if not 1 <= size <= maximum_size:
        raise RuntimeError(f"{description} exceeds its frozen size bound")
    payload = path.read_bytes()
    if len(payload) != size:
        raise RuntimeError(f"{description} changed while being read")
    return payload


def _canonical_document(payload: bytes, description: str) -> Mapping[str, object]:
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{description} is not valid JSON") from error
    if not isinstance(document, Mapping) or _canonical_bytes(document) != payload:
        raise RuntimeError(f"{description} is not canonical JSON")
    return document


@dataclass(frozen=True)
class PilotEstimate:
    sigma: float
    length: int
    kappa: float
    replica_count: int
    means: Mapping[str, float]
    standard_errors: Mapping[str, float]
    request_sha256: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "means", MappingProxyType(dict(self.means)))
        object.__setattr__(
            self,
            "standard_errors",
            MappingProxyType(dict(self.standard_errors)),
        )
        object.__setattr__(self, "request_sha256", tuple(self.request_sha256))

    def to_document(self) -> dict[str, object]:
        return {
            "sigma_hex": float(self.sigma).hex(),
            "length": self.length,
            "kappa_hex": float(self.kappa).hex(),
            "replica_count": self.replica_count,
            "means": dict(self.means),
            "standard_errors": dict(self.standard_errors),
            "request_sha256": list(self.request_sha256),
        }


def _protocol_axis(protocol: Mapping[str, object], name: str) -> Sequence[object]:
    value = protocol.get(name)
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _malformed(f"pilot protocol {name} axis is malformed")
    return value


def _validated_axes(
    spec: Mapping[str, object],
) -> tuple[tuple[float, ...], tuple[int, ...], tuple[int, ...], tuple[float, ...]]:
    protocol = spec.get("protocol")
    if not isinstance(protocol, Mapping):
        _malformed("pilot protocol is missing")
    try:
        sigmas = tuple(
            float.fromhex(str(value)) for value in _protocol_axis(protocol, "sigmas")
        )
        lengths = tuple(int(value) for value in _protocol_axis(protocol, "lengths"))
        replicas = tuple(int(value) for value in _protocol_axis(protocol, "replicas"))
        kappas = tuple(
            float.fromhex(str(value)) for value in _protocol_axis(protocol, "kappas")
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("pilot protocol axes are malformed") from error
    if protocol.get("loop_order") != ["sigma", "length", "replica"]:
        raise RuntimeError("pilot protocol loop order is not canonical")
    if len(replicas) < 2:
        raise RuntimeError(
            "missing replicas: sample standard errors require two replicas"
        )
    if len(set(replicas)) != len(replicas):
        raise RuntimeError("duplicate replicas in pilot protocol")
    if (
        not sigmas
        or not lengths
        or not kappas
        or len(set(sigmas)) != len(sigmas)
        or len(set(lengths)) != len(lengths)
        or len(set(kappas)) != len(kappas)
    ):
        raise RuntimeError("pilot protocol axes are empty or duplicate")
    return sigmas, lengths, replicas, kappas


def _validate_cells(
    spec: Mapping[str, object],
    sigmas: tuple[float, ...],
    lengths: tuple[int, ...],
    replicas: tuple[int, ...],
    kappas: tuple[float, ...],
) -> Sequence[object]:
    raw_cells = spec.get("cells")
    if isinstance(raw_cells, (str, bytes)) or not isinstance(raw_cells, Sequence):
        _malformed("pilot cells are malformed")
    expected_count = len(sigmas) * len(lengths) * len(replicas)
    if len(raw_cells) != expected_count:
        raise RuntimeError("missing replicas: pilot cell cardinality is incomplete")
    seen: set[tuple[float, int, int]] = set()
    expected_identities = (
        (sigma, length, replica)
        for sigma in sigmas
        for length in lengths
        for replica in replicas
    )
    for index, (raw, expected_identity) in enumerate(
        zip(raw_cells, expected_identities, strict=True)
    ):
        if not isinstance(raw, Mapping):
            _malformed("pilot cell is malformed")
        cell = PilotCell.from_document(raw)
        identity = (cell.sigma, cell.length, cell.replica)
        if identity in seen:
            raise RuntimeError("duplicate replica in pilot cells")
        seen.add(identity)
        if (
            identity != expected_identity
            or cell.cell_index != index
            or cell.kappas != kappas
        ):
            raise RuntimeError("pilot cells are not in canonical protocol order")
    return raw_cells


def _expected_provenance(spec: Mapping[str, object], cell: PilotCell) -> dict[str, str]:
    return {
        "request_sha256": cell.request_sha256,
        "kernel_sha256": cell.kernel_sha256,
        "source_revision": str(spec["orchestration_revision"]),
        "uv_lock_sha256": str(spec["uv_lock_sha256"]),
        "runtime_capability_sha256": str(spec["runtime_capability_sha256"]),
        "analysis_plan_sha256": str(spec["analysis_plan_sha256"]),
        "rng_sha256": str(spec["rng_assignment_sha256"]),
        "conversion_version": CONVERSION_VERSION,
        "rng_version": RNG_VERSION,
    }


def _trajectory_path(root: Path, cell: PilotCell) -> Path:
    expected_run_path = f"cells/{cell.cell_id}/run"
    if cell.run_path != expected_run_path:
        raise RuntimeError("pilot cell run path is not canonical")
    return (
        root
        / expected_run_path
        / "trajectories"
        / f"trajectory-{cell.request_sha256}.h5"
    )


def _validate_progress(
    progress: Mapping[str, object],
    spec: Mapping[str, object],
    raw_cells: Sequence[object],
) -> None:
    progress_cells = progress.get("cells")
    if (
        progress.get("run_spec_sha256") != spec.get("run_spec_sha256")
        or progress.get("cell_count") != len(raw_cells)
        or progress.get("trajectory_count") != len(raw_cells)
        or isinstance(progress_cells, (str, bytes))
        or not isinstance(progress_cells, Sequence)
        or len(progress_cells) != len(raw_cells)
    ):
        raise RuntimeError("P0 progress is incomplete or bound to another run")
    for raw_cell, raw_progress in zip(raw_cells, progress_cells, strict=True):
        if not isinstance(raw_cell, Mapping) or not isinstance(raw_progress, Mapping):
            _malformed("P0 progress cell is malformed")
        for key in ("cell_index", "cell_id", "manifest_path", "request_sha256"):
            if raw_progress.get(key) != raw_cell.get(key):
                raise RuntimeError("P0 progress cell order or identity is stale")


def _group_estimates(
    sigma: float,
    length: int,
    kappas: tuple[float, ...],
    values: np.ndarray,
    request_sha256: tuple[str, ...],
) -> list[PilotEstimate]:
    replica_count = values.shape[0]
    means = np.mean(values, axis=0)
    standard_errors = np.std(values, axis=0, ddof=1) / math.sqrt(replica_count)
    estimates: list[PilotEstimate] = []
    names = tuple(OBSERVABLE_COLUMNS)
    for kappa_index, kappa in enumerate(kappas):
        estimates.append(
            PilotEstimate(
                sigma=sigma,
                length=length,
                kappa=kappa,
                replica_count=replica_count,
                means={
                    name: float(means[kappa_index, observable_index])
                    for observable_index, name in enumerate(names)
                },
                standard_errors={
                    name: float(standard_errors[kappa_index, observable_index])
                    for observable_index, name in enumerate(names)
                },
                request_sha256=request_sha256,
            )
        )
    return estimates


def aggregate_p0(run_spec: Path) -> dict[str, object]:
    if not isinstance(run_spec, Path) or not run_spec.is_absolute():
        raise RuntimeError("P0 run spec path must be absolute")
    run_spec_payload = _bounded_payload(
        run_spec, PILOT_RUN_SPEC_MAX_BYTES, "P0 run spec"
    )
    progress_path = run_spec.parent / "progress.json"
    progress_payload = _bounded_payload(
        progress_path, PILOT_PROGRESS_MAX_BYTES, "P0 progress"
    )
    progress = _canonical_document(progress_payload, "P0 progress")
    spec = load_pilot_run_spec(run_spec, False)
    sigmas, lengths, replicas, kappas = _validated_axes(spec)
    raw_cells = _validate_cells(spec, sigmas, lengths, replicas, kappas)
    _validate_progress(progress, spec, raw_cells)

    estimates: list[dict[str, object]] = []
    cell_index = 0
    for sigma in sigmas:
        for length in lengths:
            values = np.empty(
                (len(replicas), len(kappas), len(OBSERVABLE_COLUMNS)),
                dtype=np.float64,
            )
            request_hashes: list[str] = []
            for _replica in replicas:
                raw_cell = raw_cells[cell_index]
                if not isinstance(raw_cell, Mapping):  # validated above
                    _malformed("pilot cell is malformed")
                cell = PilotCell.from_document(raw_cell)
                result = load_verified_trajectory(
                    _trajectory_path(run_spec.parent, cell),
                    _expected_provenance(spec, cell),
                )
                if (
                    result.observables.shape != (len(kappas), 10)
                    or not np.isfinite(result.observables).all()
                ):
                    raise RuntimeError("verified trajectory observables are malformed")
                values[len(request_hashes), :, :] = result.observables[
                    :, _OBSERVABLE_INDICES
                ]
                request_hashes.append(cell.request_sha256)
                cell_index += 1
                del result
            estimates.extend(
                estimate.to_document()
                for estimate in _group_estimates(
                    sigma,
                    length,
                    kappas,
                    values,
                    tuple(request_hashes),
                )
            )

    if (
        _bounded_payload(run_spec, PILOT_RUN_SPEC_MAX_BYTES, "P0 run spec")
        != run_spec_payload
        or _bounded_payload(progress_path, PILOT_PROGRESS_MAX_BYTES, "P0 progress")
        != progress_payload
    ):
        raise RuntimeError("P0 sources changed during aggregation")
    document: dict[str, object] = {
        "schema_version": ANALYSIS_SCHEMA,
        "p0_run_spec_sha256": _sha256(run_spec_payload),
        "p0_progress_sha256": _sha256(progress_payload),
        "source_revision": spec["orchestration_revision"],
        "analysis_plan_sha256": spec["analysis_plan_sha256"],
        "observable_columns": dict(OBSERVABLE_COLUMNS),
        "estimates": estimates,
    }
    document["analysis_document_sha256"] = _sha256(_canonical_bytes(document))
    return document
