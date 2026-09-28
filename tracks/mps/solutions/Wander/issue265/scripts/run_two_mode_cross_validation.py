#!/usr/bin/env python3
"""Run or aggregate registered two-mode cross-validation shards."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_two_mode_comparison import (
    accepted_convergence_floor,
    analysis_source_closure,
    audit_available_inputs,
    solver_budget_error,
)
from src.two_mode_cross_validation import (
    aggregate_cross_validation,
    registered_cross_validation_folds,
    run_cross_validation_shard,
)
from src.two_mode_forward import (
    RegisteredForwardPredictor,
    fidelity_from_rules,
)


def _json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return dict(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError):
        return None


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        choices=("list", "run", "aggregate"),
        required=True,
    )
    parser.add_argument("--task-index", type=int)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "production_manifest_v2.json",
    )
    parser.add_argument(
        "--base-manifest",
        type=Path,
        default=ROOT / "results_research_program" / "manifest.json",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=ROOT
        / "configs"
        / "two_mode_fcs_decision_rules_20260730.json",
    )
    parser.add_argument(
        "--solver-budget",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "two_mode"
        / "solver_budget.json",
    )
    parser.add_argument(
        "--reuse-attestations",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "production_v2_reuse_attestations.json",
    )
    parser.add_argument(
        "--convergence-audit",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "convergence"
        / "summary.json",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "two_mode"
        / "cross_validation",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        help=(
            "Cluster root containing production_a/; frozen manifest paths "
            "are used when omitted."
        ),
    )
    return parser


def _ready_context(args: argparse.Namespace) -> tuple[Any, dict, dict, float]:
    summary, context = audit_available_inputs(
        manifest_path=args.manifest,
        base_manifest_path=args.base_manifest,
        rules_path=args.rules,
        solver_budget_path=args.solver_budget,
        reuse_attestations_path=args.reuse_attestations,
        phase="validation",
        selection_record_path=None,
        data_root=args.data_root,
    )
    if summary.get("status") != "observables_ready":
        raise ValueError(
            "registered observables are not ready: "
            + str(summary.get("status"))
        )
    rules = context["rules"]
    budget = _json(args.solver_budget) or {}
    budget_error = solver_budget_error(rules, budget)
    if budget_error is not None:
        raise ValueError(budget_error)
    floor = accepted_convergence_floor(_json(args.convergence_audit))
    return context["panel"], rules, budget, floor


def _tasks(panel: Any, rules: dict) -> list[dict[str, Any]]:
    controls = rules["cross_validation"]
    folds = registered_cross_validation_folds(panel, controls)
    models = tuple(map(str, controls["models"]))
    tasks = [
        {
            "task_index": index,
            "model": model,
            "fold": fold,
        }
        for index, (model, fold) in enumerate(
            (model, fold) for model in models for fold in folds
        )
    ]
    expected = int(controls["expected_shards"])
    if len(tasks) != expected:
        raise ValueError(
            "derived cross-validation task count does not match the frozen "
            f"rule: derived {len(tasks)}, expected {expected}"
        )
    return tasks


def main() -> None:
    args = _parser().parse_args()
    try:
        panel, rules, budget, floor = _ready_context(args)
    except ValueError as error:
        payload = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "blocked",
            "reason": str(error),
        }
        _atomic_json(args.outdir / "gate_status.json", payload)
        print(json.dumps(payload, sort_keys=True))
        raise SystemExit(2) from error
    tasks = _tasks(panel, rules)
    if args.action == "list":
        payload = {
            "schema_version": 1,
            "status": "ready",
            "task_count": len(tasks),
            "tasks": [
                {
                    "task_index": task["task_index"],
                    "model": task["model"],
                    "fold": task["fold"].fold_id,
                }
                for task in tasks
            ],
        }
        print(json.dumps(payload, sort_keys=True))
        return
    if args.action == "run":
        if args.task_index is None or not 0 <= args.task_index < len(tasks):
            raise SystemExit(
                f"task-index must be between 0 and {len(tasks) - 1}"
            )
        task = tasks[args.task_index]
        shard = run_cross_validation_shard(
            model=task["model"],
            fold=task["fold"],
            panel=panel,
            rules=rules,
            screening_predictor=RegisteredForwardPredictor(
                fidelity_from_rules(rules, final=False)
            ),
            final_predictor=RegisteredForwardPredictor(
                fidelity_from_rules(rules, final=True)
            ),
            quantum_numerical_floor=floor,
        )
        shard.update(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "task_index": args.task_index,
                "analysis_source": analysis_source_closure(),
                "solver_budget_config_sha256": budget.get("config_sha256"),
            }
        )
        output = (
            args.outdir
            / "shards"
            / (
                f"{args.task_index:02d}_{task['model']}"
                f"__{task['fold'].fold_id}.json"
            )
        )
        _atomic_json(output, shard)
        print(
            json.dumps(
                {
                    "status": shard["status"],
                    "task_index": args.task_index,
                    "output": str(output),
                },
                sort_keys=True,
            )
        )
        if shard["status"] != "fit_complete":
            raise SystemExit(1)
        return

    shard_paths = sorted((args.outdir / "shards").glob("*.json"))
    loaded = [
        (path, payload)
        for path in shard_paths
        if (payload := _json(path)) is not None
    ]
    shards = [payload for _, payload in loaded]
    source_closure = analysis_source_closure()
    stale_shards = [
        str(path)
        for path, shard in loaded
        if shard.get("analysis_source", {}).get("closure_sha256")
        != source_closure["closure_sha256"]
    ]
    if stale_shards:
        aggregate = {
            "schema_version": 1,
            "status": "incomplete",
            "expected_shards": len(tasks),
            "received_shards": len(shards),
            "invalid_source_shards": stale_shards,
        }
        _atomic_json(args.outdir / "summary.json", aggregate)
        print(json.dumps(aggregate, sort_keys=True))
        raise SystemExit(1)
    aggregate = aggregate_cross_validation(
        panel=panel,
        rules=rules,
        shards=shards,
    )
    aggregate.update(
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "analysis_source": source_closure,
            "solver_budget_config_sha256": budget.get("config_sha256"),
            "quantum_numerical_floor": floor,
            "shard_paths": [str(path) for path in shard_paths],
        }
    )
    _atomic_json(args.outdir / "summary.json", aggregate)
    print(
        json.dumps(
            {
                "status": aggregate["status"],
                "expected_shards": aggregate["expected_shards"],
                "received_shards": aggregate["received_shards"],
            },
            sort_keys=True,
        )
    )
    if aggregate["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
