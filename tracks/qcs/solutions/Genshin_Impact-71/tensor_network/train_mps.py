#!/usr/bin/env python3
"""Train-only continuous MPS baseline with one-site ridge ALS.

The program never imports the truth evaluator.  Hyperparameters and validation
split are fixed before any full-domain audit.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np

from tn_common import (
    INSTANCE_SPECS,
    ORDER_NAMES,
    atomic_json,
    classification_metrics,
    initialize_mps,
    load_train_csv,
    predict_scores,
    right_canonicalize,
    save_models,
    sha256_file,
    stable_seed,
    update_one_site,
    variable_order,
    left_canonicalize,
)


def split_indices(n_rows: int, seed: int, validation_fraction: float) -> tuple[np.ndarray, np.ndarray]:
    if not (0.0 < validation_fraction < 0.5):
        raise ValueError("validation_fraction must lie in (0, 0.5)")
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(n_rows)
    n_validation = max(1, min(n_rows - 1, int(round(n_rows * validation_fraction))))
    return permutation[n_validation:], permutation[:n_validation]


def scalar_metrics(
    cores: list[np.ndarray], x_ordered: np.ndarray, y_bit: np.ndarray
) -> dict[str, float]:
    scores = predict_scores(cores, x_ordered)
    targets_pm1 = 2.0 * y_bit.astype(np.float64) - 1.0
    return {
        "accuracy": float(np.mean((scores >= 0.0) == y_bit)),
        "rmse_pm1": float(np.sqrt(np.mean((scores - targets_pm1) ** 2))),
    }


def fit_output(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_validation: np.ndarray,
    y_validation: np.ndarray,
    max_bond: int,
    ridge: float,
    sweeps: int,
    patience: int,
    seed: int,
    cg_iterations: int,
    cg_tolerance: float,
    progress_prefix: str,
) -> tuple[list[np.ndarray], list[dict]]:
    rng = np.random.default_rng(seed)
    cores = initialize_mps(x_train.shape[1], max_bond, rng)
    targets_pm1 = 2.0 * y_train.astype(np.float64) - 1.0
    best_cores = copy.deepcopy(cores)
    best_key = (-1.0, float("-inf"))
    history: list[dict] = []
    no_improvement = 0

    for sweep in range(1, sweeps + 1):
        cg_total = 0
        cg_worst = 0.0
        for site in range(len(cores)):
            diagnostics = update_one_site(
                cores,
                x_train,
                targets_pm1,
                site,
                ridge,
                cg_iterations,
                cg_tolerance,
            )
            cg_total += int(diagnostics["cg_iterations"])
            cg_worst = max(cg_worst, float(diagnostics["worst_relative_residual"]))
            if site + 1 < len(cores):
                left_canonicalize(cores, site)
        for site in range(len(cores) - 1, -1, -1):
            diagnostics = update_one_site(
                cores,
                x_train,
                targets_pm1,
                site,
                ridge,
                cg_iterations,
                cg_tolerance,
            )
            cg_total += int(diagnostics["cg_iterations"])
            cg_worst = max(cg_worst, float(diagnostics["worst_relative_residual"]))
            if site > 0:
                right_canonicalize(cores, site)

        train_metrics = scalar_metrics(cores, x_train, y_train)
        validation_metrics = scalar_metrics(cores, x_validation, y_validation)
        record = {
            "sweep": sweep,
            "train": train_metrics,
            "validation": validation_metrics,
            "cg_iterations": cg_total,
            "worst_cg_relative_residual": cg_worst,
        }
        history.append(record)
        print(
            f"{progress_prefix} sweep={sweep} "
            f"train_acc={train_metrics['accuracy']:.6f} "
            f"val_acc={validation_metrics['accuracy']:.6f} "
            f"val_rmse={validation_metrics['rmse_pm1']:.6f}",
            flush=True,
        )
        selection_key = (
            validation_metrics["accuracy"],
            -validation_metrics["rmse_pm1"],
        )
        if selection_key > best_key:
            best_key = selection_key
            best_cores = copy.deepcopy(cores)
            no_improvement = 0
        else:
            no_improvement += 1
        if no_improvement >= patience:
            break
    return best_cores, history


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True, choices=sorted(INSTANCE_SPECS))
    parser.add_argument("--train-csv", required=True, type=Path)
    parser.add_argument("--order", required=True, choices=ORDER_NAMES)
    parser.add_argument("--bond", required=True, type=int)
    parser.add_argument("--ridge", type=float, default=1e-5)
    parser.add_argument("--sweeps", type=int, default=8)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--root-seed", type=int, default=42)
    parser.add_argument("--cg-iterations", type=int, default=80)
    parser.add_argument("--cg-tolerance", type=float, default=1e-7)
    parser.add_argument("--model-out", required=True, type=Path)
    parser.add_argument("--report-out", required=True, type=Path)
    args = parser.parse_args()

    if args.bond < 1 or args.sweeps < 1 or args.patience < 1:
        parser.error("bond, sweeps, and patience must be positive")
    x_bits, y_bits = load_train_csv(args.train_csv, args.instance)
    spec = INSTANCE_SPECS[args.instance]
    order = variable_order(int(spec["n"]), args.order)
    x_ordered = x_bits[:, order]
    train_indices, validation_indices = split_indices(
        x_bits.shape[0],
        stable_seed(args.root_seed, args.instance, args.order, "split"),
        args.validation_fraction,
    )
    models: list[list[np.ndarray]] = []
    histories: list[list[dict]] = []
    for output_index in range(y_bits.shape[1]):
        print(
            f"fit instance={args.instance} order={args.order} bond={args.bond} "
            f"output={output_index}/{y_bits.shape[1] - 1}",
            flush=True,
        )
        model, history = fit_output(
            x_ordered[train_indices],
            y_bits[train_indices, output_index],
            x_ordered[validation_indices],
            y_bits[validation_indices, output_index],
            args.bond,
            args.ridge,
            args.sweeps,
            args.patience,
            stable_seed(
                args.root_seed,
                args.instance,
                args.order,
                args.bond,
                output_index,
                "mps",
            ),
            args.cg_iterations,
            args.cg_tolerance,
            f"output={output_index}",
        )
        models.append(model)
        histories.append(history)

    train_metrics = classification_metrics(
        models, x_ordered[train_indices], y_bits[train_indices]
    )
    validation_metrics = classification_metrics(
        models, x_ordered[validation_indices], y_bits[validation_indices]
    )
    metadata = {
        "schema": "occam71-continuous-mps-v1",
        "instance": args.instance,
        "n_sites": int(x_bits.shape[1]),
        "n_outputs": int(y_bits.shape[1]),
        "order_name": args.order,
        "order_original_axes": order,
        "max_bond": args.bond,
        "ridge": args.ridge,
        "sweeps_budget": args.sweeps,
        "patience": args.patience,
        "validation_fraction": args.validation_fraction,
        "root_seed": args.root_seed,
        "training_csv_sha256": sha256_file(args.train_csv),
        "train_rows": int(train_indices.size),
        "validation_rows": int(validation_indices.size),
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
    }
    save_models(args.model_out, metadata, models)
    report = {
        **metadata,
        "model_path": str(args.model_out),
        "model_sha256": sha256_file(args.model_out),
        "per_output_history": histories,
    }
    atomic_json(args.report_out, report)
    print(json.dumps({k: report[k] for k in (
        "instance", "order_name", "max_bond", "train_metrics",
        "validation_metrics", "model_sha256"
    )}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
