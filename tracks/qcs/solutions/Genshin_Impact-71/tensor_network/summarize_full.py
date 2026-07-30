#!/usr/bin/env python3
"""Validate and summarize all 80 promoted tensor-network cells."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from summarize_pilot import summarize_rank_report
from tn_common import atomic_json, sha256_file


INSTANCES = ("mystery-A", "mystery-B", "mystery-C", "mystery-D")
ORDERS = (
    "blocked_lsb",
    "blocked_msb",
    "interleaved_lsb",
    "interleaved_msb",
)
BONDS = (2, 4, 8, 16)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_cell(cell: Path, kind: str) -> dict:
    if not (cell / "SUCCESS").is_file():
        raise RuntimeError(f"missing SUCCESS: {cell}")
    manifest = load(cell / "manifest.json")
    if manifest.get("status") != "success" or manifest.get("kind") != kind:
        raise RuntimeError(f"invalid manifest status/kind: {cell}")
    for artifact in manifest["artifacts"]:
        path = cell / artifact["path"]
        if sha256_file(path) != artifact["sha256"]:
            raise RuntimeError(f"artifact hash mismatch: {path}")
    return manifest


def selection_key(configuration: dict) -> tuple[float, float, float, int]:
    validation = configuration["validation"]
    return (
        float(validation["exact_accuracy"]),
        float(validation["bit_accuracy"]),
        -float(validation["rmse_pm1"]),
        -int(configuration["bond"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank-root", required=True, type=Path)
    parser.add_argument("--mps-root", required=True, type=Path)
    parser.add_argument("--report-out", required=True, type=Path)
    args = parser.parse_args()

    rank_results = []
    rank_cells = sorted((args.rank_root / "cells").glob("*"))
    if len(rank_cells) != 16:
        raise RuntimeError(f"expected 16 rank cells, found {len(rank_cells)}")
    for cell in rank_cells:
        manifest = validate_cell(cell, "rank")
        rank_report = load(cell / "rank.json")
        oracle_report = load(cell / "oracle-ranks.json")
        rank_results.append(
            {
                "instance": manifest["instance"],
                "order": manifest["order"],
                "elapsed_seconds": int(manifest["elapsed_seconds"]),
                "train_completion_proxy": summarize_rank_report(rank_report),
                "oracle_audit_only": {
                    "domain_rows": oracle_report["domain_rows"],
                    "boolean_max_rank_by_cut": oracle_report["boolean_01"][
                        "max_across_outputs_by_cut"
                    ],
                    "signed_max_rank_by_cut": oracle_report["signed_pm1"][
                        "max_across_outputs_by_cut"
                    ],
                },
                "rank_report_sha256": sha256_file(cell / "rank.json"),
                "oracle_report_sha256": sha256_file(cell / "oracle-ranks.json"),
            }
        )

    configurations = []
    mps_cells = sorted((args.mps_root / "cells").glob("*"))
    if len(mps_cells) != 64:
        raise RuntimeError(f"expected 64 MPS cells, found {len(mps_cells)}")
    for cell in mps_cells:
        manifest = validate_cell(cell, "mps")
        train = load(cell / "train.json")
        audit = load(cell / "audit.json")
        if audit["model_sha256"] != sha256_file(cell / "model.npz"):
            raise RuntimeError(f"audit/model hash mismatch: {cell}")
        configurations.append(
            {
                "instance": manifest["instance"],
                "order": manifest["order"],
                "bond": int(manifest["bond"]),
                "elapsed_seconds": int(manifest["elapsed_seconds"]),
                "validation": train["validation_metrics"],
                "training": train["train_metrics"],
                "full_domain_audit": audit["full_domain_metrics"],
                "mismatching_rows": int(audit["mismatching_rows"]),
                "model_sha256": audit["model_sha256"],
                "train_report_sha256": sha256_file(cell / "train.json"),
                "audit_report_sha256": sha256_file(cell / "audit.json"),
            }
        )

    selected = []
    for instance in INSTANCES:
        for order in ORDERS:
            candidates = [
                item
                for item in configurations
                if item["instance"] == instance and item["order"] == order
            ]
            if {item["bond"] for item in candidates} != set(BONDS):
                raise RuntimeError(f"incomplete bond sweep: {instance} {order}")
            selected.append(max(candidates, key=selection_key))
    exact_models = [
        item for item in configurations if int(item["mismatching_rows"]) == 0
    ]
    summary = {
        "schema": "occam71-tn-full-summary-v1",
        "root_seed": 42,
        "rank_job_id": load(rank_cells[0] / "manifest.json")["job_id"],
        "mps_job_id": load(mps_cells[0] / "manifest.json")["job_id"],
        "selection_rule": (
            "Within each instance/order: maximize train-only validation exact "
            "accuracy, then validation bit accuracy, then lower validation RMSE, "
            "then smaller bond."
        ),
        "selection_firewall": (
            "Full-domain audits were executed only after each model was frozen "
            "and hashed; no full-domain metric participated in selection."
        ),
        "interpretation": (
            "A continuous thresholded MPS with any mismatch is not exact Boolean "
            "recovery and is not a legal candidate gate circuit."
        ),
        "rank_diagnostics": rank_results,
        "all_mps_configurations": configurations,
        "train_validation_selected": selected,
        "exact_full_domain_models": exact_models,
        "legal_candidate_circuits_produced": 0,
        "runtime_seconds": {
            "rank_cells_sum": int(
                np.sum([item["elapsed_seconds"] for item in rank_results])
            ),
            "rank_cell_max": int(
                np.max([item["elapsed_seconds"] for item in rank_results])
            ),
            "mps_cells_sum": int(
                np.sum([item["elapsed_seconds"] for item in configurations])
            ),
            "mps_cell_max": int(
                np.max([item["elapsed_seconds"] for item in configurations])
            ),
        },
    }
    atomic_json(args.report_out, summary)
    print(json.dumps({
        "rank_cells": len(rank_results),
        "mps_cells": len(configurations),
        "exact_models": len(exact_models),
        "selected": selected,
        "runtime_seconds": summary["runtime_seconds"],
        "report": str(args.report_out),
        "report_sha256": sha256_file(args.report_out),
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
