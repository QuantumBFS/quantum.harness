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
    assigned_grid,
    EXPERIMENT_ID,
    pilot_release_digest,
    Stage4Policy,
    synchronize_pair_budgets,
    validate_pilot_replicas,
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
    cells = assigned_grid()
    cells_by_id = {cell.cell_id: cell for cell in cells}
    summaries_by_cell: dict[str, list[dict[str, object]]] = {}
    validation_errors: list[str] = []
    for summary_path in sorted(
        args.output_dir.glob("cells/*/pilot/replica_*/summary.json")
    ):
        row = json.loads(summary_path.read_text(encoding="utf-8"))
        if row.get("status") != "COMPLETE":
            validation_errors.append(f"non-COMPLETE summary: {summary_path}")
            continue
        path_cell_id = summary_path.parents[2].name
        path_replica = summary_path.parent.name
        embedded_cell_id = str(row.get("cell_id", ""))
        embedded_replica = int(row.get("replica", -1))
        if (
            path_cell_id != embedded_cell_id
            or path_replica != f"replica_{embedded_replica:02d}"
            or embedded_cell_id not in cells_by_id
        ):
            validation_errors.append(f"path/identity mismatch: {summary_path}")
            continue
        summaries_by_cell.setdefault(embedded_cell_id, []).append(row)

    source_revisions: set[str] = set()
    for cell in cells:
        try:
            source_revisions.add(
                validate_pilot_replicas(
                    cell,
                    summaries_by_cell.get(cell.cell_id, []),
                    policy=policy,
                )
            )
        except ValueError as error:
            validation_errors.append(f"{cell.cell_id}: {error}")
    if len(source_revisions) != 1:
        validation_errors.append(
            "pilot grid does not have one common source revision"
        )
    aggregate_dir = args.output_dir / "aggregate"
    complete_replicas = sum(len(rows) for rows in summaries_by_cell.values())
    if validation_errors:
        budget_path = aggregate_dir / "budget_plan.json"
        if budget_path.exists():
            budget_path.unlink()
        summary = {
            "experiment_id": EXPERIMENT_ID,
            "released": False,
            "expected_cells": len(cells),
            "expected_replicas": len(cells) * policy.pilot_replicas,
            "complete_replicas": complete_replicas,
            "validation_errors": validation_errors,
        }
        _atomic_json(aggregate_dir / "pilot_summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        raise RuntimeError("pilot provenance validation failed")

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

    _write_csv(aggregate_dir / "pilot_table.csv", table)
    all_summaries = [
        row
        for cell in cells
        for row in summaries_by_cell[cell.cell_id]
    ]
    source_revision = source_revisions.pop()
    _atomic_json(
        aggregate_dir / "budget_plan.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "released": True,
            "source_revision": source_revision,
            "pilot_digest": pilot_release_digest(all_summaries),
            "policy": asdict(policy),
            "decisions": decisions,
        },
    )
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "released": True,
        "source_revision": source_revision,
        "expected_cells": len(cells),
        "expected_replicas": len(cells) * policy.pilot_replicas,
        "complete_replicas": complete_replicas,
        "run_cells": sum(
            decision["status"] == "RUN" for decision in decisions.values()
        ),
        "stop_cells": sum(
            decision["status"] == "STOP" for decision in decisions.values()
        ),
        "validation_errors": [],
    }
    _atomic_json(aggregate_dir / "pilot_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
