"""Static, provenance-bound exact-evaluation shard production."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import socket
import time
from typing import Any, Mapping

from flax import serialization
import numpy as np

from .artifacts import publish_production_envelope
from .generations import VerifiedGeneration
from .oracle import (
    ExactNQSMetrics,
    VerifiedOracle,
    evaluate_exact_nqs,
    quadrature_cache_info,
)
from .production_policy import policy_sha256
from .production_vmc import (
    JaxCompileEventRecorder,
)
from .production_schema import (
    JSONValue,
    payload_sha256,
    validate_envelope,
)


EXACT_METRIC_TOLERANCE = 2e-11
EXACT_THRESHOLD_PRECISION = 2e-13
_OVERLAP_THRESHOLD = 0.99
_TARGET_L_RESIDUAL_THRESHOLD = 1e-10
_QUADRATURE_CHANGE_THRESHOLD = 1e-11
_SINGULAR_RANK_THRESHOLD = 1e-10
_METRIC_CACHE_MAX_ENTRIES = 8
_METRIC_CACHE: OrderedDict[
    tuple[str, str, int, int, int], ExactNQSMetrics
] = OrderedDict()
_METRIC_CACHE_HITS = 0
_METRIC_CACHE_MISSES = 0


@dataclass(frozen=True, slots=True)
class ExactLayoutComparison:
    classification: str
    ambiguous: bool
    reference_sha256: str
    absolute_tolerance: float
    maximum_difference: float
    passed: bool
    straddled_gates: tuple[str, ...]
    reference_gates: Mapping[str, bool]
    candidate_gates: Mapping[str, bool]


@dataclass(frozen=True, slots=True)
class ExactEvaluationShard:
    metrics: ExactNQSMetrics
    classification: str
    canonical_payload: Mapping[str, JSONValue]
    payload_sha256: str
    payload_path: Path
    receipt_payload: Mapping[str, JSONValue]
    receipt_sha256: str
    receipt_path: Path


def clear_exact_evaluation_cache() -> None:
    global _METRIC_CACHE_HITS, _METRIC_CACHE_MISSES
    _METRIC_CACHE.clear()
    _METRIC_CACHE_HITS = 0
    _METRIC_CACHE_MISSES = 0


def exact_evaluation_cache_info() -> dict[str, int]:
    return {
        "hits": _METRIC_CACHE_HITS,
        "misses": _METRIC_CACHE_MISSES,
        "entries": len(_METRIC_CACHE),
    }


def evaluate_exact_shard(
    oracle: VerifiedOracle,
    generation: VerifiedGeneration,
    determinant_block: int,
    carrier_block: int,
    quadrature_block: int,
    destination: Path,
) -> ExactEvaluationShard:
    """Evaluate one exact shard with invocation-wide JAX compile telemetry."""

    with JaxCompileEventRecorder() as telemetry:
        return _evaluate_exact_shard(
            oracle,
            generation,
            determinant_block,
            carrier_block,
            quadrature_block,
            destination,
            telemetry=telemetry,
        )


def evaluate_exact_shard_from_envelopes(
    oracle_path: Path,
    generation_path: Path,
    *,
    determinant_block: int,
    carrier_block: int,
    quadrature_block: int,
    destination: Path,
) -> Path:
    """Load immutable production sidecars and execute one exact shard."""
    from .generations import VerifiedGeneration
    from .oracle import VerifiedOracle, oracle_from_cache_payload
    from .production_schema import payload_sha256, validate_envelope

    oracle_payload = validate_envelope(
        Path(oracle_path), "challenge15.production-oracle.v1"
    )
    generation_payload = validate_envelope(
        Path(generation_path), "challenge15.training-generation.v1"
    )
    cache_path = Path(oracle_path).parent / "oracle-cache.json"
    if not cache_path.is_file() or cache_path.is_symlink():
        raise ValueError("production oracle immutable cache sidecar is missing")
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    expected_members = {
        str(member["identity"]): str(member["sha256"])
        for member in oracle_payload["array_manifest"]["members"]
    }
    cache_digest = hashlib.sha256(cache_path.read_bytes()).hexdigest()
    if expected_members.get("oracle-cache.json") != cache_digest:
        raise ValueError("production oracle cache sidecar SHA256 mismatch")
    verified_oracle = VerifiedOracle(
        path=Path(oracle_path),
        payload_sha256=payload_sha256(oracle_payload),
        payload=oracle_payload,
        result=oracle_from_cache_payload(cache),
    )
    verified_generation = VerifiedGeneration(
        path=Path(generation_path),
        payload_sha256=payload_sha256(generation_payload),
        payload=generation_payload,
    )
    result = evaluate_exact_shard(
        verified_oracle,
        verified_generation,
        determinant_block,
        carrier_block,
        quadrature_block,
        Path(destination),
    )
    return result.payload_path


def _evaluate_exact_shard(
    oracle: VerifiedOracle,
    generation: VerifiedGeneration,
    determinant_block: int,
    carrier_block: int,
    quadrature_block: int,
    destination: Path,
    *,
    telemetry: JaxCompileEventRecorder,
) -> ExactEvaluationShard:
    """Evaluate and exclusively publish one exact ``(rank, seed)`` shard."""

    started_at = _utc_now()
    _validate_inputs(
        oracle,
        generation,
        determinant_block,
        carrier_block,
        quadrature_block,
    )
    output = Path(destination)
    if not output.is_dir() or output.is_symlink():
        raise ValueError("exact shard destination must be an existing regular directory")
    lock_fd = os.open(
        output / ".publication.lock",
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if tuple(output.glob("*.json")):
            raise FileExistsError(
                "exact shard identity namespace is already occupied"
            )
        parameters = _load_generation_parameters(generation)
        reference = _cached_metrics(oracle, generation, parameters, 1, 1, 1)
        candidate = _cached_metrics(
            oracle,
            generation,
            parameters,
            determinant_block,
            carrier_block,
            quadrature_block,
        )
        comparison = classify_exact_layout(
            reference,
            candidate,
            absolute_tolerance=EXACT_METRIC_TOLERANCE,
            oracle=oracle,
        )
        primitive_metrics = _primitive_metrics(candidate)
        gate_metrics = _gate_metrics(candidate, oracle)
        common = _common_provenance(generation.payload)
        canonical_payload: dict[str, JSONValue] = {
            **common,
            "seed": int(generation.payload["seed"]),
            "rank": int(generation.payload["rank"]),
            "generation_sha256": generation.payload_sha256,
            "oracle_sha256": oracle.payload_sha256,
            "parameter_sha256": str(generation.payload["parameter_sha256"]),
            "block_layout": {
                "carrier_block": carrier_block,
                "determinant_block": determinant_block,
                "quadrature_block": quadrature_block,
            },
            "primitive_metrics": primitive_metrics,
            "metric_equivalence": {
                "reference_sha256": comparison.reference_sha256,
                "absolute_tolerance": comparison.absolute_tolerance,
                "maximum_difference": comparison.maximum_difference,
                "classification": comparison.classification,
                "ambiguous": comparison.ambiguous,
                "straddled_gates": list(comparison.straddled_gates),
                "passed": comparison.passed,
            },
            "gate_metrics": gate_metrics,
        }
        shard_digest = payload_sha256(canonical_payload)
        shard_path = output / f"{shard_digest}.json"
        published_digest = publish_production_envelope(
            shard_path,
            "challenge15.exact-evaluation-shard.v1",
            canonical_payload,
        )
        if published_digest != shard_digest:
            raise RuntimeError("published exact shard digest changed")

        finished_at = _utc_now()
        receipt_payload = _receipt_payload(
            common,
            generation,
            shard_digest,
            started_at=started_at,
            finished_at=finished_at,
            telemetry=telemetry.telemetry(),
            selected_layout={
                "walker_microbatch": None,
                "determinant_block": determinant_block,
                "carrier_block": carrier_block,
                "quadrature_block": quadrature_block,
            },
            metric_equivalence={
                "canonical_completed": True,
                "bitwise_equal": comparison.maximum_difference == 0.0,
                "classification": (
                    "passed"
                    if comparison.maximum_difference == 0.0
                    else "pending"
                ),
            },
        )
        receipt_digest = payload_sha256(receipt_payload)
        receipt_dir = output / "receipts"
        receipt_dir.mkdir(mode=0o700)
        receipt_path = receipt_dir / f"{receipt_digest}.json"
        receipt_context = {
            "approved_roots": (output,),
            "shard_path": shard_path,
            "shard_schema": "challenge15.exact-evaluation-shard.v1",
        }
        published_receipt = publish_production_envelope(
            receipt_path,
            "challenge15.evaluation-receipt.v1",
            receipt_payload,
            context=receipt_context,
        )
        if published_receipt != receipt_digest:
            raise RuntimeError("published evaluation receipt digest changed")
        return ExactEvaluationShard(
            metrics=candidate,
            classification=comparison.classification,
            canonical_payload=canonical_payload,
            payload_sha256=shard_digest,
            payload_path=shard_path,
            receipt_payload=receipt_payload,
            receipt_sha256=receipt_digest,
            receipt_path=receipt_path,
        )
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def classify_exact_layout(
    reference: ExactNQSMetrics,
    candidate: ExactNQSMetrics,
    *,
    absolute_tolerance: float = EXACT_METRIC_TOLERANCE,
    oracle: VerifiedOracle | None = None,
) -> ExactLayoutComparison:
    """Classify full metric agreement, including threshold straddles."""

    if (
        not isinstance(absolute_tolerance, (int, float))
        or isinstance(absolute_tolerance, bool)
        or not np.isfinite(absolute_tolerance)
        or absolute_tolerance < 0
    ):
        raise ValueError("absolute_tolerance must be finite and nonnegative")
    _validate_metrics(reference)
    _validate_metrics(candidate)
    differences = _metric_differences(reference, candidate)
    maximum = max(differences, default=0.0)
    reference_gates = _scientific_gates(reference, oracle)
    candidate_gates = _scientific_gates(candidate, oracle)
    straddled = _straddled_gate_thresholds(
        reference,
        candidate,
        oracle,
        precision_margin=min(
            float(absolute_tolerance), EXACT_THRESHOLD_PRECISION
        ),
    )
    ambiguous = bool(straddled)
    classification = (
        "passed"
        if maximum <= absolute_tolerance and not ambiguous
        else "pending"
    )
    passed = classification == "passed"
    return ExactLayoutComparison(
        classification=classification,
        ambiguous=ambiguous,
        reference_sha256=payload_sha256(_primitive_metrics(reference)),
        absolute_tolerance=float(absolute_tolerance),
        maximum_difference=float(maximum),
        passed=passed,
        straddled_gates=straddled,
        reference_gates=reference_gates,
        candidate_gates=candidate_gates,
    )


def _cached_metrics(
    oracle: VerifiedOracle,
    generation: VerifiedGeneration,
    parameters: Mapping[str, Any],
    determinant_block: int,
    carrier_block: int,
    quadrature_block: int,
) -> ExactNQSMetrics:
    global _METRIC_CACHE_HITS, _METRIC_CACHE_MISSES
    key = (
        oracle.payload_sha256,
        generation.payload_sha256,
        determinant_block,
        carrier_block,
        quadrature_block,
    )
    cached = _METRIC_CACHE.get(key)
    if cached is not None:
        _METRIC_CACHE.move_to_end(key)
        _METRIC_CACHE_HITS += 1
        return cached
    metrics = evaluate_exact_nqs(
        oracle.result.spec,
        parameters,
        oracle.result,
        determinant_block=determinant_block,
        carrier_block=carrier_block,
        quadrature_block=quadrature_block,
    )
    _validate_metrics(metrics)
    _METRIC_CACHE[key] = metrics
    _METRIC_CACHE.move_to_end(key)
    while len(_METRIC_CACHE) > _METRIC_CACHE_MAX_ENTRIES:
        _METRIC_CACHE.popitem(last=False)
    _METRIC_CACHE_MISSES += 1
    return metrics


def _load_generation_parameters(generation: VerifiedGeneration) -> Mapping[str, Any]:
    parameter_sha = str(generation.payload["parameter_sha256"])
    _require_sha(parameter_sha, "parameter")
    path = Path(generation.path)
    if path.name != "manifest.json" or path.parent.parent.name != "generations":
        raise ValueError("verified generation path is outside its exact namespace")
    seed_root = path.parents[2]
    blob = seed_root / "blobs" / parameter_sha
    if blob.is_symlink() or not blob.is_file():
        raise ValueError("generation parameter blob is missing")
    encoded = blob.read_bytes()
    if hashlib.sha256(encoded).hexdigest() != parameter_sha:
        raise ValueError("generation parameter blob SHA256 mismatch")
    restored = serialization.msgpack_restore(encoded)
    if not isinstance(restored, Mapping):
        raise ValueError("generation parameter blob is malformed")
    return restored


def _validate_inputs(
    oracle: VerifiedOracle,
    generation: VerifiedGeneration,
    determinant_block: int,
    carrier_block: int,
    quadrature_block: int,
) -> None:
    if not isinstance(oracle, VerifiedOracle):
        raise TypeError("oracle must be a VerifiedOracle")
    if not isinstance(generation, VerifiedGeneration):
        raise TypeError("generation must be a VerifiedGeneration")
    if payload_sha256(oracle.payload) != oracle.payload_sha256:
        raise ValueError("oracle payload SHA256 mismatch")
    if payload_sha256(generation.payload) != generation.payload_sha256:
        raise ValueError("generation payload SHA256 mismatch")
    for name, value in (
        ("determinant_block", determinant_block),
        ("carrier_block", carrier_block),
        ("quadrature_block", quadrature_block),
    ):
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value <= 0
        ):
            raise ValueError(f"{name} must be a positive Python integer")
    required = {
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
        "base_configuration_sha256",
        "particles",
    }
    if not required <= set(oracle.payload) or not (
        required | {"seed", "rank", "parameter_sha256"}
    ) <= set(generation.payload):
        raise ValueError("exact evaluation provenance is incomplete")
    for field in required:
        if oracle.payload[field] != generation.payload[field]:
            raise ValueError(f"oracle/generation {field} provenance mismatch")
    if generation.payload["policy_sha256"] != policy_sha256():
        raise ValueError("exact evaluation has stale production policy")
    if generation.payload["particles"] != oracle.result.spec.particles:
        raise ValueError("exact evaluation particle identity mismatch")
    runtime = generation.payload["runtime_attestations"]
    if (
        not isinstance(runtime, Mapping)
        or not isinstance(runtime.get("exact"), Mapping)
        or len(runtime["exact"]) != 1
    ):
        raise ValueError("exact runtime attestation is missing or ambiguous")
    for field in (
        "source_manifest_sha256",
        "base_configuration_sha256",
        "parameter_sha256",
    ):
        _require_sha(str(generation.payload[field]), field)


def _primitive_metrics(metrics: ExactNQSMetrics) -> dict[str, JSONValue]:
    exact_statistics = lambda value: {
        "estimate": float(value),
        "standard_error": 0.0,
        "ci_low": float(value),
        "ci_high": float(value),
    }
    gap = float(metrics.energy_l2 - metrics.energy_l0)
    return {
        "energy_by_sector": {
            "L0": exact_statistics(metrics.energy_l0),
            "L2": exact_statistics(metrics.energy_l2),
        },
        "gap": {
            **exact_statistics(gap),
            "monte_carlo_covariance_e0_e2": 0.0,
            "optimizer_induced_covariance_e0_e2": 0.0,
        },
        "overlap_by_sector": {
            "L0": exact_statistics(metrics.overlap_l0),
            "L2": exact_statistics(metrics.overlap_l2),
        },
        "symmetry_residual_by_sector": {
            "L0": float(metrics.l2_residual_l0),
            "L2": float(metrics.l2_residual_l2),
        },
        "per_state_gate_inputs_by_sector": {
            "L0": {
                "finite": bool(
                    np.all(
                        np.isfinite(metrics.normalized_sector_coefficients(0))
                    )
                ),
                "normalized_amplitude_nonzero": bool(
                    np.linalg.norm(metrics.normalized_sector_coefficients(0)) > 0
                ),
            },
            "L2": {
                "finite": bool(
                    np.all(
                        np.isfinite(metrics.normalized_sector_coefficients(2))
                    )
                ),
                "normalized_amplitude_nonzero": bool(
                    np.linalg.norm(metrics.normalized_sector_coefficients(2)) > 0
                ),
            },
        },
        "quadrature_change_by_sector": {
            "L0": {
                "normalized_amplitude": float(
                    metrics.quadrature_coefficient_relative_change_l0
                ),
                "energy": float(metrics.quadrature_energy_relative_change_l0),
                "symmetry": 0.0,
            },
            "L2": {
                "normalized_amplitude": float(
                    metrics.quadrature_coefficient_relative_change_l2
                ),
                "energy": float(metrics.quadrature_energy_relative_change_l2),
                "symmetry": 0.0,
            },
        },
        "projected_span": {
            "singular_values_by_sector": {
                "L0": [
                    float(value)
                    for value in metrics.carrier_gram_relative_singular_values_l0
                ],
                "L2": [
                    float(value)
                    for value in metrics.carrier_gram_relative_singular_values_l2
                ],
            },
            "numerical_rank_by_sector": {
                "L0": metrics.projected_span_rank_l0,
                "L2": metrics.projected_span_rank_l2,
            },
            "dim_m_l_by_sector": {
                "L0": metrics.projected_span_dimension_l0,
                "L2": metrics.projected_span_dimension_l2,
            },
            "completeness_claim_by_sector": {
                "L0": metrics.projected_span_complete_l0,
                "L2": metrics.projected_span_complete_l2,
            },
        },
        "normalized_coefficients_by_sector": {
            "L0": _complex_payload(
                metrics.normalized_sector_coefficients(0)
            ),
            "L2": _complex_payload(
                metrics.normalized_sector_coefficients(2)
            ),
        },
        "hamiltonian_variance_by_sector": {
            "L0": float(metrics.h_variance_l0),
            "L2": float(metrics.h_variance_l2),
        },
        "quadrature": {
            "orders_by_sector": {
                "L0": _quadrature_order_payload(metrics.quadrature_orders_l0),
                "L2": _quadrature_order_payload(metrics.quadrature_orders_l2),
            },
            "coefficient_relative_change_by_sector": {
                "L0": float(
                    metrics.quadrature_coefficient_relative_change_l0
                ),
                "L2": float(
                    metrics.quadrature_coefficient_relative_change_l2
                ),
            },
            "energy_relative_change_by_sector": {
                "L0": float(metrics.quadrature_energy_relative_change_l0),
                "L2": float(metrics.quadrature_energy_relative_change_l2),
            },
        },
    }


def _complex_payload(values: np.ndarray) -> list[dict[str, float]]:
    return [
        {"real": float(value.real), "imag": float(value.imag)}
        for value in np.asarray(values, dtype=np.complex128)
    ]


def _quadrature_order_payload(
    orders: tuple[tuple[int, int], tuple[int, int]]
) -> dict[str, dict[str, int]]:
    minimal, doubled = orders
    return {
        "minimal": {"alpha": int(minimal[0]), "beta": int(minimal[1])},
        "doubled": {"alpha": int(doubled[0]), "beta": int(doubled[1])},
    }


def _metric_differences(
    reference: ExactNQSMetrics, candidate: ExactNQSMetrics
) -> list[float]:
    differences = [
        abs(float(getattr(reference, name)) - float(getattr(candidate, name)))
        for name in (
            "energy_l0",
            "energy_l2",
            "h_variance_l0",
            "h_variance_l2",
            "overlap_l0",
            "overlap_l2",
            "l2_residual_l0",
            "l2_residual_l2",
            "l2_variance_l0",
            "l2_variance_l2",
            "quadrature_coefficient_relative_change_l0",
            "quadrature_coefficient_relative_change_l2",
            "quadrature_energy_relative_change_l0",
            "quadrature_energy_relative_change_l2",
        )
    ]
    for target_l in (0, 2):
        first = reference.normalized_sector_coefficients(target_l)
        second = candidate.normalized_sector_coefficients(target_l)
        overlap = np.vdot(first, second)
        if overlap != 0:
            second = second * np.exp(-1j * np.angle(overlap))
        differences.append(
            float(np.max(np.abs(first - second), initial=0.0))
        )
        first_singular = (
            reference.projected_carrier_relative_singular_values(target_l)
        )
        second_singular = (
            candidate.projected_carrier_relative_singular_values(target_l)
        )
        if first_singular.shape != second_singular.shape:
            differences.append(1.0)
        else:
            differences.append(
                float(
                    np.max(
                        np.abs(first_singular - second_singular), initial=0.0
                    )
                )
            )
        if (
            reference.projected_span_rank(target_l)
            != candidate.projected_span_rank(target_l)
        ):
            differences.append(1.0)
    if (
        reference.quadrature_orders_l0 != candidate.quadrature_orders_l0
        or reference.quadrature_orders_l2 != candidate.quadrature_orders_l2
    ):
        differences.append(1.0)
    return differences


def _validate_metrics(metrics: ExactNQSMetrics) -> None:
    if not isinstance(metrics, ExactNQSMetrics):
        raise TypeError("exact layout metrics must be ExactNQSMetrics")
    values: list[np.ndarray] = []
    for field in (
        "norm_l0",
        "norm_l2",
        "energy_l0",
        "energy_l2",
        "h_variance_l0",
        "h_variance_l2",
        "overlap_l0",
        "overlap_l2",
        "l2_residual_l0",
        "l2_residual_l2",
        "l2_variance_l0",
        "l2_variance_l2",
        "quadrature_coefficient_relative_change_l0",
        "quadrature_coefficient_relative_change_l2",
        "quadrature_energy_relative_change_l0",
        "quadrature_energy_relative_change_l2",
    ):
        values.append(np.asarray(getattr(metrics, field)))
    for target_l in (0, 2):
        coefficients = metrics.normalized_sector_coefficients(target_l)
        singular = metrics.projected_carrier_relative_singular_values(
            target_l
        )
        absolute_singular = np.asarray(
            getattr(metrics, f"carrier_gram_singular_values_l{target_l}")
        )
        if coefficients.ndim != 1 or not coefficients.size:
            raise ValueError("exact metrics contain malformed coefficients")
        if (
            singular.ndim != 1
            or not singular.size
            or absolute_singular.shape != singular.shape
        ):
            raise ValueError("exact metrics contain malformed singular values")
        if (
            np.any(singular < 0)
            or np.any(absolute_singular < 0)
            or np.any(singular[:-1] < singular[1:])
            or np.any(absolute_singular[:-1] < absolute_singular[1:])
        ):
            raise ValueError("exact metrics contain malformed singular values")
        values.extend(
            (
                coefficients.real,
                coefficients.imag,
                singular,
                absolute_singular,
            )
        )
    if not all(np.all(np.isfinite(value)) for value in values):
        raise ValueError("exact metrics contain nonfinite values")
    if metrics.norm_l0 <= 0 or metrics.norm_l2 <= 0:
        raise ValueError("exact metrics contain malformed norms")
    for field in (
        "h_variance_l0",
        "h_variance_l2",
        "l2_residual_l0",
        "l2_residual_l2",
        "l2_variance_l0",
        "l2_variance_l2",
        "quadrature_coefficient_relative_change_l0",
        "quadrature_coefficient_relative_change_l2",
        "quadrature_energy_relative_change_l0",
        "quadrature_energy_relative_change_l2",
    ):
        if getattr(metrics, field) < 0:
            raise ValueError("exact metrics contain malformed nonnegative values")
    if not (
        0 <= metrics.overlap_l0 <= 1 and 0 <= metrics.overlap_l2 <= 1
    ):
        raise ValueError("exact metrics contain malformed overlaps")
    if metrics.bare_potential_sampling_variance is not None:
        raise ValueError("exact metrics contain malformed exact-only values")
    for target_l in (0, 2):
        coefficients = metrics.normalized_sector_coefficients(target_l)
        singular = metrics.projected_carrier_relative_singular_values(
            target_l
        )
        rank = metrics.projected_span_rank(target_l)
        dimension = getattr(
            metrics, f"projected_span_dimension_l{target_l}"
        )
        complete = metrics.projected_span_complete(target_l)
        if (
            not isinstance(rank, int)
            or isinstance(rank, bool)
            or not isinstance(dimension, int)
            or isinstance(dimension, bool)
            or not isinstance(complete, bool)
            or dimension <= 0
            or coefficients.size != dimension
            or not 0 <= rank <= min(dimension, singular.size)
            or rank != int(
                np.count_nonzero(singular > _SINGULAR_RANK_THRESHOLD)
            )
            or complete is not (rank == dimension)
            or not np.isclose(
                np.linalg.norm(coefficients), 1.0, rtol=0.0, atol=1e-10
            )
        ):
            raise ValueError("exact metrics contain malformed span data")
        orders = getattr(metrics, f"quadrature_orders_l{target_l}")
        if (
            not isinstance(orders, tuple)
            or len(orders) != 2
            or any(
                not isinstance(order, tuple)
                or len(order) != 2
                or any(
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value <= 0
                    for value in order
                )
                for order in orders
            )
            or orders[1] != (2 * orders[0][0], 2 * orders[0][1])
        ):
            raise ValueError("exact metrics contain malformed quadrature orders")


def _scientific_gates(
    metrics: ExactNQSMetrics, oracle: VerifiedOracle | None
) -> dict[str, bool]:
    overlap = (
        metrics.overlap_l0 >= _OVERLAP_THRESHOLD
        and metrics.overlap_l2 >= _OVERLAP_THRESHOLD
    )
    symmetry = (
        metrics.l2_residual_l0 <= _TARGET_L_RESIDUAL_THRESHOLD
        and metrics.l2_residual_l2 <= _TARGET_L_RESIDUAL_THRESHOLD
        and metrics.quadrature_coefficient_relative_change_l0
        <= _QUADRATURE_CHANGE_THRESHOLD
        and metrics.quadrature_coefficient_relative_change_l2
        <= _QUADRATURE_CHANGE_THRESHOLD
        and metrics.quadrature_energy_relative_change_l0
        <= _QUADRATURE_CHANGE_THRESHOLD
        and metrics.quadrature_energy_relative_change_l2
        <= _QUADRATURE_CHANGE_THRESHOLD
    )
    if oracle is None:
        energy = True
        gap = True
    else:
        exact_gap = oracle.result.gap
        error_limit = min(1e-4, 0.01 * abs(exact_gap))
        energy = (
            abs(metrics.energy_l0 - oracle.result.energy_l0) <= error_limit
            and abs(metrics.energy_l2 - oracle.result.energy_l2)
            <= error_limit
        )
        candidate_gap = metrics.energy_l2 - metrics.energy_l0
        gap = abs(candidate_gap - exact_gap) <= 0.01 * abs(exact_gap)
    return {
        "energy": energy,
        "gap": gap,
        "overlap": overlap,
        "symmetry": symmetry,
    }


def _straddled_gate_thresholds(
    reference: ExactNQSMetrics,
    candidate: ExactNQSMetrics,
    oracle: VerifiedOracle | None,
    *,
    precision_margin: float,
) -> tuple[str, ...]:
    """Return grouped gates whose thresholds cannot be classified precisely."""

    straddled: set[str] = set()
    if any(
        _threshold_is_ambiguous(
            getattr(reference, field),
            getattr(candidate, field),
            _OVERLAP_THRESHOLD,
            precision_margin,
            passes_above=True,
        )
        for field in ("overlap_l0", "overlap_l2")
    ):
        straddled.add("overlap")
    if any(
        _threshold_is_ambiguous(
            getattr(reference, field),
            getattr(candidate, field),
            threshold,
            precision_margin,
            passes_above=False,
        )
        for field, threshold in (
            ("l2_residual_l0", _TARGET_L_RESIDUAL_THRESHOLD),
            ("l2_residual_l2", _TARGET_L_RESIDUAL_THRESHOLD),
            (
                "quadrature_coefficient_relative_change_l0",
                _QUADRATURE_CHANGE_THRESHOLD,
            ),
            (
                "quadrature_coefficient_relative_change_l2",
                _QUADRATURE_CHANGE_THRESHOLD,
            ),
            (
                "quadrature_energy_relative_change_l0",
                _QUADRATURE_CHANGE_THRESHOLD,
            ),
            (
                "quadrature_energy_relative_change_l2",
                _QUADRATURE_CHANGE_THRESHOLD,
            ),
        )
    ):
        straddled.add("symmetry")
    for target_l in (0, 2):
        first = reference.projected_carrier_relative_singular_values(target_l)
        second = candidate.projected_carrier_relative_singular_values(target_l)
        if first.shape != second.shape or any(
            _threshold_is_ambiguous(
                first_value,
                second_value,
                _SINGULAR_RANK_THRESHOLD,
                precision_margin,
                passes_above=True,
            )
            for first_value, second_value in zip(first, second, strict=True)
        ):
            straddled.add("singular_rank")
            break
    if oracle is not None:
        exact_gap = oracle.result.gap
        error_limit = min(1e-4, 0.01 * abs(exact_gap))
        if any(
            _threshold_is_ambiguous(
                abs(getattr(reference, field) - exact),
                abs(getattr(candidate, field) - exact),
                error_limit,
                precision_margin,
                passes_above=False,
            )
            for field, exact in (
                ("energy_l0", oracle.result.energy_l0),
                ("energy_l2", oracle.result.energy_l2),
            )
        ):
            straddled.add("energy")
        reference_gap_error = abs(
            reference.energy_l2 - reference.energy_l0 - exact_gap
        )
        candidate_gap_error = abs(
            candidate.energy_l2 - candidate.energy_l0 - exact_gap
        )
        gap_limit = 0.01 * abs(exact_gap)
        if _threshold_is_ambiguous(
            reference_gap_error,
            candidate_gap_error,
            gap_limit,
            precision_margin,
            passes_above=False,
        ):
            straddled.add("gap")
    return tuple(sorted(straddled))


def _threshold_is_ambiguous(
    reference: float,
    candidate: float,
    threshold: float,
    precision_margin: float,
    *,
    passes_above: bool,
) -> bool:
    reference_passes = (
        reference >= threshold if passes_above else reference <= threshold
    )
    candidate_passes = (
        candidate >= threshold if passes_above else candidate <= threshold
    )
    return (
        reference_passes is not candidate_passes
        or abs(reference - threshold) <= precision_margin
        or abs(candidate - threshold) <= precision_margin
    )


def _gate_metrics(
    metrics: ExactNQSMetrics,
    oracle: VerifiedOracle,
) -> dict[str, bool]:
    gates = _scientific_gates(metrics, oracle)
    per_state = gates["energy"] and gates["overlap"] and gates["symmetry"]
    return {
        "finite": True,
        "per_state": per_state,
        "energy": gates["energy"],
        "gap": gates["gap"],
        "overlap": gates["overlap"],
        "symmetry": gates["symmetry"],
    }


def _common_provenance(payload: Mapping[str, Any]) -> dict[str, JSONValue]:
    return {
        field: payload[field]
        for field in (
            "policy_sha256",
            "source_manifest_sha256",
            "runtime_attestations",
            "base_configuration_sha256",
            "particles",
        )
    }


def _receipt_payload(
    common: Mapping[str, JSONValue],
    generation: VerifiedGeneration,
    shard_sha256: str,
    *,
    started_at: str,
    finished_at: str,
    telemetry: Mapping[str, Any],
    selected_layout: Mapping[str, JSONValue],
    metric_equivalence: Mapping[str, JSONValue],
) -> dict[str, JSONValue]:
    runtime = generation.payload["runtime_attestations"]
    assert isinstance(runtime, Mapping)
    exact_runtime = runtime["exact"]
    assert isinstance(exact_runtime, Mapping)
    controller = sorted(str(value) for value in exact_runtime)[0]
    metric_cache = exact_evaluation_cache_info()
    quadrature_cache = quadrature_cache_info()
    invocation_sha256 = payload_sha256(
        {
            "stage": "exact",
            "shard_sha256": shard_sha256,
            "started_at_utc": started_at,
        }
    )
    return {
        **common,
        "stage": "exact",
        "identity": {
            "stage": "exact",
            "seed": int(generation.payload["seed"]),
            "rank": int(generation.payload["rank"]),
        },
        "shard_sha256": shard_sha256,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "hostname": socket.gethostname(),
        "controller": controller,
        "device": platform.machine() or "cpu",
        "peak_rss_mib": float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        / 1024.0,
        "compile_seconds": telemetry["compile_seconds"],
        "compile_events": telemetry["compile_events"],
        "compile_event_count": telemetry["compile_event_count"],
        "elapsed_seconds": float(telemetry["elapsed_seconds"]),
        "cache_counters": {
            "hits": (
                telemetry["cache_counters"]["hits"]
                + metric_cache["hits"]
                + quadrature_cache["hits"]
            ),
            "misses": (
                telemetry["cache_counters"]["misses"]
                + metric_cache["misses"]
                + quadrature_cache["misses"]
            ),
        },
        "telemetry_invocation_sha256": invocation_sha256,
        "selected_layout": dict(selected_layout),
        "metric_equivalence": dict(metric_equivalence),
    }


def _require_sha(value: str, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA256")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")
