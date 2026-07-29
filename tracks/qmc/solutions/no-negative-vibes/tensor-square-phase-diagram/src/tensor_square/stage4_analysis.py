"""Conservative Stage 4 replica aggregation and frozen candidate gates."""

from __future__ import annotations

import math
import statistics
from typing import Iterable, Mapping

from .scan import run_fingerprint


STRICT_Z = 2.0
EXTEND_Z = 1.2
MIN_RELATIVE_ENHANCEMENT = 0.05

DIAGNOSTIC_METRICS = (
    "staggered_structure",
    "q_a_susceptibility",
    "q_b_susceptibility",
    "q_a_binder",
    "q_b_binder",
    "correlation_length_over_m",
)

PRODUCTION_METRICS: dict[str, tuple[str, str | None]] = {
    "q_combined": ("q_combined_mean", "q_combined_stderr"),
    "q_a_sq": ("q_a_sq_mean", "q_a_sq_stderr"),
    "q_b_sq": ("q_b_sq_mean", "q_b_sq_stderr"),
    "q_a_mean": ("q_a_mean_mean", "q_a_mean_stderr"),
    "q_b_mean": ("q_b_mean_mean", "q_b_mean_stderr"),
    "channel_balance": ("channel_balance_mean", "channel_balance_stderr"),
    "staggered_structure": (
        "staggered_structure_mean",
        "staggered_structure_stderr",
    ),
    "near_staggered_structure": (
        "near_staggered_structure_mean",
        "near_staggered_structure_stderr",
    ),
    "energy": ("energy_mean", "energy_stderr"),
    "density": ("density_mean", "density_stderr"),
    "nematic_sq": ("nematic_sq_mean", "nematic_sq_stderr"),
    "q_a_susceptibility": ("q_a_susceptibility", None),
    "q_b_susceptibility": ("q_b_susceptibility", None),
    "q_a_binder": ("q_a_binder", None),
    "q_b_binder": ("q_b_binder", None),
    "correlation_length_over_m": ("correlation_length_over_m", None),
    "correlation_length_proxy": ("correlation_length_proxy", None),
}


def aggregate_replica_estimate(
    replicas: Iterable[Mapping[str, object]],
    *,
    value_key: str,
    stderr_key: str | None = None,
) -> dict[str, float]:
    """Combine independent chain estimates without hiding chain scatter."""
    rows = list(replicas)
    if not rows:
        raise ValueError("at least one replica is required")
    values = [float(row[value_key]) for row in rows]
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{value_key} contains a non-finite value")
    replica_count = len(values)
    mean = statistics.fmean(values)
    between = (
        statistics.stdev(values) / math.sqrt(replica_count)
        if replica_count > 1
        else 0.0
    )
    within = 0.0
    if stderr_key is not None:
        errors = [float(row[stderr_key]) for row in rows]
        if not all(
            math.isfinite(error) and error >= 0.0 for error in errors
        ):
            raise ValueError(f"{stderr_key} contains an invalid value")
        within = math.sqrt(sum(error * error for error in errors)) / replica_count
    return {
        "mean": mean,
        "stderr": max(within, between),
        "within_replica_stderr": within,
        "between_replica_stderr": between,
    }


