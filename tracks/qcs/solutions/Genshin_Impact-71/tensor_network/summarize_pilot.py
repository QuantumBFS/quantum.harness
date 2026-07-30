#!/usr/bin/env python3
"""Summarize a completed immutable issue-71 TN pilot directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from tn_common import atomic_json, sha256_file


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_rank_report(report: dict) -> dict:
    ranks = [int(value) for value in report["candidate_ranks"]]
    by_rank: dict[str, dict] = {}
    for rank_index, rank in enumerate(ranks):
        validation_values = []
        covered_values = []
        train_values = []
        for cut in report["cuts"]:
            for output in cut["outputs"]:
                item = output["rank_results"][rank_index]
                train_values.append(float(item["train"]["sign_accuracy"]))
                validation_values.append(float(item["validation"]["sign_accuracy"]))
                covered = item["covered_validation"]["sign_accuracy"]
                if covered is not None:
                    covered_values.append(float(covered))
        by_rank[str(rank)] = {
            "mean_train_sign_accuracy": float(np.mean(train_values)),
            "mean_validation_sign_accuracy": float(np.mean(validation_values)),
            "mean_covered_validation_sign_accuracy": (
                float(np.mean(covered_values)) if covered_values else None
            ),
        }
    return by_rank


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run = args.run_directory
    manifest = load_json(run / "manifest.json")
    if manifest.get("status") != "success" or not (run / "SUCCESS").is_file():
        raise RuntimeError("pilot is not marked successful")

    configurations = []
    for audit_path in sorted((run / "reports").glob("audit-*.json")):
        audit = load_json(audit_path)
        stem = audit_path.name[len("audit-") : -len(".json")]
        train_path = run / "reports" / f"train-{stem}.json"
        train = load_json(train_path)
        configurations.append(
            {
                "instance": audit["instance"],
                "order": audit["order_name"],
                "bond": int(audit["max_bond"]),
                "validation": train["validation_metrics"],
                "full_domain": audit["full_domain_metrics"],
                "mismatching_rows": int(audit["mismatching_rows"]),
                "model_sha256": audit["model_sha256"],
                "oracle_boolean_max_rank_by_cut": audit[
                    "oracle_tt_ranks_audit_only"
                ]["boolean_01"]["max_across_outputs_by_cut"],
                "oracle_signed_max_rank_by_cut": audit[
                    "oracle_tt_ranks_audit_only"
                ]["signed_pm1"]["max_across_outputs_by_cut"],
            }
        )
    rank_proxies = []
    for rank_path in sorted((run / "reports").glob("rank-*.json")):
        report = load_json(rank_path)
        rank_proxies.append(
            {
                "instance": report["instance"],
                "order": report["order_name"],
                "aggregated_over_cuts_and_outputs": summarize_rank_report(report),
                "report_sha256": sha256_file(rank_path),
            }
        )
    summary = {
        "schema": "occam71-tn-pilot-summary-v1",
        "source_manifest_sha256": sha256_file(run / "manifest.json"),
        "job_id": manifest["job_id"],
        "configurations": configurations,
        "rank_completion_proxies": rank_proxies,
    }
    output = args.output or run / "summary.json"
    atomic_json(output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
