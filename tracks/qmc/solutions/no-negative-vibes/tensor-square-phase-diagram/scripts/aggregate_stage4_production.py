#!/usr/bin/env python3
"""Audit Stage 4 production replicas and rank dense-scan candidates."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

from tensor_square.stage4 import (
    assigned_grid,
    EXPERIMENT_ID,
    MONITORED_TAU_KEYS,
    Stage4Policy,
)
from tensor_square.stage4_analysis import (
    aggregate_production_cell,
    classify_numerical_sentinel,
    classify_stage4_candidate,
)


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    records = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in records for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in records:
            writer.writerow(
                {
                    key: (
                        ";".join(str(item) for item in value)
                        if isinstance(value, list)
                        else value
                    )
                    for key, value in row.items()
                }
            )


def _candidate_id(
    cohort: str,
    g_ratio: float,
    t: float,
    mu: float,
) -> str:
    return (
        f"{cohort}_g{g_ratio:g}_t{t:g}_mu"
        f"{mu:+g}".replace("+0", "0")
    )


def _pair_budget_verified(
    cells: list[object],
    decisions: dict[str, dict[str, object]],
) -> bool:
    by_pair: dict[str, list[object]] = {}
    for cell in cells:
        pair_id = getattr(cell, "pair_id")
        if pair_id is not None:
            by_pair.setdefault(str(pair_id), []).append(cell)
    for pair in by_pair.values():
        if len(pair) != 2:
            return False
        pair_decisions = [decisions[getattr(cell, "cell_id")] for cell in pair]
        statuses = {str(decision["status"]) for decision in pair_decisions}
        if len(statuses) != 1:
            return False
        if statuses == {"RUN"}:
            budgets = {
                (
                    int(decision["warmup_sweeps"]),
                    int(decision["measurement_sweeps"]),
                    int(decision["production_replicas"]),
                )
                for decision in pair_decisions
            }
            if len(budgets) != 1:
                return False
    return True


def _rank(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    priority = {"SURVIVE": 0, "EXTEND": 1, "STOP": 2}
    ranked = sorted(
        candidates,
        key=lambda row: (
            priority[str(row["classification"])],
            -float(row["ranking_score"]),
            str(row["candidate_id"]),
        ),
    )
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    return ranked


def _m10_shortlist(
    ranked: list[dict[str, object]],
) -> list[dict[str, object]]:
    survivors = [
        row for row in ranked if row["classification"] == "SURVIVE"
    ][:6]
    selected = list(survivors)
    if len(selected) < 3:
        extensions = [
            row
            for row in ranked
            if row["classification"] == "EXTEND"
            and row["inference_scope"] == "physics"
            and float(row["ranking_score"]) > 0.0
        ]
        for row in extensions:
            if row not in selected:
                selected.append(row)
            if len(selected) == 3:
                break
    selected = selected[:6]
    result: list[dict[str, object]] = []
    for shortlist_rank, row in enumerate(selected, start=1):
        result.append(
            {
                **row,
                "shortlist_rank": shortlist_rank,
                "m10_action": "RUN_SENTINEL",
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-results-dir", required=True, type=Path)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    policy = Stage4Policy()
    plan_path = args.pilot_results_dir / "aggregate" / "budget_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (
        plan.get("experiment_id") != EXPERIMENT_ID
        or plan.get("released") is not True
    ):
        raise ValueError("released Stage 4 budget plan is required")
    decisions = dict(plan["decisions"])
    cells = assigned_grid()
    cells_by_id = {cell.cell_id: cell for cell in cells}

    summaries_by_cell: dict[str, list[dict[str, object]]] = {}
    validation_errors: list[str] = []
    for path in sorted(
        args.results_dir.glob(
            "cells/*/production/replica_*/summary.json"
        )
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        embedded_cell = str(payload.get("cell_id", ""))
        embedded_replica = int(payload.get("replica", -1))
        if (
            embedded_cell not in cells_by_id
            or path.parents[2].name != embedded_cell
            or path.parent.name != f"replica_{embedded_replica:02d}"
        ):
            validation_errors.append(f"path/identity mismatch: {path}")
            continue
        summaries_by_cell.setdefault(embedded_cell, []).append(payload)

    cell_rows: list[dict[str, object]] = []
    for cell in cells:
        decision = dict(decisions[cell.cell_id])
        config = cell.config.as_dict()
        if decision["status"] == "RUN":
            row = aggregate_production_cell(
                summaries_by_cell.get(cell.cell_id, []),
                expected_replicas=policy.production_replicas,
                target_ess=policy.target_ess_per_replica,
            )
        else:
            row = {
                "cell_id": cell.cell_id,
                "cohort": cell.cohort,
                "pair_id": cell.pair_id,
                **config,
                "production_replicas": 0,
                "audit_status": "NOT_RUN",
                "audit_reason": f"pilot early stop: {decision['reason']}",
            }
        row.update(
            {
                "cell_index": cell.index,
                "pilot_decision": decision["status"],
                "pilot_reason": decision["reason"],
            }
        )
        cell_rows.append(row)

    unexpected_cells = sorted(
        cell_id
        for cell_id in summaries_by_cell
        if decisions[cell_id]["status"] != "RUN"
    )
    if unexpected_cells:
        validation_errors.append(
            f"production summaries exist for pilot STOP cells: {unexpected_cells}"
        )

    grouped_cells: dict[
        tuple[str, float, float, float], list[dict[str, object]]
    ] = {}
    grouped_specs: dict[tuple[str, float, float, float], list[object]] = {}
    for cell, row in zip(cells, cell_rows):
        key = (
            cell.cohort,
            float(cell.config.g_b_over_g_a),
            float(cell.config.t),
            float(cell.config.mu),
        )
        grouped_cells.setdefault(key, []).append(row)
        grouped_specs.setdefault(key, []).append(cell)

    candidates: list[dict[str, object]] = []
    competition_budget_verified = _pair_budget_verified(
        [
            cell
            for cell in cells
            if cell.cohort == "paired_competition"
        ],
        decisions,
    )
    for key, rows in sorted(grouped_cells.items()):
        cohort, g_ratio, t, mu = key
        classification = classify_stage4_candidate(rows, cohort=cohort)
        candidates.append(
            {
                "candidate_id": _candidate_id(cohort, g_ratio, t, mu),
                "cohort": cohort,
                "g_b_over_g_a": g_ratio,
                "t": t,
                "mu": mu,
                "paired_budget_verified": (
                    competition_budget_verified
                    if cohort == "paired_competition"
                    else True
                ),
                **classification,
            }
        )

    candidate_lookup = {
        (
            str(row["cohort"]),
            float(row["g_b_over_g_a"]),
            float(row["t"]),
            float(row["mu"]),
        ): row
        for row in candidates
    }
    cell_lookup = {
        (
            str(row["cohort"]),
            float(row.get("g_b_over_g_a", math.nan)),
            float(row.get("t", math.nan)),
            float(row.get("mu", math.nan)),
            int(row.get("m", -1)),
            float(row.get("beta", math.nan)),
        ): row
        for row in cell_rows
    }
    for g_ratio in (0.75, 1.0, 1.25):
        for t in (0.5, 1.0):
            negative = candidate_lookup[
                ("paired_competition", g_ratio, t, -1.5)
            ]
            positive = candidate_lookup[
                ("paired_competition", g_ratio, t, 1.5)
            ]
            negative_m8 = cell_lookup[
                ("paired_competition", g_ratio, t, -1.5, 8, 8.0)
            ]
            positive_m8 = cell_lookup[
                ("paired_competition", g_ratio, t, 1.5, 8, 8.0)
            ]
            pair_audit = (
                negative["inference_scope"] == "physics"
                and positive["inference_scope"] == "physics"
                and negative_m8["audit_status"] == "PASS"
                and positive_m8["audit_status"] == "PASS"
            )
            if pair_audit:
                delta = float(positive_m8["channel_balance_mean"]) - float(
                    negative_m8["channel_balance_mean"]
                )
                error = math.hypot(
                    float(positive_m8["channel_balance_stderr"]),
                    float(negative_m8["channel_balance_stderr"]),
                )
                z = abs(delta) / error if error > 0.0 else (
                    1.0e12 if delta != 0.0 else 0.0
                )
                pair_fields = {
                    "particle_hole_balance_delta": delta,
                    "particle_hole_balance_z": z,
                    "particle_hole_consistent_within_2sigma": z < 2.0,
                    "paired_numerical_audit": True,
                }
                negative.update(pair_fields)
                positive.update(pair_fields)
            else:
                for row in (negative, positive):
                    row.update(
                        {
                            "classification": "STOP",
                            "inference_scope": "statistical_only",
                            "reason": (
                                "paired member failed the numerical audit; "
                                "no physics inference"
                            ),
                            "ranking_score": -1.0e9,
                            "paired_numerical_audit": False,
                        }
                    )

    ranked = _rank(candidates)
    shortlist = _m10_shortlist(ranked)
    sentinel_candidates: list[dict[str, object]] = []
    for g_ratio in (0.25, 0.5, 1.0):
        for t in (0.25, 0.5, 1.0):
            key = ("half_filled_core", g_ratio, t, 0.0)
            result = classify_numerical_sentinel(
                grouped_cells[key],
                beta=4.0,
            )
            sentinel_candidates.append(
                {
                    "candidate_id": _candidate_id(
                        "half_filled_core", g_ratio, t, 0.0
                    ),
                    "cohort": "half_filled_core",
                    "g_b_over_g_a": g_ratio,
                    "t": t,
                    "mu": 0.0,
                    "beta": 4.0,
                    **result,
                }
            )
    sentinel_candidates.sort(
        key=lambda row: (
            row["sentinel_classification"] != "ELIGIBLE",
            -float(row["sentinel_ranking_score"]),
            str(row["candidate_id"]),
        )
    )
    numerical_sentinel = next(
        (
            dict(row)
            for row in sentinel_candidates
            if row["sentinel_classification"] == "ELIGIBLE"
        ),
        None,
    )
    if numerical_sentinel is not None:
        sentinel_cell = next(
            cell
            for cell in cells
            if cell.cohort == "half_filled_core"
            and cell.config.m == 8
            and cell.config.beta == 4.0
            and cell.config.g_b_over_g_a
            == numerical_sentinel["g_b_over_g_a"]
            and cell.config.t == numerical_sentinel["t"]
            and cell.config.mu == numerical_sentinel["mu"]
        )
        sentinel_replicas = summaries_by_cell[sentinel_cell.cell_id]
        worst_tau = max(
            float(row[key])
            for row in sentinel_replicas
            for key in MONITORED_TAU_KEYS
        )
        numerical_sentinel.update(
            {
                "m": 10,
                "dt": 0.2,
                "proposal_scale": 0.5,
                "selection_source_cell": sentinel_cell.cell_id,
                "m8_worst_tau_int": worst_tau,
                "initial_warmup_sweeps": max(
                    policy.min_warmup_sweeps,
                    math.ceil(policy.warmup_tau_multiples * worst_tau)
                    * policy.measure_every,
                ),
                "initial_measurement_sweeps": max(
                    policy.min_measurement_sweeps,
                    math.ceil(
                        2.0 * worst_tau * policy.target_ess_per_replica
                    )
                    * policy.measure_every,
                ),
                "measure_every": policy.measure_every,
                "target_ess_per_replica": policy.target_ess_per_replica,
                "production_replicas": policy.production_replicas,
                "maximum_measurement_sweeps": (
                    policy.max_measurement_sweeps
                ),
                "physics_claim_permitted": False,
            }
        )
    evidence_records = [
        row
        for cell_id in sorted(summaries_by_cell)
        for row in sorted(
            summaries_by_cell[cell_id],
            key=lambda item: int(item["replica"]),
        )
    ]
    evidence_digest = hashlib.sha256(
        json.dumps(
            evidence_records,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    sentinel_release = {
        "experiment_id": "stage4-m10-numerical-sentinel-20260729-v1",
        "selection_policy": (
            "beta=4 numerical-only sentinel; frozen 2-sigma/5-percent "
            "size gate, monotonic m=4,6,8, and independent diagnostic"
        ),
        "stage4_source_revision": plan["source_revision"],
        "production_evidence_digest": evidence_digest,
        "selected": numerical_sentinel,
    }
    counts = {
        label: sum(row["classification"] == label for row in ranked)
        for label in ("SURVIVE", "EXTEND", "STOP")
    }
    passing_cells = [
        row for row in cell_rows if row["audit_status"] == "PASS"
    ]
    stopped_cells = [
        row for row in cell_rows if row["audit_status"] == "STOP"
    ]
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": plan["source_revision"],
        "pilot_digest": plan["pilot_digest"],
        "expected_cells": len(cells),
        "pilot_run_cells": sum(
            decision["status"] == "RUN" for decision in decisions.values()
        ),
        "pilot_stop_cells": sum(
            decision["status"] == "STOP" for decision in decisions.values()
        ),
        "production_pass_cells": len(passing_cells),
        "production_early_stop_cells": len(stopped_cells),
        "production_summary_replicas": sum(
            len(rows) for rows in summaries_by_cell.values()
        ),
        "validation_errors": validation_errors,
        "classification_counts": counts,
        "m10_shortlist_count": len(shortlist),
        "m10_shortlist": shortlist,
        "m10_numerical_sentinel_released": numerical_sentinel is not None,
        "m10_numerical_sentinel": numerical_sentinel,
        "minimum_ess": min(
            (float(row["minimum_ess"]) for row in passing_cells),
            default=None,
        ),
        "minimum_acceptance": min(
            (float(row["acceptance_min"]) for row in passing_cells),
            default=None,
        ),
        "maximum_acceptance": max(
            (float(row["acceptance_max"]) for row in passing_cells),
            default=None,
        ),
        "minimum_direct_sign": min(
            (float(row["direct_sign_min"]) for row in passing_cells),
            default=None,
        ),
        "maximum_weight_log_error": max(
            (float(row["weight_log_error_max"]) for row in passing_cells),
            default=None,
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_dir / "production_cells.csv", cell_rows)
    _write_csv(args.output_dir / "candidate_ranking.csv", ranked)
    _write_csv(args.output_dir / "m10_shortlist.csv", shortlist)
    _write_csv(
        args.output_dir / "m10_numerical_sentinel_candidates.csv",
        sentinel_candidates,
    )
    _atomic_json(args.output_dir / "candidate_ranking.json", ranked)
    _atomic_json(
        args.output_dir / "m10_numerical_sentinel_release.json",
        sentinel_release,
    )
    _atomic_json(args.output_dir / "production_summary.json", summary)
    lines = [
        "# Stage 4 production audit",
        "",
        (
            f"- Pilot RUN / STOP cells: {summary['pilot_run_cells']} / "
            f"{summary['pilot_stop_cells']}"
        ),
        (
            f"- Production PASS / early-stop cells: "
            f"{summary['production_pass_cells']} / "
            f"{summary['production_early_stop_cells']}"
        ),
        (
            "- Candidate classifications: "
            f"SURVIVE={counts['SURVIVE']}, "
            f"EXTEND={counts['EXTEND']}, STOP={counts['STOP']}"
        ),
        f"- m=10 sentinel shortlist: {len(shortlist)}",
        (
            "- Numerical-only beta=4 m=10 sentinel released: "
            f"{numerical_sentinel is not None}"
        ),
        f"- Validation errors: {len(validation_errors)}",
        "",
        "A statistical-only STOP is not a physical no-go statement.",
    ]
    (args.output_dir / "production_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    if validation_errors:
        raise RuntimeError("production provenance validation failed")


if __name__ == "__main__":
    main()