def aggregate_production_cell(
    replicas: Iterable[Mapping[str, object]],
    *,
    expected_replicas: int = 4,
    target_ess: float = 40.0,
) -> dict[str, object]:
    """Audit and conservatively aggregate one production cell."""
    rows = list(replicas)
    first = rows[0] if rows else {}
    identity = {
        "cell_id": first.get("cell_id", ""),
        "cohort": first.get("cohort", ""),
        "pair_id": first.get("pair_id"),
    }
    run_spec = first.get("run_spec")
    config = (
        dict(run_spec.get("config", {}))
        if isinstance(run_spec, Mapping)
        else {}
    )
    base = {
        **identity,
        **config,
        "production_replicas": len(rows),
    }
    replica_ids = [int(row.get("replica", -1)) for row in rows]
    if (
        len(rows) != expected_replicas
        or set(replica_ids) != set(range(expected_replicas))
    ):
        return {
            **base,
            "audit_status": "STOP",
            "audit_reason": "incomplete or duplicated production replicas",
        }

    source_revisions: set[str] = set()
    plan_digests: set[str] = set()
    for row in rows:
        row_spec = row.get("run_spec")
        final_audit = row.get("final_audit")
        if (
            row.get("status") != "COMPLETE"
            or not isinstance(row_spec, Mapping)
            or not isinstance(final_audit, Mapping)
            or final_audit.get("status") != "PASS"
            or float(final_audit.get("achieved_ess", 0.0)) < target_ess
        ):
            return {
                **base,
                "audit_status": "STOP",
                "audit_reason": (
                    "production replica failed status, ESS, or numerical audit"
                ),
            }
        if (
            row.get("cell_id") != identity["cell_id"]
            or row.get("cohort") != identity["cohort"]
            or row_spec.get("config") != config
            or run_fingerprint(row_spec)
            != str(row.get("run_fingerprint", ""))
        ):
            return {
                **base,
                "audit_status": "STOP",
                "audit_reason": "production identity or fingerprint mismatch",
            }
        source_revisions.add(str(row_spec.get("source_revision", "")))
        plan_digests.add(str(row_spec.get("budget_plan_digest", "")))
    if (
        len(source_revisions) != 1
        or "" in source_revisions
        or len(plan_digests) != 1
        or "" in plan_digests
    ):
        return {
            **base,
            "audit_status": "STOP",
            "audit_reason": "production source or budget provenance mismatch",
        }

    result: dict[str, object] = {
        **base,
        "audit_status": "PASS",
        "audit_reason": "all production replicas pass",
        "source_revision": source_revisions.pop(),
        "budget_plan_digest": plan_digests.pop(),
        "minimum_ess": min(
            float(dict(row["final_audit"])["achieved_ess"]) for row in rows
        ),
        "acceptance_min": min(float(row["acceptance"]) for row in rows),
        "acceptance_max": max(float(row["acceptance"]) for row in rows),
        "direct_sign_min": min(float(row["direct_sign_min"]) for row in rows),
        "weight_log_error_max": max(
            float(row["weight_log_error_max"]) for row in rows
        ),
        "realized_measurement_sweeps_max": max(
            int(row["realized_measurement_sweeps"]) for row in rows
        ),
    }
    for metric, (value_key, stderr_key) in PRODUCTION_METRICS.items():
        estimate = aggregate_replica_estimate(
            rows,
            value_key=value_key,
            stderr_key=stderr_key,
        )
        result[f"{metric}_mean"] = estimate["mean"]
        result[f"{metric}_stderr"] = estimate["stderr"]
        result[f"{metric}_between_replica_stderr"] = estimate[
            "between_replica_stderr"
        ]
        result[f"{metric}_within_replica_stderr"] = estimate[
            "within_replica_stderr"
        ]
    return result


def metric_trend(
    low: Mapping[str, object],
    high: Mapping[str, object],
    *,
    metric: str,
) -> dict[str, float | bool]:
    """Evaluate a pre-registered high-minus-low enhancement."""
    low_mean = float(low[f"{metric}_mean"])
    high_mean = float(high[f"{metric}_mean"])
    low_error = float(low[f"{metric}_stderr"])
    high_error = float(high[f"{metric}_stderr"])
    delta = high_mean - low_mean
    combined_error = math.hypot(low_error, high_error)
    if combined_error > 0.0:
        z = delta / combined_error
    elif delta > 0.0:
        z = 1.0e12
    elif delta < 0.0:
        z = -1.0e12
    else:
        z = 0.0
    scale = max(abs(low_mean), 1.0e-12)
    relative_delta = delta / scale
    return {
        "low": low_mean,
        "high": high_mean,
        "delta": delta,
        "combined_stderr": combined_error,
        "z": z,
        "relative_delta": relative_delta,
        "strict_positive": (
            delta > 0.0
            and z >= STRICT_Z
            and relative_delta >= MIN_RELATIVE_ENHANCEMENT
        ),
        "extend_positive": (
            delta > 0.0
            and z >= EXTEND_Z
            and relative_delta > 0.0
        ),
    }


def _monotone_with_errors(rows: list[Mapping[str, object]]) -> bool:
    ordered = sorted(rows, key=lambda row: int(row["m"]))
    return all(
        float(right["q_combined_mean"])
        + float(right["q_combined_stderr"])
        >= float(left["q_combined_mean"])
        - float(left["q_combined_stderr"])
        for left, right in zip(ordered, ordered[1:])
    )


