from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from types import MappingProxyType
from typing import Never

import numpy as np

from . import pilot as _pilot
from .counter_rng import STREAM_COUNT, StreamIdentity, derive_stream_material
from .kernel import periodic_kernel
from .pilot import PilotCell
from .trajectory import TrajectoryRequest, request_digest

ANALYSIS_SCHEMA = "challenge-194-p0-analysis-v1"
BRACKET_SCHEMA = "challenge-194-p1-brackets-v1"
P1_PROTOCOL_SCHEMA = "challenge-194-p1-protocol-v1"
P1_MASTER_SEED = 19_420_261_729
P1_REPLICAS = tuple(range(8, 24))
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
    snapshot_parent: Path | None = None,
    _snapshot_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if not isinstance(run_spec, Path) or not run_spec.is_absolute():
        raise RuntimeError("P0 run spec path must be absolute")
    with _pilot._open_verified_pilot_analysis_snapshot(
        run_spec,
        production=production,
        snapshot_parent=snapshot_parent,
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


def aggregate_p0(
    run_spec: Path,
    *,
    snapshot_parent: Path | None = None,
) -> dict[str, object]:
    return _aggregate_p0(
        run_spec,
        production=True,
        snapshot_parent=snapshot_parent,
    )


def _aggregate_test_p0(
    run_spec: Path,
    *,
    snapshot_parent: Path | None = None,
    _snapshot_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    return _aggregate_p0(
        run_spec,
        production=False,
        snapshot_parent=snapshot_parent,
        _snapshot_hook=_snapshot_hook,
    )


def _exact_hex_value(raw: object, name: str) -> float:
    try:
        value = float.fromhex(str(raw))
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"analysis {name} is malformed") from error
    if not math.isfinite(value) or value.hex() != raw:
        raise RuntimeError(f"analysis {name} is not canonical finite binary64")
    return value


def _selector_estimates(
    analysis: Mapping[str, object],
) -> tuple[
    tuple[float, ...],
    tuple[int, ...],
    tuple[float, ...],
    dict[tuple[float, int, float], tuple[float, float]],
]:
    if analysis.get("schema_version") != ANALYSIS_SCHEMA:
        raise RuntimeError("analysis schema version is not supported")
    raw_estimates = analysis.get("estimates")
    if isinstance(raw_estimates, (str, bytes)) or not isinstance(
        raw_estimates, Sequence
    ):
        _malformed("analysis estimates are malformed")

    identities: list[tuple[float, int, float]] = []
    values: dict[tuple[float, int, float], tuple[float, float]] = {}
    sigmas: list[float] = []
    lengths: list[int] = []
    kappas: list[float] = []
    for raw in raw_estimates:
        if not isinstance(raw, Mapping):
            _malformed("analysis estimate is malformed")
        sigma = _exact_hex_value(raw.get("sigma_hex"), "sigma")
        kappa = _exact_hex_value(raw.get("kappa_hex"), "coupling")
        length = raw.get("length")
        if not isinstance(length, int) or isinstance(length, bool) or length <= 0:
            _malformed("analysis length is malformed")
        means = raw.get("means")
        if not isinstance(means, Mapping):
            _malformed("analysis estimate means are malformed")
        observables: list[float] = []
        for name in ("q_g", "four_sector_crossing"):
            value = means.get(name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                _malformed(f"analysis {name} mean is malformed")
            value = float(value)
            if not math.isfinite(value):
                raise RuntimeError("analysis estimator means must be finite")
            observables.append(value)
        identity = (sigma, length, kappa)
        if identity in values:
            raise RuntimeError("analysis contains duplicate estimates")
        identities.append(identity)
        values[identity] = (observables[0], observables[1])
        if sigma not in sigmas:
            sigmas.append(sigma)
        if length not in lengths:
            lengths.append(length)
        if kappa not in kappas:
            kappas.append(kappa)

    if len(lengths) < 2:
        raise RuntimeError("analysis lacks two largest sizes")
    if (
        not kappas
        or kappas[0] != 0.0
        or any(right <= left for left, right in pairwise(kappas))
    ):
        raise RuntimeError("analysis estimates are not in canonical coupling order")
    expected = [
        (sigma, length, kappa)
        for sigma in sigmas
        for length in lengths
        for kappa in kappas
    ]
    if identities != expected:
        if len(identities) != len(expected):
            raise RuntimeError("analysis is missing largest-size estimates")
        raise RuntimeError("analysis estimates are not in canonical coupling order")

    digest = analysis.get("analysis_document_sha256")
    if not isinstance(digest, str):
        _malformed("analysis document digest is malformed")
    unsigned = dict(analysis)
    unsigned.pop("analysis_document_sha256", None)
    if _sha256(_canonical_bytes(unsigned)) != digest:
        raise RuntimeError("analysis document digest mismatch")
    return tuple(sigmas), tuple(lengths), tuple(kappas), values


def _sign_change(left: float, right: float) -> bool:
    return (left <= 0.0 <= right) or (right <= 0.0 <= left)


def _transition_evidence(
    sigma: float,
    lengths: tuple[int, int],
    kappas: tuple[float, ...],
    values: Mapping[tuple[float, int, float], tuple[float, float]],
    interval_index: int,
) -> tuple[bool, bool, dict[str, object]]:
    lower = kappas[interval_index]
    upper = kappas[interval_index + 1]
    q_endpoints: list[list[str]] = []
    crossing_endpoints: list[list[str]] = []
    q_differences: list[float] = []
    crossing_marked = False
    for kappa in (lower, upper):
        small = values[(sigma, lengths[0], kappa)]
        large = values[(sigma, lengths[1], kappa)]
        q_differences.append(small[0] - large[0])
        q_endpoints.append([small[0].hex(), large[0].hex()])
        crossing_endpoints.append([small[1].hex(), large[1].hex()])
    for length_index in range(2):
        endpoints = (
            float.fromhex(crossing_endpoints[0][length_index]),
            float.fromhex(crossing_endpoints[1][length_index]),
        )
        crossing_marked |= min(endpoints) <= 0.25 and max(endpoints) >= 0.75
    q_marked = _sign_change(q_differences[0], q_differences[1])
    return (
        q_marked,
        crossing_marked,
        {
            "q_g": {
                "marked": q_marked,
                "largest_size_difference_hex": [value.hex() for value in q_differences],
                "endpoint_means_hex": q_endpoints,
            },
            "four_sector_crossing": {
                "marked": crossing_marked,
                "closed_target_range_hex": [(0.25).hex(), (0.75).hex()],
                "endpoint_means_hex": crossing_endpoints,
            },
        },
    )


def _select_transition_bracket(
    sigma: float,
    lengths: tuple[int, int],
    kappas: tuple[float, ...],
    values: Mapping[tuple[float, int, float], tuple[float, float]],
) -> dict[str, object]:
    candidates: list[tuple[float, float, int, dict[str, object]]] = []
    zero_interval_is_common = False
    for interval_index in range(len(kappas) - 1):
        q_marked, crossing_marked, evidence = _transition_evidence(
            sigma, lengths, kappas, values, interval_index
        )
        if not (q_marked and crossing_marked):
            continue
        if kappas[interval_index] == 0.0:
            zero_interval_is_common = True
            continue
        candidates.append(
            (
                kappas[interval_index + 1] - kappas[interval_index],
                kappas[interval_index],
                interval_index,
                evidence,
            )
        )
    if not candidates:
        if zero_interval_is_common:
            raise RuntimeError("zero-coupling interval cannot be selected")
        return {
            "sigma_hex": sigma.hex(),
            "status": "requires_p0_extension",
            "reason": "no_nonzero_interval_marked_by_both_estimators",
            "lengths": list(lengths),
        }
    width, lower, interval_index, evidence = min(
        candidates, key=lambda candidate: (candidate[0], candidate[1])
    )
    return {
        "sigma_hex": sigma.hex(),
        "status": "selected",
        "purpose": "transition_refinement",
        "lower_kappa_hex": lower.hex(),
        "upper_kappa_hex": kappas[interval_index + 1].hex(),
        "lengths": list(lengths),
        "estimator_evidence": evidence,
        "tie_break": {
            "rule": "narrowest_interval_then_lower_coupling",
            "candidate_count": len(candidates),
            "selected_width_hex": width.hex(),
        },
    }


def _select_crossover_bracket(
    sigma: float,
    lengths: tuple[int, int],
    kappas: tuple[float, ...],
    values: Mapping[tuple[float, int, float], tuple[float, float]],
) -> dict[str, object]:
    largest = lengths[1]
    candidates: list[tuple[float, float, int, float, float]] = []
    for interval_index in range(1, len(kappas) - 1):
        lower = kappas[interval_index]
        upper = kappas[interval_index + 1]
        left = values[(sigma, largest, lower)][1]
        right = values[(sigma, largest, upper)][1]
        slope = abs(right - left) / (upper - lower)
        candidates.append((-slope, lower, interval_index, left, right))
    if not candidates:
        raise RuntimeError("no nonzero crossover interval is available")
    negative_slope, lower, interval_index, left, right = min(candidates)
    slope = -negative_slope
    return {
        "sigma_hex": sigma.hex(),
        "status": "selected",
        "purpose": "crossover_refinement",
        "lower_kappa_hex": lower.hex(),
        "upper_kappa_hex": kappas[interval_index + 1].hex(),
        "lengths": list(lengths),
        "estimator_evidence": {
            "estimator": "largest_size_four_sector_crossing",
            "largest_length": largest,
            "endpoint_means_hex": [left.hex(), right.hex()],
            "absolute_slope_hex": slope.hex(),
        },
        "tie_break": {
            "rule": "maximum_absolute_slope_then_lower_coupling",
            "candidate_count": len(candidates),
        },
    }


def select_p1_brackets(analysis: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(analysis, Mapping):
        _malformed("analysis document is malformed")
    sigmas, all_lengths, kappas, values = _selector_estimates(analysis)
    lengths = (all_lengths[-2], all_lengths[-1])
    brackets = [
        (
            _select_transition_bracket(sigma, lengths, kappas, values)
            if sigma <= 1.0
            else _select_crossover_bracket(sigma, lengths, kappas, values)
        )
        for sigma in sigmas
    ]
    document: dict[str, object] = {
        "schema_version": BRACKET_SCHEMA,
        "source_analysis_document_sha256": analysis["analysis_document_sha256"],
        "requires_p0_extension": any(
            bracket["status"] == "requires_p0_extension" for bracket in brackets
        ),
        "brackets": brackets,
    }
    document["bracket_document_sha256"] = _sha256(_canonical_bytes(document))
    return document


def _validate_bracket_document(
    analysis: Mapping[str, object],
    brackets: Mapping[str, object],
) -> Sequence[object]:
    if brackets.get("schema_version") != BRACKET_SCHEMA:
        raise RuntimeError("bracket schema version is not supported")
    if brackets.get("source_analysis_document_sha256") != analysis.get(
        "analysis_document_sha256"
    ):
        raise RuntimeError("bracket document is not bound to the analysis")
    digest = brackets.get("bracket_document_sha256")
    if not isinstance(digest, str):
        _malformed("bracket document digest is malformed")
    unsigned = dict(brackets)
    unsigned.pop("bracket_document_sha256", None)
    if _sha256(_canonical_bytes(unsigned)) != digest:
        raise RuntimeError("bracket document digest mismatch")
    raw = brackets.get("brackets")
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        _malformed("bracket entries are malformed")
    extension_sigmas = [
        str(entry.get("sigma_hex"))
        for entry in raw
        if isinstance(entry, Mapping) and entry.get("status") == "requires_p0_extension"
    ]
    if brackets.get("requires_p0_extension") is True or extension_sigmas:
        labels = ", ".join(str(float.fromhex(value)) for value in extension_sigmas)
        raise RuntimeError(f"P0 extension required before P1 publication: {labels}")
    return raw


def _recursive_binary64_grid(lower: float, upper: float) -> tuple[float, ...]:
    if (
        not math.isfinite(lower)
        or not math.isfinite(upper)
        or lower <= 0.0
        or upper <= lower
    ):
        raise RuntimeError("P1 bracket endpoints are invalid")
    points = [lower, upper]
    for _level in range(3):
        previous = sorted(points)
        points.extend(left + (right - left) / 2.0 for left, right in pairwise(previous))
    ordered = tuple(sorted({value.hex(): value for value in points}.values()))
    if (
        len(ordered) != 9
        or ordered[0] != lower
        or ordered[-1] != upper
        or any(right <= left for left, right in pairwise(ordered))
    ):
        raise RuntimeError("P1 bracket cannot produce nine unique binary64 points")
    return ordered


def _p1_stream_hashes(
    length: int,
    sigma_grid_id: str,
    replica: int,
) -> tuple[str, ...]:
    return tuple(
        derive_stream_material(
            StreamIdentity(
                master_seed=P1_MASTER_SEED,
                phase="pilot",
                length=length,
                sigma_grid_id=sigma_grid_id,
                replica=replica,
                stream_id=stream,
            )
        ).material_sha256
        for stream in range(STREAM_COUNT)
    )


def build_p1_protocol(
    analysis: Mapping[str, object],
    brackets: Mapping[str, object] | None = None,
) -> dict[str, object]:
    sigmas, lengths, _p0_kappas, _values = _selector_estimates(analysis)
    if len(sigmas) != 4 or len(lengths) != 3:
        raise RuntimeError("P1 requires exactly four sigmas and three lengths")
    bracket_document = select_p1_brackets(analysis) if brackets is None else brackets
    raw_brackets = _validate_bracket_document(analysis, bracket_document)
    if len(raw_brackets) != len(sigmas):
        raise RuntimeError("P1 requires one bracket per sigma")

    sigma_entries: list[dict[str, object]] = []
    grids: dict[float, tuple[float, ...]] = {}
    grid_ids: dict[float, str] = {}
    for sigma, raw in zip(sigmas, raw_brackets, strict=True):
        if not isinstance(raw, Mapping):
            _malformed("bracket entry is malformed")
        raw_sigma = _exact_hex_value(raw.get("sigma_hex"), "bracket sigma")
        if raw_sigma != sigma or raw.get("status") != "selected":
            raise RuntimeError("bracket entries are not in canonical sigma order")
        lower = _exact_hex_value(raw.get("lower_kappa_hex"), "lower bracket")
        upper = _exact_hex_value(raw.get("upper_kappa_hex"), "upper bracket")
        grid = _recursive_binary64_grid(lower, upper)
        grid_id = (
            f"pilot-p1-v1|sigma-f64={sigma.hex()}|"
            f"analysis={analysis['analysis_document_sha256']}"
        )
        grids[sigma] = grid
        grid_ids[sigma] = grid_id
        sigma_entries.append(
            {
                "sigma_hex": sigma.hex(),
                "purpose": raw.get("purpose"),
                "lower_kappa_hex": lower.hex(),
                "upper_kappa_hex": upper.hex(),
                "kappas": [value.hex() for value in grid],
                "sigma_grid_id": grid_id,
            }
        )

    cells: list[dict[str, object]] = []
    assignments: list[dict[str, object]] = []
    request_ids: set[str] = set()
    stream_ids: set[str] = set()
    for sigma in sigmas:
        grid = grids[sigma]
        grid_id = grid_ids[sigma]
        for length in lengths:
            kernel = periodic_kernel(length, sigma)
            kernel_sha256 = _sha256(kernel.astype("<f8", copy=False).tobytes(order="C"))
            for replica in P1_REPLICAS:
                request = TrajectoryRequest(
                    length=length,
                    sigma=sigma,
                    sigma_grid_id=grid_id,
                    kappas=np.asarray(grid, dtype=np.float64),
                    master_seed=P1_MASTER_SEED,
                    phase="pilot",
                    replica=replica,
                    kernel_sha256=kernel_sha256,
                )
                request_sha256 = request_digest(request)
                streams = _p1_stream_hashes(length, grid_id, replica)
                if request_sha256 in request_ids or any(
                    stream in stream_ids for stream in streams
                ):
                    raise RuntimeError("P1 request or RNG identity collision")
                request_ids.add(request_sha256)
                stream_ids.update(streams)
                index = len(cells)
                identity = {
                    "cell_index": index,
                    "sigma_hex": sigma.hex(),
                    "length": length,
                    "replica": replica,
                    "request_sha256": request_sha256,
                }
                cell_id = f"{index:03d}-{_sha256(_canonical_bytes(identity))[:16]}"
                cell_path = f"cells/{cell_id}"
                cells.append(
                    {
                        **identity,
                        "cell_id": cell_id,
                        "sigma_grid_id": grid_id,
                        "kappas": [value.hex() for value in grid],
                        "kernel_sha256": kernel_sha256,
                        "rng_material_sha256": list(streams),
                        "cell_path": cell_path,
                        "run_path": f"{cell_path}/run",
                        "manifest_path": f"{cell_path}/manifest.json",
                    }
                )
                assignments.append(
                    {
                        "cell_index": index,
                        "request_sha256": request_sha256,
                        "streams": list(streams),
                    }
                )

    document: dict[str, object] = {
        "schema_version": P1_PROTOCOL_SCHEMA,
        "source_analysis_document_sha256": analysis["analysis_document_sha256"],
        "source_bracket_document_sha256": bracket_document["bracket_document_sha256"],
        "grid_namespace": "pilot-p1-v1",
        "master_seed": P1_MASTER_SEED,
        "phase": "pilot",
        "purpose": "exploratory-refinement-only",
        "lengths": list(lengths),
        "replicas": list(P1_REPLICAS),
        "loop_order": ["sigma", "length", "replica"],
        "sigma_entries": sigma_entries,
        "cells": cells,
        "cell_count": len(cells),
        "rng_assignment_sha256": _sha256(
            _canonical_bytes({"assignments": assignments})
        ),
    }
    document["protocol_sha256"] = _sha256(_canonical_bytes(document))
    return document


def validate_p1_protocol(
    analysis: Mapping[str, object],
    protocol: Mapping[str, object],
) -> None:
    _selector_estimates(analysis)
    if protocol.get("schema_version") != P1_PROTOCOL_SCHEMA:
        raise RuntimeError("P1 protocol schema version is not supported")
    if protocol.get("source_analysis_document_sha256") != analysis.get(
        "analysis_document_sha256"
    ):
        raise RuntimeError("P1 protocol is not bound to the analysis")
    digest = protocol.get("protocol_sha256")
    if not isinstance(digest, str):
        _malformed("P1 protocol digest is malformed")
    unsigned = dict(protocol)
    unsigned.pop("protocol_sha256", None)
    if _sha256(_canonical_bytes(unsigned)) != digest:
        raise RuntimeError("P1 protocol digest mismatch")
    cells = protocol.get("cells")
    if (
        not isinstance(cells, Sequence)
        or isinstance(cells, (str, bytes))
        or len(cells) != 4 * 3 * len(P1_REPLICAS)
        or protocol.get("cell_count") != len(cells)
    ):
        raise RuntimeError("P1 protocol cell cardinality is invalid")
    request_ids: set[str] = set()
    stream_ids: set[str] = set()
    for index, raw in enumerate(cells):
        if not isinstance(raw, Mapping) or raw.get("cell_index") != index:
            raise RuntimeError("P1 cells are not in canonical order")
        request_id = raw.get("request_sha256")
        streams = raw.get("rng_material_sha256")
        if (
            not isinstance(request_id, str)
            or request_id in request_ids
            or not isinstance(streams, Sequence)
            or isinstance(streams, (str, bytes))
            or len(streams) != STREAM_COUNT
            or any(not isinstance(value, str) for value in streams)
            or any(value in stream_ids for value in streams)
        ):
            raise RuntimeError("P1 request or RNG identities are invalid")
        request_ids.add(request_id)
        stream_ids.update(streams)
