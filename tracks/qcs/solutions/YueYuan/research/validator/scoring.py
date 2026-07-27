from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from schema import error, extract_runs, validate_run_shape


HEADLINE_INSTANCE = "two_qubit_cz_minimal"
INFIDELITY_THRESHOLD = 1e-3
REQUIRED_METHODS = {
    "full_raw_nelder_mead",
    "hessian_subspace_nelder_mead",
    "random_subspace_nelder_mead",
}
REQUIRED_HESSIAN_K = {0, 3, 8, 15, 24, 48}
SMALL_K = {0, 3, 8}
FAIRNESS_FIELDS = ["initial_pulse_id", "query_budget", "stopping_rule", "optimizer"]


def evaluate_submission(
    payload: dict[str, Any], instance_payload: dict[str, Any]
) -> tuple[float | None, dict[str, Any], list[dict[str, Any]]]:
    runs, errors = extract_runs(payload)
    if errors:
        return None, {}, errors
    errors.extend(validate_run_shape(runs))
    if errors:
        return None, {}, errors

    instance_ids = {
        instance["id"]
        for instance in instance_payload.get("instances", [])
        if isinstance(instance, dict) and "id" in instance
    }
    headline_rows = [row for row in runs if row.get("instance") == HEADLINE_INSTANCE]
    if HEADLINE_INSTANCE not in instance_ids:
        errors.append(error("validator_fixture_missing", "headline instance is absent from split"))
    if not headline_rows:
        errors.append(error("missing_instance", f"no rows for {HEADLINE_INSTANCE}"))
        return None, {}, errors

    methods = {str(row.get("method")) for row in headline_rows}
    for method in sorted(REQUIRED_METHODS - methods):
        errors.append(error("missing_required_method", f"missing method {method}", method=method))

    hessian_rows = [
        row for row in headline_rows if row.get("method") == "hessian_subspace_nelder_mead"
    ]
    hessian_ks = {_as_int(row.get("k")) for row in hessian_rows}
    missing_k = sorted(REQUIRED_HESSIAN_K - hessian_ks)
    if missing_k:
        errors.append(error("missing_k_sweep", "hessian k sweep is incomplete", missing_k=missing_k))

    nonzero_gaps = sorted(
        {
            _as_float(row.get("model_truth_gap"))
            for row in hessian_rows
            if _as_float(row.get("model_truth_gap")) > 0
        }
    )
    if len(nonzero_gaps) < 2:
        errors.append(
            error(
                "insufficient_gap_sweep",
                "need at least two nonzero model-truth gaps",
                gaps=nonzero_gaps,
            )
        )

    errors.extend(_check_exact_success_rows(headline_rows))
    errors.extend(_check_fairness(headline_rows))
    errors.extend(_check_seed_counts(headline_rows))
    errors.extend(_check_small_k_failure(hessian_rows))

    per_instance = _score_headline(headline_rows, nonzero_gaps)
    if per_instance.get("errors"):
        errors.extend(per_instance.pop("errors"))

    if errors:
        return None, {HEADLINE_INSTANCE: per_instance} if per_instance else {}, errors

    score = per_instance["median_query_speedup"]
    return score, {HEADLINE_INSTANCE: per_instance}, []


def _check_exact_success_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not row.get("claim_success"):
            continue
        if not row.get("stopped_on_exact_check"):
            errors.append(
                error(
                    "no_exact_final_check",
                    "successful calibration must stop on an exact final check",
                    index=index,
                    method=row.get("method"),
                )
            )
        final = _as_float(row.get("final_exact_true_infidelity"))
        if final > INFIDELITY_THRESHOLD:
            errors.append(
                error(
                    "final_infidelity_above_threshold",
                    "successful calibration exceeds exact infidelity threshold",
                    index=index,
                    method=row.get("method"),
                    value=final,
                    threshold=INFIDELITY_THRESHOLD,
                )
            )
        if row.get("queries_to_target") is None:
            errors.append(
                error(
                    "missing_query_count",
                    "successful calibration must include queries_to_target",
                    index=index,
                    method=row.get("method"),
                )
            )
    return errors


