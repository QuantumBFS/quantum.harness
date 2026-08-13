#!/usr/bin/env python3
"""Audit the numerical-only m=10 sentinel and compare it with m=8."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from tensor_square.scan import run_fingerprint
from tensor_square.stage4_analysis import (
    aggregate_replica_estimate,
    metric_trend,
    PRODUCTION_METRICS,
)


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _load_m8_row(
    path: Path,
    *,
    cell_id: str,
) -> dict[str, object]:
    with path.open(encoding="utf-8", newline="") as handle:
        row = next(
            record
            for record in csv.DictReader(handle)
            if record["cell_id"] == cell_id
        )
    numeric: dict[str, object] = dict(row)
    for key, value in row.items():
        if value == "":
            continue
        try:
            numeric[key] = float(value)
        except ValueError:
            pass
    return numeric


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sentinel-results-dir", required=True, type=Path)
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--stage4-cell-table", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    release = json.loads(args.release.read_text(encoding="utf-8"))
    selected = dict(release["selected"])
    summaries = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(
            args.sentinel_results_dir.glob(
                "cells/*/production/replica_*/summary.json"
            )
        )
    ]
    if len(summaries) != 4 or {
        int(row["replica"]) for row in summaries
    } != {0, 1, 2, 3}:
        raise ValueError("m=10 sentinel replica set is incomplete")
    release_digest = str(summaries[0]["run_spec"]["budget_plan_digest"])
    source_revision = str(summaries[0]["run_spec"]["source_revision"])
    replica_audit: list[dict[str, object]] = []
    complete: list[dict[str, object]] = []
    for row in summaries:
        run_spec = dict(row["run_spec"])
        if (
            run_fingerprint(run_spec) != row["run_fingerprint"]
            or run_spec["budget_plan_digest"] != release_digest
            or run_spec["source_revision"] != source_revision
        ):
            raise ValueError("m=10 sentinel provenance mismatch")
        final_audit = dict(row["final_audit"])
        passed = (
            row["status"] == "COMPLETE"
            and final_audit["status"] == "PASS"
            and float(final_audit["achieved_ess"]) >= 40.0
        )
        if passed:
            complete.append(row)
        replica_audit.append(
            {
                "replica": int(row["replica"]),
                "seed": int(row["seed"]),
                "status": row["status"],
                "audit_status": final_audit["status"],
                "audit_reason": final_audit["reason"],
                "achieved_ess": float(
                    final_audit.get("achieved_ess", 0.0)
                ),
                "worst_tau_int": float(
                    final_audit.get("worst_tau_int", math.nan)
                ),
                "realized_measurement_sweeps": int(
                    row["realized_measurement_sweeps"]
                ),
                "acceptance": float(row["acceptance"]),
                "direct_sign_min": float(row["direct_sign_min"]),
                "weight_log_error_max": float(
                    row["weight_log_error_max"]
                ),
                "q_combined_mean": float(row["q_combined_mean"]),
                "q_combined_stderr": float(row["q_combined_stderr"]),
            }
        )

    partial: dict[str, object] = {}
    for metric, (value_key, stderr_key) in PRODUCTION_METRICS.items():
        estimate = aggregate_replica_estimate(
            complete,
            value_key=value_key,
            stderr_key=stderr_key,
        )
        partial[f"{metric}_mean"] = estimate["mean"]
        partial[f"{metric}_stderr"] = estimate["stderr"]
    m8 = _load_m8_row(
        args.stage4_cell_table,
        cell_id=str(selected["selection_source_cell"]),
    )
    q_trend = metric_trend(m8, partial, metric="q_combined")
    diagnostic_trends = {
        metric: metric_trend(m8, partial, metric=metric)
        for metric in (
            "staggered_structure",
            "q_a_susceptibility",
            "q_b_susceptibility",
            "q_a_binder",
            "q_b_binder",
            "correlation_length_over_m",
        )
    }
    diagnostic_support = [
        metric
        for metric, trend in diagnostic_trends.items()
        if bool(trend["strict_positive"])
        and float(partial[f"{metric}_mean"]) > 0.0
    ]
    healthy_cell = len(complete) == 4
    conclusion = (
        "支持继续 Stage 5"
        if healthy_cell
        and bool(q_trend["strict_positive"])
        and bool(diagnostic_support)
        else (
            "达到早停；当前信号按有限尺寸或普通 crossover 处理，"
            "不支持继续 Stage 5 的相主张"
        )
    )
    summary = {
        "experiment_id": release["experiment_id"],
        "candidate": {
            key: selected[key]
            for key in (
                "g_b_over_g_a",
                "t",
                "mu",
                "beta",
                "m",
            )
        },
        "source_revision": source_revision,
        "release_digest": release_digest,
        "physics_claim_permitted": False,
        "requested_replicas": len(summaries),
        "audited_m10_replicas": len(complete),
        "early_stop_replicas": len(summaries) - len(complete),
        "healthy_m10_cell": healthy_cell,
        "minimum_direct_sign": min(
            float(row["direct_sign_min"]) for row in summaries
        ),
        "maximum_weight_log_error": max(
            float(row["weight_log_error_max"]) for row in summaries
        ),
        "acceptance_range": [
            min(float(row["acceptance"]) for row in summaries),
            max(float(row["acceptance"]) for row in summaries),
        ],
        "m8_reference": {
            "q_combined_mean": m8["q_combined_mean"],
            "q_combined_stderr": m8["q_combined_stderr"],
        },
        "m10_passing_replica_aggregate": partial,
        "m8_to_m10_q_trend": q_trend,
        "m8_to_m10_diagnostic_trends": diagnostic_trends,
        "m8_to_m10_supporting_diagnostics": diagnostic_support,
        "finite_size_judgement": conclusion,
        "supports_continue_stage5_phase_claim": conclusion
        == "支持继续 Stage 5",
        "residual_uncertainty": (
            "Two passing replicas show size enhancement, but two matched "
            "replicas hit the frozen autocorrelation cap."
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_dir / "m10_replica_audit.csv", replica_audit)
    _atomic_json(args.output_dir / "m10_sentinel_summary.json", summary)
    lines = [
        "# Stage 4 m=10 numerical sentinel",
        "",
        (
            f"- Audited / early-stop replicas: {len(complete)} / "
            f"{len(summaries) - len(complete)}"
        ),
        (
            "- m=8 -> m=10 Q change: "
            f"{float(q_trend['relative_delta']):.1%}, "
            f"z={float(q_trend['z']):.2f}"
        ),
        (
            "- Supporting diagnostics among passing replicas: "
            + (", ".join(diagnostic_support) or "none")
        ),
        f"- Finite-size judgement: {conclusion}",
        "",
        "The m=10 partial estimate is numerical-only and is not phase evidence.",
    ]
    (args.output_dir / "m10_sentinel_summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
