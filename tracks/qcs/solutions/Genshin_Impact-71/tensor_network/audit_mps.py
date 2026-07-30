#!/usr/bin/env python3
"""Full-domain audit of a frozen train-only MPS model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from tn_common import (
    atomic_json,
    classification_metrics,
    load_models,
    predict_scores,
    sha256_file,
)
from tn_truth import enumerate_full_domain, tt_rank_vectors


def rank_summary(rank_vectors: list[list[int]]) -> dict:
    if not rank_vectors:
        return {"per_output": [], "max_across_outputs_by_cut": []}
    return {
        "per_output": rank_vectors,
        "max_across_outputs_by_cut": np.max(
            np.asarray(rank_vectors, dtype=np.int64), axis=0
        ).astype(int).tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--report-out", required=True, type=Path)
    parser.add_argument(
        "--oracle-ranks",
        action="store_true",
        help="also compute exact full-target TT ranks; audit-only, never model selection",
    )
    args = parser.parse_args()
    saved = load_models(args.model)
    metadata = saved.metadata
    instance = str(metadata["instance"])
    order = [int(value) for value in metadata["order_original_axes"]]
    x_bits, y_bits = enumerate_full_domain(instance)
    x_ordered = x_bits[:, order]
    metrics = classification_metrics(saved.models, x_ordered, y_bits)
    scores = np.column_stack(
        [predict_scores(output_model, x_ordered) for output_model in saved.models]
    )
    predictions = (scores >= 0.0).astype(np.int8)
    mismatching_rows = np.flatnonzero(np.any(predictions != y_bits, axis=1))
    report = {
        "schema": "occam71-mps-full-domain-audit-v1",
        "model_path": str(args.model),
        "model_sha256": sha256_file(args.model),
        "instance": instance,
        "order_name": metadata["order_name"],
        "max_bond": metadata["max_bond"],
        "full_domain_metrics": metrics,
        "mismatching_rows": int(mismatching_rows.size),
        "first_mismatching_indices": mismatching_rows[:32].astype(int).tolist(),
        "selection_firewall": (
            "Full-domain truth imported only by audit_mps.py after model freeze; "
            "these metrics were not used for training or hyperparameter selection."
        ),
    }
    if args.oracle_ranks:
        boolean_ranks = tt_rank_vectors(y_bits.astype(np.float64), order)
        signed_ranks = tt_rank_vectors(
            2.0 * y_bits.astype(np.float64) - 1.0, order
        )
        predicted_ranks = tt_rank_vectors(predictions.astype(np.float64), order)
        report["oracle_tt_ranks_audit_only"] = {
            "boolean_01": rank_summary(boolean_ranks),
            "signed_pm1": rank_summary(signed_ranks),
            "thresholded_prediction_01": rank_summary(predicted_ranks),
        }
    atomic_json(args.report_out, report)
    print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
