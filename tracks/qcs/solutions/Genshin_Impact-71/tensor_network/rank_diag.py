#!/usr/bin/env python3
"""Train-only variable-order TT unfolding rank diagnostics.

For every cut, this fits low-rank matrix completions to observed coordinates
only.  It is a diagnostic proxy, not a claim about the exact hidden TT rank.
The independent audit later computes exact full-domain ranks for comparison.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from tn_common import (
    INSTANCE_SPECS,
    ORDER_NAMES,
    atomic_json,
    comma_ints,
    load_train_csv,
    sha256_file,
    stable_seed,
    variable_order,
)


def binary_codes(bits: np.ndarray) -> np.ndarray:
    if bits.shape[1] == 0:
        return np.zeros(bits.shape[0], dtype=np.int64)
    weights = (np.int64(1) << np.arange(bits.shape[1], dtype=np.int64))
    return bits.astype(np.int64) @ weights


def split_observations(n_rows: int, seed: int, fraction: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(n_rows)
    n_validation = max(1, min(n_rows - 1, int(round(fraction * n_rows))))
    return permutation[n_validation:], permutation[:n_validation]


def fit_matrix_completion(
    row_ids: np.ndarray,
    column_ids: np.ndarray,
    targets: np.ndarray,
    train_indices: np.ndarray,
    validation_indices: np.ndarray,
    rank: int,
    ridge: float,
    iterations: int,
    seed: int,
) -> dict:
    n_rows = int(row_ids.max()) + 1
    n_columns = int(column_ids.max()) + 1
    rng = np.random.default_rng(seed)
    left = rng.normal(0.0, 0.1 / np.sqrt(rank), size=(n_rows, rank))
    right = rng.normal(0.0, 0.1 / np.sqrt(rank), size=(n_columns, rank))

    train_by_row: list[list[int]] = [[] for _ in range(n_rows)]
    train_by_column: list[list[int]] = [[] for _ in range(n_columns)]
    for observation in train_indices.tolist():
        train_by_row[int(row_ids[observation])].append(observation)
        train_by_column[int(column_ids[observation])].append(observation)
    identity = np.eye(rank, dtype=np.float64)
    for _ in range(iterations):
        for row, observations in enumerate(train_by_row):
            if not observations:
                left[row, :] = 0.0
                continue
            obs = np.asarray(observations, dtype=np.int64)
            design = right[column_ids[obs]]
            left[row, :] = np.linalg.solve(
                design.T @ design + ridge * identity,
                design.T @ targets[obs],
            )
        for column, observations in enumerate(train_by_column):
            if not observations:
                right[column, :] = 0.0
                continue
            obs = np.asarray(observations, dtype=np.int64)
            design = left[row_ids[obs]]
            right[column, :] = np.linalg.solve(
                design.T @ design + ridge * identity,
                design.T @ targets[obs],
            )

    def metrics(indices: np.ndarray) -> dict:
        scores = np.sum(left[row_ids[indices]] * right[column_ids[indices]], axis=1)
        return {
            "observations": int(indices.size),
            "sign_accuracy": float(np.mean((scores >= 0.0) == (targets[indices] >= 0.0))),
            "rmse_pm1": float(np.sqrt(np.mean((scores - targets[indices]) ** 2))),
        }

    seen_rows = np.zeros(n_rows, dtype=bool)
    seen_columns = np.zeros(n_columns, dtype=bool)
    seen_rows[row_ids[train_indices]] = True
    seen_columns[column_ids[train_indices]] = True
    covered_validation = validation_indices[
        seen_rows[row_ids[validation_indices]]
        & seen_columns[column_ids[validation_indices]]
    ]
    return {
        "rank": rank,
        "train": metrics(train_indices),
        "validation": metrics(validation_indices),
        "covered_validation": (
            metrics(covered_validation)
            if covered_validation.size
            else {"observations": 0, "sign_accuracy": None, "rmse_pm1": None}
        ),
        "train_seen_rows": int(np.count_nonzero(seen_rows)),
        "train_seen_columns": int(np.count_nonzero(seen_columns)),
        "total_rows": n_rows,
        "total_columns": n_columns,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True, choices=sorted(INSTANCE_SPECS))
    parser.add_argument("--train-csv", required=True, type=Path)
    parser.add_argument("--order", required=True, choices=ORDER_NAMES)
    parser.add_argument("--ranks", default="1,2,4,8")
    parser.add_argument("--ridge", type=float, default=1e-4)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--root-seed", type=int, default=42)
    parser.add_argument("--report-out", required=True, type=Path)
    args = parser.parse_args()
    ranks = comma_ints(args.ranks)
    if args.iterations < 1 or args.ridge <= 0.0:
        parser.error("iterations and ridge must be positive")

    x_bits, y_bits = load_train_csv(args.train_csv, args.instance)
    n = int(INSTANCE_SPECS[args.instance]["n"])
    order = variable_order(n, args.order)
    x_ordered = x_bits[:, order]
    train_indices, validation_indices = split_observations(
        x_bits.shape[0],
        stable_seed(args.root_seed, args.instance, args.order, "rank-split"),
    )
    cuts: list[dict] = []
    for cut in range(1, x_ordered.shape[1]):
        row_ids = binary_codes(x_ordered[:, :cut])
        column_ids = binary_codes(x_ordered[:, cut:])
        output_diagnostics = []
        for output_index in range(y_bits.shape[1]):
            targets = 2.0 * y_bits[:, output_index].astype(np.float64) - 1.0
            rank_results = []
            for rank in ranks:
                result = fit_matrix_completion(
                    row_ids,
                    column_ids,
                    targets,
                    train_indices,
                    validation_indices,
                    rank,
                    args.ridge,
                    args.iterations,
                    stable_seed(
                        args.root_seed,
                        args.instance,
                        args.order,
                        cut,
                        output_index,
                        rank,
                        "rank-completion",
                    ),
                )
                rank_results.append(result)
            output_diagnostics.append(
                {"output_index": output_index, "rank_results": rank_results}
            )
        cuts.append(
            {
                "cut_after_sites": cut,
                "prefix_original_axes": order[:cut],
                "suffix_original_axes": order[cut:],
                "outputs": output_diagnostics,
            }
        )
        mean_validation = {
            rank: float(
                np.mean(
                    [
                        output["rank_results"][rank_index]["validation"]["sign_accuracy"]
                        for output in output_diagnostics
                    ]
                )
            )
            for rank_index, rank in enumerate(ranks)
        }
        print(
            f"rank-diagnostic instance={args.instance} order={args.order} "
            f"cut={cut}/{x_ordered.shape[1] - 1} mean_val={mean_validation}",
            flush=True,
        )

    report = {
        "schema": "occam71-train-unfolding-completion-v1",
        "interpretation": (
            "Train-only low-rank completion proxy for each TT unfolding; "
            "not an exact hidden-rank certificate."
        ),
        "instance": args.instance,
        "order_name": args.order,
        "order_original_axes": order,
        "candidate_ranks": ranks,
        "ridge": args.ridge,
        "als_iterations": args.iterations,
        "root_seed": args.root_seed,
        "training_csv_sha256": sha256_file(args.train_csv),
        "train_observations": int(train_indices.size),
        "validation_observations": int(validation_indices.size),
        "cuts": cuts,
    }
    atomic_json(args.report_out, report)
    print(json.dumps({
        "instance": args.instance,
        "order": args.order,
        "cuts": len(cuts),
        "report": str(args.report_out),
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
