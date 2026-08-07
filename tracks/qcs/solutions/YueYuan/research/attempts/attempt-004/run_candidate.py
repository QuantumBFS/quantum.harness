#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from collections import defaultdict
from pathlib import Path

import config
import experiments


def _to_validator_groups(rows):
    grouped = defaultdict(list)
    shared = {}
    for row in rows:
        key = (
            row["system"],
            row["method"],
            row["k"],
            row["mismatch"],
            row["shots_per_query"],
            row["query_budget"],
        )
        grouped[key].append(
            {
                "seed": row["seed"],
                "queries_to_target": row["queries_to_target"],
                "shot_count": row["total_shots"],
                "final_exact_true_infidelity": round(row["final_infidelity"], 10),
            }
        )
        shared[key] = row
    groups = []
    for key, seeds in grouped.items():
        row = shared[key]
        groups.append(
            {
                "instance": row["system"],
                "method": row["method"],
                "k": row["k"],
                "model_truth_gap": row["mismatch"],
                "shots_per_query": row["shots_per_query"],
                "query_budget": row["query_budget"],
                "stopped_on_exact_check": True,
                "claim_success": all(seed["queries_to_target"] is not None for seed in seeds),
                "initial_pulse_id": f"{row['system']}-open-loop-jax",
                "stopping_rule": "query-only-noisy-optimizer-with-private-audit",
                "optimizer": "Nelder-Mead",
                "diagnostics": {
                    "pulse_dim": row["pulse_dim"],
                    "hilbert_dim": row["hilbert_dim"],
                },
                "seeds": seeds,
            }
        )
    return groups


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        rows = experiments.run_sweep(config.default_smoke_sweep(), Path(tmp), fast=args.fast)
    payload = {
        "schema_version": 1,
        "attempt": "attempt-004-full-checklist",
        "notes": [
            "JAX differentiable model, Hessian subspaces, strict query-only noisy device, and multi-axis sweeps.",
            "Exact true fidelity is used only by the audit layer after query-only optimization decisions.",
        ],
        "results": _to_validator_groups(rows),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"groups": len(payload["results"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