def _check_fairness(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    shots = {_as_int(row.get("shots_per_query")) for row in rows}
    if len(shots) != 1:
        errors.append(error("unequal_shots", "shots_per_query must be equal across compared rows"))
    for field in FAIRNESS_FIELDS:
        values = {str(row.get(field)) for row in rows if field in row}
        if len(values) != 1:
            errors.append(
                error("unequal_fairness_field", f"{field} differs across rows", field=field)
            )
    return errors


def _check_seed_counts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    grouped: dict[tuple[str, float], set[int]] = defaultdict(set)
    for row in rows:
        method = str(row.get("method"))
        if method not in REQUIRED_METHODS:
            continue
        grouped[(method, _as_float(row.get("model_truth_gap")))].add(_as_int(row.get("seed")))
    for (method, gap), seeds in sorted(grouped.items()):
        if gap <= 0:
            continue
        if len(seeds) < 5:
            errors.append(
                error(
                    "insufficient_seeds",
                    "each method/gap cell needs at least five seeds",
                    method=method,
                    model_truth_gap=gap,
                    seeds=sorted(seeds),
                )
            )
    return errors


def _check_small_k_failure(hessian_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in hessian_rows:
        if _as_int(row.get("k")) not in SMALL_K:
            continue
        if not row.get("claim_success"):
            return []
        if row.get("queries_to_target") is None:
            return []
        if _as_float(row.get("final_exact_true_infidelity")) > INFIDELITY_THRESHOLD:
            return []
    return [
        error(
            "missing_small_k_failure",
            "candidate must report a failure or plateau for too-small Hessian subspaces",
        )
    ]


def _score_headline(rows: list[dict[str, Any]], gaps: list[float]) -> dict[str, Any]:
    speedups: list[float] = []
    details: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for gap in gaps:
        full = _successful_queries(rows, "full_raw_nelder_mead", gap, k=48)
        hessian = _successful_queries(rows, "hessian_subspace_nelder_mead", gap, k=15)
        random = _successful_queries(rows, "random_subspace_nelder_mead", gap)
        if len(full) < 5 or len(hessian) < 5 or len(random) < 5:
            errors.append(
                error(
                    "incomplete_headline_cell",
                    "headline comparison needs five successful seeds per method",
                    model_truth_gap=gap,
                )
            )
            continue
        full_median = statistics.median(full)
        hessian_median = statistics.median(hessian)
        random_median = statistics.median(random)
        speedup = full_median / hessian_median if hessian_median else 0.0
        details.append(
            {
                "model_truth_gap": gap,
                "median_full_queries": full_median,
                "median_hessian_queries": hessian_median,
                "median_random_queries": random_median,
                "median_query_speedup": speedup,
            }
        )
        speedups.append(speedup)

    if speedups and min(speedups) < 2.0:
        errors.append(
            error(
                "insufficient_speedup",
                "hessian median query count must be at least 2x better than full raw",
                minimum_speedup=2.0,
                observed=min(speedups),
            )
        )

    return {
        "evaluated_gaps": details,
        "median_query_speedup": min(speedups) if speedups else None,
        "errors": errors,
    }


def _successful_queries(
    rows: list[dict[str, Any]], method: str, gap: float, k: int | None = None
) -> list[float]:
    queries: list[float] = []
    for row in rows:
        if row.get("method") != method or _as_float(row.get("model_truth_gap")) != gap:
            continue
        if k is not None and _as_int(row.get("k")) != k:
            continue
        if not row.get("claim_success"):
            continue
        if _as_float(row.get("final_exact_true_infidelity")) > INFIDELITY_THRESHOLD:
            continue
        value = row.get("queries_to_target")
        if value is not None:
            queries.append(float(value))
    return queries


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")
