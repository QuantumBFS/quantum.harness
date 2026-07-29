from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Never

import numpy as np

from . import pilot as _pilot
from .pilot import PilotCell

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


def _aggregate_p0(
    run_spec: Path,
    *,
    production: bool,
    _snapshot_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if not isinstance(run_spec, Path) or not run_spec.is_absolute():
        raise RuntimeError("P0 run spec path must be absolute")
    with _pilot._open_verified_pilot_analysis_snapshot(
        run_spec,
        production=production,
        _snapshot_hook=_snapshot_hook,
    ) as snapshot:
        spec = snapshot.spec
        sigmas, lengths, replicas, kappas = _validated_axes(spec)
        raw_cells = _validate_cells(spec, sigmas, lengths, replicas, kappas)

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
                    result = snapshot.load_trajectory(cell_index)
                    if (
                        result.observables.shape != (len(kappas), 10)
                        or not np.isfinite(result.observables).all()
                    ):
                        raise RuntimeError(
                            "verified trajectory observables are malformed"
                        )
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

        document: dict[str, object] = {
            "schema_version": ANALYSIS_SCHEMA,
            "p0_run_spec_sha256": _sha256(snapshot.run_spec_payload),
            "p0_progress_sha256": _sha256(snapshot.progress_payload),
            "source_revision": spec["orchestration_revision"],
            "analysis_plan_sha256": spec["analysis_plan_sha256"],
            "observable_columns": dict(OBSERVABLE_COLUMNS),
            "estimates": estimates,
        }
        document["analysis_document_sha256"] = _sha256(_canonical_bytes(document))
        return document


def aggregate_p0(run_spec: Path) -> dict[str, object]:
    return _aggregate_p0(run_spec, production=True)


def _aggregate_test_p0(
    run_spec: Path,
    *,
    _snapshot_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    return _aggregate_p0(
        run_spec,
        production=False,
        _snapshot_hook=_snapshot_hook,
    )
