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
from .pilot import PilotCell

ANALYSIS_SCHEMA = "challenge-194-p0-analysis-v1"
BRACKET_SCHEMA = "challenge-194-p1-brackets-v1"
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