def _diagnostic_support(
    low: Mapping[str, object],
    high: Mapping[str, object],
) -> tuple[bool, bool, list[str], float]:
    strict: list[str] = []
    extend: list[str] = []
    best_z = -math.inf
    for metric in DIAGNOSTIC_METRICS:
        trend = metric_trend(low, high, metric=metric)
        best_z = max(best_z, float(trend["z"]))
        physically_positive = float(high[f"{metric}_mean"]) > 0.0
        if physically_positive and bool(trend["strict_positive"]):
            strict.append(metric)
        if (
            physically_positive
            and bool(trend["extend_positive"])
        ):
            extend.append(metric)
    return bool(strict), bool(extend), strict, best_z


def _incomplete_result(
    *,
    required: set[tuple[int, float]],
    present: set[tuple[int, float]],
) -> dict[str, object]:
    missing = sorted(required - present)
    return {
        "classification": "STOP",
        "inference_scope": "statistical_only",
        "reason": (
            "incomplete audited long-chain grid; no physics inference "
            f"(missing or failed {missing})"
        ),
        "missing_points": [f"m={m},beta={beta:g}" for m, beta in missing],
        "ranking_score": -1.0e9,
    }


def classify_stage4_candidate(
    cell_rows: Iterable[Mapping[str, object]],
    *,
    cohort: str,
) -> dict[str, object]:
    """Apply the frozen Stage 4 SURVIVE/EXTEND/STOP interpretation gate."""
    rows = list(cell_rows)
    if cohort == "half_filled_core":
        required = {
            (m, beta)
            for m in (4, 6, 8)
            for beta in (4.0, 8.0)
        }
    elif cohort == "paired_competition":
        required = {(m, 8.0) for m in (4, 6, 8)}
    else:
        raise ValueError(f"unknown Stage 4 cohort: {cohort}")

    audited = {
        (int(row["m"]), float(row["beta"])): row
        for row in rows
        if row.get("audit_status") == "PASS"
    }
    if not required <= audited.keys():
        return _incomplete_result(
            required=required,
            present=set(audited),
        )

    size_low = audited[(4, 8.0)]
    size_high = audited[(8, 8.0)]
    size = metric_trend(size_low, size_high, metric="q_combined")
    monotone = _monotone_with_errors(
        [audited[(m, 8.0)] for m in (4, 6, 8)]
    )
    diag_strict, diag_extend, diag_names, best_diag_z = _diagnostic_support(
        size_low, size_high
    )
    result: dict[str, object] = {
        "primary_size_delta": size["delta"],
        "primary_size_relative_delta": size["relative_delta"],
        "primary_size_z": size["z"],
        "primary_size_strict": size["strict_positive"],
        "size_monotone_with_errors": monotone,
        "independent_diagnostic_support": diag_strict,
        "independent_diagnostic_extend": diag_extend,
        "supporting_diagnostics": diag_names,
        "best_diagnostic_z": best_diag_z,
    }

    if cohort == "half_filled_core":
        thermal = metric_trend(
            audited[(8, 4.0)],
            audited[(8, 8.0)],
            metric="q_combined",
        )
        primary_strict = (
            bool(size["strict_positive"])
            and bool(thermal["strict_positive"])
            and monotone
        )
        primary_extend = (
            bool(size["extend_positive"])
            and bool(thermal["extend_positive"])
        )
        result.update(
            {
                "primary_thermal_delta": thermal["delta"],
                "primary_thermal_relative_delta": thermal["relative_delta"],
                "primary_thermal_z": thermal["z"],
                "primary_thermal_strict": thermal["strict_positive"],
            }
        )
        limiting_z = min(float(size["z"]), float(thermal["z"]))
    else:
        primary_strict = bool(size["strict_positive"]) and monotone
        primary_extend = bool(size["extend_positive"])
        limiting_z = float(size["z"])

    if primary_strict and diag_strict:
        classification = "SURVIVE"
        reason = (
            "pre-registered primary trend and independent collective "
            "diagnostic both pass"
        )
    elif primary_strict or (primary_extend and diag_extend):
        classification = "EXTEND"
        reason = (
            "positive long-chain trend remains but one pre-registered "
            "significance or diagnostic gate is unresolved"
        )
    else:
        classification = "STOP"
        reason = (
            "audit-passing long chains do not meet the pre-registered "
            "positive trend gate"
        )
    result.update(
        {
            "classification": classification,
            "inference_scope": "physics",
            "reason": reason,
            "ranking_score": (
                min(limiting_z, 20.0)
                + min(max(best_diag_z, 0.0), 20.0)
            ),
        }
    )
    return result
