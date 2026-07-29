#!/usr/bin/env python3
"""Aggregate Stage 4 pilot replicas into an auditable production budget."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import csv
import json
from pathlib import Path

from tensor_square.stage4 import (
    adaptive_budget,
    dense_grid,
    EXPERIMENT_ID,
    Stage4Policy,
    synchronize_pair_budgets,
)


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    policy = Stage4Policy()
    cells = dense_grid()
    summaries_by_cell: dict[str, list[dict[str, object]]] = {}
    errors: list[str] = []
    for summary_path in sorted(
        args.output_dir.glob("cells/*/pilot/replica_*/summary.json")
    ):
        row = json.loads(summary_path.read_text(encoding="utf-8"))
        if row.get("status") != "COMPLETE":
            errors.append(str(summary_path))
            continue
        summaries_by_cell.setdefault(str(row["cell_id"]), []).append(row)

    raw_decisions = {
        cell.cell_id: adaptive_budget(
            summaries_by_cell.get(cell.cell_id, []),
            policy=policy,
        )
        for cell in cells
    }
    decisions = synchronize_pair_budgets(cells, raw_decisions)
    table: list[dict[str, object]] = []
    for cell in cells:
        replicas = summaries_by_cell.get(cell.cell_id, [])
        decision = decisions[cell.cell_id]
        table.append(
            {
                "cell_id": cell.cell_id,
                "cohort": cell.cohort,
                "pair_id": cell.pair_id or "",
                "m": cell.config.m,
                "beta": cell.config.beta,
                "g_b_over_g_a": cell.config.g_b_over_g_a,
                "t": cell.config.t,
                "mu": cell.config.mu,
                "pilot_replicas": len(replicas),
                "pilot_acceptance_min": (
                    min(float(row["acceptance"]) for row in replicas)
                    if replicas
                    else ""
                ),
                "pilot_acceptance_max": (
                    max(float(row["acceptance"]) for row in replicas)
                    if replicas
                    else ""
                ),
                **decision,
            }
        )

    aggregate_dir = args.output_dir / "aggregate"
    _write_csv(aggregate_dir / "pilot_table.csv", table)
    _atomic_json(
        aggregate_dir / "budget_plan.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "policy": asdict(policy),
            "decisions": decisions,
        },
    )
    complete_replicas = sum(len(rows) for rows in summaries_by_cell.values())
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "expected_cells": len(cells),
        "expected_replicas": len(cells) * policy.pilot_replicas,
        "complete_replicas": complete_replicas,
        "run_cells": sum(
            decision["status"] == "RUN" for decision in decisions.values()
        ),
        "stop_cells": sum(
            decision["status"] == "STOP" for decision in decisions.values()
        ),
        "error_summaries": errors,
    }
    _atomic_json(aggregate_dir / "pilot_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if complete_replicas != summary["expected_replicas"] or errors:
        raise RuntimeError("pilot aggregation incomplete; production not released")


if __name__ == "__main__":
    main()
